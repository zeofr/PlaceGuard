"""Quick script to check timestamps in the Facts table."""

from database.connection import get_db_context
from database.models import Fact

with get_db_context() as db:
    facts = db.query(Fact).filter(
        Fact.drive_id == 'DRIVE_JPMORGANCHASE'
    ).order_by(Fact.timestamp.desc()).limit(10).all()
    
    print("=" * 80)
    print("JPMorganChase Facts (newest first):")
    print("=" * 80)
    
    for f in facts:
        print(f"{f.timestamp} | {f.criterion_type:20} = {f.value:30} | {f.source_id}")
    
    print("\n" + "=" * 80)
    print("Reconciliation check:")
    print("=" * 80)
    
    from reconciliation.temporal_provenance_engine import reconcile_facts
    
    reconciled = reconcile_facts(facts)
    
    for key, fact in reconciled.items():
        print(f"{key}: {fact.value} (from {fact.source_id} at {fact.timestamp})")
