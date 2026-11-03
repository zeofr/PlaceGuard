#!/usr/bin/env python3
"""Compare RAG-assisted reconciliation vs pure SQL reconciliation.

Verifies the architectural guarantee that vector-assisted retrieval never
changes the reconciled outcome: the deterministic authority + temporal
logic in reconcile_facts() is the only thing that picks a winning fact.

Usage (from project root):
    python scripts/compare_rag_vs_sql.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db
from database.connection import get_db_context
from database.crud import get_drive
from reconciliation.rag_reconciliation import reconcile_facts_for_drive_rag
from reconciliation.temporal_provenance_engine import reconcile_facts_for_drive


def compare_reconciliation(drive_id: str) -> None:
    """Compare SQL vs RAG reconciliation for a drive."""
    print(f"\n{'=' * 70}")
    print(f"Comparing: {drive_id}")
    print(f"{'=' * 70}\n")

    with get_db_context() as db:
        if not get_drive(db, drive_id):
            print(f"   Skipped — drive {drive_id} not found in the SQL database.")
            return

        print("1. SQL-only reconciliation:")
        sql_result = reconcile_facts_for_drive(db, drive_id, persist=False)
        print(f"   Criteria: {len(sql_result)}")
        for key, fact in list(sql_result.items())[:3]:
            print(f"   - {key}: {fact.value} (rank {fact.authority_rank})")

        print()

        print("2. RAG-assisted reconciliation:")
        rag_result = reconcile_facts_for_drive_rag(
            db, drive_id, persist=False, use_rag=True
        )
        print(f"   Criteria: {len(rag_result)}")
        for key, fact in list(rag_result.items())[:3]:
            print(f"   - {key}: {fact.value} (rank {fact.authority_rank})")

        print()

        print("3. Comparison:")
        if sql_result.keys() == rag_result.keys():
            print("   Same criteria keys")

            mismatches = [
                key for key in sql_result if sql_result[key].value != rag_result[key].value
            ]

            if mismatches:
                print(f"   {len(mismatches)} value mismatches:")
                for key in mismatches:
                    print(f"      {key}:")
                    print(f"         SQL: {sql_result[key].value}")
                    print(f"         RAG: {rag_result[key].value}")
            else:
                print("   All values match")
        else:
            print("   Different criteria keys!")
            sql_only = sql_result.keys() - rag_result.keys()
            rag_only = rag_result.keys() - sql_result.keys()

            if sql_only:
                print(f"   SQL-only keys: {sql_only}")
            if rag_only:
                print(f"   RAG-only keys: {rag_only}")


def main() -> None:
    print("=" * 70)
    print("RAG VS SQL RECONCILIATION COMPARISON")
    print("=" * 70)

    init_db()

    with get_db_context() as db:
        from database.models import Drive

        drive_ids = [row.drive_id for row in db.query(Drive.drive_id).all()]

    if not drive_ids:
        print("\nNo drives found in the SQL database — nothing to compare.")
        return

    for drive_id in drive_ids:
        compare_reconciliation(drive_id)

    print("\n" + "=" * 70)
    print("COMPARISON COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
