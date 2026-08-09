import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.repository import SmsStagingRepository, MappingRepository

_STATUSES = ("pending", "approved", "rejected", "duplicate")


def cmd_stats():
    counts = SmsStagingRepository().count_by_status()
    print()
    print(f"{'='*40}")
    print("  SMS STAGING — STATUS COUNTS")
    print(f"{'='*40}")
    for status in _STATUSES:
        print(f"  {status:<12}: {counts.get(status, 0)}")
    total = sum(counts.values())
    print(f"  {'TOTAL':<12}: {total}")
    print()


def cmd_list(status: str = "pending"):
    if status not in _STATUSES:
        print(f"Unknown status '{status}'. Choose from: {', '.join(_STATUSES)}")
        return

    rows = SmsStagingRepository().get_by_status(status, limit=50)
    if not rows:
        print(f"\nNo rows with status '{status}'.")
        return

    print(f"\n{'='*80}")
    print(f"  SMS STAGING — {status.upper()} ({len(rows)} shown, max 50)")
    print(f"{'='*80}")
    print(f"  {'ID':>5}  {'RECEIVED':<12}  {'BANK':<8}  {'AMOUNT':>10}  {'MERCHANT':<22}  {'TYPE'}")
    print(f"  {'-'*5}  {'-'*12}  {'-'*8}  {'-'*10}  {'-'*22}  {'-'*6}")
    for r in rows:
        date_str   = str(r.received_at)[:10] if r.received_at else "—"
        amount_str = f"₹{r.parsed_amount}" if r.parsed_amount else "—"
        print(
            f"  {r.id:>5}  {date_str:<12}  {(r.parsed_bank or '—'):<8}  "
            f"{amount_str:>10}  {(r.parsed_merchant or '—'):<22}  {r.txn_type or '—'}"
        )
    print()


def cmd_review():
    repo     = SmsStagingRepository()
    mappings = MappingRepository().get_all_sorted()
    rows     = repo.get_by_status("pending", limit=200)

    if not rows:
        print("\nNo pending SMS rows. Run stats to check other statuses.")
        return

    total = len(rows)
    print(f"\nFound {total} pending SMS row(s).")
    print("Controls: [Enter]/[a] approve   [r] reject   [s] skip   [q] quit\n")

    for i, row in enumerate(rows):
        print("─" * 60)
        print(f"[{i+1}/{total}]  id={row.id}  |  {str(row.received_at)[:16]}  |  sender: {row.sender}")
        print(f"  bank     : {row.parsed_bank or '—'}")
        print(f"  merchant : {row.parsed_merchant or '—'}")
        print(f"  amount   : {'₹' + str(row.parsed_amount) if row.parsed_amount else '—'}")
        print(f"  type     : {row.txn_type or '—'}")
        print(f"  date     : {row.parsed_date or '—'}")
        if row.duplicate_of:
            print(f"  ⚠ duplicate of: {row.duplicate_of}")
        print(f"\n  raw SMS  :")
        for line in (row.raw_sms or "").strip().splitlines():
            line = line.strip()
            if line:
                print(f"    {line}")
        print()

        try:
            cmd = input("[Enter]/[a] approve   [r] reject   [s] skip   [q] quit: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if cmd == "q":
            break
        elif cmd in ("", "a"):
            result = repo.approve(row.id, mappings)
            if result:
                print(f"  ✓ Approved → {result.get('merchant')} ₹{result.get('amount')} [{result.get('category')}]\n")
            else:
                print("  ✗ Could not approve (already processed or missing amount).\n")
        elif cmd == "r":
            repo.reject(row.id)
            print("  Rejected.\n")
        # 's' or anything else → skip

    print("\nReview complete.")


def cmd_approve(row_id: int):
    mappings = MappingRepository().get_all_sorted()
    result   = SmsStagingRepository().approve(row_id, mappings)
    if result:
        print(f"Approved id={row_id} → {result.get('merchant')} ₹{result.get('amount')} [{result.get('category')}]")
    else:
        print(f"Could not approve id={row_id} — not found, not pending, or missing amount/date.")


def cmd_reject(row_id: int):
    ok = SmsStagingRepository().reject(row_id)
    print(f"Rejected id={row_id}." if ok else f"Could not reject id={row_id} — not found or not pending.")


def main():
    parser = argparse.ArgumentParser(description="Manage SMS staging table")
    sub    = parser.add_subparsers(dest="command", metavar="COMMAND")

    sub.add_parser("stats",  help="Count rows by status")
    sub.add_parser("review", help="Interactive review of pending rows")

    p_list = sub.add_parser("list", help="List rows by status")
    p_list.add_argument(
        "--status", choices=_STATUSES, default="pending",
        help="Status to filter (default: pending)"
    )

    p_approve = sub.add_parser("approve", help="Approve a staged row by ID")
    p_approve.add_argument("id", type=int, help="Row ID to approve")

    p_reject = sub.add_parser("reject", help="Reject a staged row by ID")
    p_reject.add_argument("id", type=int, help="Row ID to reject")

    args = parser.parse_args()

    if args.command == "stats":
        cmd_stats()
    elif args.command == "review":
        cmd_review()
    elif args.command == "list":
        cmd_list(args.status)
    elif args.command == "approve":
        cmd_approve(args.id)
    elif args.command == "reject":
        cmd_reject(args.id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
