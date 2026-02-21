from sqlalchemy import text
from storage.db import engine


def truncate_expenses():
    """
    Deletes all rows from expenses table.
    Keeps schema intact.
    """

    print("[RESET] Truncating expenses table...")

    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE expenses RESTART IDENTITY CASCADE;"))
        conn.commit()

    print("[RESET] Expenses table cleared.")


def drop_expenses_table():
    """
    Drops the expenses table entirely.
    """

    print("[RESET] Dropping expenses table...")

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS expenses CASCADE;"))
        conn.commit()

    print("[RESET] Expenses table dropped.")
