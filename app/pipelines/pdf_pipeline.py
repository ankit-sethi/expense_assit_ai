import logging
from ingestion.pdf_parser import PDFParser
from normalization.categorizer import Categorizer
from storage.repository import ExpenseRepository, CreditRepository
from ai.embeddings import build_embedding_text, create_embedding

logger = logging.getLogger(__name__)


def run_pdf_pipeline(pdf_path: str, password: str | None = None) -> dict:
    parser    = PDFParser()
    norm      = Categorizer()
    exp_repo  = ExpenseRepository()
    cred_repo = CreditRepository()

    rows = parser.parse(pdf_path, password=password)
    if not rows:
        return {"saved_debits": 0, "saved_credits": 0, "skipped": 0, "failed": 0}

    saved_debits = saved_credits = skipped = failed = 0

    for row in rows:
        source   = row["source"]
        txn_type = row.pop("txn_type")
        repo     = exp_repo if txn_type == "debit" else cred_repo

        try:
            if repo.exists(source):
                logger.info(f"[PDF PIPELINE] Skipping duplicate {source}")
                skipped += 1
                continue

            normalized = norm.normalize(row)
            normalized["embedding"] = create_embedding(build_embedding_text(normalized))
            repo.save(normalized)

            if txn_type == "debit":
                saved_debits += 1
                logger.info(f"[PDF PIPELINE] Saved debit: {normalized['merchant']} ₹{normalized['amount']}")
            else:
                saved_credits += 1
                logger.info(f"[PDF PIPELINE] Saved credit: {normalized['merchant']} ₹{normalized['amount']}")

        except Exception as e:
            logger.error(f"[PDF PIPELINE] Error processing row {source}: {e}")
            failed += 1

    summary = {"saved_debits": saved_debits, "saved_credits": saved_credits, "skipped": skipped, "failed": failed}
    logger.info(f"[PDF PIPELINE] Done — {summary}")
    return summary


if __name__ == "__main__":
    import sys
    path     = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else None
    print(run_pdf_pipeline(path, password=password))
