#!/usr/bin/env python3
"""Load email + WhatsApp notices through the real LLM extraction pipeline.

Replaces the old hardcoded-criteria stand-in (data/load_manual_criteria.py,
now removed): now that local Ollama extraction is fast and reliable enough to
run during seeding, this makes the seeded demo data indistinguishable from
what live ingestion produces -- same Fact rows, same branch-delta merging,
same reconciliation, same registration_link/deadline/etc. extraction -- for
every notice in data/notices.json and data/whatsapp_messages.json.

Safe to re-run: each source_id is skipped if its Facts already exist (the
Facts table is append-only, same guarantee real ingestion gives).

Usage (from project root):
    python data/load_notices_via_llm.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from api.routes.ingestion import _merge_branch_delta_facts
from core.schemas import SourceType
from database import init_db
from database.connection import get_db_context
from database.crud import create_drive, get_drive, get_fact_by_source
from database.vector_indexing import reindex_all_facts
from extraction.llm_client import get_llm_client
from extraction.notice_extractor import extract_with_confidence
from reconciliation.temporal_provenance_engine import reconcile_facts_for_drive

DATA_DIR = Path(__file__).parent
NOTICES_FILE = DATA_DIR / "notices.json"
WHATSAPP_FILE = DATA_DIR / "whatsapp_messages.json"


def _load_sources() -> list[dict[str, Any]]:
    """Merge notices.json + whatsapp_messages.json into one chronological list.

    Chronological order matters: branch "add"/"remove" deltas and reconciliation
    both need to see each drive's prior state in the order it actually happened,
    exactly like live ingestion processing messages as they arrive.
    """
    notices = json.loads(NOTICES_FILE.read_text(encoding="utf-8"))
    whatsapp = (
        json.loads(WHATSAPP_FILE.read_text(encoding="utf-8")) if WHATSAPP_FILE.exists() else []
    )
    items = notices + whatsapp
    items.sort(key=lambda i: i["timestamp"])
    return items


def load_notices_via_llm(db) -> dict[str, Any]:
    llm_client = get_llm_client()
    items = _load_sources()

    stats = {"total": len(items), "processed": 0, "skipped": 0, "facts": 0, "drives": set()}

    for i, item in enumerate(items, 1):
        source_id = item["source_id"]
        drive_id = item["drive_id"]

        if get_fact_by_source(db, source_id):
            stats["skipped"] += 1
            print(f"  [{i}/{len(items)}] skip  {source_id} (already ingested)")
            continue

        if not get_drive(db, drive_id):
            create_drive(db, drive_id=drive_id, company_name=item["company"])

        facts, low_confidence_items = extract_with_confidence(
            notice_text=item["text"],
            source_id=source_id,
            source_type=SourceType(item["source_type"]),
            timestamp=date_parser.parse(item["timestamp"]),
            drive_id=drive_id,
            llm_client=llm_client,
        )
        _merge_branch_delta_facts(db, facts)

        for fact in facts:
            db.add(fact)
        db.commit()

        reconcile_facts_for_drive(db, drive_id, persist=True)

        stats["processed"] += 1
        stats["facts"] += len(facts)
        stats["drives"].add(drive_id)

        note = f" ({len(low_confidence_items)} low-confidence held back)" if low_confidence_items else ""
        print(f"  [{i}/{len(items)}] done  {drive_id:<22} {source_id:<35} {len(facts)} fact(s){note}")

    stats["drives"] = sorted(stats["drives"])
    return stats


def main() -> None:
    print("=" * 70)
    print("LOADING NOTICES VIA REAL LLM EXTRACTION")
    print("=" * 70)
    print()
    print("Initialising database …")
    init_db()
    print()

    with get_db_context() as db:
        stats = load_notices_via_llm(db)
        print()
        print(f"  Processed : {stats['processed']}")
        print(f"  Skipped   : {stats['skipped']} (already ingested)")
        print(f"  Facts     : {stats['facts']}")
        print(f"  Drives    : {len(stats['drives'])}")
        print()

        print("Indexing extracted facts into the vector store …")
        indexed = reindex_all_facts(db)
        print(f"  ✓ Indexed {indexed} notice(s)")

    print()
    print("=" * 70)
    print("✅ NOTICES LOADED VIA LLM EXTRACTION")
    print("=" * 70)


if __name__ == "__main__":
    main()
