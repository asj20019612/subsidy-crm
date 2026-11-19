"""FastAPI entry point."""
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from database import init_db, SessionLocal
from auth import ensure_default_admin, _LoginRedirect
from helpers import badge_style, fmt_money, days_until, is_overdue
from routers import (auth_router, dashboard, projects, clients,
                     settings_router, files, programs, execution, contracts,
                     opportunities)
# 已停用（選單移除，程式保留供日後恢復）：writing, contacts, finance, calendar_router, analytics

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="補助顧問管理系統")

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please-use-long-random-string")
# 雲端（有設 DATABASE_URL）一定要自己設密鑰，否則別人能偽造登入
if os.getenv("DATABASE_URL") and SECRET_KEY.startswith("change-me"):
    raise RuntimeError("雲端環境必須設定 SECRET_KEY 環境變數")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400 * 30)

BASE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE / "templates"))

# Register Jinja2 globals
templates.env.globals["badge_style"] = badge_style
templates.env.globals["fmt_money"]   = fmt_money
templates.env.globals["days_until"]  = days_until
templates.env.globals["is_overdue"]  = is_overdue

# Dynamic date (evaluated at each request via a callable)
from datetime import date as _date
def _now_date():
    d = _date.today()
    return f"{d.year} 年 {d.month} 月 {d.day} 日"

templates.env.globals["now_date"] = _now_date()

from routers.files import human_size as _human_size
templates.env.globals["human_size"] = _human_size


# ── Exception handler for login redirect ──────────────────────────────────────
@app.exception_handler(_LoginRedirect)
async def login_redirect_handler(request: Request, exc: _LoginRedirect):
    return RedirectResponse("/login", status_code=302)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
        from routers.programs import seed_programs
        seed_programs(db)
        from routers.settings_router import seed_phases
        seed_phases(db)
    finally:
        db.close()


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(dashboard.router)
app.include_router(opportunities.router)
app.include_router(projects.router)
app.include_router(clients.router)
app.include_router(contracts.router)
app.include_router(files.router)
app.include_router(programs.router)
app.include_router(execution.router)
app.include_router(execution.overview_router)
app.include_router(settings_router.router)
# 已停用：writing / contacts / finance / calendar_router / analytics
