from fastapi import FastAPI, HTTPException
from expense_assit_ai.app.ai.sql_agent import generate_sql
from expense_assit_ai.app.storage.db import run_sql
from expense_assit_ai.app.ai.sql_validator import validate_sql

app = FastAPI()

@app.get("/query")
def query_expenses(q: str):

    sql = generate_sql(q)

    if not validate_sql(sql):
        raise HTTPException(
            status_code=400,
            detail="Unsafe query generated"
        )

    result = run_sql(sql)

    return {
        "sql": sql,
        "result": result
    }
