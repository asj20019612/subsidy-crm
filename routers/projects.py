from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import User, Project, Client, WritingProgress, Setting
from helpers import badge_style, days_until, is_overdue, DONE_STATUSES, fmt_money

router = APIRouter(prefix="/projects")
templates = Jinja2Templates(directory="templates")

# Ordered pipeline stages (displayed as kanban columns)
PIPELINE_STAGES = [
    "已洽談", "已提供合約", "撰寫中",
    "書面審查", "簡報審查", "待核定", "獲補助",
]

# Stage accent colours for kanban column headers
STAGE_COLORS = {
    "已洽談":     "#9A948A",
    "已提供合約": "#2E4C6B",
    "撰寫中":     "#35655F",
    "書面審查":   "#8A6A2F",
    "簡報審查":   "#A0603C",
    "待核定":     "#5A5578",
    "獲補助":     "#3F6B52",
}


def _settings(db, cat):
    return [r.value for r in db.query(Setting)
            .filter_by(category=cat, is_active=1)
            .order_by(Setting.sort_order).all()]


def _apply_filters(qry, q, status, stage, subsidy, priority, deal_status):
    if q:
        qry = qry.filter(
            Project.client_name.ilike(f"%{q}%") |
            Project.project_name.ilike(f"%{q}%") |
            Project.next_action.ilike(f"%{q}%") |
            Project.owner.ilike(f"%{q}%")
        )
    if status:      qry = qry.filter(Project.status == status)
    if stage:       qry = qry.filter(Project.current_stage == stage)
    if subsidy:     qry = qry.filter(Project.subsidy_type == subsidy)
    if priority:    qry = qry.filter(Project.priority == priority)
    if deal_status: qry = qry.filter(Project.deal_status == deal_status)
    return qry


# ── Pipeline (default view) ───────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def list_projects(request: Request,
                  view: str = "pipeline",
                  q: str = "", status: str = "", stage: str = "",
                  subsidy: str = "", priority: str = "", deal_status: str = "",
                  user: User = Depends(require_user),
                  db: Session = Depends(get_db)):

    qry = _apply_filters(db.query(Project), q, status, stage, subsidy, priority, deal_status)
    projects = qry.order_by(Project.updated_at.desc()).all()

    filter_ctx = dict(
        q=q, sel_status=status, sel_stage=stage,
        sel_subsidy=subsidy, sel_priority=priority, sel_deal=deal_status,
        statuses=_settings(db, "狀態"),
        stages=_settings(db, "目前階段"),
        subsidy_types=_settings(db, "補助類型"),
        priorities=_settings(db, "優先級"),
        deal_statuses=_settings(db, "成交狀態"),
        badge_style=badge_style,
        days_until=days_until,
        is_overdue=is_overdue,
        DONE=DONE_STATUSES,
        fmt_money=fmt_money,
        view=view,
    )

    if view == "table":
        return templates.TemplateResponse(request, "projects/list.html", {
            "request": request, "user": user,
            "projects": projects,
            **filter_ctx,
        })

    # ── Pipeline kanban ──────────────────────────────────────────────
    grouped: dict[str, list] = {s: [] for s in PIPELINE_STAGES}
    for p in projects:
        if p.current_stage in grouped:
            grouped[p.current_stage].append(p)
        else:
            grouped.setdefault(p.current_stage, []).append(p)

    def _deal_value(p):
        if p.writing_fee:
            return p.writing_fee
        return (p.approved_subsidy or 0) * (p.success_fee_rate or 15) / 100

    stage_meta: dict[str, dict] = {}
    for s in PIPELINE_STAGES:
        projs = grouped.get(s, [])
        stage_meta[s] = {
            "count": len(projs),
            "total": sum(_deal_value(p) for p in projs),
            "color": STAGE_COLORS.get(s, "#9CA3AF"),
        }

    return templates.TemplateResponse(request, "projects/pipeline.html", {
        "request": request, "user": user,
        "grouped": grouped,
        "stage_order": PIPELINE_STAGES,
        "stage_meta": stage_meta,
        "deal_value": _deal_value,
        "total_value": sum(_deal_value(p) for p in projects),
        "total_deals": len(projects),
        "total_active": sum(1 for p in projects if p.status not in DONE_STATUSES),
        **filter_ctx,
    })


# ── Drag-and-drop stage move (JSON, called via fetch) ─────────────────────────

@router.post("/{pid}/move")
def move_stage(pid: int,
               stage: str  = Form(...),
               user: User  = Depends(require_user),
               db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if p and stage:
        p.current_stage = stage
        p.updated_at    = now_str()
        db.commit()
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False}, status_code=404)


# ── Quick stage change (form, full reload) ────────────────────────────────────

