import base64
from email.mime import text
from bs4 import BeautifulSoup

from ingestion.gmail_auth import get_gmail_service

def is_transaction_email(self, text: str):
        text = text.lower()
        strong_keywords = [
            "debited",
            "credited",
            "upi txn",
            "rs.",
            "inr",
            "a/c",
            "account",
        ]
        match_count = sum(1 for k in strong_keywords if k in text)

    # require at least 2 strong signals
        return match_count >= 2    

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
            print(f"[GMAIL] Query matched {len(messages)} message(s)")

            output = []

            for msg in messages:

                print(f"[GMAIL] Fetching message {msg['id']}")

                full = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()

                payload = full['payload']
                parts = payload.get('parts', [])

                body = ""

                # Handle multipart emails
                if parts:
                    for part in parts:
                        if part['mimeType'] in ['text/plain', 'text/html']:
                            data = part['body'].get('data')
                            if data:
                                body += base64.urlsafe_b64decode(data).decode(errors="ignore")

                # Handle single part emails
                else:
                    data = payload.get('body', {}).get('data')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode(errors="ignore")

                #Clean HTML
                if "<html" in body.lower():
                    body = BeautifulSoup(body, "html.parser").get_text(" ")
                    if self.is_transaction_email(body):

                        output.append({
                            "source": "gmail",
                            "message_id": msg["id"],
                            "timestamp": int(full["internalDate"]),
                            "raw_text": body
                        })

            print(f"[GMAIL] Imported {len(output)} message(s) successfully")

            return output

        except Exception as e:
            print("[GMAIL FETCH ERROR]", e)
            return []