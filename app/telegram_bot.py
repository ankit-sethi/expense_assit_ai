import os
import logging
import tempfile
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler,
)
from storage.db import SessionLocal
from storage.models import Expense, Credit
from storage.repository import MappingRepository, apply_mappings_to_db
from sqlalchemy import func
from config import TELEGRAM_TOKEN
from datetime import datetime, timedelta
from pipelines.pdf_pipeline import run_pdf_pipeline

logger = logging.getLogger(__name__)

TOKEN = TELEGRAM_TOKEN

# ConversationHandler states for /addmap
ASK_PATTERN, ASK_CLEAN_NAME, ASK_CATEGORY, ASK_SUBCATEGORY = range(4)
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
        "If password-protected, add the password as the file caption.\n\n"
        "Data quality commands:\n"
        "/quality — data quality report\n"
        "/review — view raw text for unknown/uncategorised rows\n"
        "/listmaps — show merchant mappings\n"
        "/addmap — add/update a merchant mapping\n"
        "/applymap — apply mappings to all existing transactions"
    )


# ---------------------------------------------------------------------------
# /quality
# ---------------------------------------------------------------------------

async def quality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        lines = []
        for label, model in [("expenses", Expense), ("credits", Credit)]:
            total          = db.query(func.count(model.id)).scalar()
            null_merchant  = db.query(func.count(model.id)).filter(
                (model.merchant == None) | (model.merchant == "")
            ).scalar()
            other_category = db.query(func.count(model.id)).filter(
                (model.category == "Other") | (model.category == None)
            ).scalar()
            empty_sub      = db.query(func.count(model.id)).filter(
                (model.sub_category == None) | (model.sub_category == "")
            ).scalar()

            lines.append(f"{label.upper()} ({total} rows)")
            lines.append(f"  missing merchant   : {null_merchant}")
            lines.append(f"  category = Other   : {other_category}")
            lines.append(f"  empty sub_category : {empty_sub}")
            lines.append("")

        top = (
            db.query(Expense.merchant, func.count(Expense.id).label("cnt"))
            .filter(Expense.merchant != None, Expense.merchant != "")
            .group_by(Expense.merchant)
            .order_by(func.count(Expense.id).desc())
            .limit(10)
            .all()
        )
        lines.append("TOP 10 MERCHANTS (expenses)")
        for merchant, cnt in top:
            lines.append(f"  {cnt:>4}  {merchant}")
    finally:
        db.close()

    msg = "<pre>" + "\n".join(lines) + "</pre>"
    # Telegram message limit is 4096 chars
    if len(msg) > 4000:
        msg = "<pre>" + "\n".join(lines[:60]) + "\n...</pre>"
    await update.message.reply_text(msg, parse_mode="HTML")


# ---------------------------------------------------------------------------
# /listmaps
# ---------------------------------------------------------------------------

async def listmaps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mappings = MappingRepository().get_all_sorted()
    if not mappings:
        await update.message.reply_text("No mappings configured yet. Use /addmap to add one.")
        return

    lines = [f"{'PRI':>3}  {'PATTERN':<25}  {'CLEAN NAME':<18}  CATEGORY"]
    lines.append("-" * 65)
    for m in mappings[:20]:
        lines.append(f"{m.priority:>3}  {m.raw_pattern:<25}  {m.clean_name:<18}  {m.category} / {m.sub_category}")

    if len(mappings) > 20:
        lines.append(f"... and {len(mappings) - 20} more")

    await update.message.reply_text("<pre>" + "\n".join(lines) + "</pre>", parse_mode="HTML")


# ---------------------------------------------------------------------------
# /applymap
# ---------------------------------------------------------------------------

async def applymap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mappings = MappingRepository().get_all_sorted()
    if not mappings:
        await update.message.reply_text("No mappings configured yet.")
        return

    await update.message.reply_text(f"Applying {len(mappings)} mapping(s)...")

    db = SessionLocal()
    try:
        result = apply_mappings_to_db(mappings, db)
        db.commit()
    except Exception as e:
        db.rollback()
        await update.message.reply_text(f"Error during apply: {e}")
        return
    finally:
        db.close()

    lines = []
    for d in result["details"]:
        if d["expenses"] or d["credits"]:
            lines.append(f"  {d['pattern']:<28} exp:{d['expenses']:>4}  cred:{d['credits']:>4}")

    summary = (
        f"Done.\n"
        f"expenses updated: {result['total_expenses']}\n"
        f"credits  updated: {result['total_credits']}"
    )
    if lines:
        summary += "\n\n<pre>" + "\n".join(lines) + "</pre>"

    await update.message.reply_text(summary, parse_mode="HTML")


# ---------------------------------------------------------------------------
# /review [page]
# ---------------------------------------------------------------------------

_REVIEW_PAGE_SIZE = 3  # rows per Telegram message


