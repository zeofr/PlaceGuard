"""Utilities for indexing Facts into the vector store."""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from database.models import Fact
from database.vector_store import get_vector_store


def _fact_text_and_metadata(fact: Fact) -> tuple[str, dict]:
    text = fact.raw_notice_text or f"{fact.criterion_type}: {fact.value}"
    metadata = {
        "drive_id": fact.drive_id,
        "source_type": fact.source_type,
        "authority_rank": fact.authority_rank,
        "timestamp": fact.timestamp.isoformat(),
        "criterion_type": fact.criterion_type,
    }
    return text, metadata


def index_fact_to_vector_store(fact: Fact) -> None:
    """Index a single fact into the vector store.

    Args:
        fact: Fact ORM object to index
    """
    vector_store = get_vector_store()
    text, metadata = _fact_text_and_metadata(fact)
    vector_store.add_notice(notice_id=fact.source_id, text=text, metadata=metadata)


def index_facts_batch(facts: List[Fact], batch_size: int = 32) -> None:
    """Batch index facts for better performance.

    Args:
        facts: List of Fact objects
        batch_size: Number of facts per batch
    """
    vector_store = get_vector_store()

    # Deduplicate by source_id (one notice can produce several facts/criteria).
    facts_by_source = {}
    for fact in facts:
        facts_by_source.setdefault(fact.source_id, fact)

    notice_ids: List[str] = []
    texts: List[str] = []
    metadatas: List[dict] = []

    for fact in facts_by_source.values():
        text, metadata = _fact_text_and_metadata(fact)
        notice_ids.append(fact.source_id)
        texts.append(text)
        metadatas.append(metadata)

        if len(notice_ids) >= batch_size:
            vector_store.add_notices_batch(notice_ids, texts, metadatas)
            notice_ids, texts, metadatas = [], [], []

    if notice_ids:
        vector_store.add_notices_batch(notice_ids, texts, metadatas)


def reindex_all_facts(db: Session, batch_size: int = 50) -> int:
    """Reindex all facts from the SQL database into the vector store.

    Args:
        db: Database session
        batch_size: Batch size for indexing

    Returns:
        Number of unique notices indexed
    """
    vector_store = get_vector_store()

    print("Resetting vector store...")
    vector_store.reset()

    print("Fetching facts from the SQL database...")
    facts = db.query(Fact).all()
    print(f"Found {len(facts)} facts to index")

    print("Indexing to vector store...")
    index_facts_batch(facts, batch_size=batch_size)

    indexed_count = vector_store.count_notices()
    print(f"Indexed {indexed_count} unique notices")

    return indexed_count
