#!/usr/bin/env python3
"""Migrate existing facts into the vector store.

Run once to populate the vector store with facts already in the SQL
database. Safe to re-run — it resets the collection before reindexing.

Usage (from project root):
    python scripts/migrate_to_vector_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db
from database.connection import get_db_context
from database.vector_indexing import reindex_all_facts


def main() -> None:
    print("=" * 70)
    print("PLACEGUARD: MIGRATE TO VECTOR STORE")
    print("=" * 70)
    print()

    print("This will:")
    print("   1. Reset the vector store (delete all existing vectors)")
    print("   2. Index all facts from the SQL database into ChromaDB")
    print("   3. May take a minute or two depending on data volume")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Migration cancelled.")
        return

    print()
    init_db()

    with get_db_context() as db:
        indexed_count = reindex_all_facts(db, batch_size=50)

    print()
    print("=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)
    print(f"   Indexed {indexed_count} unique notices")
    print()
    print("Next steps:")
    print("   1. Test vector search: python scripts/test_vector_search.py")
    print("   2. Compare with SQL: python scripts/compare_rag_vs_sql.py")
    print("   3. Confirm vector_store_enabled=true in .env (default is on)")
    print()


if __name__ == "__main__":
    main()
