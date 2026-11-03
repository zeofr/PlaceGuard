"""Unit tests for the vector store (traditional RAG retrieval layer)."""

import pytest

from database.vector_store import PlacementVectorStore


class TestVectorStore:
    @pytest.fixture
    def vector_store(self, tmp_path):
        return PlacementVectorStore(
            persist_directory=str(tmp_path / "test_chroma"),
            embedding_model="all-MiniLM-L6-v2",
        )

    def test_add_notice(self, vector_store):
        vector_store.add_notice(
            notice_id="test_001",
            text="CGPA 7.5 required for CSE branch",
            metadata={"drive_id": "TEST_DRIVE", "authority_rank": 2},
        )

        assert vector_store.count_notices() == 1

    def test_search_similar(self, vector_store):
        vector_store.add_notice(
            "test_001", "CGPA 7.5 required", {"drive_id": "TEST", "authority_rank": 1}
        )
        vector_store.add_notice(
            "test_002", "CGPA 8.0 required", {"drive_id": "TEST", "authority_rank": 1}
        )

        results = vector_store.search_similar("CGPA requirement", n_results=2)

        assert len(results) == 2
        assert all("id" in r for r in results)

    def test_search_empty_store_returns_no_results(self, vector_store):
        results = vector_store.search_similar("anything", n_results=5)
        assert results == []

    def test_search_filters_by_drive_id(self, vector_store):
        vector_store.add_notice(
            "a1", "CGPA 7.5 requirement", {"drive_id": "DRIVE_A", "authority_rank": 1}
        )
        vector_store.add_notice(
            "b1", "CGPA 7.5 requirement", {"drive_id": "DRIVE_B", "authority_rank": 1}
        )

        results = vector_store.search_similar(
            "CGPA requirement", n_results=5, drive_id="DRIVE_A"
        )

        assert len(results) == 1
        assert results[0]["id"] == "a1"

    def test_delete_notice(self, vector_store):
        vector_store.add_notice(
            "del_001", "Backlogs must be zero", {"drive_id": "TEST", "authority_rank": 1}
        )
        assert vector_store.count_notices() == 1

        vector_store.delete_notice("del_001")
        assert vector_store.count_notices() == 0

    def test_reset_clears_collection(self, vector_store):
        vector_store.add_notice(
            "r1", "Branch restricted to CSE", {"drive_id": "TEST", "authority_rank": 1}
        )
        vector_store.reset()
        assert vector_store.count_notices() == 0
