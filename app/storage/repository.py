import logging
from typing import Generic, Type, TypeVar
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from storage.db import SessionLocal, get_db
from storage.models import Expense, Credit, MerchantMapping, SmsStaging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseRepository(Generic[T]):

    def __init__(self, model: Type[T]):
        self._model = model

    def exists(self, source_id: str) -> bool:
        with get_db() as db:
            return db.query(self._model).filter(self._model.source == source_id).first() is not None

    def save(self, txn: dict):
        with get_db() as db:
            try:
                db.add(self._model(**txn))
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"[REPO] Failed to save {self._model.__name__}: {e}")
                raise


class ExpenseRepository(BaseRepository[Expense]):
    def __init__(self):
        super().__init__(Expense)


class CreditRepository(BaseRepository[Credit]):
    def __init__(self):
        super().__init__(Credit)


class MappingRepository:

    def get_all_sorted(self) -> list:
        with get_db() as db:
            return (
                db.query(MerchantMapping)
                .order_by(MerchantMapping.priority.desc(), MerchantMapping.id.asc())
                .all()
            )

    def get_by_pattern(self, raw_pattern: str):
        with get_db() as db:
            return db.query(MerchantMapping).filter(
                MerchantMapping.raw_pattern == raw_pattern.lower().strip()
            ).first()

    def upsert(self, raw_pattern: str, clean_name: str, category: str,
               sub_category: str = "", priority: int = 0):
        with get_db() as db:
            try:
                stmt = pg_insert(MerchantMapping).values(
                    raw_pattern=raw_pattern.lower().strip(),
                    clean_name=clean_name.strip(),
                    category=category.strip(),
                    sub_category=sub_category.strip(),
                    priority=priority,
                ).on_conflict_do_update(
                    index_elements=["raw_pattern"],
                    set_=dict(
                        clean_name=clean_name.strip(),
                        category=category.strip(),
                        sub_category=sub_category.strip(),
                        priority=priority,
                    )
                )
                db.execute(stmt)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"[MAPPING REPO] upsert failed: {e}")
                raise

    def delete_by_pattern(self, raw_pattern: str) -> bool:
        with get_db() as db:
            try:
                row = db.query(MerchantMapping).filter(
                    MerchantMapping.raw_pattern == raw_pattern.lower().strip()
                ).first()
                if not row:
                    return False
                db.delete(row)
                db.commit()
                return True
            except Exception as e:
                db.rollback()
                logger.error(f"[MAPPING REPO] delete failed: {e}")
                raise


