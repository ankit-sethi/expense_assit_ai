import re
from datetime import datetime

class TransactionParser:

    def parse(self, raw):

        text = raw["raw_text"]
        txn_datetime= datetime.fromtimestamp(raw["timestamp"] / 1000)
        amount_pattern = r"(?:INR|Rs\.?)\s?([0-9,]+(?:\.[0-9]{1,2})?)"
        amt = re.search(amount_pattern, text, re.IGNORECASE)
        merchant_pattern = r"(?:at|on|for|name)\s+([A-Za-z0-9 &\.-]+)"
        merchant = re.search(merchant_pattern, text, re.IGNORECASE)

        score = 0

        if amt:
            score += 1

        if merchant:
            score += 1

        if "debited" in text.lower():
            score += 1

        if score >= 2:
            return {
            "txn_date": txn_datetime,
            "amount": float(amt.group(1)),
            "merchant": merchant.group(1) if merchant else "Unknown",
            "source": raw["source"],
            "raw_text": text
        }
        else:
            return None
