from sqlalchemy import text
from storage.db import engine
import pandas as pd

def test_embeddings():

    with engine.connect() as conn:

        rows = conn.execute(text("""
            SELECT embedding
            FROM expenses
            WHERE embedding IS NOT NULL
            LIMIT 5
        """)).fetchall()

        if not rows:
            print("No embeddings found.")
            return

        for r in rows:
            print("Merchant:", r[0])
            print(type(r[0]))
            print(len(r[0]))
            print("Amount:", r[1])
            print("Vector length:", len(r[2]))
            print("-"*30)


if __name__ == "__main__":
    test_embeddings()
