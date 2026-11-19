import calendar as _cal
from datetime import date
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from auth import require_user
from models import User, Project
from helpers import parse_date, badge_style, DONE_STATUSES

router = APIRouter(prefix="/calendar")
templates = Jinja2Templates(directory="templates")

_cal.setfirstweekday(_cal.SUNDAY)
WEEKDAY_LABELS = ["日", "一", "二", "三", "四", "五", "六"]


@router.get("", response_class=HTMLResponse)
def calendar_view(request: Request,
                  year: int = 0, month: int = 0,
                  user: User = Depends(require_user),
                  db: Session = Depends(get_db)):
    today = date.today()
    if not year:  year = today.year
    if not month: month = today.month
    # normalise out-of-range months
    if month < 1:  year -= 1; month = 12
    if month > 12: year += 1; month = 1

    projects = db.query(Project).all()

    # Bucket deadlines by ISO date string within this month
    prefix = f"{year:04d}-{month:02d}"
    submissions: dict[str, list] = {}   # 送件截止日 (critical)
    next_actions: dict[str, list] = {}  # 下一步到期日

    for p in projects:
        if p.status in DONE_STATUSES:
            continue
        sd = (p.submission_deadline or "").strip()
        nd = (p.next_deadline or "").strip()
        if sd.startswith(prefix):
            submissions.setdefault(sd, []).append(p)
        if nd.startswith(prefix):
            next_actions.setdefault(nd, []).append(p)

    weeks = _cal.monthcalendar(year, month)  # list[list[int]], 0 = padding

    # Upcoming submission deadlines (next 30 days, any month) for the side list
    upcoming = []
    for p in projects:
        if p.status in DONE_STATUSES:
            continue
        d = parse_date(p.submission_deadline)
        if d and 0 <= (d - today).days <= 30:
            upcoming.append((d, p))
    upcoming.sort(key=lambda x: x[0])

    return templates.TemplateResponse(request, "calendar.html", {
        "request": request, "user": user,
        "year": year, "month": month,
        "weeks": weeks,
        "weekday_labels": WEEKDAY_LABELS,
        "submissions": submissions,
        "next_actions": next_actions,
        "today": today,
        "today_iso": today.isoformat(),
        "prev_year": year if month > 1 else year - 1,
        "prev_month": month - 1 if month > 1 else 12,
        "next_year": year if month < 12 else year + 1,
        "next_month": month + 1 if month < 12 else 1,
        "upcoming": upcoming,
        "badge_style": badge_style,
    })
