from ingestion.gmail_client import GmailClient

gmail = GmailClient()
messages = gmail.fetch_messages()
print(gmail)