import os
import logging
import tempfile
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from storage.db import SessionLocal
from storage.models import Expense
from sqlalchemy import func
from config import TELEGRAM_TOKEN
from datetime import datetime, timedelta
from pipelines.pdf_pipeline import run_pdf_pipeline

logger = logging.getLogger(__name__)

TOKEN = TELEGRAM_TOKEN
def interpret_query(text: str):

    text = text.lower()

    filters_dict = {}

    # --- detect merchant keywords dynamically ---
    filters_dict["merchant"] = None

    # crude heuristic: last word may be merchant
    words = text.split()
    if len(words) > 1:
        filters_dict["merchant"] = words[-1]

    # --- detect time ranges ---
    today = datetime.today()

    if "today" in text:
        filters_dict["start_date"] = today.replace(hour=0, minute=0, second=0)

    elif "yesterday" in text:
        y = today - timedelta(days=1)
        filters_dict["start_date"] = y.replace(hour=0, minute=0, second=0)
        filters_dict["end_date"] = today.replace(hour=0, minute=0, second=0)

    elif "week" in text:
        filters_dict["start_date"] = today - timedelta(days=7)

    elif "month" in text:
        filters_dict["start_date"] = today - timedelta(days=30)

    # --- detect categories ---
    categories = ["food", "shopping", "transport", "travel"]
    for c in categories:
        if c in text:
            filters_dict["category"] = c

    # --- detect payment method ---
    if "upi" in text:
        filters_dict["payment_method"] = "upi"

    return filters_dict


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    parsed = interpret_query(text)

    db = SessionLocal()

    query = db.query(func.sum(Expense.amount))

    # merchant filter
    if parsed.get("merchant"):
        query = query.filter(
            Expense.merchant.ilike(f"%{parsed['merchant']}%")
        )

    # category filter
    if parsed.get("category"):
        query = query.filter(
            Expense.category.ilike(f"%{parsed['category']}%")
        )

    # payment method
    if parsed.get("payment_method"):
        query = query.filter(
            Expense.payment_method.ilike(f"%{parsed['payment_method']}%")
        )

    # date filters
    if parsed.get("start_date"):
        query = query.filter(Expense.txn_date >= parsed["start_date"])

    if parsed.get("end_date"):
        query = query.filter(Expense.txn_date <= parsed["end_date"])

    total = query.scalar() or 0

    await update.message.reply_text(f"Total spending: ₹{float(total):.2f}")

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document

    if doc.mime_type != "application/pdf":
        await update.message.reply_text("Please send a PDF file.")
        return

    await update.message.reply_text("Processing your bank statement, please wait...")

    tg_file = await doc.get_file()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await tg_file.download_to_drive(tmp_path)
        password = update.message.caption.strip() if update.message.caption else None
        summary  = run_pdf_pipeline(tmp_path, password=password)

        reply = (
            f"Statement processed.\n"
            f"Debits saved:  {summary['saved_debits']}\n"
            f"Credits saved: {summary['saved_credits']}\n"
            f"Skipped (dup): {summary['skipped']}\n"
            f"Failed:        {summary['failed']}"
        )
    except ValueError as e:
        reply = f"Could not open PDF: {e}\nIf password-protected, send the file with the password as the caption."
    except Exception as e:
        logger.error(f"[BOT] PDF processing error: {e}")
        reply = "An error occurred while processing the PDF."
    finally:
        os.unlink(tmp_path)

    await update.message.reply_text(reply)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Ask me about your expenses.\n"
        "Examples:\n"
        "- food this month\n"
        "- swiggy last week\n"
        "- upi today\n\n"
        "You can also send a bank statement PDF to import transactions.\n"
        "If password-protected, add the password as the file caption."
    )



def run_bot():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    run_bot()
