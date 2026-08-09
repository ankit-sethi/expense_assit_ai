import hashlib
import logging
from datetime import datetime

from parsing.transaction_parser import TransactionParser
from parsing.parse_utils import clean_merchant_name, clean_vpa

logger = logging.getLogger(__name__)

_parser = TransactionParser()

# Maps SMS sender IDs to canonical bank names used in expenses/credits
_SENDER_BANK_MAP = {
    "AXISBK-S": "AXIS",
    "AMEXIN-S": "AMEX",
    "HDFCBK-T": "HDFC",
    "HDFCBK-S": "HDFC",
    "CBSSBI-S": "SBI",
}


def parse_sms(body: str, sender: str, received_at: str | None) -> dict:
    """
    Parse a raw bank SMS into a staging dict ready for SmsStagingRepository.save().

    Reuses TransactionParser (the same pipeline used for email bodies).
    Unparseable fields are set to None — they are surfaced during the review step.
    """
    bank_name = _extract_bank(sender)

    # Normalise received_at
    dt = _parse_received_at(received_at)

    # Build a pseudo-email dict so we can reuse TransactionParser unchanged
    pseudo_email = {
        "body":       body,
        "subject":    "",
        "sender":     sender,
        "message_id": "",
        "timestamp":  dt.isoformat(),
        "bank_name":  bank_name,
    }

    parsed = _parser.parse(pseudo_email) or {}

    # Stable dedup key: hash of sender + body prefix + date
    source_raw = f"sms:{sender}:{body[:100]}:{dt.date()}"
    source     = "sms:" + hashlib.sha256(source_raw.encode()).hexdigest()[:16]

    merchant = parsed.get("merchant")
    # Extra clean pass in case parser returned a VPA
    if merchant and "@" in merchant:
        merchant = clean_vpa(merchant)
    elif merchant:
        merchant = clean_merchant_name(merchant) or merchant

    return {
        "raw_sms":         body,
        "sender":          sender,
        "received_at":     dt,
        "parsed_amount":   parsed.get("amount"),
        "parsed_merchant": merchant,
        "parsed_date":     parsed.get("txn_date").date() if parsed.get("txn_date") else dt.date(),
        "parsed_bank":     parsed.get("bank_name") or bank_name,
        "txn_type":        parsed.get("txn_type"),
        "source":          source,
        "status":          "pending",
    }


def _extract_bank(sender: str) -> str | None:
    return _SENDER_BANK_MAP.get((sender or "").upper().strip())


def _parse_received_at(received_at: str | None) -> datetime:
    if not received_at:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(received_at)
    except ValueError:
        logger.warning(f"[SMS PARSER] Could not parse received_at: {received_at!r}")
        return datetime.utcnow()
