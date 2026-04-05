import re
from datetime import datetime

MAX_AMOUNT = 10_000_000  # 1 crore — reject anything above as a likely parse error

_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %B %Y", "%d %b %Y")

# ---------------------------------------------------------------------------
# Merchant name cleaning
# ---------------------------------------------------------------------------

# Indian cities commonly appended to merchant names by banks
_CITY_RE = re.compile(
    r'(?:BANGALORE|BENGALURU|MUMBAI|BOMBAY|PUNE|DELHI|NEW DELHI|HYDERABAD|'
    r'CHENNAI|MADRAS|KOLKATA|CALCUTTA|SATARA|GURGAON|GURUGRAM|NOIDA|'
    r'AHMEDABAD|SURAT|JAIPUR|LUCKNOW|NAGPUR|VADODARA|INDORE|BHOPAL|PATNA|'
    r'KOCHI|COCHIN|COIMBATORE|VISAKHAPATNAM|VIZAG|'
    r'FARIDABAD|GHAZIABAD|MEERUT|AGRA|THANE|NAVI MUMBAI|'
    r'CHANDIGARH|MYSURU|MYSORE|MANGALORE|MANGALURU|HUBLI)\s*$',
    re.IGNORECASE,
)

# "IN" + city stuck together at end: PHARMEASY INMUMBAI
_IN_CITY_RE = re.compile(
    r'\s+IN(?:BANGALORE|BENGALURU|MUMBAI|BOMBAY|PUNE|DELHI|HYDERABAD|'
    r'CHENNAI|KOLKATA|SATARA|GURGAON|GURUGRAM|NOIDA|AHMEDABAD|SURAT|'
    r'JAIPUR|LUCKNOW|NAGPUR|VADODARA|INDORE|BHOPAL|PATNA|KOCHI|'
    r'COIMBATORE|VISAKHAPATNAM|FARIDABAD|CHANDIGARH|MYSURU|MYSORE)\s*$',
    re.IGNORECASE,
)

# Trailing reference / transaction numbers (6+ consecutive digits)
_TRAILING_DIGITS_RE = re.compile(r'\s*\d{6,}\s*$')

# Legal entity suffixes that add no merchant value
_LEGAL_SUFFIX_RE = re.compile(
    r'\s+(?:PVT\.?\s*LTD\.?|PRIVATE LIMITED|LIMITED|LLP|LLC|INC\.?|CORP\.?|PVT\.?)\s*$',
    re.IGNORECASE,
)

# Words that indicate the string is an email body fragment, not a merchant name
_SENTENCE_INDICATORS = {
    "wish", "inform", "kindly", "regards", "sincerely",
    "notify", "notification", "alert", "dear", "please",
    "thank", "welcome", "greet",
}

_MAX_MERCHANT_WORDS = 6


def clean_merchant_name(raw: str | None) -> str | None:
    """
    Normalise a raw merchant string extracted from a bank email or PDF statement.

    Strips: EMI prefix, asterisk separators, trailing reference numbers,
    city suffixes (direct and IN+city), legal suffixes.
    Rejects: too short, too many words (sentence fragment), sentence indicator words.
    """
    if not raw:
        return None

    m = raw.strip()

    # 1. Strip leading EMI marker (instalment payments)
    m = re.sub(r'^EMI\s+', '', m, flags=re.IGNORECASE).strip()

    # 2. Replace asterisk separator with space (e.g. "OPENAI *CHATGPT SUBSCR")
    m = m.replace('*', ' ')

    # 3. Strip trailing reference numbers (6+ digits)
    m = _TRAILING_DIGITS_RE.sub('', m).strip()

    # 4. Strip " IN<CITY>" stuck to end before stripping plain city
    m = _IN_CITY_RE.sub('', m).strip()

    # 5. Strip bare city suffix (may be directly concatenated with no space)
    m = _CITY_RE.sub('', m).strip()

    # 6. Strip legal entity suffixes
    m = _LEGAL_SUFFIX_RE.sub('', m).strip()

    # 7. Collapse multiple spaces
    m = re.sub(r'\s{2,}', ' ', m).strip()

    # 8. Truncate
    m = m[:50].strip()

    # 9. Too short to be meaningful
    if len(m) < 3:
        return None

    # 10. Contains a transaction reference marker — fee/charge description, not a merchant
    if re.search(r'ref#', m, re.IGNORECASE):
        return None

    # 11. Contains a percentage — fee line (e.g. "1% on all DCC Transaction")
    if '%' in m:
        return None

    # 12. Too many words — likely a sentence fragment captured by mistake
    words = m.split()
    if len(words) > _MAX_MERCHANT_WORDS:
        return None

    # 13. Contains words that indicate email body text, not a merchant name
    if _SENTENCE_INDICATORS & {w.lower() for w in words}:
        return None

    return m


# ---------------------------------------------------------------------------
# VPA (UPI Virtual Payment Address) cleaning
# ---------------------------------------------------------------------------

_VPA_ALL_DIGITS     = re.compile(r'^[\d.]+$')           # 9876543210 or 100022.456@bank
_VPA_Q_CODE         = re.compile(r'^q\d+$', re.IGNORECASE)  # QR merchant codes: q809008926
_VPA_GPAY_DIGITS    = re.compile(r'^gpay-\d+$', re.IGNORECASE)
_VPA_GPAY_UTILITY   = re.compile(r'^gpay-(utility|p2p|merchant|upi)$', re.IGNORECASE)


def clean_vpa(vpa: str) -> str:
    """
    Derive a readable merchant name from a UPI VPA string.
    Returns "UPI Transfer" when no readable name can be extracted.
    """
    handle = vpa.split('@')[0]

    # Pure digits or digits.digits (phone number / account number)
    if _VPA_ALL_DIGITS.match(handle):
        return "UPI Transfer"

    # QR code merchant handle (q + digits)
    if _VPA_Q_CODE.match(handle):
        return "UPI Transfer"

    low = handle.lower()

    # GPay P2P / utility (gpay-<phone> or gpay-utility)
    if _VPA_GPAY_DIGITS.match(handle) or _VPA_GPAY_UTILITY.match(handle):
        return "UPI Transfer"

    # GPay business handle (gpay-<name>)
    if low.startswith('gpay-'):
        name = handle[5:].replace('-', ' ')
        return name.title() if len(name) >= 3 else "UPI Transfer"

    # PhonePe handles
    if low.startswith(('phonepe-', 'pe.', 'ybl.')):
        return "UPI Transfer"

    # Paytm handles
    if low.startswith('paytm'):
        return "UPI Transfer"

    # Dotted handles like "phi.xpressbees" — extract last meaningful segment
    if '.' in handle:
        parts = [p for p in handle.split('.') if len(p) > 2 and not re.match(r'^\d+$', p)]
        if parts:
            return parts[-1].replace('-', ' ').title()
        return "UPI Transfer"

    # Plain handle — clean up and title-case
    name = handle.replace('-', ' ').replace('_', ' ').strip()
    if len(name) < 3 or re.match(r'^\d+$', name):
        return "UPI Transfer"
    return name.title()


def parse_amount(val) -> float | None:
    if not val:
        return None
    cleaned = str(val).replace(",", "").strip()
    try:
        v = float(cleaned)
        return v if 0 < v <= MAX_AMOUNT else None
    except ValueError:
        return None


def parse_date(val) -> datetime | None:
    if not val:
        return None
    raw = str(val).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None
