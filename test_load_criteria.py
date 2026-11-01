"""Manual notice processing for testing without LLM API key."""
import json
from datetime import datetime
from database import crud, init_db
from database.connection import get_db_context

# Initialize database
init_db()

# Load notices
with open("data/synthetic_notices.json", "r", encoding="utf-8") as f:
    notices = json.load(f)

# Manually define criteria for TechCorp (based on notice text)
techcorp_criteria = [
    {
        "drive_id": "DRIVE_TECHCORP",
        "criterion_type": "min_cgpa",
        "operator": "gte",
        "value": "7.5",
        "source_id": "msg_techcorp_001",
        "source_type": "placement_cell_whatsapp",
        "authority_rank": 2,
        "timestamp": datetime.fromisoformat("2026-10-26T09:00:00"),
    },
    {
        "drive_id": "DRIVE_TECHCORP",
        "criterion_type": "allowed_branches",
        "operator": "in",
        "value": json.dumps(["CSE", "ISE"]),
        "source_id": "msg_techcorp_001",
        "source_type": "placement_cell_whatsapp",
        "authority_rank": 2,
        "timestamp": datetime.fromisoformat("2026-10-26T09:00:00"),
    },
    {
        "drive_id": "DRIVE_TECHCORP",
        "criterion_type": "max_backlogs",
        "operator": "eq",
        "value": "0",
        "source_id": "msg_techcorp_001",
        "source_type": "placement_cell_whatsapp",
        "authority_rank": 2,
        "timestamp": datetime.fromisoformat("2026-10-26T09:00:00"),
    },
    # Correction: CGPA revised to 7.0
    {
        "drive_id": "DRIVE_TECHCORP",
        "criterion_type": "min_cgpa",
        "operator": "gte",
        "value": "7.0",
        "source_id": "msg_techcorp_002",
        "source_type": "placement_cell_whatsapp",
        "authority_rank": 2,
        "timestamp": datetime.fromisoformat("2026-10-26T11:30:00"),
    },
]

with get_db_context() as db:
    for criterion in techcorp_criteria:
        crud.upsert_extracted_criterion(db, **criterion)
    print(f"✓ Loaded {len(techcorp_criteria)} criteria for DRIVE_TECHCORP")
    
    # Check what we have
    criteria = crud.get_extracted_criteria_for_drive(db, "DRIVE_TECHCORP")
    print(f"\n✓ Current criteria for DRIVE_TECHCORP:")
    for c in criteria:
        print(f"  - {c.criterion_type}: {c.value} (from {c.source_id})")

print("\nNow you can test eligibility checking!")
