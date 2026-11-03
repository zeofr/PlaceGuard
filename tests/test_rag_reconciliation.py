"""Integration tests for RAG-assisted reconciliation.

Verifies that vector-assisted retrieval never changes the reconciled
outcome versus pure SQL reconciliation -- the deterministic authority +
temporal logic in reconcile_facts() remains the sole decision-maker.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import crud
from database.models import Base, Fact
from database.vector_store import PlacementVectorStore
from reconciliation import rag_reconciliation as rag_module
from reconciliation.rag_reconciliation import reconcile_facts_for_drive_rag
from reconciliation.temporal_provenance_engine import reconcile_facts_for_drive


@pytest.fixture(scope="function")
def test_db() -> Session:
    """In-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def fake_vector_store(tmp_path, monkeypatch):
    """A real, isolated ChromaDB instance, substituted for the singleton."""
    store = PlacementVectorStore(persist_directory=str(tmp_path / "chroma"))
    monkeypatch.setattr(rag_module, "get_vector_store", lambda: store)
    return store


def _seed_facts(db: Session, drive_id: str = "DRIVE_TEST") -> None:
    crud.insert_fact(
        db,
        source_id="official_pdf_001",
        source_type="placement_cell_pdf",
        authority_rank=1,
        timestamp=datetime(2026, 1, 1, 9, 0, 0),
        drive_id=drive_id,
        criterion_type="min_cgpa",
        operator="gte",
        value='"7.5"',
        raw_notice_text="Minimum CGPA 7.5 required for all branches.",
    )
    crud.insert_fact(
        db,
        source_id="whatsapp_forward_002",
        source_type="whatsapp_student",
        authority_rank=5,
        timestamp=datetime(2026, 1, 1, 10, 0, 0),
        drive_id=drive_id,
        criterion_type="max_backlogs",
        operator="eq",
        value='"0"',
        raw_notice_text="No active backlogs allowed, forwarded by a student.",
    )
    db.commit()


class TestRagMatchesSql:
    def test_rag_disabled_matches_sql_exactly(self, test_db, fake_vector_store):
        """use_rag=False must behave identically to the plain SQL path."""
        _seed_facts(test_db)

        sql_result = reconcile_facts_for_drive(test_db, "DRIVE_TEST", persist=False)
        rag_result = reconcile_facts_for_drive_rag(
            test_db, "DRIVE_TEST", persist=False, use_rag=False
        )

        assert sql_result.keys() == rag_result.keys()
        for key in sql_result:
            assert sql_result[key].source_id == rag_result[key].source_id
            assert sql_result[key].value == rag_result[key].value

    def test_rag_enabled_with_populated_index_matches_sql(self, test_db, fake_vector_store):
        """When the vector index is fully populated, RAG must match SQL."""
        _seed_facts(test_db)

        for fact in crud.get_facts_by_drive(test_db, "DRIVE_TEST"):
            fake_vector_store.add_notice(
                notice_id=fact.source_id,
                text=fact.raw_notice_text,
                metadata={
                    "drive_id": fact.drive_id,
                    "source_type": fact.source_type,
                    "authority_rank": fact.authority_rank,
                    "timestamp": fact.timestamp,
                },
            )

        sql_result = reconcile_facts_for_drive(test_db, "DRIVE_TEST", persist=False)
        rag_result = reconcile_facts_for_drive_rag(
            test_db, "DRIVE_TEST", persist=False, use_rag=True
        )

        assert sql_result.keys() == rag_result.keys()
        for key in sql_result:
            assert sql_result[key].value == rag_result[key].value


class TestRagSafetyNet:
    def test_high_authority_fact_never_dropped_when_vector_search_misses_it(
        self, test_db, fake_vector_store
    ):
        """A rank-1 official fact must survive even if vector search doesn't surface it.

        The vector index is deliberately left empty, which emulates a vector
        search that misses every fact for this drive.
        """
        _seed_facts(test_db)

        rag_result = reconcile_facts_for_drive_rag(
            test_db, "DRIVE_TEST", persist=False, use_rag=True
        )
        sql_result = reconcile_facts_for_drive(test_db, "DRIVE_TEST", persist=False)

        # Safety net: an empty/partial vector index falls back to full SQL facts.
        assert rag_result.keys() == sql_result.keys()
        for key in sql_result:
            assert rag_result[key].source_id == sql_result[key].source_id

    def test_vector_search_failure_falls_back_to_sql(self, test_db, monkeypatch, fake_vector_store):
        """If vector search raises, reconciliation must still succeed via SQL."""
        _seed_facts(test_db)

        def _boom(*args, **kwargs):
            raise RuntimeError("vector backend unavailable")

        monkeypatch.setattr(fake_vector_store, "search_similar", _boom)

        rag_result = reconcile_facts_for_drive_rag(
            test_db, "DRIVE_TEST", persist=False, use_rag=True
        )
        sql_result = reconcile_facts_for_drive(test_db, "DRIVE_TEST", persist=False)

        assert rag_result.keys() == sql_result.keys()
