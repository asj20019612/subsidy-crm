"""Database engine + session factory.

Dev  → SQLite (same tracker.db so existing data works immediately)
Prod → set DATABASE_URL env var to postgresql://...
"""
from __future__ import annotations
import os
from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from models import Base

# ── URL ───────────────────────────────────────────────────────────────────────
_BASE_DIR   = Path(__file__).parent.parent          # subsidy_tracker/
_SQLITE_URL = f"sqlite:///{_BASE_DIR}/data/tracker.db"
DATABASE_URL = os.getenv("DATABASE_URL", _SQLITE_URL)

# Railway PostgreSQL fix (postgres:// → postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ── Engine ────────────────────────────────────────────────────────────────────
_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=False,
)

# Enable WAL mode + foreign keys for SQLite
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(conn, _rec):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency — yields a DB session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (safe to call multiple times — skips existing tables)."""
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Idempotent column additions for existing databases (no data loss)."""
    # New columns added to `clients` after initial release.
    _add_columns_if_missing("clients", {
        "referred_by":       "TEXT DEFAULT ''",
        "referral_relation": "TEXT DEFAULT ''",
    })
    # Attachment can also belong to a contract.
    _add_columns_if_missing("attachments", {
        "contract_id": "INTEGER",
    })


def _add_columns_if_missing(table: str, columns: dict[str, str]):
    insp_sql = text(f"PRAGMA table_info({table})") if _is_sqlite \
        else text("SELECT column_name FROM information_schema.columns WHERE table_name=:t")
    with engine.begin() as conn:
        if _is_sqlite:
            existing = {row[1] for row in conn.execute(insp_sql)}
        else:
            existing = {row[0] for row in conn.execute(insp_sql, {"t": table})}
        for col, ddl in columns.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


def now_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
