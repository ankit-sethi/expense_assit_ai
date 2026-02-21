from storage.db import SessionLocal
from storage.models import Expense

class ExpenseRepository:

    def save(self, txn):

        db = SessionLocal()

        obj = Expense(**txn)

        db.add(obj)
        db.commit()
