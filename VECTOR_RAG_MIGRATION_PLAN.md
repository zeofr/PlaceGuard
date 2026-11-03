# Traditional RAG + Vector Database Implementation Plan

## Overview

This document specifies all changes needed to migrate PlaceGuard from SQL-based retrieval to traditional RAG with vector database (ChromaDB/FAISS).

**Branch Name:** `feature/vector-rag`

**Goal:** Implement semantic search-based retrieval while maintaining deterministic decision-making.

---

## Table of Contents

1. [Dependencies & Infrastructure](#1-dependencies--infrastructure)
2. [New Modules & Files](#2-new-modules--files)
3. [Modified Existing Files](#3-modified-existing-files)
4. [Database Schema Changes](#4-database-schema-changes)
5. [Configuration Updates](#5-configuration-updates)
6. [Migration Scripts](#6-migration-scripts)
7. [Testing Strategy](#7-testing-strategy)
8. [Deployment Checklist](#8-deployment-checklist)

---

## 1. Dependencies & Infrastructure

### 1.1 Update `requirements.txt`

**Add these lines:**

```python
# Vector Database & Embeddings
chromadb>=0.4.22                    # Primary vector store
# ALTERNATIVE: faiss-cpu>=1.7.4    # If using FAISS instead

# Embedding Models
sentence-transformers>=2.3.0        # For generating embeddings
transformers>=4.35.0                # Required by sentence-transformers

# LangChain Vector Store Integration
langchain-community>=0.3.0          # Vector store integrations
langchain-chroma>=0.1.0             # ChromaDB integration

# Additional utilities
tiktoken>=0.5.0                     # Token counting for embeddings
```

### 1.2 Infrastructure Requirements

**New Services Needed:**

1. **ChromaDB Server** (if using client-server mode)
   - Docker image: `chromadb/chroma:latest`
   - Port: 8001 (default)
   - Persistent volume: `./data/chroma_db`

2. **Embedding Model Storage**
   - Location: `./models/embeddings/`
   - Model: `all-MiniLM-L6-v2` (384 dimensions, 80MB)
   - Alternative: `all-mpnet-base-v2` (768 dimensions, 420MB, better quality)

3. **Additional RAM Requirements**
   - Embedding model: ~500MB-2GB
   - Vector index: ~100MB per 10k documents

---

## 2. New Modules & Files

### 2.1 Vector Store Module

**File:** `database/vector_store.py`

```python
"""Vector store management for PlaceGuard RAG system.

Provides semantic search over placement notices using ChromaDB.
"""

from __future__ import annotations

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class PlacementVectorStore:
    """ChromaDB-based vector store for semantic search over notices.
    
    Handles:
    - Notice embedding and indexing
    - Semantic similarity search
    - Metadata filtering (drive_id, source_type, date range)
    - Batch operations for performance
    """
    
    def __init__(
        self, 
        persist_directory: str = "./data/chroma_db",
        embedding_model: str = "all-MiniLM-L6-v2",
        collection_name: str = "placement_notices"
    ):
        """Initialize vector store with ChromaDB client.
        
        Args:
            persist_directory: Path for persistent storage
            embedding_model: SentenceTransformer model name
            collection_name: ChromaDB collection name
        """
        # Initialize ChromaDB client
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False,
            allow_reset=True
        ))
        
        # Initialize embedding function
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={
                "hnsw:space": "cosine",  # Cosine similarity
                "hnsw:construction_ef": 100,
                "hnsw:M": 16
            }
        )
        
        self.embedder = SentenceTransformer(embedding_model)
    
    def add_notice(
        self, 
        notice_id: str, 
        text: str, 
        metadata: Dict[str, Any]
    ) -> None:
        """Add single notice to vector store.
        
        Args:
            notice_id: Unique identifier (e.g., "email_kpmg_001")
            text: Notice text content
            metadata: Dictionary with drive_id, source_type, timestamp, authority_rank
        """
        # Ensure timestamp is string
        if 'timestamp' in metadata and isinstance(metadata['timestamp'], datetime):
            metadata['timestamp'] = metadata['timestamp'].isoformat()
        
        self.collection.add(
            ids=[notice_id],
            documents=[text],
            metadatas=[metadata]
        )
    
    def add_notices_batch(
        self, 
        notice_ids: List[str], 
        texts: List[str], 
        metadatas: List[Dict[str, Any]]
    ) -> None:
        """Batch add notices for better performance.
        
        Args:
            notice_ids: List of unique identifiers
            texts: List of notice texts
            metadatas: List of metadata dicts
        """
        # Process timestamps
        for metadata in metadatas:
            if 'timestamp' in metadata and isinstance(metadata['timestamp'], datetime):
                metadata['timestamp'] = metadata['timestamp'].isoformat()
        
        self.collection.add(
            ids=notice_ids,
            documents=texts,
            metadatas=metadatas
        )
    
    def search_similar(
        self,
        query: str,
        n_results: int = 10,
        drive_id: Optional[str] = None,
        source_types: Optional[List[str]] = None,
        min_authority_rank: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Semantic search for similar notices with filtering.
        
        Args:
            query: Search query text
            n_results: Maximum number of results
            drive_id: Filter by specific drive
            source_types: Filter by source types (e.g., ["placement_cell_email"])
            min_authority_rank: Only return notices with rank <= this value
            date_from: Filter notices after this date
            date_to: Filter notices before this date
            
        Returns:
            List of dicts with id, text, metadata, distance
        """
        # Build where filter
        where_filter = {}
        if drive_id:
            where_filter["drive_id"] = drive_id
        
        if source_types:
            where_filter["source_type"] = {"$in": source_types}
        
        if min_authority_rank:
            where_filter["authority_rank"] = {"$lte": min_authority_rank}
        
        # Perform search
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter if where_filter else None
        )
        
        # Format results
        formatted_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "id": results['ids'][0][i],
                    "text": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if results.get('distances') else None
                })
        
        return formatted_results
    
    def get_by_drive(self, drive_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve all notices for a specific drive.
        
        Args:
            drive_id: Drive identifier
            limit: Maximum results
            
        Returns:
            List of notice dicts
        """
        results = self.collection.get(
            where={"drive_id": drive_id},
            limit=limit
        )
        
        formatted_results = []
        if results['ids']:
            for i in range(len(results['ids'])):
                formatted_results.append({
                    "id": results['ids'][i],
                    "text": results['documents'][i],
                    "metadata": results['metadatas'][i]
                })
        
        return formatted_results
    
    def update_notice(
        self, 
        notice_id: str, 
        text: Optional[str] = None, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update existing notice.
        
        Args:
            notice_id: Notice to update
            text: New text (if updating)
            metadata: New metadata (if updating)
        """
        update_args = {"ids": [notice_id]}
        
        if text:
            update_args["documents"] = [text]
        
        if metadata:
            if 'timestamp' in metadata and isinstance(metadata['timestamp'], datetime):
                metadata['timestamp'] = metadata['timestamp'].isoformat()
            update_args["metadatas"] = [metadata]
        
        self.collection.update(**update_args)
    
    def delete_notice(self, notice_id: str) -> None:
        """Delete notice from vector store.
        
        Args:
            notice_id: Notice to delete
        """
        self.collection.delete(ids=[notice_id])
    
    def count_notices(self) -> int:
        """Get total number of indexed notices."""
        return self.collection.count()
    
    def reset(self) -> None:
        """Delete all notices (use with caution!)."""
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            embedding_function=self.embedding_fn
        )


# Singleton instance
_vector_store: Optional[PlacementVectorStore] = None


def get_vector_store() -> PlacementVectorStore:
    """Get or create singleton vector store instance."""
    global _vector_store
    if _vector_store is None:
        from config import settings
        _vector_store = PlacementVectorStore(
            persist_directory=settings.VECTOR_STORE_PATH,
            embedding_model=settings.EMBEDDING_MODEL,
            collection_name="placement_notices"
        )
    return _vector_store
```

**Purpose:** Core vector store operations - embedding, indexing, semantic search.

---

### 2.2 RAG Reconciliation Module

**File:** `reconciliation/rag_reconciliation.py`

```python
"""RAG-based reconciliation using vector similarity + authority ranking.

Combines semantic search (vector DB) with deterministic authority logic (SQL).
"""

from __future__ import annotations

from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from database.vector_store import get_vector_store
from database.crud import get_facts_by_drive
from database.models import Fact
from reconciliation.temporal_provenance_engine import (
    reconcile_facts,
    RuleKey,
    get_reconciliation_trace
)


class RAGReconciliationEngine:
    """Hybrid reconciliation: Vector search + SQL verification + Authority logic."""
    
    def __init__(self):
        self.vector_store = get_vector_store()
    
    def reconcile_with_rag(
        self,
        db: Session,
        drive_id: str,
        use_semantic_search: bool = True,
        top_k: int = 20
    ) -> Dict[RuleKey, Fact]:
        """Reconcile facts using RAG approach.
        
        Strategy:
        1. Vector search for semantically similar notices (top-K)
        2. SQL retrieval for ALL facts (safety net)
        3. Merge both sets (union)
        4. Apply authority + temporal logic
        
        Args:
            db: Database session
            drive_id: Drive to reconcile
            use_semantic_search: Whether to use vector search
            top_k: Number of results from vector search
            
        Returns:
            Dict mapping RuleKey to authoritative Fact
        """
        # Step 1: Get all facts from SQL (baseline - always complete)
        sql_facts = get_facts_by_drive(db, drive_id)
        
        if not use_semantic_search:
            # Fallback to pure SQL approach
            return reconcile_facts(sql_facts)
        
        # Step 2: Vector search for semantically related notices
        vector_results = self.vector_store.search_similar(
            query=f"eligibility criteria requirements for {drive_id}",
            n_results=top_k,
            drive_id=drive_id
        )
        
        # Step 3: Get notice IDs from vector search
        vector_notice_ids = {result['id'] for result in vector_results}
        
        # Step 4: Filter SQL facts to those found by vector search
        # BUT include ALL high-authority facts regardless (safety)
        rag_facts = [
            fact for fact in sql_facts
            if fact.source_id in vector_notice_ids or fact.authority_rank <= 2
        ]
        
        # Step 5: Ensure we didn't miss anything critical
        # If vector search returned fewer facts than SQL, log warning
        if len(rag_facts) < len(sql_facts):
            missing_count = len(sql_facts) - len(rag_facts)
            print(f"Warning: Vector search missed {missing_count} facts for {drive_id}")
            print(f"Including all facts from SQL to ensure correctness.")
            rag_facts = sql_facts  # Safety: use all facts
        
        # Step 6: Apply deterministic reconciliation (unchanged)
        reconciled = reconcile_facts(rag_facts)
        
        return reconciled
    
    def explain_rag_retrieval(
        self,
        db: Session,
        drive_id: str,
        top_k: int = 10
    ) -> Dict[str, any]:
        """Generate detailed explanation of RAG retrieval process.
        
        Useful for debugging and understanding what was retrieved.
        
        Returns:
            Dict with vector_results, sql_results, reconciliation_trace
        """
        # Vector search results
        vector_results = self.vector_store.search_similar(
            query=f"eligibility criteria for {drive_id}",
            n_results=top_k,
            drive_id=drive_id
        )
        
        # SQL results
        sql_facts = get_facts_by_drive(db, drive_id)
        
        # Reconciliation trace
        reconciled = reconcile_facts(sql_facts)
        trace = get_reconciliation_trace(sql_facts)
        
        return {
            "drive_id": drive_id,
            "vector_search": {
                "query": f"eligibility criteria for {drive_id}",
                "top_k": top_k,
                "results_count": len(vector_results),
                "results": [
                    {
                        "id": r['id'],
                        "distance": r.get('distance'),
                        "authority_rank": r['metadata'].get('authority_rank'),
                        "source_type": r['metadata'].get('source_type'),
                        "snippet": r['text'][:200] + "..."
                    }
                    for r in vector_results
                ]
            },
            "sql_retrieval": {
                "total_facts": len(sql_facts),
                "by_source": {
                    source_type: len([f for f in sql_facts if f.source_type == source_type])
                    for source_type in set(f.source_type for f in sql_facts)
                }
            },
            "reconciliation": trace,
            "final_criteria_count": len(reconciled)
        }


def reconcile_facts_for_drive_rag(
    db: Session,
    drive_id: str,
    persist: bool = True,
    use_rag: bool = True
) -> Dict[RuleKey, Fact]:
    """Drop-in replacement for reconcile_facts_for_drive with RAG support.
    
    Args:
        db: Database session
        drive_id: Drive to reconcile
        persist: Whether to save to extracted_criteria table
        use_rag: Whether to use RAG (False = fallback to SQL)
        
    Returns:
        Reconciled facts dict
    """
    engine = RAGReconciliationEngine()
    reconciled = engine.reconcile_with_rag(db, drive_id, use_semantic_search=use_rag)
    
    if persist:
        from database.crud import upsert_extracted_criterion
        for rule_key, fact in reconciled.items():
            upsert_extracted_criterion(
                db=db,
                drive_id=fact.drive_id,
                criterion_type=fact.criterion_type,
                operator=fact.operator,
                value=fact.value,
                source_id=fact.source_id,
                source_type=fact.source_type,
                authority_rank=fact.authority_rank,
                timestamp=fact.timestamp,
                scope=fact.scope,
            )
    
    return reconciled
```

**Purpose:** Hybrid reconciliation combining vector search with SQL safety net.

---

### 2.3 Vector Indexing Utilities

**File:** `database/vector_indexing.py`

```python
"""Utilities for indexing facts into vector store."""

from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session
from tqdm import tqdm

from database.models import Fact
from database.vector_store import get_vector_store


def index_fact_to_vector_store(fact: Fact) -> None:
    """Index single fact into vector store.
    
    Args:
        fact: Fact ORM object to index
    """
    vector_store = get_vector_store()
    
    # Use raw_notice_text if available, otherwise reconstruct from criterion
    text = fact.raw_notice_text or f"{fact.criterion_type}: {fact.value}"
    
    metadata = {
        "drive_id": fact.drive_id,
        "source_type": fact.source_type,
        "authority_rank": fact.authority_rank,
        "timestamp": fact.timestamp.isoformat(),
        "criterion_type": fact.criterion_type
    }
    
    vector_store.add_notice(
        notice_id=fact.source_id,
        text=text,
        metadata=metadata
    )


def index_facts_batch(facts: List[Fact], batch_size: int = 32) -> None:
    """Batch index facts for better performance.
    
    Args:
        facts: List of Fact objects
        batch_size: Number of facts per batch
    """
    vector_store = get_vector_store()
    
    # Group facts by source_id to avoid duplicates
    facts_by_source = {}
    for fact in facts:
        if fact.source_id not in facts_by_source:
            facts_by_source[fact.source_id] = fact
    
    # Prepare batch data
    notice_ids = []
    texts = []
    metadatas = []
    
    for fact in tqdm(facts_by_source.values(), desc="Preparing batch"):
        text = fact.raw_notice_text or f"{fact.criterion_type}: {fact.value}"
        
        metadata = {
            "drive_id": fact.drive_id,
            "source_type": fact.source_type,
            "authority_rank": fact.authority_rank,
            "timestamp": fact.timestamp.isoformat(),
            "criterion_type": fact.criterion_type
        }
        
        notice_ids.append(fact.source_id)
        texts.append(text)
        metadatas.append(metadata)
        
        # Index in batches
        if len(notice_ids) >= batch_size:
            vector_store.add_notices_batch(notice_ids, texts, metadatas)
            notice_ids, texts, metadatas = [], [], []
    
    # Index remaining
    if notice_ids:
        vector_store.add_notices_batch(notice_ids, texts, metadatas)


def reindex_all_facts(db: Session, batch_size: int = 50) -> int:
    """Reindex all facts from database into vector store.
    
    Args:
        db: Database session
        batch_size: Batch size for indexing
        
    Returns:
        Number of facts indexed
    """
    vector_store = get_vector_store()
    
    # Reset vector store
    print("Resetting vector store...")
    vector_store.reset()
    
    # Get all facts
    print("Fetching facts from database...")
    facts = db.query(Fact).all()
    print(f"Found {len(facts)} facts to index")
    
    # Batch index
    print("Indexing to vector store...")
    index_facts_batch(facts, batch_size=batch_size)
    
    indexed_count = vector_store.count_notices()
    print(f"✅ Indexed {indexed_count} unique notices")
    
    return indexed_count
```

**Purpose:** Batch indexing and reindexing of facts into vector store.

---

### 2.4 Configuration Module Updates

**File:** `config.py`

Add these settings:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Vector Store Settings
    VECTOR_STORE_ENABLED: bool = True
    VECTOR_STORE_TYPE: str = "chromadb"  # or "faiss"
    VECTOR_STORE_PATH: str = "./data/chroma_db"
    
    # Embedding Settings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    # Alternative: "all-mpnet-base-v2" for better quality
    EMBEDDING_DIMENSION: int = 384  # 384 for MiniLM, 768 for mpnet
    EMBEDDING_BATCH_SIZE: int = 32
    
    # RAG Settings
    RAG_TOP_K: int = 20  # Number of results from vector search
    RAG_SIMILARITY_THRESHOLD: float = 0.7  # Minimum similarity score
    RAG_FALLBACK_TO_SQL: bool = True  # Always use SQL as safety net
    
    class Config:
        env_file = ".env"
```

---

### 2.5 Migration Scripts

**File:** `scripts/migrate_to_vector_db.py`

```python
#!/usr/bin/env python3
"""Migrate existing facts to vector database.

Run once to populate vector store with existing data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db
from database.connection import get_db_context
from database.vector_indexing import reindex_all_facts


def main():
    print("=" * 70)
    print("PLACEGUARD: MIGRATE TO VECTOR DATABASE")
    print("=" * 70)
    print()
    
    print("⚠️  This will:")
    print("   1. Reset the vector store (delete all existing vectors)")
    print("   2. Index all facts from PostgreSQL into ChromaDB")
    print("   3. May take several minutes for large datasets")
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
    print("✅ MIGRATION COMPLETE")
    print("=" * 70)
    print(f"   Indexed {indexed_count} unique notices")
    print()
    print("Next steps:")
    print("   1. Test vector search: python scripts/test_vector_search.py")
    print("   2. Compare with SQL: python scripts/compare_rag_vs_sql.py")
    print("   3. Update API to use RAG: Set RAG_ENABLED=true in .env")
    print()


if __name__ == "__main__":
    main()
```

**File:** `scripts/test_vector_search.py`

```python
#!/usr/bin/env python3
"""Test vector search functionality."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.vector_store import get_vector_store


def main():
    print("=" * 70)
    print("VECTOR SEARCH TEST")
    print("=" * 70)
    print()
    
    vector_store = get_vector_store()
    
    # Test 1: Count
    count = vector_store.count_notices()
    print(f"✅ Total notices indexed: {count}")
    print()
    
    # Test 2: Simple search
    print("Test: Searching for 'CGPA 7.5 requirement'")
    results = vector_store.search_similar(
        query="CGPA 7.5 requirement",
        n_results=5
    )
    
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
```

**File:** `scripts/compare_rag_vs_sql.py`

```python
#!/usr/bin/env python3
"""Compare RAG-based reconciliation vs SQL-only reconciliation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db
from database.connection import get_db_context
from database.crud import get_drive
from reconciliation.temporal_provenance_engine import reconcile_facts_for_drive
from reconciliation.rag_reconciliation import reconcile_facts_for_drive_rag


def compare_reconciliation(drive_id: str):
    """Compare SQL vs RAG reconciliation for a drive."""
    print(f"\n{'=' * 70}")
    print(f"Comparing: {drive_id}")
    print(f"{'=' * 70}\n")
    
    with get_db_context() as db:
        # SQL-only approach
        print("1. SQL-only reconciliation:")
        sql_result = reconcile_facts_for_drive(db, drive_id, persist=False)
        print(f"   Criteria: {len(sql_result)}")
        for key, fact in list(sql_result.items())[:3]:
            print(f"   - {key}: {fact.value} (rank {fact.authority_rank})")
        
        print()
        
        # RAG approach
        print("2. RAG-based reconciliation:")
        rag_result = reconcile_facts_for_drive_rag(db, drive_id, persist=False, use_rag=True)
        print(f"   Criteria: {len(rag_result)}")
        for key, fact in list(rag_result.items())[:3]:
            print(f"   - {key}: {fact.value} (rank {fact.authority_rank})")
        
        print()
        
        # Compare
        print("3. Comparison:")
        if sql_result.keys() == rag_result.keys():
            print("   ✅ Same criteria keys")
            
            # Check if values match
            mismatches = []
            for key in sql_result:
                if sql_result[key].value != rag_result[key].value:
                    mismatches.append(key)
            
            if mismatches:
                print(f"   ⚠️  {len(mismatches)} value mismatches:")
                for key in mismatches:
                    print(f"      {key}:")
                    print(f"         SQL: {sql_result[key].value}")
                    print(f"         RAG: {rag_result[key].value}")
            else:
                print("   ✅ All values match")
        else:
            print("   ❌ Different criteria keys!")
            sql_only = sql_result.keys() - rag_result.keys()
            rag_only = rag_result.keys() - sql_result.keys()
            
            if sql_only:
                print(f"   SQL-only keys: {sql_only}")
            if rag_only:
                print(f"   RAG-only keys: {rag_only}")


def main():
    print("=" * 70)
    print("RAG VS SQL RECONCILIATION COMPARISON")
    print("=" * 70)
    
    init_db()
    
    # Test drives
    test_drives = ["DRIVE_KPMG", "DRIVE_NVIDIA", "DRIVE_BOEING"]
    
    for drive_id in test_drives:
        compare_reconciliation(drive_id)
    
    print("\n" + "=" * 70)
    print("COMPARISON COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
```

---

## 3. Modified Existing Files

### 3.1 Ingestion Routes

**File:** `api/routes/ingestion.py`

**Changes:**

```python
# Add imports
from database.vector_store import get_vector_store
from database.vector_indexing import index_fact_to_vector_store

# Modify ingest_notice endpoint
@router.post("/notice", response_model=IngestNoticeResponse)
async def ingest_notice(request: IngestNoticeRequest, db: Session = Depends(get_db)):
    # ... existing extraction code ...
    
    # Store facts in database (existing)
    for fact in facts:
        db.add(fact)
    db.commit()
    
    # NEW: Index to vector store
    if settings.VECTOR_STORE_ENABLED:
        try:
            for fact in facts:
                index_fact_to_vector_store(fact)
        except Exception as e:
            # Log but don't fail ingestion
            print(f"Warning: Vector indexing failed: {e}")
    
    # ... rest of existing code ...
```

**Changes:** Add vector indexing after SQL storage (parallel operation).

---

### 3.2 Eligibility Routes

**File:** `api/routes/eligibility.py`

**Changes:**

```python
# Add imports
from reconciliation.rag_reconciliation import reconcile_facts_for_drive_rag
from config import settings

# Modify check_eligibility endpoint
@router.get("/eligibility/{usn}/{drive_id}")
async def check_eligibility(usn: str, drive_id: str, db: Session = Depends(get_db)):
    # ... existing student lookup ...
    
    # Use RAG or SQL based on config
    if settings.VECTOR_STORE_ENABLED:
        reconciled = reconcile_facts_for_drive_rag(
            db, drive_id, persist=False, use_rag=True
        )
    else:
        reconciled = reconcile_facts_for_drive(db, drive_id, persist=False)
    
    # ... rest remains unchanged ...
```

**Changes:** Add conditional RAG usage based on feature flag.

---

### 3.3 Portal/Email/WhatsApp Adapters

**File:** `ingestion/portal/adapter.py`, `ingestion/mock_email/adapter.py`

**Changes:**

No changes needed - vector indexing happens in ingestion endpoint, not adapters.

---

### 3.4 Database CRUD

**File:** `database/crud.py`

**Add new function:**

```python
def get_fact_by_source(db: Session, source_id: str) -> List[Fact]:
    """Get all facts from a specific source.
    
    Used to check if notice already processed.
    """
    return db.query(Fact).filter(Fact.source_id == source_id).all()
```

**Purpose:** Check if notice already indexed (prevent duplicates).

---

## 4. Database Schema Changes

### 4.1 PostgreSQL (No changes needed)

Existing `facts` table remains unchanged - vector store is parallel storage.

### 4.2 Vector Store Schema (ChromaDB)

**Collection:** `placement_notices`

**Fields:**
- `id`: Notice source_id (e.g., "email_kpmg_001")
- `embedding`: 384-dim or 768-dim vector
- `document`: Full notice text
- `metadata`:
  - `drive_id`: String
  - `source_type`: String
  - `authority_rank`: Integer
  - `timestamp`: ISO string
  - `criterion_type`: String (optional)

**Indexes:**
- HNSW index on embeddings (cosine similarity)
- B-tree index on metadata.drive_id
- B-tree index on metadata.authority_rank

---

## 5. Configuration Updates

### 5.1 Environment Variables

**Add to `.env`:**

```bash
# Vector Store Configuration
VECTOR_STORE_ENABLED=true
VECTOR_STORE_TYPE=chromadb
VECTOR_STORE_PATH=./data/chroma_db

# Embedding Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EMBEDDING_BATCH_SIZE=32

# RAG Configuration
RAG_TOP_K=20
RAG_SIMILARITY_THRESHOLD=0.7
RAG_FALLBACK_TO_SQL=true

# Performance Tuning
VECTOR_SEARCH_TIMEOUT=5000
EMBEDDING_CACHE_SIZE=1000
```

### 5.2 Docker Compose (Optional)

**File:** `docker-compose.yml` (if using containerized ChromaDB)

```yaml
version: '3.8'

services:
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - ./data/chroma_db:/chroma/chroma
    environment:
      - ALLOW_RESET=TRUE
      - ANONYMIZED_TELEMETRY=FALSE
```

---

## 6. Migration Scripts

### 6.1 Initial Migration

**Steps:**

1. Install dependencies: `pip install -r requirements.txt`
2. Download embedding model: `python scripts/download_embedding_model.py`
3. Initialize vector store: `python scripts/init_vector_store.py`
4. Migrate existing data: `python scripts/migrate_to_vector_db.py`
5. Test vector search: `python scripts/test_vector_search.py`
6. Compare RAG vs SQL: `python scripts/compare_rag_vs_sql.py`

### 6.2 Ongoing Sync

**File:** `scripts/sync_vector_store.py`

```python
#!/usr/bin/env python3
"""Periodic sync to ensure vector store matches SQL database."""

from database import init_db
from database.connection import get_db_context
from database.models import Fact
from database.vector_store import get_vector_store
from database.vector_indexing import index_fact_to_vector_store


def sync_vector_store():
    """Sync vector store with SQL database."""
    init_db()
    vector_store = get_vector_store()
    
    with get_db_context() as db:
        # Get all fact source IDs from SQL
        sql_source_ids = {f.source_id for f in db.query(Fact.source_id).all()}
        
        # Get all notice IDs from vector store
        all_notices = vector_store.collection.get()
        vector_source_ids = set(all_notices['ids'])
        
        # Find missing in vector store
        missing_in_vector = sql_source_ids - vector_source_ids
        
        if missing_in_vector:
            print(f"Found {len(missing_in_vector)} facts missing in vector store")
            print("Indexing missing facts...")
            
            for source_id in missing_in_vector:
                fact = db.query(Fact).filter(Fact.source_id == source_id).first()
                if fact:
                    index_fact_to_vector_store(fact)
            
            print("✅ Sync complete")
        else:
            print("✅ Vector store is in sync")


if __name__ == "__main__":
    sync_vector_store()
```

**Cron job:** Run daily at midnight
```bash
0 0 * * * cd /path/to/placeguard && python scripts/sync_vector_store.py
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

**File:** `tests/test_vector_store.py`

```python
"""Unit tests for vector store operations."""

import pytest
from database.vector_store import PlacementVectorStore


class TestVectorStore:
    @pytest.fixture
    def vector_store(self, tmp_path):
        return PlacementVectorStore(
            persist_directory=str(tmp_path / "test_chroma"),
            embedding_model="all-MiniLM-L6-v2"
        )
    
    def test_add_notice(self, vector_store):
        vector_store.add_notice(
            notice_id="test_001",
            text="CGPA 7.5 required for CSE branch",
            metadata={"drive_id": "TEST_DRIVE", "authority_rank": 2}
        )
        
        assert vector_store.count_notices() == 1
    
    def test_search_similar(self, vector_store):
        # Add test notices
        vector_store.add_notice("test_001", "CGPA 7.5", {"drive_id": "TEST"})
        vector_store.add_notice("test_002", "CGPA 8.0", {"drive_id": "TEST"})
        
        # Search
        results = vector_store.search_similar("CGPA requirement", n_results=2)
        
        assert len(results) == 2
        assert all('id' in r for r in results)
```

### 7.2 Integration Tests

**File:** `tests/test_rag_reconciliation.py`

```python
"""Integration tests for RAG-based reconciliation."""

import pytest
from reconciliation.rag_reconciliation import RAGReconciliationEngine


class TestRAGReconciliation:
    def test_rag_matches_sql(self, test_db):
        """RAG reconciliation should match SQL for complete data."""
        # Add test data...
        # Compare SQL vs RAG results
        # Assert they match
        pass
    
    def test_rag_safety_net(self, test_db):
        """RAG should fall back to SQL if vector search misses facts."""
        # Test scenario where vector search returns incomplete results
        # Assert high-authority facts still included
        pass
```

### 7.3 Performance Tests

**File:** `tests/test_performance.py`

```python
"""Performance benchmarks for SQL vs RAG."""

import time
from database.connection import get_db_context
from reconciliation.temporal_provenance_engine import reconcile_facts_for_drive
from reconciliation.rag_reconciliation import reconcile_facts_for_drive_rag


def benchmark_sql():
    with get_db_context() as db:
        start = time.time()
        reconcile_facts_for_drive(db, "DRIVE_KPMG", persist=False)
        end = time.time()
        return end - start


def benchmark_rag():
    with get_db_context() as db:
        start = time.time()
        reconcile_facts_for_drive_rag(db, "DRIVE_KPMG", persist=False)
        end = time.time()
        return end - start


def test_performance_comparison():
    sql_time = benchmark_sql()
    rag_time = benchmark_rag()
    
    print(f"SQL: {sql_time:.3f}s")
    print(f"RAG: {rag_time:.3f}s")
    print(f"Overhead: {((rag_time - sql_time) / sql_time * 100):.1f}%")
    
    # Assert RAG isn't more than 5x slower
    assert rag_time < sql_time * 5
```

---

## 8. Deployment Checklist

### 8.1 Pre-Deployment

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Download embedding model (will happen on first run)
- [ ] Create vector store directory: `mkdir -p data/chroma_db`
- [ ] Update `.env` with vector store settings
- [ ] Run migration script: `python scripts/migrate_to_vector_db.py`
- [ ] Run comparison tests: `python scripts/compare_rag_vs_sql.py`
- [ ] Verify accuracy: All test drives should match

### 8.2 Deployment

- [ ] Create git branch: `git checkout -b feature/vector-rag`
- [ ] Commit all changes
- [ ] Run full test suite: `pytest tests/`
- [ ] Performance benchmarks acceptable (< 5x overhead)
- [ ] Set `VECTOR_STORE_ENABLED=true` in production `.env`
- [ ] Deploy with zero-downtime (keep SQL as fallback)

### 8.3 Post-Deployment Monitoring

- [ ] Monitor vector store size growth
- [ ] Monitor search latency (should be < 200ms)
- [ ] Monitor sync failures (should be 0%)
- [ ] Monitor accuracy (compare RAG vs SQL daily)
- [ ] Set up alerts for sync failures

### 8.4 Rollback Plan

If issues detected:

1. Set `VECTOR_STORE_ENABLED=false` in `.env`
2. Restart API (falls back to SQL immediately)
3. Investigate vector store issues
4. Fix and re-migrate
5. Re-enable when validated

---

## 9. Success Criteria

### 9.1 Functional Requirements

- ✅ Vector search returns relevant notices
- ✅ RAG reconciliation matches SQL reconciliation (100% accuracy)
- ✅ High-authority facts never missed
- ✅ Fallback to SQL works if vector search fails

### 9.2 Performance Requirements

- ✅ Search latency < 200ms (p95)
- ✅ Indexing throughput > 10 notices/second
- ✅ Total overhead < 5x SQL-only approach

### 9.3 Reliability Requirements

- ✅ Sync failures < 1% of operations
- ✅ Graceful degradation to SQL on vector store failure
- ✅ No data loss during vector store operations

---

## 10. Timeline Estimate

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Setup** | 1 day | Install deps, create modules |
| **Development** | 3-4 days | Implement vector store, RAG reconciliation |
| **Migration** | 1 day | Write migration scripts, migrate data |
| **Testing** | 2-3 days | Unit tests, integration tests, performance tests |
| **Validation** | 2 days | Compare with SQL, validate accuracy |
| **Documentation** | 1 day | Update docs, create runbooks |
| **Total** | **10-12 days** | Full implementation and validation |

---

## 11. Risk Mitigation Summary

| Risk | Mitigation | Fallback |
|------|------------|----------|
| Vector search misses facts | Include all high-authority facts | Fall back to SQL |
| Sync failures | Daily sync script, monitoring | Manual reindex |
| Performance issues | Caching, batch operations | Disable RAG |
| Accuracy degradation | Compare with SQL daily | Roll back to SQL |

---

## 12. Future Enhancements (Not in Scope)

- Fine-tune embedding model on placement notices
- Multi-modal embeddings (text + metadata)
- Semantic caching for frequent queries
- Distributed vector store for horizontal scaling
- Real-time streaming updates to vector store

---

## Summary

This migration adds traditional RAG with vector database while maintaining PlaceGuard's core principle:

> **"GenAI extracts and explains. A deterministic rule engine decides."**

The vector store enhances **retrieval** through semantic search, but **decision-making** remains deterministic and auditable.

**Key Points:**
1. ✅ Vector store for semantic search
2. ✅ SQL as safety net (never miss facts)
3. ✅ Authority logic unchanged (deterministic)
4. ✅ Graceful fallback on failure
5. ✅ Backward compatible (feature flag)

**Implementation Time:** 10-12 days  
**Risk Level:** Medium (50%) with proper testing  
**Benefit:** Scalable to 1000+ companies while maintaining correctness
