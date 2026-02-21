from ai.sql_agent import ask as sql_ask
from ai.embeddings import create_embedding   # or semantic search function
from ai.semantic_search import search_similar

NUMERIC_KEYWORDS = [
    "how much", "total", "sum", "spent",
    "count", "average", "monthly", "last month",
    "this year"
]


def is_structured_query(q: str) -> bool:
    q = q.lower()
    return any(k in q for k in NUMERIC_KEYWORDS)


def route_query(q: str):

    if is_structured_query(q):
        print("[ROUTER] Using SQL agent")
        return sql_ask(q)

    else:
        print("[ROUTER] Using semantic search")
        return search_similar(q)
