import io
import re
import hashlib
import logging
from datetime import datetime
from pathlib import Path

import pikepdf
import pdfplumber

from parsing.parse_utils import MAX_AMOUNT, parse_amount, parse_date, clean_merchant_name

logger = logging.getLogger(__name__)

# PII patterns to redact from raw_text before storage
_PII_PATTERNS = [
    (re.compile(r'\b[A-Z0-9]{4,6}[\*Xx]+\d{4}\b'), "[REDACTED_CARD]"),
    (re.compile(r'\b\d{12,19}\b'), "[REDACTED_ACCT]"),
    (re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'), "[REDACTED_EMAIL]"),
    (re.compile(r'\b\d{6}\b'), "[REDACTED_PIN]"),
    (re.compile(r'Ref#\s*\d+'), "Ref#[REDACTED]"),
]

# Standard multi-column bank account statement formats
BANK_SIGNATURES = {
    "axis": {"withdrawal amt", "deposit amt"},
    "hdfc": {"debit amt", "credit amt", "narration"},
    "sbi":  {"txn date", "debit", "credit", "ref no"},
}

COLUMN_MAP = {
    "axis": {"date": 0, "description": 1, "debit": 4, "credit": 5},
    "hdfc": {"date": 0, "description": 1, "debit": 3, "credit": 4},
    "sbi":  {"date": 0, "description": 2, "debit": 4, "credit": 5},
}

# HDFC credit card: each row is a single merged cell
# Format: "DD/MM/YYYY| HH:MM <DESCRIPTION> [+] C <AMOUNT> l"
# "+" prefix = credit (payment received), no "+" = debit (purchase)
_HDFC_CC_KEYWORDS = {"date & time", "transaction", "description", "amount"}
_HDFC_CC_ROW = re.compile(
    r'(\d{2}/\d{2}/\d{4})\|\s*\d{2}:\d{2}\s+'   # date + time
    r'(.+?)\s+'                                    # description
    r'(\+)?\s*[A-Z]\s+'                           # optional credit indicator
    r'([0-9,]+(?:\.[0-9]{2})?)\s',                # amount
    re.DOTALL
)


# ---------------------------------------------------------------------------
# Amex credit card statement (text-based, no tables)
# Format: "February 13   AMAZON   Mumbai   640.00"
# ---------------------------------------------------------------------------

_AMEX_TXN_RE = re.compile(
    r'^(January|February|March|April|May|June|July|August|'
    r'September|October|November|December)\s+(\d{1,2})\s+'
    r'(.+)\s+'
    r'([0-9,]+\.[0-9]{2})\s*$',
    re.IGNORECASE,
)

_AMEX_MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5,     'june': 6,     'july': 7,  'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
}

# Lines that are section headers, summaries, or fee entries — not real transactions
_AMEX_SKIP_RE = re.compile(
    r'FINANCE CHARGES|GST/IGST|INSTALLMENT PRINCIPAL AMOUNT|'
    r'New domestic transactions|New overseas transactions|'
    r'Total of Installments|TOTAL OVERSEAS SPEND|'
    r'Card Number XXXX|UNITED STATES DOLLAR|'
    r'Foreign Spending|Amount Rs|^Details\b|'
    r'Page \d+ of \d+|americanexpress\.co\.in|Statement of Account|'
    r'Membership Number|Prepared for|Credit Summary|Credit Limit|'
    r'Installment Plan|CardMember|Payment Information|Payment Methods|'
    r'NEFT details|IFSC Code|Drop Box|Mailing Preference|'
    r'Foreign Exchange Currency|Permanent Account Number|GSTIN|'
    r'Current Rates of Interest|Opening Balance|Closing Balance|'
    r'Min Payment Due|Minimum Payment',
    re.IGNORECASE,
)


def _redact_pii(text: str) -> str:
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _row_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _is_hdfc_cc(header_cell: str) -> bool:
    text = str(header_cell).lower()
    return all(kw in text for kw in _HDFC_CC_KEYWORDS)


