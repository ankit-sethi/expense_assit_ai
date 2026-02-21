from expense_assit_ai.app.storage.db import SessionLocal
from expense_assit_ai.app.storage.models import Expense
from datetime import datetime

db = SessionLocal()

test_expense = Expense(
    txn_date=datetime.now(),
    amount=499.00,
    merchant="Test Amazon",
    category="Shopping",
    payment_method="Credit Card",
    bank_name="HDFC",
    source="test"
)

db.add(test_expense)

db.commit()

print("Inserted successfully!")
