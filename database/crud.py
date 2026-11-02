"""CRUD operations for PlaceGuard database.

Key principles:
- Facts are append-only (insert only, never update/delete)
- Students and Drives support full CRUD (admin-imported, read-only to students)
- ExtractedCriteria are managed by reconciliation engine
- Registrations are write-once (eligibility-gated audit trail)
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import List

from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.schemas import Student as StudentSchema
from database.models import Drive, ExtractedCriterion, Fact, Registration, Student, utcnow


# ============================================================================
# STUDENT OPERATIONS
# ============================================================================

def create_student(db: Session, student: StudentSchema) -> Student:
    """Create a new student record.

    USN is the canonical identifier; student_id mirrors USN for compat.
    """
    db_student = Student(
        usn=student.usn,
        student_id=student.usn,          # keep in sync
        name=student.name,
        date_of_birth=student.date_of_birth,
        cgpa=student.cgpa,
        branch=student.branch,
        backlogs=student.backlogs,
        has_prior_offer=student.has_prior_offer,
        tenth_pct=student.tenth_pct,
        twelfth_pct=student.twelfth_pct,
    )
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student


def get_student(db: Session, student_id: str) -> Student | None:
    """Retrieve a student by USN (or legacy student_id)."""
    return (
        db.query(Student)
        .filter(
            (Student.usn == student_id) | (Student.student_id == student_id)
        )
        .first()
    )


def get_student_by_usn(db: Session, usn: str) -> Student | None:
    """Retrieve a student by USN."""
    return db.query(Student).filter(Student.usn == usn.upper()).first()


def authenticate_student(
    db: Session, usn: str, date_of_birth: date
) -> Student | None:
    """Validate USN + date of birth login.

    Returns the Student record if credentials match, None otherwise.
    This is the only auth check — no password hashing needed because
    the DOB comes from the college's admin-imported dataset.
    """
    return (
        db.query(Student)
        .filter(
            and_(
                Student.usn == usn.upper(),
                Student.date_of_birth == date_of_birth,
            )
        )
        .first()
    )


def get_students(
    db: Session, skip: int = 0, limit: int = 100
) -> List[Student]:
    """List all students with pagination."""
    return db.query(Student).offset(skip).limit(limit).all()


def update_student(
    db: Session, student_id: str, updates: dict
) -> Student | None:
    """Update student fields."""
    db_student = get_student(db, student_id)
    if not db_student:
        return None
    
    for key, value in updates.items():
        if hasattr(db_student, key):
            setattr(db_student, key, value)
    
    db_student.updated_at = utcnow()
    db.commit()
    db.refresh(db_student)
    return db_student


def delete_student(db: Session, student_id: str) -> bool:
    """Delete a student record."""
    db_student = get_student(db, student_id)
    if not db_student:
        return False
    
    db.delete(db_student)
    db.commit()
    return True


def search_students(
    db: Session, branch: str | None = None, min_cgpa: float | None = None
) -> List[Student]:
    """Search students by criteria."""
    query = db.query(Student)
    
    if branch:
        query = query.filter(Student.branch == branch)
    if min_cgpa is not None:
        query = query.filter(Student.cgpa >= min_cgpa)
    
    return query.all()


# ============================================================================
# DRIVE OPERATIONS
# ============================================================================

def create_drive(
    db: Session,
    drive_id: str,
    company_name: str,
    deadline: datetime | None = None,
    status: str = "active",
) -> Drive:
    """Create a new placement drive."""
    db_drive = Drive(
        drive_id=drive_id,
        company_name=company_name,
        deadline=deadline,
        status=status,
    )
    db.add(db_drive)
    db.commit()
    db.refresh(db_drive)
    return db_drive


def get_drive(db: Session, drive_id: str) -> Drive | None:
    """Retrieve a drive by ID."""
    return db.query(Drive).filter(Drive.drive_id == drive_id).first()


def get_drives(
    db: Session, status: str | None = None, skip: int = 0, limit: int = 100
) -> List[Drive]:
    """List drives with optional status filter."""
    query = db.query(Drive)
    
    if status:
        query = query.filter(Drive.status == status)
    
    return query.offset(skip).limit(limit).all()


def update_drive(
    db: Session, drive_id: str, updates: dict
) -> Drive | None:
    """Update drive fields."""
    db_drive = get_drive(db, drive_id)
    if not db_drive:
        return None
    
    for key, value in updates.items():
        if hasattr(db_drive, key):
            setattr(db_drive, key, value)
    
    db_drive.updated_at = utcnow()
    db.commit()
    db.refresh(db_drive)
    return db_drive


# ============================================================================
# FACT OPERATIONS (APPEND-ONLY)
# ============================================================================

def insert_fact(
    db: Session,
    source_id: str,
    source_type: str,
    authority_rank: int,
    timestamp: datetime,
    drive_id: str,
    criterion_type: str,
    operator: str,
    value: str,
    scope: str = "ALL",
    effective_timestamp: datetime | None = None,
    is_correction: bool = False,
    supersedes_ref: str | None = None,
    raw_notice_text: str | None = None,
) -> Fact:
    """Insert a new fact (NEVER update or delete).
    
    This is the only write operation allowed on the facts table.
    """
    if effective_timestamp is None:
        effective_timestamp = timestamp
    
    db_fact = Fact(
        source_id=source_id,
        source_type=source_type,
        authority_rank=authority_rank,
        timestamp=timestamp,
        effective_timestamp=effective_timestamp,
        drive_id=drive_id,
        criterion_type=criterion_type,
        operator=operator,
        value=value,
        scope=scope,
        is_correction=is_correction,
        supersedes_ref=supersedes_ref,
        raw_notice_text=raw_notice_text,
    )
    db.add(db_fact)
    db.commit()
    db.refresh(db_fact)
    return db_fact


def get_facts_by_drive(db: Session, drive_id: str) -> List[Fact]:
    """Retrieve all facts for a drive."""
    return db.query(Fact).filter(Fact.drive_id == drive_id).all()


def get_facts_by_rule_key(
    db: Session, drive_id: str, criterion_type: str, scope: str = "ALL"
) -> List[Fact]:
    """Retrieve all facts matching a rule key (drive_id, criterion_type, scope).
    
    This is the input to the reconciliation engine for determining current value.
    """
    return (
        db.query(Fact)
        .filter(
            and_(
                Fact.drive_id == drive_id,
                Fact.criterion_type == criterion_type,
                Fact.scope == scope,
            )
        )
        .order_by(Fact.authority_rank, Fact.effective_timestamp.desc())
        .all()
    )


def get_fact_by_source(db: Session, source_id: str) -> List[Fact]:
    """Retrieve all facts from a specific source."""
    return db.query(Fact).filter(Fact.source_id == source_id).all()


# ============================================================================
# EXTRACTED CRITERIA OPERATIONS (MANAGED BY RECONCILIATION ENGINE)
# ============================================================================

def upsert_extracted_criterion(
    db: Session,
    drive_id: str,
    criterion_type: str,
    operator: str,
    value: str,
    source_id: str,
    source_type: str,
    authority_rank: int,
    timestamp: datetime,
    scope: str = "ALL",
) -> ExtractedCriterion:
    """Insert or update the current extracted criterion for a rule key.
    
    This is called by the reconciliation engine after determining the
    current value via authority ranking and temporal logic.
    """
    # Check if criterion already exists
    existing = (
        db.query(ExtractedCriterion)
        .filter(
            and_(
                ExtractedCriterion.drive_id == drive_id,
                ExtractedCriterion.criterion_type == criterion_type,
                ExtractedCriterion.scope == scope,
            )
        )
        .first()
    )
    
    if existing:
        # Update existing
        existing.operator = operator
        existing.value = value
        existing.source_id = source_id
        existing.source_type = source_type
        existing.authority_rank = authority_rank
        existing.timestamp = timestamp
        existing.is_current = True
        existing.reconciled_at = utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Insert new
        criterion = ExtractedCriterion(
            drive_id=drive_id,
            criterion_type=criterion_type,
            scope=scope,
            operator=operator,
            value=value,
            source_id=source_id,
            source_type=source_type,
            authority_rank=authority_rank,
            timestamp=timestamp,
            is_current=True,
        )
        db.add(criterion)
        db.commit()
        db.refresh(criterion)
        return criterion


def get_current_criteria(
    db: Session, drive_id: str
) -> List[ExtractedCriterion]:
    """Retrieve all current criteria for a drive."""
    return (
        db.query(ExtractedCriterion)
        .filter(
            and_(
                ExtractedCriterion.drive_id == drive_id,
                ExtractedCriterion.is_current == True,
            )
        )
        .all()
    )


def get_criterion_by_type(
    db: Session, drive_id: str, criterion_type: str, scope: str = "ALL"
) -> ExtractedCriterion | None:
    """Retrieve a specific current criterion."""
    return (
        db.query(ExtractedCriterion)
        .filter(
            and_(
                ExtractedCriterion.drive_id == drive_id,
                ExtractedCriterion.criterion_type == criterion_type,
                ExtractedCriterion.scope == scope,
                ExtractedCriterion.is_current == True,
            )
        )
        .first()
    )


# ============================================================================
# REGISTRATION OPERATIONS (WRITE-ONCE — eligibility-gated audit trail)
# ============================================================================

def create_registration(
    db: Session,
    usn: str,
    drive_id: str,
    eligibility_snapshot: dict | None = None,
) -> Registration:
    """Record that an eligible student received the registration link.

    This is write-once — a student can only register once per drive
    (enforced by the unique constraint on usn + drive_id).

    Args:
        db: Database session
        usn: Student USN
        drive_id: Drive identifier
        eligibility_snapshot: Full EligibilityResult dict for audit
    """
    snapshot_str = json.dumps(eligibility_snapshot) if eligibility_snapshot else None
    reg = Registration(
        usn=usn.upper(),
        drive_id=drive_id,
        eligibility_snapshot=snapshot_str,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


def get_registration(db: Session, usn: str, drive_id: str) -> Registration | None:
    """Check if a student has already registered for a drive."""
    return (
        db.query(Registration)
        .filter(
            and_(
                Registration.usn == usn.upper(),
                Registration.drive_id == drive_id,
            )
        )
        .first()
    )


def get_registrations_by_student(db: Session, usn: str) -> List[Registration]:
    """All drives a student has registered for."""
    return (
        db.query(Registration)
        .filter(Registration.usn == usn.upper())
        .order_by(Registration.registered_at.desc())
        .all()
    )


def get_registrations_by_drive(db: Session, drive_id: str) -> List[Registration]:
    """All students who registered for a specific drive."""
    return (
        db.query(Registration)
        .filter(Registration.drive_id == drive_id)
        .order_by(Registration.registered_at)
        .all()
    )


# ============================================================================
# TIMELINE QUERY — all facts for a drive in chronological order
# ============================================================================

def get_drive_timeline(db: Session, drive_id: str) -> List[Fact]:
    """Return all facts for a drive ordered by timestamp ascending.

    This powers the company time-series view shown to students — every
    extracted criterion from every source, in the order they arrived.
    The reconciliation engine's final verdict is stored in ExtractedCriterion;
    the timeline shows the full history including superseded facts.
    """
    return (
        db.query(Fact)
        .filter(Fact.drive_id == drive_id)
        .order_by(Fact.timestamp.asc())
        .all()
    )


# ============================================================================
# PROCESSED EMAIL OPERATIONS (Gmail duplicate prevention)
# ============================================================================

def create_processed_email(
    db: Session,
    message_id: str,
    gmail_id: str,
    sender_email: str,
    classification: str,
    confidence: float,
    drive_id: str | None = None,
    facts_extracted: int = 0,
    labeled: bool = False,
    classification_reason: str | None = None,
) -> "ProcessedEmail":
    """Record that an email has been processed.
    
    Args:
        db: Database session
        message_id: Our internal message ID
        gmail_id: Gmail message ID
        sender_email: Email address of sender
        classification: LLM classification result
        confidence: Classification confidence (0.0-1.0)
        drive_id: Associated drive ID (if relevant)
        facts_extracted: Number of facts extracted
        labeled: Whether Gmail label was applied
        classification_reason: Reason for classification
        
    Returns:
        Created ProcessedEmail record
    """
    from database.models import ProcessedEmail
    
    processed = ProcessedEmail(
        message_id=message_id,
        gmail_id=gmail_id,
        sender_email=sender_email,
        classification=classification,
        confidence=confidence,
        drive_id=drive_id,
        facts_extracted=facts_extracted,
        labeled=labeled,
        classification_reason=classification_reason,
    )
    db.add(processed)
    db.commit()
    db.refresh(processed)
    return processed


def get_processed_email(db: Session, message_id: str) -> "ProcessedEmail | None":
    """Check if an email has been processed.
    
    Args:
        db: Database session
        message_id: Our internal message ID
        
    Returns:
        ProcessedEmail record if found, None otherwise
    """
    from database.models import ProcessedEmail
    
    return (
        db.query(ProcessedEmail)
        .filter(ProcessedEmail.message_id == message_id)
        .first()
    )


def is_email_processed(db: Session, message_id: str) -> bool:
    """Check if an email has already been processed.
    
    Args:
        db: Database session
        message_id: Our internal message ID
        
    Returns:
        True if email was already processed, False otherwise
    """
    return get_processed_email(db, message_id) is not None


def get_processed_emails_by_drive(
    db: Session, drive_id: str
) -> List["ProcessedEmail"]:
    """Get all processed emails for a specific drive.
    
    Args:
        db: Database session
        drive_id: Drive identifier
        
    Returns:
        List of ProcessedEmail records
    """
    from database.models import ProcessedEmail
    
    return (
        db.query(ProcessedEmail)
        .filter(ProcessedEmail.drive_id == drive_id)
        .order_by(ProcessedEmail.processed_at.desc())
        .all()
    )


def get_recent_processed_emails(
    db: Session, limit: int = 100
) -> List["ProcessedEmail"]:
    """Get recently processed emails.
    
    Args:
        db: Database session
        limit: Maximum number of records to return
        
    Returns:
        List of ProcessedEmail records ordered by processed_at desc
    """
    from database.models import ProcessedEmail
    
    return (
        db.query(ProcessedEmail)
        .order_by(ProcessedEmail.processed_at.desc())
        .limit(limit)
        .all()
    )


def update_processed_email_label_status(
    db: Session, message_id: str, labeled: bool = True
) -> bool:
    """Update the labeled status of a processed email.
    
    Args:
        db: Database session
        message_id: Our internal message ID
        labeled: New labeled status
        
    Returns:
        True if updated, False if not found
    """
    from database.models import ProcessedEmail
    
    processed = get_processed_email(db, message_id)
    if not processed:
        return False
    
    processed.labeled = labeled
    db.commit()
    return True
