"""Vector store management for PlaceGuard's traditional-RAG retrieval layer.

Provides semantic search over placement notices using ChromaDB. This module
is retrieval-only infrastructure: it never decides eligibility. The winning
fact for each rule key is still chosen by the deterministic authority +
temporal logic in reconciliation/temporal_provenance_engine.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions


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
        collection_name: str = "placement_notices",
    ):
        """Initialize vector store with an embedded, persistent ChromaDB client.

        Args:
            persist_directory: Path for persistent storage
            embedding_model: SentenceTransformer model name
            collection_name: ChromaDB collection name
        """
        self.client = chromadb.PersistentClient(path=persist_directory)

        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 100,
                "hnsw:M": 16,
            },
        )

    def add_notice(self, notice_id: str, text: str, metadata: Dict[str, Any]) -> None:
        """Add a single notice to the vector store.

        Args:
            notice_id: Unique identifier (e.g. a Fact.source_id)
            text: Notice text content
            metadata: Dict with drive_id, source_type, timestamp, authority_rank
        """
        metadata = _stringify_timestamps(metadata)
        self.collection.add(ids=[notice_id], documents=[text], metadatas=[metadata])

    def add_notices_batch(
        self,
        notice_ids: List[str],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Batch add notices for better performance."""
        metadatas = [_stringify_timestamps(m) for m in metadatas]
        self.collection.add(ids=notice_ids, documents=texts, metadatas=metadatas)

    def search_similar(
        self,
        query: str,
        n_results: int = 10,
        drive_id: Optional[str] = None,
        source_types: Optional[List[str]] = None,
        min_authority_rank: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search for similar notices with metadata filtering.

        Args:
            query: Search query text
            n_results: Maximum number of results
            drive_id: Filter by specific drive
            source_types: Filter by source types (e.g. ["placement_cell_email"])
            min_authority_rank: Only return notices with rank <= this value
            date_from: Filter notices after this date (reserved; not yet applied)
            date_to: Filter notices before this date (reserved; not yet applied)

        Returns:
            List of dicts with id, text, metadata, distance
        """
        where_filter: Dict[str, Any] = {}
        if drive_id:
            where_filter["drive_id"] = drive_id
        if source_types:
            where_filter["source_type"] = {"$in": source_types}
        if min_authority_rank is not None:
            where_filter["authority_rank"] = {"$lte": min_authority_rank}

        if self.count_notices() == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter if where_filter else None,
        )

        formatted_results = []
        if results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                formatted_results.append(
                    {
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i]
                        if results.get("distances")
                        else None,
                    }
                )

        return formatted_results

    def get_by_drive(self, drive_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve all notices for a specific drive."""
        results = self.collection.get(where={"drive_id": drive_id}, limit=limit)

        formatted_results = []
        if results["ids"]:
            for i in range(len(results["ids"])):
                formatted_results.append(
                    {
                        "id": results["ids"][i],
                        "text": results["documents"][i],
                        "metadata": results["metadatas"][i],
                    }
                )

        return formatted_results

    def update_notice(
        self,
        notice_id: str,
        text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update an existing notice's text and/or metadata."""
        update_args: Dict[str, Any] = {"ids": [notice_id]}

        if text:
            update_args["documents"] = [text]

        if metadata:
            update_args["metadatas"] = [_stringify_timestamps(metadata)]

        self.collection.update(**update_args)

    def delete_notice(self, notice_id: str) -> None:
        """Delete a notice from the vector store."""
        self.collection.delete(ids=[notice_id])

    def count_notices(self) -> int:
        """Get total number of indexed notices."""
        return self.collection.count()

    def reset(self) -> None:
        """Delete all notices (use with caution!)."""
        name = self.collection.name
        self.client.delete_collection(name)
        self.collection = self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embedding_fn,
        )


def _stringify_timestamps(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of metadata with any datetime values converted to ISO strings."""
    metadata = dict(metadata)
    if isinstance(metadata.get("timestamp"), datetime):
        metadata["timestamp"] = metadata["timestamp"].isoformat()
    return metadata


# Singleton instance
_vector_store: Optional[PlacementVectorStore] = None


def get_vector_store() -> PlacementVectorStore:
    """Get or create the singleton vector store instance."""
    global _vector_store
    if _vector_store is None:
        from config import settings

        _vector_store = PlacementVectorStore(
            persist_directory=settings.vector_store_path,
            embedding_model=settings.embedding_model,
            collection_name="placement_notices",
        )
    return _vector_store
