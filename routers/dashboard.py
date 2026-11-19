from datetime import date
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import User, Project, ConsultantProfile
from helpers import DONE_STATUSES, days_until, days_since, is_overdue, badge_style

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# How many days of silence before a "waiting" item is flagged for follow-up
FOLLOWUP_DAYS = 3


def _build_groups(projects: list[Project]) -> dict:
    def active(p): return p.status not in DONE_STATUSES

    def overdue(p):
        return active(p) and is_overdue(p.next_deadline, p.status)

    def due_today(p):
        d = days_until(p.next_deadline)
        return active(p) and d == 0

    def due_week(p):
        d = days_until(p.next_deadline)
        return active(p) and d is not None and 1 <= d <= 7

    def no_contact(p):
        ds = days_since(p.last_contact_date)
        return active(p) and p.status in {"進行中", "需追蹤"} and (ds is None or ds > 7)

    def waiting(p):
        # 等待對方回覆（不分階段）
        return active(p) and p.status == "等待對方"

    def quoted(p):
        return p.deal_status == "已報價" and p.status not in DONE_STATUSES

    groups = [
        ("today",   "🔴 今日到期",       "#DC2626", [p for p in projects if due_today(p)]),
        ("overdue", "🚨 已逾期",         "#DC2626", [p for p in projects if overdue(p)]),
        ("week",    "🟡 7 天內到期",     "#D97706", [p for p in projects if due_week(p)]),
        ("contact", "📞 超過 7 天未聯絡", "#6D28D9", [p for p in projects if no_contact(p)]),
        ("waiting", "⏳ 等待客戶回覆",    "#0284C7", [p for p in projects if waiting(p)]),
        ("quoted",  "💼 已報價未成交",   "#15803D", [p for p in projects if quoted(p)]),
    ]
    return groups


def _followup_message(p: Project, consultant_name: str) -> str:
    """Build a polite, copy-paste-ready follow-up message for a client."""
    contact = (p.client_contact or p.client_name or "您好").strip()
    ds = days_since(p.last_contact_date)

    lines = [f"{contact} 您好：", ""]
    body = f"想跟您確認一下「{p.project_name}」一案的進度，"
    if ds is not None and ds > 0:
        body += f"距離上次聯繫已 {ds} 天，"
    if p.next_action:
        body += f"關於「{p.next_action}」不曉得目前是否方便提供或回覆？"
    else:
        body += "不曉得目前是否方便回覆？"
    lines.append(body)
    lines.append("")
    lines.append("如有任何需要我們協助的地方，都歡迎隨時與我聯繫，謝謝您！")
    lines.append("")
    if consultant_name:
        lines.append(f"{consultant_name} 敬上")
    return "\n".join(lines)


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request,
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    projects = (db.query(Project)
                  .order_by(Project.next_deadline)
                  .all())
    groups   = _build_groups(projects)
    counts   = {g[0]: len(g[3]) for g in groups}

    prof = db.query(ConsultantProfile).first()
    consultant_name = prof.name if prof else ""
    followups = {p.id: _followup_message(p, consultant_name) for p in projects}

    return templates.TemplateResponse(request, "dashboard.html", {
        "request": request,
        "user": user,
        "groups": groups,
        "counts": counts,
        "today": date.today(),
        "days_until": days_until,
        "days_since": days_since,
        "badge_style": badge_style,
        "followups": followups,
        "followup_days": FOLLOWUP_DAYS,
        "DONE": DONE_STATUSES,
    })


@router.post("/projects/{pid}/quick-update")
def quick_update(pid: int,
                 current_stage: str  = Form(""),
                 status: str         = Form(""),
                 next_action: str    = Form(""),
                 next_deadline: str  = Form(""),
                 last_contact_date: str = Form(""),
                 user: User          = Depends(require_user),
                 db: Session         = Depends(get_db)):
    p = db.get(Project, pid)
    if p:
        p.current_stage     = current_stage
        p.status            = status
        p.next_action       = next_action
        p.next_deadline     = next_deadline
        p.last_contact_date = last_contact_date
        p.updated_at        = now_str()
        db.commit()
    return RedirectResponse("/", status_code=303)
