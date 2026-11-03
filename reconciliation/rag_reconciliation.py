"""RAG-based reconciliation using vector similarity + authority ranking.

Combines semantic search (vector DB) with the existing deterministic
authority + temporal reconciliation logic (SQL). The vector store only
narrows which facts are *considered* -- it never decides which fact wins.
That decision stays entirely inside reconcile_facts(), exactly as before
this module existed, so the ELIGIBLE/INELIGIBLE/UNKNOWN decision boundary
in rules/eligibility_engine.py is unaffected by this layer.
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from database.crud import get_facts_by_drive, upsert_extracted_criterion
from database.models import Fact
from database.vector_store import get_vector_store
from reconciliation.temporal_provenance_engine import (
    RuleKey,
    get_reconciliation_trace,
    reconcile_facts,
)


class RAGReconciliationEngine:
    """Hybrid reconciliation: vector search + SQL safety net + authority logic."""

    def __init__(self):
        self.vector_store = get_vector_store()

    def reconcile_with_rag(
        self,
        db: Session,
        drive_id: str,
        use_semantic_search: bool = True,
        top_k: int = 20,
    ) -> Dict[RuleKey, Fact]:
        """Reconcile facts for a drive using a RAG-assisted retrieval strategy.

        Strategy:
        1. Vector search for semantically similar notices (top-K)
        2. SQL retrieval for ALL facts (safety net)
        3. Merge: keep facts found by vector search, plus every high-authority
           fact regardless of whether vector search surfaced it
        4. Apply the unchanged deterministic authority + temporal logic

        Args:
            db: Database session
            drive_id: Drive to reconcile
            use_semantic_search: Whether to use vector search at all
            top_k: Number of results to pull from vector search

        Returns:
            Dict mapping RuleKey to the authoritative Fact
        """
        sql_facts = get_facts_by_drive(db, drive_id)

        if not use_semantic_search:
            return reconcile_facts(sql_facts)

        try:
            vector_results = self.vector_store.search_similar(
                query=f"eligibility criteria requirements for {drive_id}",
                n_results=top_k,
                drive_id=drive_id,
            )
        except Exception as e:
            # Vector search is retrieval-assist only; any failure here must
            # never block reconciliation. Fall back to the full SQL set.
            print(f"Warning: vector search failed for {drive_id}: {e}")
            return reconcile_facts(sql_facts)

        vector_notice_ids = {result["id"] for result in vector_results}

        # Keep anything vector search found, plus every high-authority fact
        # (rank <= 2) so an official source can never be dropped by retrieval.
        rag_facts = [
            fact
            for fact in sql_facts
            if fact.source_id in vector_notice_ids or fact.authority_rank <= 2
        ]

        if len(rag_facts) < len(sql_facts):
            missing_count = len(sql_facts) - len(rag_facts)
            print(
                f"Warning: vector search missed {missing_count} facts for "
                f"{drive_id}. Including all facts from SQL to ensure correctness."
            )
            rag_facts = sql_facts

        return reconcile_facts(rag_facts)

    def explain_rag_retrieval(
        self,
        db: Session,
        drive_id: str,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """Generate a detailed explanation of the RAG retrieval process.

        Useful for debugging and auditing what was retrieved for a drive.
        """
        vector_results = self.vector_store.search_similar(
            query=f"eligibility criteria for {drive_id}",
            n_results=top_k,
            drive_id=drive_id,
        )

        sql_facts = get_facts_by_drive(db, drive_id)
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
                        "id": r["id"],
                        "distance": r.get("distance"),
                        "authority_rank": r["metadata"].get("authority_rank"),
                        "source_type": r["metadata"].get("source_type"),
                        "snippet": r["text"][:200] + "...",
                    }
                    for r in vector_results
                ],
            },
            "sql_retrieval": {
                "total_facts": len(sql_facts),
                "by_source": {
                    source_type: len(
                        [f for f in sql_facts if f.source_type == source_type]
                    )
                    for source_type in {f.source_type for f in sql_facts}
                },
            },
            "reconciliation": trace,
            "final_criteria_count": len(reconciled),
        }


def reconcile_facts_for_drive_rag(
    db: Session,
    drive_id: str,
    persist: bool = True,
    use_rag: bool = True,
) -> Dict[RuleKey, Fact]:
    """Drop-in, RAG-assisted replacement for reconcile_facts_for_drive().

    Args:
        db: Database session
        drive_id: Drive to reconcile
        persist: Whether to save results to the extracted_criteria table
        use_rag: Whether to use vector-assisted retrieval (False = pure SQL)

    Returns:
        Reconciled facts dict, identical in shape to reconcile_facts_for_drive()
    """
    engine = RAGReconciliationEngine()
    reconciled = engine.reconcile_with_rag(db, drive_id, use_semantic_search=use_rag)

    if persist:
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