class PDFParser:

    def parse(self, pdf_path: str, password: str | None = None) -> list[dict]:
        pdf_bytes = self._decrypt(pdf_path, password)
        filename  = Path(pdf_path).stem

        # Check Amex first — it uses plain text, not PDF tables
        full_text = self._extract_full_text(pdf_bytes)
        if self._is_amex(full_text):
            logger.info("[PDF] Detected format: AMEX Credit Card")
            return self._parse_amex(full_text, filename)

        tables = self._extract_tables(pdf_bytes)

        if not tables:
            logger.warning(f"[PDF] No tables found in {pdf_path}")
            return []

        # Check for HDFC credit card format first (single-cell rows)
        for table in tables:
            if table and table[0] and _is_hdfc_cc(table[0][0]):
                logger.info("[PDF] Detected format: HDFC Credit Card")
                return self._parse_hdfc_cc(tables, filename)

        # Fall back to standard multi-column formats
        bank, col, start_idx = "unknown", None, -1
        for i, table in enumerate(tables):
            if not table or not table[0]:
                continue
            normalized = {str(h).lower().strip() for h in table[0] if h}
            for b, keywords in BANK_SIGNATURES.items():
                if keywords.issubset(normalized):
                    bank, col, start_idx = b, COLUMN_MAP[b], i
                    break
            if col:
                break

        if not col:
            logger.error(f"[PDF] Unrecognised bank format — first table header: {tables[0][0] if tables else '?'}")
            return []

        logger.info(f"[PDF] Detected bank: {bank.upper()}")
        rows = []
        for table in tables[start_idx:]:
            for raw_row in table[1:]:
                try:
                    row = self._extract_standard_row(raw_row, col, bank, filename)
                    if row:
                        rows.append(row)
                except Exception as e:
                    logger.debug(f"[PDF] Skipping row: {e}")

        logger.info(f"[PDF] Extracted {len(rows)} transactions")
        return rows

    # ------------------------------------------------------------------ #
    #  HDFC Credit Card parser                                            #
    # ------------------------------------------------------------------ #

    def _parse_hdfc_cc(self, tables: list, filename: str) -> list[dict]:
        rows = []
        for table in tables:
            if not table or not table[0] or not _is_hdfc_cc(table[0][0]):
                continue
            for raw_row in table[1:]:
                cell = str(raw_row[0] or "").strip()
                if not cell:
                    continue
                match = _HDFC_CC_ROW.search(cell)
                if not match:
                    continue
                date_str, desc, plus_sign, amt_str = match.groups()
                txn_date = parse_date(date_str)
                amount   = parse_amount(amt_str)
                if not txn_date or not amount:
                    continue

                txn_type = "credit" if plus_sign else "debit"

                rows.append({
                    "txn_date":       txn_date,
                    "amount":         amount,
                    "merchant":       clean_merchant_name(desc) or desc.strip()[:50],
                    "payment_method": "CREDIT CARD",
                    "bank_name":      "HDFC",
                    "source":         f"pdf:{filename}:{_row_hash(cell)}",
                    "raw_text":       _redact_pii(cell),
                    "txn_type":       txn_type,
                })

        logger.info(f"[PDF] HDFC CC: extracted {len(rows)} transactions")
        return rows

    # ------------------------------------------------------------------ #
    #  Standard multi-column parser (Axis / HDFC account / SBI)          #
    # ------------------------------------------------------------------ #

    def _extract_standard_row(self, raw_row: list, col: dict, bank: str, filename: str) -> dict | None:
        def cell(key):
            idx = col.get(key, -1)
            return raw_row[idx] if 0 <= idx < len(raw_row) else None

        txn_date = parse_date(cell("date"))
        if not txn_date:
            return None

        debit  = parse_amount(cell("debit"))
        credit = parse_amount(cell("credit"))

        if debit and credit:
            txn_type = "debit" if debit >= credit else "credit"
            amount   = debit if txn_type == "debit" else credit
        elif debit:
            txn_type, amount = "debit", debit
        elif credit:
            txn_type, amount = "credit", credit
        else:
            return None

        raw_text = " | ".join(str(c) for c in raw_row if c)
        return {
            "txn_date":       txn_date,
            "amount":         amount,
            "merchant":       clean_merchant_name(str(cell("description") or "")) or "Unknown",
            "payment_method": "",
            "bank_name":      bank.upper(),
            "source":         f"pdf:{filename}:{_row_hash(raw_text)}",
            "raw_text":       _redact_pii(raw_text),
            "txn_type":       txn_type,
        }

    # ------------------------------------------------------------------ #
    #  Amex credit card parser (text-based)                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_amex(text: str) -> bool:
        lower = text.lower()
        return "american express" in lower and "membership number" in lower

    @staticmethod
    def _amex_statement_year(text: str) -> int:
        """Extract year from the statement date header (DD/MM/YYYY)."""
        m = re.search(r'\b\d{2}/\d{2}/(\d{4})\b', text)
        return int(m.group(1)) if m else datetime.now().year

    def _parse_amex(self, full_text: str, filename: str) -> list[dict]:
        year = self._amex_statement_year(full_text)
        rows = []
        seen = set()
        in_installment_section = False

        for line in full_text.splitlines():
            line = line.strip()
            if not line:
                continue

            # Track installment section — transactions here are EMI breakdowns, not new spend
            if re.search(r'installment plan transactions', line, re.IGNORECASE):
                in_installment_section = True
                continue

            # Skip noise lines
            if _AMEX_SKIP_RE.search(line):
                continue

            m = _AMEX_TXN_RE.match(line)
            if not m:
                continue

            month_str, day_str, desc, amt_str = m.groups()

            # Strip trailing foreign-currency amount left in description
            # e.g. "ANTHROPIC SAN FRANCISCO 5.90" → "ANTHROPIC SAN FRANCISCO"
            desc = re.sub(r'\s+\d+\.\d+\s*$', '', desc).strip()
            # Strip PDF tilde artifacts (IKEA INDIA PVT LTD~~~~~)
            desc = re.sub(r'~+', ' ', desc).strip()

            amount = parse_amount(amt_str)
            if not amount:
                continue

            month = _AMEX_MONTH_MAP.get(month_str.lower())
            if not month:
                continue
            day = int(day_str)

            # Handle year-boundary statements (e.g. Dec–Jan)
            # Statement year is the end month's year; earlier months may be prior year
            stmt_end_month = self._amex_statement_year_month(full_text)
            if stmt_end_month and month > stmt_end_month:
                txn_year = year - 1
            else:
                txn_year = year

            try:
                txn_date = datetime(txn_year, month, day)
            except ValueError:
                continue

            is_credit = bool(re.search(r'PAYMENT RECEIVED', desc, re.IGNORECASE))

            # Skip installment section finance entries but keep insurance/principal
            if in_installment_section and re.search(
                r'FINANCE CHARGES|GST/IGST|INSTALLMENT PRINCIPAL', desc, re.IGNORECASE
            ):
                continue

            merchant  = clean_merchant_name(desc) or desc.strip()[:50]
            raw_line  = f"{month_str} {day_str} | {desc} | {amt_str}"
            source    = f"pdf:{filename}:{_row_hash(raw_line)}"

            if source in seen:
                continue
            seen.add(source)

            rows.append({
                "txn_date":       txn_date,
                "amount":         amount,
                "merchant":       merchant,
                "payment_method": "CREDIT CARD",
                "bank_name":      "AMEX",
                "source":         source,
                "raw_text":       _redact_pii(raw_line),
                "txn_type":       "credit" if is_credit else "debit",
            })

        logger.info(f"[PDF] AMEX: extracted {len(rows)} transactions")
        return rows

    @staticmethod
    def _amex_statement_year_month(text: str) -> int | None:
        """Extract the statement end month number for year-boundary handling."""
        m = re.search(r'to\s+(January|February|March|April|May|June|July|August|'
                      r'September|October|November|December)', text, re.IGNORECASE)
        if m:
            return _AMEX_MONTH_MAP.get(m.group(1).lower())
        return None

    def _extract_full_text(self, pdf_bytes: bytes) -> str:
        """Extract all text from all pages as a single string."""
        pages = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(text)
        return "\n".join(pages)

    # ------------------------------------------------------------------ #

    def _decrypt(self, path: str, password: str | None) -> bytes:
        try:
            pdf = pikepdf.open(path, password=password or "")
        except pikepdf.PasswordError:
            raise ValueError(f"Wrong or missing password for {Path(path).name}")
        buf = io.BytesIO()
        pdf.save(buf)
        buf.seek(0)
        return buf.read()

    def _extract_tables(self, pdf_bytes: bytes) -> list:
        all_tables = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
        return all_tables
