"""Auth helpers — password hashing + session current-user.

Uses the `bcrypt` library directly (not passlib) — passlib 1.7.4 is
incompatible with bcrypt 5.x and crashes at import-time backend detection.
"""
from __future__ import annotations
import os
import bcrypt
from fastapi import Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from models import User


def hash_password(plain: str) -> str:
    # bcrypt has a hard 72-byte limit; truncate defensively.
    pw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        pw = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.get(User, uid)


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency: redirect to /login if not authenticated."""
    user = get_current_user(request, db)
    if user is None:
        raise _LoginRedirect()
    return user


class _LoginRedirect(Exception):
    pass


def ensure_default_admin(db: Session) -> None:
    """Create default admin account on first run if no users exist."""
    if db.query(User).count() == 0:
        from database import now_str
        db.add(User(
            username="admin",
            name="管理員",
            # 雲端可用環境變數 ADMIN_PASSWORD 指定初始密碼；沒設就用預設（本機用）
            password=hash_password(os.getenv("ADMIN_PASSWORD") or "admin1234"),
            is_active=True,
            created_at=now_str(),
        ))
        db.commit()
