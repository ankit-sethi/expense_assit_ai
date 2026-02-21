from openai import OpenAI
from sqlalchemy import text
from config import OPENAI_KEY
from datetime import datetime
from storage.db import engine
import re

client = OpenAI(api_key=OPENAI_KEY)

SCHEMA = """
Table: expenses

Columns:
txn_date TIMESTAMP
amount NUMERIC
merchant TEXT
category TEXT
payment_method TEXT
bank_name TEXT
"""

def generate_sql(user_query: str):

    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
You are an elite PostgreSQL generator.

TODAY: {today}

{SCHEMA}

RULES:
- ONLY generate SELECT queries
- NEVER modify data
- Use SUM(amount) for totals
- Always apply date filters if user implies time
- Return ONLY SQL. No explanation.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_query}
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()


def clean_sql(query: str) -> str:
    # removes ```sql ... ``` or ``` ... ``` wrappers
    query = re.sub(r"```(?:sql)?", "", query)
    return query.strip()

def run_sql(sql):
    sql = clean_sql(sql)

    if "DELETE" in sql or "DROP" in sql:
        raise Exception("Unsafe query")

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        return result.fetchall()

def ask(question):

    sql = generate_sql(question)
    rows = run_sql(sql)

    return {
        "sql": sql,
        "result": rows
    }
