from openai import OpenAI
from sqlalchemy import text
from storage.db import engine

client = OpenAI()


def build_embedding_text(txn: dict) -> str:
    """
    Convert transaction into meaningful text for embedding.
    This improves semantic search quality.
    """

    parts = [
        txn.get("merchant", ""),
        txn.get("category", ""),
        txn.get("payment_method", ""),
        txn.get("raw_text", "")
    ]

    return " ".join(p for p in parts if p)


def create_embedding(text: str) -> list[float]:
    """
    Call OpenAI to generate embedding vector.
    """

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )

    return response.data[0].embedding



def search_similar(query):

    vector = create_embedding(query)

    sql = """
    SELECT merchant, amount, txn_date
    FROM expenses
    ORDER BY embedding <-> :vec
    LIMIT 5;
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"vec": vector}).fetchall()

    return rows
