"""Authentication routes — USN + date-of-birth login.

Students log in with their college USN and date of birth, matching the
convention used by the existing student portal.  On success a signed JWT
is returned.  Every protected route verifies this token via
``get_current_student``.

Session duration: 1 hour (configurable via JWT_EXPIRATION_HOURS in .env).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database.connection import get_db
from database.crud import authenticate_student, get_student_by_usn
from database.models import Student

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    usn: str
    date_of_birth: date  # ISO-8601 string in JSON, e.g. "2003-05-14"


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    usn: str
    name: str


class StudentProfile(BaseModel):
    """Minimal profile returned alongside the token and in /auth/me."""

    usn: str
    name: str
    branch: str | None
    cgpa: float | None
    backlogs: int | None
    has_prior_offer: bool | None
    tenth_pct: float | None
    twelfth_pct: float | None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _create_access_token(usn: str) -> tuple[str, int]:
    """Create a signed JWT for the given USN.

    Returns:
        (token_string, expiry_seconds)
    """
    expiry_seconds = settings.jwt_expiration_hours * 3600
    expire = datetime.now(UTC) + timedelta(seconds=expiry_seconds)
    payload = {
        "sub": usn.upper(),
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, expiry_seconds


def get_current_student(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Student:
    """FastAPI dependency — validates JWT and returns the Student ORM object.

    Usage in a protected route::

        @router.get("/me")
        def me(student: Student = Depends(get_current_student)):
            ...
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        usn: str | None = payload.get("sub")
        if not usn:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    student = get_student_by_usn(db, usn)
    if student is None:
        raise credentials_exception

    return student


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Log in with USN + date of birth.

    Returns a JWT access token valid for ``JWT_EXPIRATION_HOURS`` (default 1 h).
    Include it in subsequent requests as::

        Authorization: Bearer <token>
    """
    student = authenticate_student(db, request.usn, request.date_of_birth)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid USN or date of birth.",
        )

    token, expiry = _create_access_token(student.usn)
    return LoginResponse(
        access_token=token,
        expires_in_seconds=expiry,
        usn=student.usn,
        name=student.name,
    )


@router.get("/me", response_model=StudentProfile)
def me(student: Student = Depends(get_current_student)):
    """Return the profile of the currently logged-in student."""
    return StudentProfile.model_validate(student)
