from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import User, Project, WritingProgress
from helpers import badge_style, DONE_STATUSES

router = APIRouter(prefix="/writing")
templates = Jinja2Templates(directory="templates")

W_BG = {
    "未開始":    ("#F1F5F9", "#CBD5E1"),
    "撰寫中":    ("#EFF6FF", "#BFDBFE"),
    "待客戶資料": ("#FFFBEB", "#FDE68A"),
    "待審稿":    ("#FFF7ED", "#FED7AA"),
    "已完成":    ("#DCFCE7", "#86EFAC"),
}


@router.get("", response_class=HTMLResponse)
def index(request: Request,
          pid: int = 0,
          user: User = Depends(require_user),
          db: Session = Depends(get_db)):
    active = (db.query(Project)
                .filter(~Project.status.in_(DONE_STATUSES))
                .order_by(Project.updated_at.desc())
                .all())
    selected = db.get(Project, pid) if pid else (active[0] if active else None)
    sections = []
    if selected:
        sections = (db.query(WritingProgress)
                      .filter_by(project_id=selected.id)
                      .order_by(WritingProgress.id)
                      .all())
    done_n = sum(1 for s in sections if s.status == "已完成")
    return templates.TemplateResponse(request, "writing/index.html", {
        "request": request, "user": user,
        "active_projects": active,
        "selected": selected,
        "sections": sections,
        "done_n": done_n,
        "w_bg": W_BG,
        "badge_style": badge_style,
    })


@router.post("/save")
def save(request: Request,
         pid: int = Form(...),
         user: User = Depends(require_user),
         db: Session = Depends(get_db)):
    sections = db.query(WritingProgress).filter_by(project_id=pid).all()
    ts = now_str()
    for sec in sections:
        sid = sec.id
        done    = request.form  # accessed below via sync workaround
    return RedirectResponse(f"/writing?pid={pid}", status_code=303)


@router.post("/save-sections")
async def save_sections(request: Request,
                        user: User = Depends(require_user),
                        db: Session = Depends(get_db)):
    form = await request.form()
    pid  = int(form.get("pid", 0))
    sections = db.query(WritingProgress).filter_by(project_id=pid).all()
    ts = now_str()
    for sec in sections:
        sid = sec.id
        sec.status             = "已完成" if form.get(f"done_{sid}") else "未開始"
        sec.blocker            = form.get(f"blocker_{sid}", "") or ""
        sec.needs_client_data  = form.get(f"needs_{sid}", "") or ""
        sec.estimated_completion = form.get(f"est_{sid}", "") or ""
        sec.updated_at         = ts
    db.commit()
    return RedirectResponse(f"/writing?pid={pid}", status_code=303)
