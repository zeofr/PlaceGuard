"""SQLAlchemy ORM models for PlaceGuard database.

Key design principles from DESIGN.md:
1. Facts table is immutable and append-only (event-sourced)
2. No UPDATE/DELETE on facts - only INSERT and SELECT
3. Current state is derived via reconciliation queries, not stored directly
4. Full provenance tracking on every fact
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Return a timezone-naive UTC timestamp, replacing the deprecated ``datetime.utcnow()``.

    SQLAlchemy's default ``DateTime`` columns store naive datetimes, so we strip the
    tzinfo to keep existing column behavior identical while avoiding the
    ``DeprecationWarning`` emitted by ``datetime.utcnow()`` (scheduled for removal in
    a future Python release). Use this callable for column ``default``/``onupdate``
    and for any explicit timestamp assignment.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Student(Base):
    """Student profile with eligibility-relevant attributes.

    Login credentials: usn + date_of_birth (matches college portal convention).
    USN format: 1MS<YY><BRANCH><NUMBER>  e.g. 1MS22CS042
    All eligibility fields are nullable to correctly propagate UNKNOWN state.
    """
    
    __tablename__ = "students"
    
    # Primary key — internal autoincrement so USN can be updated if needed
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Login / identity fields
    usn: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)

    # Profile
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Kept for backward-compat with existing code that references student_id.
    # Populated automatically as the USN; callers that pass student_id still work.
    student_id: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )
    
    # Eligibility criteria fields (nullable to support UNKNOWN state)
    cgpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    branch: Mapped[str | None] = mapped_column(String(50), nullable=True)
    backlogs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_prior_offer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tenth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    twelfth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
    
    def __repr__(self) -> str:
        return f"<Student {self.usn} ({self.name})>"


class Drive(Base):
    """Placement drive/company metadata."""
    
    __tablename__ = "drives"
    
    drive_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | closed | cancelled
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # URL shown to eligible students — populated by admin when drive is created
    registration_link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Optional short description / job profile
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
    
    def __repr__(self) -> str:
        return f"<Drive {self.drive_id} ({self.company_name})>"


class Fact(Base):
    """Immutable, append-only event log of extracted eligibility criteria.
    
    CRITICAL: This table is write-once. Never UPDATE or DELETE.
    
    Each fact represents one extracted criterion from one source at one point in time.
    The reconciliation engine queries this table to derive the "current" state by
    applying authority ranking and temporal logic (DESIGN.md 3.1).
    """
    
    __tablename__ = "facts"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Provenance: where did this fact come from?
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    authority_rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Temporal: when was this fact asserted?
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )  # When the source communicated this
    effective_timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )  # When this fact takes effect (may differ for scheduled updates)
    
    # Rule key: (drive_id, criterion_type, scope) from DESIGN.md 3.3
    drive_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    criterion_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ALL", index=True
    )
    
    # Criterion value
    operator: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # gte | lte | eq | in | not_in
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-serialized value
    
    # Supersession tracking (DESIGN.md 3.2)
    is_correction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supersedes_ref: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # source_id of fact this supersedes
    
    # Audit trail
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )  # When LLM extraction occurred
    raw_notice_text: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Original notice for audit
    
    def __repr__(self) -> str:
        return (
            f"<Fact {self.drive_id}.{self.criterion_type}={self.value} "
            f"from {self.source_type} at {self.timestamp}>"
        )


class ExtractedCriterion(Base):
    """Derived view of current criteria per drive after reconciliation.
    
    This table is populated/updated by the reconciliation engine after processing
    facts. It represents the "current truth" after applying authority ranking,
    temporal logic, and supersession detection.
    
    This is NOT append-only like Facts — it's a materialized view that gets
    updated when reconciliation runs.
    """
    
    __tablename__ = "extracted_criteria"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Rule key
    drive_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    criterion_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(50), nullable=False, default="ALL")
    
    # Current value
    operator: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Provenance of current value
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    authority_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Status
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    
    def __repr__(self) -> str:
        return (
            f"<ExtractedCriterion {self.drive_id}.{self.criterion_type}={self.value} "
            f"from {self.source_type}>"
        )


class Registration(Base):
    """Audit record of a student receiving a registration link.

    Created the moment an eligible student's request is gated-and-approved.
    This is the proof that the system worked — ineligible students never get
    a row here.  Write-once (no updates) to preserve the audit trail.

    Fields:
        usn          — student USN (matches Student.usn)
        drive_id     — drive the student registered for
        registered_at — when the link was surfaced to the student
        eligibility_snapshot — JSON snapshot of the EligibilityResult at
                               the time of registration, for audit purposes
    """

    __tablename__ = "registrations"

    __table_args__ = (
        UniqueConstraint("usn", "drive_id", name="uq_registration_usn_drive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usn: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    drive_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    # Full JSON snapshot of the eligibility result for auditing
    eligibility_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Registration {self.usn} → {self.drive_id} at {self.registered_at}>"


class ProcessedEmail(Base):
    """Track processed Gmail messages to prevent duplicate processing.
    
    This table stores message IDs that have been processed through the
    Gmail ingestion pipeline. Before processing a new email, we check
    this table to avoid re-extracting criteria from the same message.
    
    Fields:
        message_id      — our internal message ID (format: gmail_{id}_{sender})
        gmail_id        — original Gmail message ID for reference
        sender_email    — email address of sender (placement officer)
        processed_at    — when the email was processed
        classification  — LLM classification result (new_offer, offer_update, etc.)
        drive_id        — drive this email was associated with (if relevant)
        facts_extracted — number of facts extracted from this email
        labeled         — whether Gmail label was successfully applied
    """
    
    __tablename__ = "processed_emails"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Message identifiers
    message_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    gmail_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sender_email: Mapped[str] = mapped_column(String(200), nullable=False)
    
    # Processing metadata
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    classification: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Results
    drive_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    facts_extracted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    labeled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Optional: store classification reason for debugging
    classification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    def __repr__(self) -> str:
        return f"<ProcessedEmail {self.message_id} [{self.classification}] at {self.processed_at}>"
