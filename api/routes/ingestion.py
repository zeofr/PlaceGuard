"""Ingestion routes for notice processing."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.schemas import SourceType
from database.connection import get_db
from database.crud import create_drive, get_drive
from extraction.llm_client import get_llm_client
from extraction.notice_extractor import extract_criteria_from_notice
from reconciliation.temporal_provenance_engine import reconcile_facts_for_drive

router = APIRouter(prefix="/ingest", tags=["ingestion"])


# ============================================================================
# Mock WhatsApp Integration
# ============================================================================

class ProcessWhatsAppResponse(BaseModel):
    """Response from processing mock WhatsApp messages."""
    
    success: bool
    messages_processed: int
    total_facts_extracted: int
    drives_updated: list[str]
    details: list[dict]


class IngestNoticeRequest(BaseModel):
    """Request to ingest a placement notice."""
    
    notice_text: str
    source_id: str
    source_type: SourceType
    timestamp: datetime | None = None
    drive_id: str
    drive_name: str | None = None


class IngestNoticeResponse(BaseModel):
    """Response from notice ingestion."""
    
    success: bool
    drive_id: str
    facts_extracted: int
    criteria_reconciled: int
    message: str


@router.post("/notice", response_model=IngestNoticeResponse)
async def ingest_notice(
    request: IngestNoticeRequest,
    db: Session = Depends(get_db),
):
    """Ingest a placement notice and extract criteria.
    
    This endpoint:
    1. Creates drive if it doesn't exist
    2. Extracts criteria from notice text using LLM
    3. Stores facts in database
    4. Runs reconciliation to update current criteria
    
    Args:
        request: Notice ingestion request
        db: Database session
    
    Returns:
        Ingestion result with counts
    """
    try:
        # Ensure drive exists
        drive = get_drive(db, request.drive_id)
        if not drive:
            drive_name = request.drive_name or request.drive_id
            drive = create_drive(
                db,
                drive_id=request.drive_id,
                company_name=drive_name,
            )
        
        # Use current time if not provided
        timestamp = request.timestamp or datetime.now(UTC).replace(tzinfo=None)
        
        # Extract criteria from notice
        llm_client = get_llm_client()
        facts = extract_criteria_from_notice(
            notice_text=request.notice_text,
            source_id=request.source_id,
            source_type=request.source_type,
            timestamp=timestamp,
            drive_id=request.drive_id,
            llm_client=llm_client,
        )
        
        # Store facts in database
        for fact in facts:
            db.add(fact)
        db.commit()
        
        # Run reconciliation to update current criteria
        reconciled = reconcile_facts_for_drive(db, request.drive_id, persist=True)
        
        return IngestNoticeResponse(
            success=True,
            drive_id=request.drive_id,
            facts_extracted=len(facts),
            criteria_reconciled=len(reconciled),
            message=f"Successfully ingested notice and extracted {len(facts)} facts, reconciled to {len(reconciled)} current criteria",
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest notice: {str(e)}",
        )


@router.post("/process-whatsapp", response_model=ProcessWhatsAppResponse)
async def process_whatsapp_messages(
    whatsapp_url: str = "http://localhost:8001",
    db: Session = Depends(get_db),
):
    """Process all pending mock WhatsApp messages.
    
    This endpoint:
    1. Fetches messages from the mock WhatsApp console API
    2. Uses LLM to identify which company/drive each message refers to
    3. Extracts criteria from each message
    4. Creates facts in the database
    5. Runs reconciliation for affected drives
    
    Args:
        whatsapp_url: URL of the mock WhatsApp console (default: http://localhost:8001)
    
    Returns:
        Processing result with counts and details
    """
    try:
        import requests
        from core.schemas import RawMessage
        
        # Fetch messages from WhatsApp console
        try:
            response = requests.get(f"{whatsapp_url}/messages", timeout=5)
            response.raise_for_status()
            messages_data = response.json()
            messages = [RawMessage(**msg) for msg in messages_data]
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=503,
                detail=f"Cannot connect to WhatsApp console at {whatsapp_url}: {str(e)}. "
                       f"Start it with: uvicorn ingestion.mock_whatsapp.console:app --reload --port 8001"
            )
        
        if not messages:
            return ProcessWhatsAppResponse(
                success=True,
                messages_processed=0,
                total_facts_extracted=0,
                drives_updated=[],
                details=[],
            )
        
        llm_client = get_llm_client()
        total_facts = 0
        drives_affected = set()
        processing_details = []
        
        for msg in messages:
            try:
                # First, use LLM to identify which drive this message refers to
                drive_id, company_name = _identify_drive_from_message(msg.body, llm_client, db)
                
                if not drive_id:
                    # Could not identify drive - skip this message
                    processing_details.append({
                        "message_id": msg.message_id,
                        "body": msg.body[:100] + "..." if len(msg.body) > 100 else msg.body,
                        "status": "skipped",
                        "reason": "Could not identify company/drive from message",
                    })
                    continue
                
                # Ensure drive exists
                drive = get_drive(db, drive_id)
                if not drive:
                    drive = create_drive(
                        db,
                        drive_id=drive_id,
                        company_name=company_name,
                    )
                
                # Extract criteria from message
                facts = extract_criteria_from_notice(
                    notice_text=msg.body,
                    source_id=msg.message_id,
                    source_type=msg.source_type,
                    timestamp=msg.timestamp.replace(tzinfo=None),
                    drive_id=drive_id,
                    llm_client=llm_client,
                )
                
                # Store facts
                for fact in facts:
                    db.add(fact)
                db.commit()
                
                total_facts += len(facts)
                drives_affected.add(drive_id)
                
                processing_details.append({
                    "message_id": msg.message_id,
                    "drive_id": drive_id,
                    "company_name": company_name,
                    "source_type": msg.source_type.value,
                    "facts_extracted": len(facts),
                    "status": "success",
                    "body_preview": msg.body[:100] + "..." if len(msg.body) > 100 else msg.body,
                })
                
            except Exception as e:
                processing_details.append({
                    "message_id": msg.message_id,
                    "body": msg.body[:100] + "..." if len(msg.body) > 100 else msg.body,
                    "status": "error",
                    "error": str(e),
                })
        
        # Run reconciliation for all affected drives
        for drive_id in drives_affected:
            reconcile_facts_for_drive(db, drive_id, persist=True)
        
        return ProcessWhatsAppResponse(
            success=True,
            messages_processed=len(messages),
            total_facts_extracted=total_facts,
            drives_updated=list(drives_affected),
            details=processing_details,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process WhatsApp messages: {str(e)}",
        )


def _identify_drive_from_message(message_text: str, llm_client, db: Session) -> tuple[str | None, str | None]:
    """Use LLM to identify which company/drive a WhatsApp message refers to.
    
    Args:
        message_text: The WhatsApp message text
        llm_client: LLM client for extraction
        db: Database session
        
    Returns:
        Tuple of (drive_id, company_name) or (None, None) if not identifiable
    """
    # Get list of existing drives to help LLM match
    from database.models import Drive
    existing_drives = db.query(Drive).all()
    
    drives_context = "\n".join([
        f"- {d.drive_id}: {d.company_name}"
        for d in existing_drives
    ])
    
    prompt = f"""Analyze this WhatsApp message and identify which company/placement drive it refers to.

Message:
{message_text}

Existing companies/drives in the system:
{drives_context}

Task:
1. Identify the company name mentioned in the message (could be abbreviated, e.g., "TechM" for "Tech Mahindra")
2. Match it to an existing drive if possible, or provide the full company name if it's new
3. Generate a drive_id in the format: DRIVE_<COMPANY_NAME_UPPERCASE> (e.g., DRIVE_TECHMAHINDRA)

Return JSON with:
{{
  "drive_id": "DRIVE_XXX",
  "company_name": "Full Company Name",
  "confidence": "high/medium/low"
}}

If you cannot identify a company from the message, return:
{{
  "drive_id": null,
  "company_name": null,
  "confidence": "none"
}}
"""
    
    try:
        result = llm_client.generate_structured(prompt, temperature=0.0)
        
        if result.get("confidence") == "none" or not result.get("drive_id"):
            return None, None
        
        return result["drive_id"], result["company_name"]
        
    except Exception:
        # If LLM fails, return None
        return None, None
