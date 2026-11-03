#!/usr/bin/env python3
"""Smoke-test vector search functionality.

Usage (from project root):
    python scripts/test_vector_search.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.vector_store import get_vector_store


def main() -> None:
    print("=" * 70)
    print("VECTOR SEARCH TEST")
    print("=" * 70)
    print()

    vector_store = get_vector_store()

    count = vector_store.count_notices()
    print(f"Total notices indexed: {count}")
    print()

    if count == 0:
        print("No notices indexed yet. Run scripts/migrate_to_vector_db.py first.")
        return

    print("Test: Searching for 'CGPA 7.5 requirement'")
    results = vector_store.search_similar(query="CGPA 7.5 requirement", n_results=5)

    print(f"Found {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['id']}")
        print(f"   Distance: {result.get('distance', 'N/A')}")
        print(f"   Drive: {result['metadata'].get('drive_id')}")
        print(f"   Source: {result['metadata'].get('source_type')}")
        print(f"   Authority: {result['metadata'].get('authority_rank')}")
        print(f"   Text: {result['text'][:100]}...")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
