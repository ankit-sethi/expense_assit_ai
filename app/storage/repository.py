import logging
from typing import Generic, Type, TypeVar
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from storage.db import SessionLocal, get_db
from storage.models import Expense, Credit, MerchantMapping

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
