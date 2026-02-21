from sqlalchemy import text
from storage.db import engine
from ai.embeddings import create_embedding


def search_similar(query: str, limit: int = 5):

    print("[SEMANTIC] Generating query embedding...")
    query_vector = create_embedding(query)

    print("[SEMANTIC] Running similarity search...")

    sql = """
        SELECT merchant, amount, txn_date,
               embedding <-> cast(:query_vector AS vector) AS distance
        FROM expenses
        WHERE embedding IS NOT NULL
        ORDER BY embedding <-> cast(:query_vector AS vector)
        LIMIT :limit;
    """

    with engine.connect() as conn:
        rows = conn.execute(
            text(sql),
            {"query_vector": query_vector, "limit": limit}
        ).fetchall()

    results = []

    for r in rows:
        results.append({
            "merchant": r[0],
            "amount": float(r[1]),
            "txn_date": r[2],
            "distance": float(r[3])
        })

    return results
