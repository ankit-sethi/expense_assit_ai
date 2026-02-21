from ingestion.gmail_client import GmailClient
from parsing.transaction_parser import TransactionParser
from normalization.categorizer import Categorizer
from storage.repository import ExpenseRepository
from ai.embeddings import build_embedding_text, create_embedding

def run_pipeline():

    gmail = GmailClient()
    parser = TransactionParser()
    norm = Categorizer()
    repo = ExpenseRepository()

    messages = gmail.fetch_messages()

    for raw in messages:

        parsed = parser.parse(raw)
        if not parsed:
            continue

        normalized = norm.normalize(parsed)

        emb_text = build_embedding_text(normalized)
        normalized["embedding"] = create_embedding(emb_text)

        repo.save(normalized)
        
        print("Saved:", parsed["merchant"], parsed["amount"])
