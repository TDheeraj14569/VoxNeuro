"""SQLite database engine, connection management, and versioned migration runner."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voxneuro.config import PROJECT_ROOT

DEFAULT_DB_DIR = PROJECT_ROOT / "workspace"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "voxneuro_research.db"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled and Row factory configured."""
    target_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    if target_path != Path(":memory:"):
        target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for atomic database transactions with automatic rollback on error."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _split_sql_script(script: str) -> list[str]:
    """Split a SQL script into individual statements safely, respecting quotes and comments."""
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    quote_char = ""

    for line in script.splitlines():
        trimmed = line.strip()
        if not in_string and (trimmed.startswith("--") or not trimmed):
            continue
        for char in line:
            if char in ("'", '"'):
                if not in_string:
                    in_string = True
                    quote_char = char
                elif quote_char == char:
                    in_string = False
                    quote_char = ""
                current.append(char)
            elif char == ";" and not in_string:
                statements.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        current.append("\n")

    remainder = "".join(current).strip()
    if remainder:
        statements.append(remainder)
    return [s for s in statements if s]


def get_applied_migrations(conn: sqlite3.Connection) -> set[int]:
    """Retrieve set of migration version integers that have already been applied."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations';"
    )
    if not cursor.fetchone():
        return set()

    cursor.execute("SELECT version FROM schema_migrations;")
    return {row["version"] for row in cursor.fetchall()}


def run_migrations(
    db_path: Path | str | None = None, migrations_dir: Path | None = None
) -> list[str]:
    """Apply any pending SQL migrations in ascending numeric order atomically."""
    mig_dir = migrations_dir or MIGRATIONS_DIR
    if not mig_dir.is_dir():
        raise FileNotFoundError(f"Migrations directory not found: {mig_dir}")

    migration_files = sorted(mig_dir.glob("*.sql"))
    if not migration_files:
        raise FileNotFoundError(f"No SQL migration files found in {mig_dir}")

    applied_names: list[str] = []
    conn = get_connection(db_path)
    try:
        # Ensure migration tracking table exists atomically
        with transaction(conn):
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
                """
            )

        already_applied = get_applied_migrations(conn)

        for file_path in migration_files:
            prefix = file_path.name.split("_")[0]
            try:
                version = int(prefix)
            except ValueError:
                continue

            if version in already_applied:
                continue

            sql_content = file_path.read_text(encoding="utf-8")
            now_iso = datetime.now(UTC).isoformat()

            # Atomically apply all statements in the migration file
            try:
                conn.execute("BEGIN IMMEDIATE;")
                for stmt in _split_sql_script(sql_content):
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                    (version, file_path.name, now_iso),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

            applied_names.append(file_path.name)
    finally:
        conn.close()

    return applied_names


def check_schema_integrity(db_path: Path | str | None = None) -> dict[str, Any]:
    """Execute SQLite integrity check and foreign key check."""
    conn = get_connection(db_path)
    try:
        integrity_cursor = conn.execute("PRAGMA integrity_check;")
        integrity_rows = [row[0] for row in integrity_cursor.fetchall()]

        fk_cursor = conn.execute("PRAGMA foreign_key_check;")
        fk_violations = [dict(row) for row in fk_cursor.fetchall()]

        tables_cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = [row["name"] for row in tables_cursor.fetchall()]

        is_clean = (integrity_rows == ["ok"]) and (len(fk_violations) == 0)
        return {
            "clean": is_clean,
            "integrity_check": integrity_rows,
            "foreign_key_violations": fk_violations,
            "tables": tables,
        }
    finally:
        conn.close()
