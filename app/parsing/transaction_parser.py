import re
import logging
from datetime import datetime
from parsing.parse_utils import MAX_AMOUNT, parse_date

logger = logging.getLogger(__name__)

PAYMENT_METHOD_PATTERN = re.compile(
    r'\b(UPI|NEFT|IMPS|RTGS|credit card|debit card|net banking)\b',
    re.IGNORECASE
)

DATE_PATTERNS = [
    re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b'),
    re.compile(r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b', re.IGNORECASE),
]

AMOUNT_PATTERN = re.compile(r'(?:INR|Rs\.?)\s?([0-9,]+(?:\.[0-9]{1,2})?)', re.IGNORECASE)

MERCHANT_PATTERN = re.compile(
    r'(?:paid to|payment to|at|for|name|to)\s+([A-Za-z0-9 &.\-]+)',
    re.IGNORECASE
)

VPA_PATTERN = re.compile(r'VPA\s+([A-Za-z0-9.\-_]+@[A-Za-z0-9.\-_]+)', re.IGNORECASE)

_MERCHANT_STOPWORDS = {"the", "a", "an", "your", "our", "this", "that", "us", "you", "we"}
MAX_MERCHANT_LEN = 50


def _parse_txn_date(text: str, fallback_ts: int) -> datetime:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            result = parse_date(match.group(1))
            if result:
                return result
    return datetime.fromtimestamp(fallback_ts / 1000)


def _clean_merchant(raw: str) -> str | None:
    merchant = raw.strip()[:MAX_MERCHANT_LEN].strip()
    if len(merchant) < 3:
        return None
    if merchant.lower() in _MERCHANT_STOPWORDS:
        return None
    return merchant


class TransactionParser:

    def parse(self, raw: dict):
        text = raw["raw_text"]
        fallback_ts = raw["timestamp"]

        amt = AMOUNT_PATTERN.search(text)
        merchant_match = MERCHANT_PATTERN.search(text)
        vpa_match = VPA_PATTERN.search(text)

        score = 0
        if amt:
            score += 1
        if merchant_match or vpa_match:
            score += 1
        if "debited" in text.lower():
            score += 1

        if score < 2:
            return None

        amount = float(amt.group(1).replace(",", ""))
        if amount <= 0 or amount > MAX_AMOUNT:
            logger.warning(f"[PARSER] Rejecting implausible amount: {amount}")
            return None

        if vpa_match:
            merchant = vpa_match.group(1)
        elif merchant_match:
            merchant = _clean_merchant(merchant_match.group(1))
            if not merchant:
                merchant = "Unknown"
        else:
            merchant = "Unknown"

        payment_method_match = PAYMENT_METHOD_PATTERN.search(text)
        payment_method = payment_method_match.group(1).upper() if payment_method_match else ""

        return {
            "txn_date": _parse_txn_date(text, fallback_ts),
            "amount": amount,
            "merchant": merchant,
            "payment_method": payment_method,
            "bank_name": raw.get("bank_name", ""),
            "source": raw.get("message_id", raw.get("source", "")),
            "raw_text": text,
        }
