import sys
import os
import re
import csv
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.db import SessionLocal
from storage.models import Expense, Credit
from storage.repository import MappingRepository, apply_mappings_to_db
from parsing.parse_utils import clean_merchant_name, clean_vpa
from sqlalchemy import func

# Default CSV path: project_root/merchant_mappings.csv
_DEFAULT_CSV = Path(__file__).parent.parent.parent / "merchant_mappings.csv"


def cmd_quality():
    db = SessionLocal()
    try:
        for label, model in [("expenses", Expense), ("credits", Credit)]:
            total = db.query(func.count(model.id)).scalar()
            null_merchant  = db.query(func.count(model.id)).filter(
                (model.merchant == None) | (model.merchant == "")
            ).scalar()
            other_category = db.query(func.count(model.id)).filter(
                (model.category == "Other") | (model.category == None)
            ).scalar()
            empty_sub      = db.query(func.count(model.id)).filter(
                (model.sub_category == None) | (model.sub_category == "")
            ).scalar()

            print(f"\n{'='*55}")
            print(f"  {label.upper()}  (total: {total})")
            print(f"{'='*55}")
            print(f"  missing merchant   : {null_merchant}/{total}")
            print(f"  category = 'Other' : {other_category}/{total}")
            print(f"  empty sub_category : {empty_sub}/{total}")

        print(f"\n{'='*55}")
        print("  TOP 20 RAW MERCHANT VALUES (expenses)")
        print(f"{'='*55}")
        rows = (
            db.query(Expense.merchant, func.count(Expense.id).label("cnt"))
            .filter(Expense.merchant != None, Expense.merchant != "")
            .group_by(Expense.merchant)
            .order_by(func.count(Expense.id).desc())
            .limit(20)
            .all()
        )
        for merchant, cnt in rows:
            print(f"  {cnt:>5}  {merchant}")
        print()
    finally:
        db.close()


def cmd_list():
    mappings = MappingRepository().get_all_sorted()
    if not mappings:
        print("No mappings configured yet.")
        return

    print(f"\n{'='*80}")
    print(f"  {'PRI':>3}  {'PATTERN':<28}  {'CLEAN NAME':<20}  {'CATEGORY':<15}  SUB")
    print(f"{'='*80}")
    for m in mappings:
        print(f"  {m.priority:>3}  {m.raw_pattern:<28}  {m.clean_name:<20}  {m.category:<15}  {m.sub_category}")
    print(f"  {len(mappings)} mapping(s)\n")


def cmd_add():
    print("\nAdd / update a merchant mapping.")
    print("(Press Ctrl+C to cancel)\n")

    try:
        pattern = input("Raw pattern to match (e.g. 'swiggy food'): ").strip().lower()
        if not pattern:
            print("Pattern cannot be empty.")
            return

        clean_name = input("Canonical merchant name (e.g. 'Swiggy'): ").strip()
        if not clean_name:
            print("Clean name cannot be empty.")
            return

        category = input("Category (e.g. 'Food'): ").strip()
        if not category:
            print("Category cannot be empty.")
            return

        sub_category = input("Sub-category (e.g. 'Food Delivery') [Enter to skip]: ").strip()

        priority_raw = input("Priority [0]: ").strip()
        try:
            priority = int(priority_raw) if priority_raw else 0
        except ValueError:
            print("Priority must be an integer. Using 0.")
            priority = 0

    except KeyboardInterrupt:
        print("\nCancelled.")
        return

    MappingRepository().upsert(
        raw_pattern=pattern,
        clean_name=clean_name,
        category=category,
        sub_category=sub_category,
        priority=priority,
    )
    print(f"\nSaved: '{pattern}' → '{clean_name}' ({category} / {sub_category})\n")


