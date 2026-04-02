import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.db import SessionLocal
from storage.models import Expense

db = SessionLocal()

try:
    bad_amount = db.query(Expense).filter(Expense.amount > 10_000_000).all()
    bad_merchant = db.query(Expense).filter(Expense.merchant.in_(["the", "a", "an"])).all()

    bad = set(bad_amount) | set(bad_merchant)

    if not bad:
        print("No bad rows found.")
    else:
        print(f"Found {len(bad)} bad row(s):")
        for r in bad:
            print(f"  id={r.id}  amount={r.amount}  merchant={r.merchant!r}")

        confirm = input("\nDelete these rows? (yes/no): ").strip().lower()
        if confirm == "yes":
            for r in bad:
                db.delete(r)
            db.commit()
            print(f"Deleted {len(bad)} row(s).")
        else:
            print("Aborted.")
finally:
    db.close()
