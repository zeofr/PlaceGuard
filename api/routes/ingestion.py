"""Ingestion routes for notice processing."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.schemas import SourceType
from database.connection import get_db
from database.crud import (
    create_drive,
    create_processed_email,
    get_drive,
    get_fact_by_source,
    is_email_processed,
)
from extraction.llm_client import get_llm_client
from extraction.notice_extractor import extract_criteria_from_notice
from ingestion.gmail.adapter import GmailAdapter, GmailAdapterError
from ingestion.gmail.auth import GmailAuthenticationError
from ingestion.gmail.classifier import EmailClassification, EmailClassifier
from ingestion.portal.adapter import PortalAdapter
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
                # Check if this message was already processed
                from database.crud import get_fact_by_source
                existing_facts = get_fact_by_source(db, msg.message_id)
                if existing_facts:
                    # Already processed - skip
                    processing_details.append({
                        "message_id": msg.message_id,
                        "body": msg.body[:100] + "..." if len(msg.body) > 100 else msg.body,
                        "status": "skipped",
                        "reason": f"Already processed ({len(existing_facts)} facts exist)",
                    })
                    continue
                
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


# ============================================================================
# Gmail Integration
# ============================================================================

class SyncGmailResponse(BaseModel):
    """Response from Gmail sync operation."""
    
    success: bool
    emails_fetched: int
    emails_classified: int
    emails_processed: int
    emails_skipped: int
    facts_extracted: int
    drives_affected: list[str]
    details: list[dict]
    errors: list[str]


@router.post("/sync-gmail", response_model=SyncGmailResponse)
async def sync_gmail(
    only_unread: bool = True,
    db: Session = Depends(get_db),
):
    """Sync emails from Gmail and process placement notices.
    
    This endpoint:
    1. Fetches emails from placement officer's Gmail
    2. Classifies emails using LLM (new_offer, offer_update, shortlist, other)
    3. For relevant emails (new_offer, offer_update):
       - Extracts eligibility criteria
       - Creates/updates drive
       - Stores facts in database
       - Runs reconciliation
       - Adds Gmail label "PlaceGuard/Processed"
    4. Tracks processed emails to prevent duplicates
    
    Args:
        only_unread: If True, only fetch unread emails (default: True)
        db: Database session
        
    Returns:
        Summary of sync operation with counts and details
    """
    errors = []
    details = []
    
    try:
        # Initialize Gmail adapter
        gmail_adapter = GmailAdapter()
        
        # Fetch emails
        try:
            messages = gmail_adapter.fetch(only_unread=only_unread)
        except (GmailAdapterError, GmailAuthenticationError) as e:
            raise HTTPException(
                status_code=503,
                detail=f"Gmail API error: {str(e)}. Check credentials and API setup.",
            )
        
        if not messages:
            return SyncGmailResponse(
                success=True,
                emails_fetched=0,
                emails_classified=0,
                emails_processed=0,
                emails_skipped=0,
                facts_extracted=0,
                drives_affected=[],
                details=[],
                errors=[],
            )
        
        # Initialize LLM client and classifier
        llm_client = get_llm_client()
        classifier = EmailClassifier(llm_client)
        
        # Track statistics
        emails_classified = 0
        emails_processed = 0
        emails_skipped = 0
        total_facts = 0
        drives_affected = set()
        
        # Process each email
        for msg in messages:
            try:
                # Check if already processed
                if is_email_processed(db, msg.message_id):
                    emails_skipped += 1
                    details.append({
                        "message_id": msg.message_id,
                        "status": "skipped",
                        "reason": "Already processed",
                        "timestamp": msg.timestamp.isoformat(),
                    })
                    continue
                
                # Classify email
                classification = classifier.classify(msg)
                emails_classified += 1
                
                # Check if relevant for processing
                if not classifier.is_relevant(classification):
                    # Not relevant - still record as processed
                    create_processed_email(
                        db=db,
                        message_id=msg.message_id,
                        gmail_id=gmail_adapter.extract_gmail_id_from_message_id(msg.message_id) or "",
                        sender_email=msg.sender_id,
                        classification=classification.category,
                        confidence=classification.confidence,
                        drive_id=None,
                        facts_extracted=0,
                        labeled=False,
                        classification_reason=classification.reason,
                    )
                    
                    emails_skipped += 1
                    details.append({
                        "message_id": msg.message_id,
                        "status": "skipped",
                        "reason": f"Not relevant ({classification.category})",
                        "classification": classification.category,
                        "confidence": classification.confidence,
                        "timestamp": msg.timestamp.isoformat(),
                    })
                    continue
                
                # Email is relevant - extract drive and criteria
                drive_id = classification.drive_id
                company_name = classification.company_name
                
                if not drive_id or not company_name:
                    # Fallback: try to extract drive info
                    from database.models import Drive
                    existing_drives = db.query(Drive).all()
                    drive_list = [{"drive_id": d.drive_id, "company_name": d.company_name} for d in existing_drives]
                    
                    drive_id, company_name = classifier.extract_drive_info(
                        msg.body,
                        existing_drives=drive_list,
                    )
                
                if not drive_id or not company_name:
                    # Still can't identify drive - skip
                    create_processed_email(
                        db=db,
                        message_id=msg.message_id,
                        gmail_id=gmail_adapter.extract_gmail_id_from_message_id(msg.message_id) or "",
                        sender_email=msg.sender_id,
                        classification=classification.category,
                        confidence=classification.confidence,
                        drive_id=None,
                        facts_extracted=0,
                        labeled=False,
                        classification_reason="Could not identify company/drive",
                    )
                    
                    emails_skipped += 1
                    details.append({
                        "message_id": msg.message_id,
                        "status": "skipped",
                        "reason": "Could not identify company/drive",
                        "classification": classification.category,
                        "timestamp": msg.timestamp.isoformat(),
                    })
                    continue
                
                # Ensure drive exists
                drive = get_drive(db, drive_id)
                if not drive:
                    drive = create_drive(
                        db=db,
                        drive_id=drive_id,
                        company_name=company_name,
                    )
                
                # Extract criteria
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
                
                # Add Gmail label
                labeled = False
                gmail_id = gmail_adapter.extract_gmail_id_from_message_id(msg.message_id)
                if gmail_id:
                    try:
                        from config import settings
                        gmail_adapter.add_label(gmail_id, settings.gmail_processed_label)
                        labeled = True
                    except Exception as e:
                        errors.append(f"Failed to label email {msg.message_id}: {str(e)}")
                
                # Record as processed
                create_processed_email(
                    db=db,
                    message_id=msg.message_id,
                    gmail_id=gmail_id or "",
                    sender_email=msg.sender_id,
                    classification=classification.category,
                    confidence=classification.confidence,
                    drive_id=drive_id,
                    facts_extracted=len(facts),
                    labeled=labeled,
                    classification_reason=classification.reason,
                )
                
                emails_processed += 1
                details.append({
                    "message_id": msg.message_id,
                    "status": "processed",
                    "drive_id": drive_id,
                    "company_name": company_name,
                    "classification": classification.category,
                    "confidence": classification.confidence,
                    "facts_extracted": len(facts),
                    "labeled": labeled,
                    "timestamp": msg.timestamp.isoformat(),
                })
                
            except Exception as e:
                # Log error but continue with other emails
                error_msg = f"Error processing email {msg.message_id}: {str(e)}"
                errors.append(error_msg)
                details.append({
                    "message_id": msg.message_id,
                    "status": "error",
                    "error": str(e),
                    "timestamp": msg.timestamp.isoformat(),
                })
                continue
        
        # Run reconciliation for all affected drives
        for drive_id in drives_affected:
            try:
                reconcile_facts_for_drive(db, drive_id, persist=True)
            except Exception as e:
                errors.append(f"Reconciliation failed for {drive_id}: {str(e)}")
        
        return SyncGmailResponse(
            success=True,
            emails_fetched=len(messages),
            emails_classified=emails_classified,
            emails_processed=emails_processed,
            emails_skipped=emails_skipped,
            facts_extracted=total_facts,
            drives_affected=list(drives_affected),
            details=details,
            errors=errors,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gmail sync failed: {str(e)}",
        )


class GmailPollingStatusResponse(BaseModel):
    """Response with Gmail polling service status."""
    
    enabled: bool
    running: bool
    polling_interval_minutes: int
    last_poll_time: str | None
    last_poll_status: str
    total_polls: int
    successful_polls: int
    failed_polls: int
    last_error: str | None


@router.get("/gmail-polling-status", response_model=GmailPollingStatusResponse)
async def get_gmail_polling_status():
    """Get current status of Gmail polling service.
    
    Returns information about the background polling service including
    last poll time, success rate, and any errors.
    
    Returns:
        Polling service status
    """
    try:
        from ingestion.gmail.polling_service import get_polling_service
        
        service = get_polling_service()
        status = service.get_status()
        
        return GmailPollingStatusResponse(**status)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get polling status: {str(e)}",
        )


class ManualPollResponse(BaseModel):
    """Response from manual poll trigger."""
    
    success: bool
    message: str
    timestamp: str


@router.post("/trigger-gmail-poll", response_model=ManualPollResponse)
async def trigger_gmail_poll():
    """Manually trigger a Gmail poll immediately.
    
    This triggers an immediate poll without waiting for the scheduled interval.
    Does not interfere with the automatic polling schedule.
    
    Returns:
        Result of the manual poll
    """
    try:
        from ingestion.gmail.polling_service import get_polling_service
        
        service = get_polling_service()
        result = await service.trigger_manual_poll()
        
        return ManualPollResponse(**result)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger manual poll: {str(e)}",
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


# ============================================================================
# Portal (SIS) Integration
# ============================================================================

class SyncPortalResponse(BaseModel):
    """Response from portal sync operation."""
    
    success: bool
    events_fetched: int
    events_processed: int
    events_skipped: int
    facts_extracted: int
    drives_affected: list[str]
    details: list[dict]
    errors: list[str]


def _normalize_drive_id(company_name: str) -> str:
    """Generate drive_id from company name.
    
    Args:
        company_name: Full company name
        
    Returns:
        Drive ID in format DRIVE_COMPANYNAME
    """
    normalized = company_name.upper().replace(" ", "")
    normalized = "".join(c for c in normalized if c.isalnum())
    return f"DRIVE_{normalized}"


@router.post("/sync-portal", response_model=SyncPortalResponse)
async def sync_portal(
    db: Session = Depends(get_db),
):
    """Sync placement events from Student Portal (SIS) and process them.
    
    This endpoint:
    1. Fetches events from the portal JSON file
    2. For each event:
       - Creates drive if it doesn't exist
       - Extracts eligibility criteria using LLM
       - Stores facts in database
       - Tracks processed events to prevent duplicates
    3. Runs reconciliation to resolve conflicts with email/WhatsApp
    
    Portal authority rank: 4 (lower than email/WhatsApp, higher than student forwards)
    This means portal data will be overridden by placement cell communications when conflicts occur.
    
    Args:
        db: Database session
        
    Returns:
        Summary of sync operation with counts and details
    """
    errors = []
    details = []
    
    try:
        # Initialize portal adapter
        portal_adapter = PortalAdapter()
        
        # Fetch portal events
        try:
            messages = portal_adapter.fetch()
        except FileNotFoundError as e:
            raise HTTPException(
                status_code=404,
                detail=str(e),
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid portal data format: {str(e)}",
            )
        
        if not messages:
            return SyncPortalResponse(
                success=True,
                events_fetched=0,
                events_processed=0,
                events_skipped=0,
                facts_extracted=0,
                drives_affected=[],
                details=[],
                errors=[],
            )
        
        # Initialize LLM client
        try:
            llm_client = get_llm_client()
        except Exception as e:
            errors.append(f"LLM initialization failed: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail="LLM service unavailable. Check GEMINI_API_KEY in .env",
            )
        
        events_processed = 0
        events_skipped = 0
        total_facts = 0
        drives_affected = set()
        
        for msg in messages:
            try:
                # Check if already processed
                existing_facts = get_fact_by_source(db, msg.message_id)
                if existing_facts:
                    events_skipped += 1
                    
                    # Extract company name for reporting
                    company_line = msg.body.split("\n")[0]
                    company_name = company_line.replace("=", "").strip()
                    
                    details.append({
                        "message_id": msg.message_id,
                        "company_name": company_name,
                        "status": "skipped",
                        "reason": f"Already processed ({len(existing_facts)} facts exist)",
                    })
                    continue
                
                # Extract company name from message
                # Format: "=== Company Name ==="
                company_line = msg.body.split("\n")[0]
                company_name = company_line.replace("=", "").strip()
                
                # Generate drive_id
                drive_id = _normalize_drive_id(company_name)
                
                # Ensure drive exists
                drive = get_drive(db, drive_id)
                if not drive:
                    drive = create_drive(
                        db,
                        drive_id=drive_id,
                        company_name=company_name,
                    )
                
                # Extract criteria from portal event
                facts = extract_criteria_from_notice(
                    notice_text=msg.body,
                    source_id=msg.message_id,
                    source_type=msg.source_type,
                    timestamp=msg.timestamp,
                    drive_id=drive_id,
                    llm_client=llm_client,
                )
                
                # Store facts
                for fact in facts:
                    db.add(fact)
                db.commit()
                
                total_facts += len(facts)
                drives_affected.add(drive_id)
                events_processed += 1
                
                details.append({
                    "message_id": msg.message_id,
                    "company_name": company_name,
                    "drive_id": drive_id,
                    "source_type": msg.source_type.value,
                    "facts_extracted": len(facts),
                    "status": "success",
                    "timestamp": msg.timestamp.isoformat(),
                })
                
            except Exception as e:
                error_msg = f"Failed to process portal event {msg.message_id}: {str(e)}"
                errors.append(error_msg)
                
                details.append({
                    "message_id": msg.message_id,
                    "status": "error",
                    "error": str(e),
                })
        
        # Run reconciliation for all affected drives
        for drive_id in drives_affected:
            try:
                reconcile_facts_for_drive(db, drive_id, persist=True)
            except Exception as e:
                error_msg = f"Reconciliation failed for {drive_id}: {str(e)}"
                errors.append(error_msg)
        
        return SyncPortalResponse(
            success=True,
            events_fetched=len(messages),
            events_processed=events_processed,
            events_skipped=events_skipped,
            facts_extracted=total_facts,
            drives_affected=list(drives_affected),
            details=details,
            errors=errors,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync portal data: {str(e)}",
        )
