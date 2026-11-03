#!/usr/bin/env python3
"""Periodic sync to ensure the vector store matches the SQL database.

Usage (from project root):
    python scripts/sync_vector_store.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db
from database.connection import get_db_context
from database.models import Fact
from database.vector_indexing import index_fact_to_vector_store
from database.vector_store import get_vector_store


def sync_vector_store() -> None:
    """Sync the vector store with the SQL database."""
    init_db()
    vector_store = get_vector_store()

    with get_db_context() as db:
        sql_source_ids = {f.source_id for f in db.query(Fact.source_id).all()}

        all_notices = vector_store.collection.get()
        vector_source_ids = set(all_notices["ids"])

        missing_in_vector = sql_source_ids - vector_source_ids

        if missing_in_vector:
            print(f"Found {len(missing_in_vector)} facts missing in vector store")
            print("Indexing missing facts...")

            for source_id in missing_in_vector:
                fact = db.query(Fact).filter(Fact.source_id == source_id).first()
                if fact:
                    index_fact_to_vector_store(fact)

            print("Sync complete")
        else:
            print("Vector store is in sync")


if __name__ == "__main__":
    sync_vector_store()
