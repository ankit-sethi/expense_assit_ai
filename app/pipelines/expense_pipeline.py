import logging
from ingestion.gmail_client import GmailClient
from parsing.transaction_parser import TransactionParser
from normalization.categorizer import Categorizer
from storage.repository import ExpenseRepository
from ai.embeddings import build_embedding_text, create_embedding

logger = logging.getLogger(__name__)


def run_pipeline():
    gmail = GmailClient()
    parser = TransactionParser()
    norm = Categorizer()
    repo = ExpenseRepository()

    messages = gmail.fetch_messages()
    saved, skipped, failed = 0, 0, 0

    for raw in messages:
        message_id = raw.get("message_id", "")

        try:
            if repo.exists(message_id):
                logger.info(f"[PIPELINE] Skipping duplicate message {message_id}")
                skipped += 1
                continue

            parsed = parser.parse(raw)
            if not parsed:
                logger.info(f"[PIPELINE] Failed to parse message {message_id}")
                failed += 1
                continue

            normalized = norm.normalize(parsed)

            emb_text = build_embedding_text(normalized)
            normalized["embedding"] = create_embedding(emb_text)

            repo.save(normalized)
            logger.info(f"[PIPELINE] Saved: {normalized['merchant']} {normalized['amount']}")
            saved += 1

        except Exception as e:
            logger.error(f"[PIPELINE] Error processing message {message_id}: {e}")
            failed += 1

    logger.info(f"[PIPELINE] Done — saved: {saved}, skipped: {skipped}, failed: {failed}")
