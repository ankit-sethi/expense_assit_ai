import base64
import logging
from bs4 import BeautifulSoup

from ingestion.gmail_auth import get_gmail_service

logger = logging.getLogger(__name__)

SENDER_BANK_MAP = {
    "hdfcbank": "HDFC",
    "sbi.co.in": "SBI",
    "axis.bank": "Axis",
    "icicibank": "ICICI",
    "kotakbank": "Kotak",
    "yesbank": "Yes Bank",
    "paytm": "Paytm",
}


def _resolve_bank_from_sender(sender: str) -> str:
    sender_lower = sender.lower()
    for key, bank in SENDER_BANK_MAP.items():
        if key in sender_lower:
            return bank
    return ""


def is_transaction_email(text: str) -> bool:
    text = text.lower()
    strong_keywords = ["debited", "credited", "upi txn", "rs.", "inr", "a/c", "account"]
    return sum(1 for k in strong_keywords if k in text) >= 2


class GmailClient:

    def __init__(self):
        self.service = get_gmail_service()

    def fetch_messages(self, max_results=100):

        query = (
            "category:primary "
            "newer_than:30d "
            "(debited OR spent OR transaction OR UPI OR INR) "
            "(from:alerts@hdfcbank.bank.in OR from:cbsalerts@sbi.co.in OR from:alerts@axis.bank.in)"
        )

        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            logger.info(f"[GMAIL] Query matched {len(messages)} message(s)")

            output = []

            for msg in messages:
                logger.info(f"[GMAIL] Fetching message {msg['id']}")

                full = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()

                payload = full['payload']
                parts = payload.get('parts', [])

                sender = next(
                    (h["value"] for h in payload.get("headers", []) if h["name"].lower() == "from"),
                    ""
                )
                bank_name = _resolve_bank_from_sender(sender)

                body = ""

                if parts:
                    for part in parts:
                        if part['mimeType'] in ['text/plain', 'text/html']:
                            data = part['body'].get('data')
                            if data:
                                body += base64.urlsafe_b64decode(data).decode(errors="ignore")
                else:
                    data = payload.get('body', {}).get('data')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode(errors="ignore")

                if "<html" in body.lower():
                    body = BeautifulSoup(body, "html.parser").get_text(" ")

                if not is_transaction_email(body):
                    logger.debug(f"[GMAIL] Skipping non-transaction message {msg['id']}")
                    continue

                output.append({
                    "source": "gmail",
                    "message_id": msg["id"],
                    "timestamp": int(full["internalDate"]),
                    "raw_text": body,
                    "bank_name": bank_name,
                })

            logger.info(f"[GMAIL] Imported {len(output)} message(s) successfully")
            return output

        except Exception as e:
            logger.error(f"[GMAIL FETCH ERROR] {e}")
            return []