@router.post("/{pid}/change-stage")
def change_stage(pid: int,
                 current_stage: str = Form(""),
                 redirect_to: str   = Form("/projects"),
                 user: User         = Depends(require_user),
                 db: Session        = Depends(get_db)):
    p = db.get(Project, pid)
    if p and current_stage:
        p.current_stage = current_stage
        p.updated_at    = now_str()
        db.commit()
    return RedirectResponse(redirect_to, status_code=303)


# ── Quick mark contacted ──────────────────────────────────────────────────────

@router.post("/{pid}/mark-contacted")
def mark_contacted(pid: int,
                   redirect_to: str = Form("/projects"),
                   user: User       = Depends(require_user),
                   db: Session      = Depends(get_db)):
    from datetime import date
    p = db.get(Project, pid)
    if p:
        p.last_contact_date = date.today().isoformat()
        p.updated_at        = now_str()
        db.commit()
    return RedirectResponse(redirect_to, status_code=303)


# ── Extend deadline ───────────────────────────────────────────────────────────

@router.post("/{pid}/extend-deadline")
def extend_deadline(pid: int,
                    days: int        = Form(3),
                    redirect_to: str = Form("/projects"),
                    user: User       = Depends(require_user),
                    db: Session      = Depends(get_db)):
    from datetime import date, timedelta
    p = db.get(Project, pid)
    if p:
        from helpers import parse_date
        current = parse_date(p.next_deadline) or date.today()
        p.next_deadline = (current + timedelta(days=days)).isoformat()
        p.updated_at    = now_str()
        db.commit()
    return RedirectResponse(redirect_to, status_code=303)


# ── Add / Edit / Delete (unchanged) ──────────────────────────────────────────

@router.get("/add", response_class=HTMLResponse)
def add_form(request: Request,
             user: User = Depends(require_user),
             db: Session = Depends(get_db)):
    clients = db.query(Client).order_by(Client.company_name).all()
    return templates.TemplateResponse(request, "projects/form.html", {
        "request": request, "user": user, "project": None,
        "clients": clients,
        "subsidy_types": _settings(db, "補助類型"),
        "stages":        _settings(db, "目前階段"),
        "statuses":      _settings(db, "狀態"),
        "priorities":    _settings(db, "優先級"),
        "deal_statuses": _settings(db, "成交狀態"),
        "work_types":    _settings(db, "工作類型"),
        "ref_relations": _settings(db, "引薦關係"),
    })


@router.post("/add")
def add_save(request: Request,
             client_id: str        = Form(""),
             client_name: str      = Form(""),
             project_name: str     = Form(""),
             subsidy_type: str     = Form(""),
             current_stage: str    = Form("新名單"),
             status: str           = Form("未開始"),
             priority: str         = Form("中"),
             owner: str            = Form(""),
             client_contact: str   = Form(""),
             next_action: str      = Form(""),
             next_deadline: str    = Form(""),
             last_contact_date: str = Form(""),
             submission_deadline: str = Form(""),
             deal_status: str      = Form("未成交"),
             writing_fee: str      = Form("0"),
             approved_subsidy: str = Form("0"),
             success_fee_rate: str = Form("15"),
             referred_by: str      = Form(""),
             referral_relation: str = Form(""),
             notes: str            = Form(""),
             user: User            = Depends(require_user),
             db: Session           = Depends(get_db)):
    ts = now_str()
    cid = int(client_id) if client_id.isdigit() else None
    if cid:
        cl = db.get(Client, cid)
        if cl: client_name = cl.company_name
    sfr = float(success_fee_rate or 15)
    p = Project(
        client_id=cid, client_name=client_name,
        project_name=project_name, subsidy_type=subsidy_type,
        current_stage=current_stage, status=status, priority=priority,
        owner=owner, client_contact=client_contact,
        next_action=next_action, next_deadline=next_deadline,
        last_contact_date=last_contact_date,
        submission_deadline=submission_deadline,
        deal_status=deal_status,
        writing_fee=float(writing_fee or 0),
        approved_subsidy=float(approved_subsidy or 0),
        success_fee_rate=sfr,
        success_fee_s1_rate=round(sfr * 0.4, 1),
        success_fee_s2_rate=round(sfr * 0.4, 1),
        success_fee_s3_rate=round(sfr * 0.2, 1),
        referred_by=referred_by,
        referral_relation=referral_relation if referral_relation != "—" else "",
        notes=notes, created_at=ts, updated_at=ts,
    )
    db.add(p)
    db.flush()
    sections = _settings(db, "計畫書段落") or [
        "計畫架構","公司背景","市場分析","創新性","可行性",
        "執行方法","查核點/KPI","經費編列","預期效益","簡報"
    ]
    for sec in sections:
        db.add(WritingProgress(project_id=p.id, section_name=sec, updated_at=ts))
    db.commit()
    return RedirectResponse("/projects", status_code=303)


