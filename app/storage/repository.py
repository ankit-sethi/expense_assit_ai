import logging
from typing import Generic, Type, TypeVar
from storage.db import SessionLocal
from storage.models import Expense, Credit

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseRepository(Generic[T]):

    def __init__(self, model: Type[T]):
        self._model = model

    def exists(self, source_id: str) -> bool:
        db = SessionLocal()
        try:
            return db.query(self._model).filter(self._model.source == source_id).first() is not None
        finally:
            db.close()

    def save(self, txn: dict):
        db = SessionLocal()
        try:
            db.add(self._model(**txn))
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[REPO] Failed to save {self._model.__name__}: {e}")
            raise
        finally:
            db.close()


class ExpenseRepository(BaseRepository[Expense]):
    def __init__(self):
        super().__init__(Expense)


class CreditRepository(BaseRepository[Credit]):
    def __init__(self):
        super().__init__(Credit)
