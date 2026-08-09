import os
import shutil
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from ai.sql_agent import generate_sql, run_sql
from ai.sql_validator import validate_sql
from storage.db import get_db
from pipelines.pdf_pipeline import run_pdf_pipeline

logger = logging.getLogger(__name__)

app = FastAPI()

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

INBOX_DIR     = Path(__file__).parent.parent / "inbox"
PROCESSED_DIR = INBOX_DIR / "processed"
FAILED_DIR    = INBOX_DIR / "failed"


@app.get("/query")
def query_expenses(q: str):
    sql = generate_sql(q)

    if not validate_sql(sql):
        raise HTTPException(status_code=400, detail="Unsafe query generated")

    result = run_sql(sql)
    return {"sql": sql, "result": result}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


def _check_db_reachable():
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
    except OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Database unreachable. Ensure Docker is running: docker-compose up -d",
        )


def _move_overwrite(path: Path, dest_dir: Path):
    """Move path into dest_dir, replacing any existing file with the same name."""
    target = dest_dir / path.name
    if target.exists():
        target.unlink()
    shutil.move(str(path), target)


def _process_pdf(path: Path, password: str | None, totals: dict, files: list):
    """Run the PDF pipeline on one file, archive it to processed/ or failed/,
    and append a per-file report. Shared by /ingest and /upload."""
    sidecar = path.with_suffix(".pdf.password")
    try:
        summary = run_pdf_pipeline(str(path), password=password)

        if summary.get("saved_debits", 0) + summary.get("saved_credits", 0) + summary.get("skipped", 0) == 0 and summary.get("failed", 0) == 0:
            # Parser returned 0 rows — unrecognised format
            files.append({
                "name": path.name,
                "status": "error",
                "stage": "pdf_parse",
                "error": "No transactions found — format may not be supported.",
                "resolution": "Supported formats: HDFC Credit Card, HDFC Account, SBI, Axis Bank, Amex Credit Card, OneCard (Federal Bank).",
            })
            _move_overwrite(path, FAILED_DIR)
            totals["failed"] += 1
            return

        for k in totals:
            totals[k] += summary.get(k, 0)

        _move_overwrite(path, PROCESSED_DIR)
        if sidecar.exists():
            _move_overwrite(sidecar, PROCESSED_DIR)

        files.append({"name": path.name, "status": "ok", **summary})
        logger.info(f"[INGEST] {path.name} — {summary}")

    except ValueError as e:
        err_msg = str(e)
        if "password" in err_msg.lower():
            resolution = (
                f"This PDF is password-protected. Supply the password in the upload form, "
                f"or create a sidecar file named '{path.name}.password' in inbox/."
            )
        else:
            resolution = f"Check the PDF file is a valid bank statement ({err_msg})."
        files.append({"name": path.name, "status": "error", "stage": "pdf_parse", "error": err_msg, "resolution": resolution})
        _move_overwrite(path, FAILED_DIR)
        totals["failed"] += 1
        logger.error(f"[INGEST] {path.name} — ValueError: {e}")

    except OperationalError as e:
        files.append({
            "name": path.name,
            "status": "error",
            "stage": "db_save",
            "error": "Database connection lost during processing.",
            "resolution": "Ensure Docker is running: docker-compose up -d",
        })
        _move_overwrite(path, FAILED_DIR)
        totals["failed"] += 1
        logger.error(f"[INGEST] {path.name} — DB error: {e}")

    except Exception as e:
        err_type = type(e).__name__
        # Detect OpenAI API errors by class name (avoids hard import dependency)
        if "openai" in err_type.lower() or "api" in err_type.lower():
            stage = "embedding"
            resolution = "Check that OPENAI_API_KEY is set correctly in your .env file."
        else:
            stage = "unknown"
            resolution = f"Unexpected error ({err_type}). Check server logs for details."
        files.append({"name": path.name, "status": "error", "stage": stage, "error": str(e), "resolution": resolution})
        _move_overwrite(path, FAILED_DIR)
        totals["failed"] += 1
        logger.error(f"[INGEST] {path.name} — {err_type}: {e}")


