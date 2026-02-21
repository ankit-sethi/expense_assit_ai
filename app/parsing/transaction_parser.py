import re
from datetime import datetime

class TransactionParser:

    def parse(self, raw):

        text = raw["raw_text"]
        txn_datetime= datetime.fromtimestamp(raw["timestamp"] / 1000)
        amt = re.search(r'(\d+)', text)
        merchant = re.search(r'at\s([A-Za-z]+)', text)

        if not amt:
            return None

        return {
            "txn_date": txn_datetime,
            "amount": float(amt.group(1)),
            "merchant": merchant.group(1) if merchant else "Unknown",
            "source": raw["source"],
            "raw_text": text
        }
