from collections import Counter
from datetime import date
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from auth import require_user
from models import User, Project
from helpers import fmt_money, badge_style, parse_date, DONE_STATUSES

router = APIRouter(prefix="/analytics")
templates = Jinja2Templates(directory="templates")

# Pipeline order (mirror of projects.PIPELINE_STAGES)
STAGE_ORDER = ["已洽談", "已提供合約", "撰寫中", "書面審查", "簡報審查", "待核定", "獲補助"]
STAGE_COLORS = {
    "已洽談": "#9CA3AF", "已提供合約": "#60A5FA", "撰寫中": "#34D399",
    "書面審查": "#FBBF24", "簡報審查": "#F97316", "待核定": "#A78BFA", "獲補助": "#4ADE80",
}


@router.get("", response_class=HTMLResponse)
def analytics(request: Request,
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    projects = db.query(Project).all()
    total = len(projects)

    # ── Stage funnel ──
    stage_counts = Counter(p.current_stage for p in projects)
    funnel = [{"stage": s, "count": stage_counts.get(s, 0),
               "color": STAGE_COLORS.get(s, "#9CA3AF")} for s in STAGE_ORDER]
    funnel_max = max([f["count"] for f in funnel], default=0)

    # ── Win rate (獲補助) ──
    won = stage_counts.get("獲補助", 0)
    win_rate = (won / total * 100) if total else 0

    # ── Deal status (成交) ──
    deal_counts = Counter(p.deal_status for p in projects if p.deal_status)
    closed = deal_counts.get("已成交", 0)
    close_rate = (closed / total * 100) if total else 0

    # ── Subsidy type distribution ──
    sub_counts = Counter(p.subsidy_type for p in projects if p.subsidy_type)
    sub_dist = sorted(sub_counts.items(), key=lambda x: -x[1])
    sub_max = max([n for _, n in sub_dist], default=0)

    # ── Referral source ranking ──
    ref_counts = Counter(p.referred_by for p in projects if p.referred_by)
    ref_rank = sorted(ref_counts.items(), key=lambda x: -x[1])[:8]
    ref_max = max([n for _, n in ref_rank], default=0)

    # ── Financials ──
    total_subsidy = sum(p.approved_subsidy or 0 for p in projects)
    total_wfee    = sum(p.writing_fee or 0 for p in projects)

    # ── Active vs done ──
    active_n = sum(1 for p in projects if p.status not in DONE_STATUSES)

    # ── Stuck deals: active projects not updated for the longest (proxy for 卡關) ──
    today = date.today()
    stuck = []
    for p in projects:
        if p.status in DONE_STATUSES or p.current_stage == "獲補助":
            continue
        d = parse_date((p.updated_at or "")[:10])
        if d:
            stuck.append(((today - d).days, p))
    stuck.sort(key=lambda x: -x[0])
    stuck = stuck[:6]

    # ── Owner workload ──
    owner_counts = Counter(p.owner for p in projects
                           if p.owner and p.status not in DONE_STATUSES)
    owner_rank = sorted(owner_counts.items(), key=lambda x: -x[1])

    return templates.TemplateResponse(request, "analytics.html", {
        "request": request, "user": user,
        "total": total, "active_n": active_n,
        "won": won, "win_rate": win_rate,
        "closed": closed, "close_rate": close_rate,
        "funnel": funnel, "funnel_max": funnel_max,
        "sub_dist": sub_dist, "sub_max": sub_max,
        "ref_rank": ref_rank, "ref_max": ref_max,
        "total_subsidy": total_subsidy, "total_wfee": total_wfee,
        "stuck": stuck, "owner_rank": owner_rank,
        "fmt_money": fmt_money, "badge_style": badge_style,
    })