@router.get("/{pid}/edit", response_class=HTMLResponse)
def edit_form(pid: int, request: Request,
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        return RedirectResponse("/projects", status_code=302)
    clients = db.query(Client).order_by(Client.company_name).all()
    from routers.files import attachments_for_project
    return templates.TemplateResponse(request, "projects/form.html", {
        "request": request, "user": user, "project": p,
        "clients": clients,
        "attachments": attachments_for_project(db, pid),
        "subsidy_types": _settings(db, "補助類型"),
        "stages":        _settings(db, "目前階段"),
        "statuses":      _settings(db, "狀態"),
        "priorities":    _settings(db, "優先級"),
        "deal_statuses": _settings(db, "成交狀態"),
        "work_types":    _settings(db, "工作類型"),
        "ref_relations": _settings(db, "引薦關係"),
    })


@router.post("/{pid}/edit")
def edit_save(pid: int,
              client_id: str        = Form(""),
              client_name: str      = Form(""),
              project_name: str     = Form(""),
              subsidy_type: str     = Form(""),
              current_stage: str    = Form(""),
              status: str           = Form(""),
              priority: str         = Form(""),
              owner: str            = Form(""),
              client_contact: str   = Form(""),
              next_action: str      = Form(""),
              next_deadline: str    = Form(""),
              last_contact_date: str = Form(""),
              submission_deadline: str = Form(""),
              deal_status: str      = Form(""),
              writing_fee: str      = Form("0"),
              writing_fee_paid: str = Form("0"),
              approved_subsidy: str = Form("0"),
              success_fee_s1_rate: str = Form("6"),
              success_fee_s2_rate: str = Form("6"),
              success_fee_s3_rate: str = Form("3"),
              success_fee_s1_paid: str = Form("0"),
              success_fee_s2_paid: str = Form("0"),
              success_fee_s3_paid: str = Form("0"),
              referred_by: str      = Form(""),
              referral_relation: str = Form(""),
              notes: str            = Form(""),
              user: User            = Depends(require_user),
              db: Session           = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        return RedirectResponse("/projects", status_code=302)
    cid = int(client_id) if client_id.isdigit() else None
    if cid:
        cl = db.get(Client, cid)
        if cl: client_name = cl.company_name
    s1r = float(success_fee_s1_rate or 6)
    s2r = float(success_fee_s2_rate or 6)
    s3r = float(success_fee_s3_rate or 3)
    p.client_id=cid; p.client_name=client_name; p.project_name=project_name
    p.subsidy_type=subsidy_type; p.current_stage=current_stage; p.status=status
    p.priority=priority; p.owner=owner; p.client_contact=client_contact
    p.next_action=next_action; p.next_deadline=next_deadline
    p.last_contact_date=last_contact_date; p.submission_deadline=submission_deadline
    p.deal_status=deal_status
    p.writing_fee=float(writing_fee or 0); p.writing_fee_paid=float(writing_fee_paid or 0)
    p.approved_subsidy=float(approved_subsidy or 0)
    p.success_fee_s1_rate=s1r; p.success_fee_s2_rate=s2r; p.success_fee_s3_rate=s3r
    p.success_fee_rate=s1r+s2r+s3r
    p.success_fee_s1_paid=float(success_fee_s1_paid or 0)
    p.success_fee_s2_paid=float(success_fee_s2_paid or 0)
    p.success_fee_s3_paid=float(success_fee_s3_paid or 0)
    p.referred_by=referred_by
    p.referral_relation=referral_relation if referral_relation != "—" else ""
    p.notes=notes; p.updated_at=now_str()
    db.commit()
    return RedirectResponse("/projects", status_code=303)


@router.post("/{pid}/delete")
def delete_project(pid: int,
                   user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if p:
        from models import (ProjectTask, ProjectDocument, PaymentLog,
                            Attachment, Opportunity)
        from routers.files import UPLOAD_DIR
        # 先清掉掛在案件底下的資料，否則外鍵限制會讓刪除失敗（500）
        db.query(ProjectTask).filter_by(project_id=pid).delete()
        db.query(ProjectDocument).filter_by(project_id=pid).delete()
        db.query(PaymentLog).filter_by(project_id=pid).delete()
        for a in db.query(Attachment).filter_by(project_id=pid).all():
            try: (UPLOAD_DIR / a.filename).unlink(missing_ok=True)
            except Exception: pass
            db.delete(a)
        # 商機只解除「已轉案」關聯，不刪商機
        db.query(Opportunity).filter_by(converted_project_id=pid).update(
            {"converted_project_id": None})
        db.delete(p)   # 計畫書進度、聯繫紀錄由 cascade 一併刪除
        db.commit()
    return RedirectResponse("/projects", status_code=303)