class SmsStagingRepository:

    def save(self, row: dict) -> tuple[SmsStaging, bool]:
        """
        Insert a parsed SMS row into sms_staging.
        Checks for:
          1. Duplicate staging (same source already staged) → skips silently.
          2. Duplicate in expenses/credits (same amount+bank+date ±1 day) → status='duplicate'.
        Returns (saved_row, was_new).
        """
        from datetime import timedelta
        with get_db() as db:
            # 1. Already staged?
            existing = db.query(SmsStaging).filter(SmsStaging.source == row["source"]).first()
            if existing:
                return existing, False

            # 2. Cross-channel dedup
            status      = "pending"
            duplicate_of = None
            if row.get("parsed_amount") and row.get("parsed_bank") and row.get("parsed_date"):
                date      = row["parsed_date"]
                match_exp = db.query(Expense.source).filter(
                    Expense.amount   == row["parsed_amount"],
                    Expense.bank_name.ilike(row["parsed_bank"]),
                    Expense.txn_date >= date - timedelta(days=1),
                    Expense.txn_date <= date + timedelta(days=1),
                ).first()
                if not match_exp:
                    match_exp = db.query(Credit.source).filter(
                        Credit.amount   == row["parsed_amount"],
                        Credit.bank_name.ilike(row["parsed_bank"]),
                        Credit.txn_date >= date - timedelta(days=1),
                        Credit.txn_date <= date + timedelta(days=1),
                    ).first()
                if match_exp:
                    status       = "duplicate"
                    duplicate_of = match_exp[0]

            obj = SmsStaging(
                raw_sms         = row["raw_sms"],
                sender          = row.get("sender"),
                received_at     = row.get("received_at"),
                parsed_amount   = row.get("parsed_amount"),
                parsed_merchant = row.get("parsed_merchant"),
                parsed_date     = row.get("parsed_date"),
                parsed_bank     = row.get("parsed_bank"),
                txn_type        = row.get("txn_type"),
                source          = row["source"],
                status          = status,
                duplicate_of    = duplicate_of,
            )
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return obj, True

    def get_by_status(self, status: str, limit: int = 50, offset: int = 0) -> list:
        with get_db() as db:
            return (
                db.query(SmsStaging)
                .filter(SmsStaging.status == status)
                .order_by(SmsStaging.received_at.desc())
                .offset(offset).limit(limit)
                .all()
            )

    def count_by_status(self) -> dict:
        with get_db() as db:
            from sqlalchemy import func as sqlfunc
            rows = (
                db.query(SmsStaging.status, sqlfunc.count(SmsStaging.id))
                .group_by(SmsStaging.status)
                .all()
            )
            return {status: count for status, count in rows}

    def get_by_id(self, row_id: int) -> SmsStaging | None:
        with get_db() as db:
            return db.query(SmsStaging).filter(SmsStaging.id == row_id).first()

    def approve(self, row_id: int, db_mappings: list) -> dict | None:
        """
        Promote a staged SMS to expenses or credits.
        Returns the saved transaction dict or None if row not found / already processed.
        """
        from normalization.categorizer import Categorizer
        from ai.embeddings import build_embedding_text, create_embedding
        from datetime import datetime

        with get_db() as db:
            row = db.query(SmsStaging).filter(SmsStaging.id == row_id).first()
            if not row or row.status != "pending":
                return None

            txn = {
                "txn_date":       datetime.combine(row.parsed_date, datetime.min.time()) if row.parsed_date else row.received_at,
                "amount":         row.parsed_amount,
                "merchant":       row.parsed_merchant or "Unknown",
                "payment_method": "SMS",
                "bank_name":      row.parsed_bank or "",
                "source":         row.source,
                "raw_text":       row.raw_sms,
                "currency":       "INR",
            }
            txn = Categorizer().normalize(txn, db_mappings=db_mappings)
            emb_text = build_embedding_text(txn)
            txn["embedding"] = create_embedding(emb_text)

            if row.txn_type == "credit":
                saved = Credit(**txn)
                db.add(saved)
                db.flush()
                row.status    = "approved"
                row.credit_id = saved.id
            else:
                saved = Expense(**txn)
                db.add(saved)
                db.flush()
                row.status     = "approved"
                row.expense_id = saved.id

            db.commit()
            return txn

    def reject(self, row_id: int) -> bool:
        with get_db() as db:
            row = db.query(SmsStaging).filter(SmsStaging.id == row_id).first()
            if not row or row.status != "pending":
                return False
            row.status = "rejected"
            db.commit()
            return True


def apply_mappings_to_db(mappings: list, db) -> dict:
    """
    Bulk-apply merchant mappings to expenses and credits tables via SQL UPDATE.
    Applies highest-priority mappings first (caller must pass already-sorted list).
    Returns {"total_expenses": N, "total_credits": M, "details": [...]}
    """
    total_expenses = total_credits = 0
    details = []

    for m in mappings:
        pat = f"%{m.raw_pattern.lower()}%"
        params = {
            "clean": m.clean_name,
            "cat":   m.category,
            "sub":   m.sub_category,
            "pat":   pat,
        }
        sql_tpl = (
            "UPDATE {table} SET merchant = :clean, category = :cat, sub_category = :sub "
            "WHERE merchant IS NOT NULL AND LOWER(merchant) LIKE :pat"
        )
        r_exp  = db.execute(text(sql_tpl.format(table="expenses")),  params)
        r_cred = db.execute(text(sql_tpl.format(table="credits")),   params)
        exp_n, cred_n = r_exp.rowcount, r_cred.rowcount
        total_expenses += exp_n
        total_credits  += cred_n
        details.append({
            "pattern":  m.raw_pattern,
            "expenses": exp_n,
            "credits":  cred_n,
        })

    return {"total_expenses": total_expenses, "total_credits": total_credits, "details": details}
