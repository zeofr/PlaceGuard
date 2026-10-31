#!/usr/bin/env python3
"""Dev migration script — applies all schema changes to the SQLite dev database.

Run this once after pulling schema changes instead of running Alembic
(Alembic is for production PostgreSQL/MySQL; for SQLite dev we just
recreate tables that don't exist yet).

Usage (from project root):
    python scripts/migrate_dev.py

Safe to run multiple times — existing tables are not dropped.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "placeguard_dev.db"


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def migrate(conn: sqlite3.Connection) -> None:
    changes: list[str] = []

    # ── students table ──────────────────────────────────────────────────────
    if table_exists(conn, "students"):
        if not column_exists(conn, "students", "usn"):
            conn.execute("ALTER TABLE students ADD COLUMN usn TEXT")
            # Back-fill usn from student_id for existing rows
            conn.execute("UPDATE students SET usn = student_id WHERE usn IS NULL")
            changes.append("students: added 'usn' column")

        if not column_exists(conn, "students", "date_of_birth"):
            conn.execute("ALTER TABLE students ADD COLUMN date_of_birth DATE")
            changes.append("students: added 'date_of_birth' column")

        if not column_exists(conn, "students", "id"):
            # SQLite doesn't support adding a PRIMARY KEY column after creation.
            # For dev the existing student_id PK is fine; new rows use the ORM
            # which handles the autoincrement id transparently via SQLAlchemy.
            changes.append("students: 'id' PK not added (SQLite limitation) — use ORM")

    # ── drives table ────────────────────────────────────────────────────────
    if table_exists(conn, "drives"):
        if not column_exists(conn, "drives", "registration_link"):
            conn.execute("ALTER TABLE drives ADD COLUMN registration_link TEXT")
            changes.append("drives: added 'registration_link' column")

        if not column_exists(conn, "drives", "description"):
            conn.execute("ALTER TABLE drives ADD COLUMN description TEXT")
            changes.append("drives: added 'description' column")

    # ── registrations table (new) ────────────────────────────────────────────
    if not table_exists(conn, "registrations"):
        conn.execute("""
            CREATE TABLE registrations (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                usn              TEXT    NOT NULL,
                drive_id         TEXT    NOT NULL,
                registered_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                eligibility_snapshot TEXT,
                CONSTRAINT uq_registration_usn_drive UNIQUE (usn, drive_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_registrations_usn      ON registrations (usn)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_registrations_drive_id ON registrations (drive_id)")
        changes.append("registrations: table created")

    conn.commit()

    if changes:
        print("Applied migrations:")
        for c in changes:
            print(f"  ✓ {c}")
    else:
        print("No migrations needed — schema is up to date.")


def main() -> None:
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Run the app once first (uvicorn api.main:app) to create it via init_db().")
        return

    print(f"Migrating {DB_PATH} …")
    conn = sqlite3.connect(DB_PATH)
    try:
        migrate(conn)
    finally:
        conn.close()

    print("\nDone. Run the data loader next:")
    print("  python data/load_synthetic_data.py")


if __name__ == "__main__":
    main()