def cmd_delete():
    print("\nDelete a merchant mapping.")
    print("(Press Ctrl+C to cancel)\n")

    try:
        pattern = input("Pattern to delete: ").strip().lower()
    except KeyboardInterrupt:
        print("\nCancelled.")
        return

    if not pattern:
        print("Pattern cannot be empty.")
        return

    repo = MappingRepository()
    row  = repo.get_by_pattern(pattern)
    if not row:
        print(f"No mapping found for pattern '{pattern}'.")
        return

    print(f"\nFound: '{row.raw_pattern}' → '{row.clean_name}' ({row.category} / {row.sub_category})")
    try:
        confirm = input("Delete this mapping? (yes/no): ").strip().lower()
    except KeyboardInterrupt:
        print("\nCancelled.")
        return

    if confirm == "yes":
        repo.delete_by_pattern(pattern)
        print("Deleted.\n")
    else:
        print("Aborted.\n")


def cmd_review(table: str = "both", issue: str = "both"):
    """
    Interactively review rows with unknown merchant or Other/null category.
    Shows the full raw_text (email body or PDF transaction line) for each row.

    table: 'expenses' | 'credits' | 'both'
    issue: 'merchant' | 'category' | 'both'
    """
    db = SessionLocal()
    try:
        sources = []
        if table in ("expenses", "both"):
            sources.append(("expenses", Expense))
        if table in ("credits", "both"):
            sources.append(("credits", Credit))

        rows = []
        for label, model in sources:
            q = db.query(model)
            if issue == "merchant":
                q = q.filter(
                    (model.merchant == None) | (model.merchant == "") | (model.merchant == "Unknown")
                )
            elif issue == "category":
                q = q.filter(
                    (model.category == "Other") | (model.category == None)
                )
            else:  # both
                q = q.filter(
                    (model.merchant == None) | (model.merchant == "") | (model.merchant == "Unknown") |
                    (model.category == "Other") | (model.category == None)
                )
            for row in q.order_by(model.txn_date.desc()).all():
                rows.append((label, row))
    finally:
        db.close()

    if not rows:
        print("No rows found matching the filter. Data looks clean!")
        return

    total = len(rows)
    print(f"\nFound {total} row(s) needing attention  "
          f"(filter: table={table}, issue={issue})")
    print("Controls: [Enter]/[n] next   [a] add mapping   [s] skip to next   [q] quit\n")

    i = 0
    while i < len(rows):
        label, row = rows[i]
        print("─" * 60)
        print(f"[{i+1}/{total}]  {label}  |  {str(row.txn_date)[:10]}  |  ₹{row.amount}")
        print(f"  merchant  : {row.merchant or '—'}")
        print(f"  category  : {row.category or '—'}  /  {row.sub_category or '—'}")
        print(f"  source    : {row.source or '—'}")
        print(f"\n  raw_text  :")
        raw = (row.raw_text or "").strip()
        for line in raw.splitlines():
            line = line.strip()
            if line:
                print(f"    {line}")
        print()

        try:
            cmd = input("[Enter] next   [a] add mapping   [q] quit: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if cmd == "q":
            break
        elif cmd == "a":
            _inline_add(raw_text=row.raw_text or "")
            # Stay on the same row so the user sees the result before moving on
            continue
        else:
            i += 1

    print("\nReview complete.")


def _extract_pattern_candidates(raw_text: str) -> list[str]:
    """
    Pull candidate merchant patterns from a raw email or PDF transaction line.
    Returns up to 5 candidates, best first.
    """
    # Noise words that are not merchant names
    _NOISE = {
        "debit", "credit", "bank", "inr", "upi", "neft", "imps", "rtgs",
        "amount", "transaction", "account", "card", "your", "has", "been",
        "used", "for", "the", "and", "via", "ref", "no", "date", "time",
        "balance", "available", "total", "rupees", "rs", "statement",
    }
    candidates = []
    seen = set()

    def _add(phrase: str):
        cleaned = clean_merchant_name(phrase)
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen or key in _NOISE:
            return
        # skip if it's only noise words
        words = {w.lower() for w in cleaned.split()}
        if words.issubset(_NOISE):
            return
        seen.add(key)
        candidates.append(key)

    # 1. Phrases after payment keywords (highest confidence)
    m = re.search(
        r'(?:paid to|payment to|at|for merchant|to merchant)\s+([A-Za-z0-9 &.\-]{3,40})',
        raw_text, re.IGNORECASE,
    )
    if m:
        _add(m.group(1))

    # 2. Consecutive uppercase words (bank statement style: SWIGGY ORDER, HDFC BANK)
    for phrase in re.findall(r'\b[A-Z][A-Z0-9&/\-]{2,}(?:\s+[A-Z][A-Z0-9&/\-]{2,}){0,3}\b', raw_text):
        _add(phrase)

    # 3. VPA handle before @ (e.g. phi.xpressbees from phi.xpressbees@icici)
    vpa = re.search(r'([A-Za-z][A-Za-z0-9.\-_]{2,})@[A-Za-z0-9.\-_]+', raw_text)
    if vpa:
        handle = vpa.group(1).replace('.', ' ').replace('-', ' ').strip()
        _add(handle)

    return candidates[:5]


def _suggest_pattern(raw_text: str, clean_label: str) -> str | None:
    """
    Given the user's clean label and the transaction's raw_text,
    return the best substring pattern to use, or None if nothing found.
    """
    text_lower = raw_text.lower()
    label_lower = clean_label.lower().strip()

    # Full label appears verbatim
    if label_lower in text_lower:
        return label_lower

    # Any individual word of the label (length > 3) appears in text
    for word in sorted(label_lower.split(), key=len, reverse=True):
        if len(word) > 3 and word in text_lower:
            return word

    return None


def _inline_add(raw_text: str = ""):
    """
    User-facing add-mapping flow embedded in the review loop.
    User provides the clean merchant label; system derives the pattern from raw_text.
    """
    print()
    try:
        clean_name = input("  What is this merchant? (clean name, e.g. 'Swiggy'): ").strip()
        if not clean_name:
            print("  Skipping.\n")
            return
    except (KeyboardInterrupt, EOFError):
        print("\n  Cancelled.\n")
        return

    # Try to auto-suggest a pattern
    pattern = _suggest_pattern(raw_text, clean_name)
    candidates = _extract_pattern_candidates(raw_text)

    try:
        if pattern:
            print(f"\n  Suggested pattern: '{pattern}'")
            ans = input("  Use this? [Y/n/type your own]: ").strip()
            if ans.lower() == 'n':
                pattern = None
            elif ans and ans.lower() != 'y':
                pattern = ans.lower()

        if not pattern:
            if candidates:
                print("\n  Candidates found in raw text:")
                for j, c in enumerate(candidates, 1):
                    print(f"    [{j}] {c}")
                choice = input("  Choose [1-5] or type your own pattern: ").strip()
                try:
                    idx = int(choice) - 1
                    pattern = candidates[idx] if 0 <= idx < len(candidates) else choice.lower()
                except ValueError:
                    pattern = choice.lower()
            else:
                pattern = input("  No candidates found. Type pattern manually: ").strip().lower()

        if not pattern:
            print("  Pattern cannot be empty — skipping.\n")
            return

        print(f"\n  Pattern confirmed: '{pattern}'")
        category = input("  Category (e.g. Food, Shopping, Bills): ").strip()
        if not category:
            print("  Category cannot be empty — skipping.\n")
            return

        sub_category = input("  Sub-category [Enter to skip]: ").strip()
        priority_raw = input("  Priority [0]: ").strip()
        try:
            priority = int(priority_raw) if priority_raw else 0
        except ValueError:
            priority = 0

    except (KeyboardInterrupt, EOFError):
        print("\n  Cancelled.\n")
        return

    MappingRepository().upsert(pattern, clean_name, category, sub_category, priority)
    print(f"\n  Saved: '{pattern}' → '{clean_name}' ({category} / {sub_category or '—'})")
    print("  Run 'apply' afterwards to update existing transactions.\n")


def cmd_clean_existing():
    """
    Re-run merchant name cleaning on all existing rows in expenses and credits.
    - Merchants containing '@' (VPAs) are passed through clean_vpa()
    - Everything else is passed through clean_merchant_name()
    - If cleaning returns None (garbage / sentence fragment) the merchant is set to NULL
    """
    db = SessionLocal()
    try:
        cleaned_count = 0
        nulled_count  = 0
        unchanged     = 0

        for label, model in [("expenses", Expense), ("credits", Credit)]:
            rows = db.query(model).filter(model.merchant != None).all()
            for row in rows:
                original = row.merchant or ""
                if not original:
                    continue

                if '@' in original:
                    result = clean_vpa(original)
                else:
                    result = clean_merchant_name(original)

                if result == original:
                    unchanged += 1
                    continue

                if result is None:
                    print(f"  [NULL]    {label}: {original!r}")
                    nulled_count += 1
                else:
                    print(f"  [CLEAN]   {label}: {original!r}  →  {result!r}")
                    cleaned_count += 1

                row.merchant = result

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        return
    finally:
        db.close()

    print(f"\nDone — cleaned: {cleaned_count}, set to NULL: {nulled_count}, unchanged: {unchanged}")
    if cleaned_count or nulled_count:
        print("Run 'apply' next to fill in proper merchant names from mappings.")


def cmd_import(csv_path: Path):
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    repo    = MappingRepository()
    added   = 0
    skipped = 0
    errors  = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(filter(lambda l: not l.startswith("#"), f)):
            pattern = row.get("raw_pattern", "").strip().lower()
            clean   = row.get("clean_name",  "").strip()
            cat     = row.get("category",    "").strip()
            sub     = row.get("sub_category","").strip()
            pri_raw = row.get("priority",    "0").strip()

            if not pattern or not clean or not cat:
                print(f"  [SKIP] missing required field — {row}")
                skipped += 1
                continue

            try:
                priority = int(pri_raw)
            except ValueError:
                print(f"  [SKIP] invalid priority '{pri_raw}' for pattern '{pattern}'")
                skipped += 1
                continue

            try:
                repo.upsert(pattern, clean, cat, sub, priority)
                print(f"  [OK]   {pattern:<30} → {clean} ({cat} / {sub})")
                added += 1
            except Exception as e:
                print(f"  [ERR]  {pattern}: {e}")
                errors += 1

    print(f"\nImport complete — added/updated: {added}, skipped: {skipped}, errors: {errors}")
    if added:
        print("Run 'apply' to update existing transactions with the new mappings.")


def cmd_apply():
    repo     = MappingRepository()
    mappings = repo.get_all_sorted()

    if not mappings:
        print("No mappings to apply.")
        return

    print(f"\nApplying {len(mappings)} mapping(s) to expenses and credits tables...")

    db = SessionLocal()
    try:
        result = apply_mappings_to_db(mappings, db)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        return
    finally:
        db.close()

    for d in result["details"]:
        if d["expenses"] or d["credits"]:
            print(f"  {d['pattern']:<30}  expenses: {d['expenses']:>4}  credits: {d['credits']:>4}")

    print(f"\nTotal updated — expenses: {result['total_expenses']}, credits: {result['total_credits']}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Manage merchant mappings for expense categorization"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.add_parser("quality",        help="Show data quality report")
    subparsers.add_parser("list",           help="List all mappings")
    subparsers.add_parser("add",            help="Add or update a mapping interactively")
    subparsers.add_parser("delete",         help="Delete a mapping interactively")
    subparsers.add_parser("apply",          help="Bulk-apply all mappings to expenses and credits")
    subparsers.add_parser("clean-existing", help="Re-run merchant cleaning on all existing DB rows")

    p_review = subparsers.add_parser(
        "review", help="Interactively view raw text for rows with unknown merchant or Other category"
    )
    p_review.add_argument(
        "--table", choices=["expenses", "credits", "both"], default="both",
        help="Which table to review (default: both)"
    )
    p_review.add_argument(
        "--issue", choices=["merchant", "category", "both"], default="both",
        help="Filter by issue type (default: both)"
    )

    p_import = subparsers.add_parser("import", help="Import mappings from a CSV file")
    p_import.add_argument(
        "file", nargs="?", default=str(_DEFAULT_CSV),
        help=f"Path to CSV file (default: {_DEFAULT_CSV})"
    )

    args = parser.parse_args()

    dispatch = {
        "quality":        cmd_quality,
        "list":           cmd_list,
        "add":            cmd_add,
        "delete":         cmd_delete,
        "apply":          cmd_apply,
        "clean-existing": cmd_clean_existing,
    }

    if args.command == "import":
        cmd_import(Path(args.file))
    elif args.command == "review":
        cmd_review(table=args.table, issue=args.issue)
    elif args.command in dispatch:
        dispatch[args.command]()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