def _ingest_response(processed: int, totals: dict, files: list, message: str | None = None):
    resp = {
        "processed_files": processed,
        "total_saved_debits": totals["saved_debits"],
        "total_saved_credits": totals["saved_credits"],
        "total_skipped": totals["skipped"],
        "total_failed": totals["failed"],
        "files": files,
    }
    if message:
        resp["message"] = message
    return resp


@app.post("/ingest")
def ingest_inbox():
    """Scan inbox/ for PDFs and ingest them incrementally into the database."""
    if not INBOX_DIR.exists():
        raise HTTPException(
            status_code=503,
            detail=f"inbox/ folder not found at {INBOX_DIR}. Create it and drop PDFs there.",
        )

    _check_db_reachable()

    PROCESSED_DIR.mkdir(exist_ok=True)
    FAILED_DIR.mkdir(exist_ok=True)

    pdfs = sorted(p for p in INBOX_DIR.iterdir() if p.suffix.lower() == ".pdf" and p.is_file())

    totals = {"saved_debits": 0, "saved_credits": 0, "skipped": 0, "failed": 0}
    files = []

    if not pdfs:
        return _ingest_response(0, totals, files, "No PDF files found in inbox/ — drop statements there and try again.")

    for path in pdfs:
        sidecar = path.with_suffix(".pdf.password")
        password = sidecar.read_text().strip() if sidecar.exists() else None
        _process_pdf(path, password, totals, files)

    return _ingest_response(len(pdfs), totals, files)


@app.post("/upload")
def upload_pdfs(files: list[UploadFile] = File(...), password: str = Form("")):
    """Upload one or more PDF statements from the browser and ingest them.

    Optional form field `password` applies to all password-protected PDFs in the batch.
    Uploaded files are staged in inbox/ and archived to processed/ or failed/."""
    _check_db_reachable()

    INBOX_DIR.mkdir(exist_ok=True)
    PROCESSED_DIR.mkdir(exist_ok=True)
    FAILED_DIR.mkdir(exist_ok=True)

    totals = {"saved_debits": 0, "saved_credits": 0, "skipped": 0, "failed": 0}
    reports = []
    processed = 0

    for uf in files:
        name = Path(uf.filename or "upload.pdf").name  # strip any client-sent path
        if not name.lower().endswith(".pdf"):
            reports.append({
                "name": name,
                "status": "error",
                "stage": "upload",
                "error": "Not a PDF file.",
                "resolution": "Only .pdf bank statements are supported.",
            })
            totals["failed"] += 1
            processed += 1
            continue

        dest = INBOX_DIR / name
        with dest.open("wb") as out:
            shutil.copyfileobj(uf.file, out)

        _process_pdf(dest, password.strip() or None, totals, reports)
        processed += 1

    return _ingest_response(processed, totals, reports)


@app.get("/dashboard/data")
def dashboard_data():
    with get_db() as db:
        monthly = db.execute(text("SELECT * FROM v_monthly_spend ORDER BY month")).mappings().all()
        categories = db.execute(text("SELECT * FROM v_category_spend ORDER BY total_spent DESC")).mappings().all()
        merchants = db.execute(text("SELECT * FROM v_top_merchants ORDER BY total_spent DESC LIMIT 15")).mappings().all()
        income_vs_exp = db.execute(text("SELECT * FROM v_monthly_income_vs_expense ORDER BY month")).mappings().all()

    def fmt(val):
        if hasattr(val, "isoformat"):
            return val.isoformat()
        if val is None:
            return 0
        return val

    return {
        "monthly_spend": [
            {"month": fmt(r["month"]), "total_spent": fmt(r["total_spent"]), "txn_count": r["txn_count"]}
            for r in monthly
        ],
        "category_spend": [
            {"category": r["category"], "total_spent": fmt(r["total_spent"]), "txn_count": r["txn_count"]}
            for r in categories
        ],
        "top_merchants": [
            {"merchant": r["merchant"], "total_spent": fmt(r["total_spent"]), "txn_count": r["txn_count"],
             "avg_amount": fmt(r["avg_amount"])}
            for r in merchants
        ],
        "income_vs_expense": [
            {"month": fmt(r["month"]), "expenses": fmt(r["expenses"]),
             "income": fmt(r["income"]), "net": fmt(r["net"])}
            for r in income_vs_exp
        ],
    }