def _fetch_review_rows(db, offset: int, limit: int) -> tuple[list, int]:
    """Return (rows, total) where each row is (table_label, orm_object)."""
    results = []
    total   = 0
    for label, model in [("expenses", Expense), ("credits", Credit)]:
        q = db.query(model).filter(
            (model.merchant == None) | (model.merchant == "") | (model.merchant == "Unknown") |
            (model.category == "Other") | (model.category == None)
        ).order_by(model.txn_date.desc())
        total += q.count()
        for row in q.offset(offset).limit(limit - len(results)).all():
            results.append((label, row))
            if len(results) >= limit:
                break
    return results, total


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args_list = context.args
    try:
        page = int(args_list[0]) if args_list else 1
        page = max(1, page)
    except (ValueError, IndexError):
        page = 1

    offset = (page - 1) * _REVIEW_PAGE_SIZE

    db = SessionLocal()
    try:
        rows, total = _fetch_review_rows(db, offset, _REVIEW_PAGE_SIZE)
    finally:
        db.close()

    if total == 0:
        await update.message.reply_text("No rows with unknown merchant or Other category. Looking clean!")
        return

    total_pages = (total + _REVIEW_PAGE_SIZE - 1) // _REVIEW_PAGE_SIZE

    if not rows:
        await update.message.reply_text(
            f"Page {page} is out of range. Use /review or /review 1 (total pages: {total_pages})"
        )
        return

    lines = [f"<b>Unknown/Other rows — page {page}/{total_pages} ({total} total)</b>\n"]

    for label, row in rows:
        raw_snippet = (row.raw_text or "").strip().replace("<", "&lt;").replace(">", "&gt;")
        # Telegram-safe truncation
        if len(raw_snippet) > 400:
            raw_snippet = raw_snippet[:400] + "…"

        lines.append(
            f"<b>{label}</b> | {str(row.txn_date)[:10]} | ₹{row.amount}\n"
            f"  merchant : {row.merchant or '—'}\n"
            f"  category : {row.category or '—'} / {row.sub_category or '—'}\n"
            f"<pre>{raw_snippet}</pre>"
        )

    if page < total_pages:
        lines.append(f"\nNext page: /review {page + 1}")

    msg = "\n\n".join(lines)
    # Split if over Telegram's 4096 char limit
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n<i>Message truncated — use /review with a specific page.</i>"

    await update.message.reply_text(msg, parse_mode="HTML")


# ---------------------------------------------------------------------------
# /addmap — ConversationHandler
# ---------------------------------------------------------------------------

async def addmap_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Adding a merchant mapping.\nSend /cancel at any time to stop.\n\n"
        "Step 1/4 — What raw pattern should I match?\n"
        "Example: <code>swiggy</code> or <code>hdfc bank</code>",
        parse_mode="HTML",
    )
    return ASK_PATTERN


async def addmap_pattern(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pattern = update.message.text.strip().lower()
    if not pattern:
        await update.message.reply_text("Pattern cannot be empty. Try again:")
        return ASK_PATTERN
    context.user_data["pattern"] = pattern
    await update.message.reply_text(
        f"Pattern: <code>{pattern}</code>\n\n"
        "Step 2/4 — What should the canonical merchant name be?\n"
        "Example: <code>Swiggy</code>",
        parse_mode="HTML",
    )
    return ASK_CLEAN_NAME


async def addmap_clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clean_name = update.message.text.strip()
    if not clean_name:
        await update.message.reply_text("Merchant name cannot be empty. Try again:")
        return ASK_CLEAN_NAME
    context.user_data["clean_name"] = clean_name
    await update.message.reply_text(
        f"Clean name: <code>{clean_name}</code>\n\n"
        "Step 3/4 — What category?\n"
        "Examples: <code>Food</code>, <code>Transport</code>, <code>Shopping</code>, <code>Bills</code>",
        parse_mode="HTML",
    )
    return ASK_CATEGORY


async def addmap_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text.strip()
    if not category:
        await update.message.reply_text("Category cannot be empty. Try again:")
        return ASK_CATEGORY
    context.user_data["category"] = category
    await update.message.reply_text(
        f"Category: <code>{category}</code>\n\n"
        "Step 4/4 — Sub-category? (send <code>-</code> to skip)\n"
        "Example: <code>Food Delivery</code>",
        parse_mode="HTML",
    )
    return ASK_SUBCATEGORY


async def addmap_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    sub_category = "" if raw == "-" else raw
    data = context.user_data

    try:
        MappingRepository().upsert(
            raw_pattern=data["pattern"],
            clean_name=data["clean_name"],
            category=data["category"],
            sub_category=sub_category,
        )
    except Exception as e:
        await update.message.reply_text(f"Failed to save mapping: {e}")
        return ConversationHandler.END

    await update.message.reply_text(
        f"Saved mapping:\n"
        f"  pattern  : <code>{data['pattern']}</code>\n"
        f"  name     : <code>{data['clean_name']}</code>\n"
        f"  category : <code>{data['category']} / {sub_category or '—'}</code>\n\n"
        f"Use /applymap to apply it to existing transactions.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def addmap_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END



def run_bot():

    app = ApplicationBuilder().token(TOKEN).build()

    # /addmap conversation — must be registered before the generic TEXT handler
    addmap_conv = ConversationHandler(
        entry_points=[CommandHandler("addmap", addmap_start)],
        states={
            ASK_PATTERN:    [MessageHandler(filters.TEXT & ~filters.COMMAND, addmap_pattern)],
            ASK_CLEAN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addmap_clean)],
            ASK_CATEGORY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, addmap_category)],
            ASK_SUBCATEGORY:[MessageHandler(filters.TEXT & ~filters.COMMAND, addmap_subcategory)],
        },
        fallbacks=[CommandHandler("cancel", addmap_cancel)],
        conversation_timeout=300,
    )
    app.add_handler(addmap_conv)

    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("quality",   quality_command))
    app.add_handler(CommandHandler("review",    review_command))
    app.add_handler(CommandHandler("listmaps",  listmaps_command))
    app.add_handler(CommandHandler("applymap",  applymap_command))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    run_bot()
