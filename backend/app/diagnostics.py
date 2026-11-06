import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import engine
from app.discovery.lifecycle import (
    compute_database_diagnostics,
    reconcile_event_lifecycle,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("diagnostics")


def print_diagnostics(report: dict):
    print("\n" + "=" * 60)
    print(" TAMIL EVENT DISCOVERY — DATABASE DIAGNOSTIC REPORT")
    print("=" * 60)
    print(f"Total events:                              {report['total_events']}")
    print(f"Published events:                          {report['published_events']}")
    print(f"Expired events:                            {report['expired_events']}")
    print(f"Cancelled events:                          {report['cancelled_events']}")
    print(f"Future events:                             {report['future_events']}")
    print(f"Ongoing events:                            {report['ongoing_events']}")
    print(f"Past events still published:               {report['past_events_still_published']}")
    print(f"Events missing end_date:                   {report['events_missing_end_date']}")
    print(f"Events with end_date < start_date:         {report['events_end_date_earlier_than_start']}")
    print(f"Events with reg deadline > start_date:     {report['events_registration_deadline_after_start']}")
    print(f"Events with inconsistent/naive timezone:   {report['events_inconsistent_timezone']}")
    print("=" * 60 + "\n")


def print_reconciliation(result: dict):
    mode = "APPLIED" if result["applied"] else "DRY-RUN (No database changes saved)"
    corrections = result["corrections"]
    print("\n" + "=" * 70)
    print(f" LIFECYCLE RECONCILIATION REPORT — [{mode}]")
    print(f" Evaluated: {result['total_events']} events | Proposed corrections: {len(corrections)}")
    print("=" * 70)

    if not corrections:
        print("All events are in their correct lifecycle states. No corrections needed.")
    else:
        for c in corrections:
            print(f"• Event #{c['event_id']}: '{c['title'][:55]}'")
            print(f"  Old Status:    {c['old_status']} (is_published={c['old_is_published']})")
            print(f"  New Lifecycle: {c['new_status']} (is_published={c['new_is_published']})")
            print(f"  Start:         {c['start_date']}")
            print(f"  End:           {c['end_date']}")
            print(f"  Effective End: {c['effective_end']}")
            print(f"  Reason:        {c['reason']}")
            print("-" * 50)
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Tamil Event Discovery Diagnostics & Reconciliation CLI")
    parser.add_argument("--report", action="store_true", help="Print database diagnostics counts")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry-run lifecycle reconciliation")
    parser.add_argument("--apply", action="store_true", help="Apply proposed lifecycle corrections safely")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")

    args = parser.parse_args()

    # Default to report + dry-run if no args specified
    show_report = args.report or (not args.dry_run and not args.apply)
    do_dry_run = args.dry_run or (not args.apply)
    do_apply = args.apply

    with Session(engine) as db:
        if show_report:
            diag = compute_database_diagnostics(db)
            if args.json:
                print(json.dumps(diag, indent=2))
            else:
                print_diagnostics(diag)

        if do_dry_run or do_apply:
            reconcile_result = reconcile_event_lifecycle(
                db,
                dry_run=not do_apply,
                preserve_manual_cancellations=True,
            )
            if args.json:
                print(json.dumps(reconcile_result, indent=2))
            else:
                print_reconciliation(reconcile_result)


if __name__ == "__main__":
    main()

