FORBIDDEN = ["drop", "delete", "update", "insert", "alter", "truncate"]

def validate_sql(query: str):
    q = query.lower().strip()

    if not q.startswith("select"):
        return False

    if any(word in q for word in FORBIDDEN):
        return False

    return True