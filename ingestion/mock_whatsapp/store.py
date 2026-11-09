"""In-memory message store for the mock WhatsApp console.

Stands in for whatever durable store the real adapter will read from later (DESIGN.md 9.1:
the console mimics the WhatsApp Business Cloud API webhook shape so swapping this module
for a real integration is an adapter change, not a rewrite).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from core.schemas import RawMessage, SenderRole, SourceType

_SENDER_ROLE_TO_SOURCE_TYPE: dict[SenderRole, SourceType] = {
    SenderRole.PLACEMENT_CELL: SourceType.PLACEMENT_CELL_WHATSAPP,
    SenderRole.COORDINATOR: SourceType.COORDINATOR_WHATSAPP,
    SenderRole.STUDENT: SourceType.STUDENT_WHATSAPP,
}

_messages: list[RawMessage] = []

UPLOADS_DIR = Path("data/mock_whatsapp_uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def add_message(
    sender_id: str,
    sender_role: SenderRole,
    body: str,
    is_forwarded: bool = False,
    image_bytes: bytes | None = None,
    image_ext: str = ".png",
) -> RawMessage:
    message_id = str(uuid.uuid4())

    image_id: str | None = None
    if image_bytes:
        image_id = f"{message_id}{image_ext}"
        (UPLOADS_DIR / image_id).write_bytes(image_bytes)

    message = RawMessage(
        message_id=message_id,
        source_type=_SENDER_ROLE_TO_SOURCE_TYPE[sender_role],
        sender_id=sender_id,
        sender_role=sender_role,
        timestamp=datetime.now(),  # Local time (timezone-naive) - NOT UTC
        body=body,
        message_type="image" if image_id else "text",
        is_forwarded=is_forwarded,
        image_id=image_id,
    )
    _messages.append(message)
    return message


def get_all() -> list[RawMessage]:
    return list(_messages)


def get_image_path(image_id: str) -> Path | None:
    path = UPLOADS_DIR / image_id
    return path if path.exists() else None


def clear() -> None:
    """Test/demo-reset helper only — never called from production code paths."""
    _messages.clear()
