"""Database connection management with session handling and pooling."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config import settings

# SQLite and PostgreSQL need different engine arguments.
# pool_size / max_overflow are not supported by the SQLite dialect.
_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    # File-based SQLite: allow multithreaded access (FastAPI threadpool) and
    # skip pool settings that SQLite doesn't support.
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.database_echo,
    )
else:
    # PostgreSQL / other RDBMS: use connection pooling.
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=settings.database_echo,
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI routes to get database session.
    
    Usage:
        @app.get("/students")
        def list_students(db: Session = Depends(get_db)):
            return crud.get_students(db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database session in non-FastAPI code.
    
    Usage:
        with get_db_context() as db:
            student = crud.get_student(db, student_id="s1")
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database by creating all tables.
    
    NOTE: In production, use Alembic migrations instead.
    This is useful for testing and development.
    """
    from database.models import Base
    
    Base.metadata.create_all(bind=engine)
