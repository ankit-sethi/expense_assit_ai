from storage.db import SessionLocal
from storage.models import Expense
from sqlalchemy import func

db = SessionLocal()

try:
    total = db.query(func.count(Expense.id)).scalar()
    print(f"\n{'='*50}")
    print(f"  TOTAL EXPENSES: {total}")
    print(f"{'='*50}\n")

    if total == 0:
        print("No records found.")
        exit()

    def pct(n): return f"{n}/{total} ({100*n//total}%)"

    filled_merchant        = db.query(func.count(Expense.id)).filter(Expense.merchant != None, Expense.merchant != "", Expense.merchant != "Unknown").scalar()
    filled_amount          = db.query(func.count(Expense.id)).filter(Expense.amount != None).scalar()
    filled_category        = db.query(func.count(Expense.id)).filter(Expense.category != None, Expense.category != "Other").scalar()
    filled_sub_category    = db.query(func.count(Expense.id)).filter(Expense.sub_category != None, Expense.sub_category != "").scalar()
    filled_payment_method  = db.query(func.count(Expense.id)).filter(Expense.payment_method != None, Expense.payment_method != "").scalar()
    filled_bank_name       = db.query(func.count(Expense.id)).filter(Expense.bank_name != None, Expense.bank_name != "").scalar()
    filled_txn_date        = db.query(func.count(Expense.id)).filter(Expense.txn_date != None).scalar()
    filled_embedding       = db.query(func.count(Expense.id)).filter(Expense.embedding != None).scalar()

    print("FIELD POPULATION RATES:")
    print(f"  amount          {pct(filled_amount)}")
    print(f"  txn_date        {pct(filled_txn_date)}")
    print(f"  merchant        {pct(filled_merchant)}")
    print(f"  category        {pct(filled_category)}")
    print(f"  sub_category    {pct(filled_sub_category)}")
    print(f"  payment_method  {pct(filled_payment_method)}")
    print(f"  bank_name       {pct(filled_bank_name)}")
    print(f"  embedding       {pct(filled_embedding)}")

    print(f"\n{'='*50}")
    print("CATEGORY BREAKDOWN:")
    for cat, count in db.query(Expense.category, func.count(Expense.id)).group_by(Expense.category).order_by(func.count(Expense.id).desc()).all():
        print(f"  {cat or 'None':<20} {count}")

    print(f"\n{'='*50}")
    print("PAYMENT METHOD BREAKDOWN:")
    for pm, count in db.query(Expense.payment_method, func.count(Expense.id)).group_by(Expense.payment_method).order_by(func.count(Expense.id).desc()).all():
        print(f"  {pm or 'None':<20} {count}")

    print(f"\n{'='*50}")
    print("SAMPLE RECORDS (latest 5):")
    rows = db.query(Expense).order_by(Expense.created_at.desc()).limit(5).all()
    for r in rows:
        print(f"\n  merchant:       {r.merchant}")
        print(f"  amount:         {r.amount} {r.currency}")
        print(f"  txn_date:       {r.txn_date}")
        print(f"  category:       {r.category} / {r.sub_category}")
        print(f"  payment_method: {r.payment_method}")
        print(f"  bank_name:      {r.bank_name}")
        print(f"  source:         {r.source}")

    print(f"\n{'='*50}\n")

finally:
    db.close()
