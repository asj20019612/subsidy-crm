from datetime import date, timedelta
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import (User, Project, ProjectTask, ProjectDocument, Setting,
                    SubsidyProgram, ProgramTask, ProgramDocument, ConsultantProfile)
from helpers import parse_date, badge_style, phase_color, DEFAULT_PHASES

router = APIRouter(prefix="/projects")
overview_router = APIRouter(prefix="/gantt")
templates = Jinja2Templates(directory="templates")


def get_phases(db) -> list:
    """統一設定的工作階段（系統設定 → 下拉選單 → 工作階段）。"""
    rows = (db.query(Setting).filter_by(category="工作階段", is_active=1)
              .order_by(Setting.sort_order, Setting.id).all())
    return [r.value for r in rows] or list(DEFAULT_PHASES)

DOC_STATUS = ["未繳", "已繳", "不需要"]
PROVIDERS  = ["客戶", "我方"]


def _tasks(db, pid):
    return (db.query(ProjectTask).filter_by(project_id=pid)
              .order_by(ProjectTask.sort_order, ProjectTask.id).all())


def _docs(db, pid):
    return (db.query(ProjectDocument).filter_by(project_id=pid)
              .order_by(ProjectDocument.sort_order, ProjectDocument.id).all())


# ── Execution page ────────────────────────────────────────────────────────────

@router.get("/{pid}/execution", response_class=HTMLResponse)
def execution(pid: int, request: Request,
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        return RedirectResponse("/projects", status_code=302)

    tasks = _tasks(db, pid)
    docs  = _docs(db, pid)

    # Gantt window (min start → max due)
    starts = [parse_date(t.start_date) for t in tasks if parse_date(t.start_date)]
    dues   = [parse_date(t.due_date)   for t in tasks if parse_date(t.due_date)]
    gantt_min = min(starts) if starts else None
    gantt_max = max(dues)   if dues   else None
    # pad a few days each side & ensure a sane window
    if gantt_min and gantt_max:
        gantt_min = gantt_min - timedelta(days=2)
        gantt_max = gantt_max + timedelta(days=2)
        span_days = (gantt_max - gantt_min).days + 1
    else:
        span_days = 0

    # does this project's program have a template?
    prog = (db.query(SubsidyProgram)
              .filter(SubsidyProgram.name == p.subsidy_type).first())
    has_template = False
    if prog:
        has_template = (db.query(ProgramTask).filter_by(program_id=prog.id).count() > 0
                        or db.query(ProgramDocument).filter_by(program_id=prog.id).count() > 0)

    doc_done = sum(1 for d in docs if d.status == "已繳")
    doc_need = sum(1 for d in docs if d.status != "不需要")
    task_avg = round(sum(t.progress or 0 for t in tasks) / len(tasks)) if tasks else 0

    return templates.TemplateResponse(request, "projects/execution.html", {
        "request": request, "user": user, "project": p,
        "tasks": tasks, "docs": docs,
        "gantt_min": gantt_min, "gantt_max": gantt_max, "span_days": span_days,
        "today": date.today(),
        "doc_status": DOC_STATUS, "providers": PROVIDERS,
        "has_template": has_template, "program_name": p.subsidy_type,
        "doc_done": doc_done, "doc_need": doc_need, "task_avg": task_avg,
        "parse_date": parse_date, "badge_style": badge_style, "timedelta": timedelta,
        "phases": get_phases(db), "phase_color": phase_color,
    })


# ── Tasks CRUD ────────────────────────────────────────────────────────────────

@router.post("/{pid}/tasks/add")
def task_add(pid: int,
             name: str       = Form(""),
             phase: str      = Form(""),
             start_date: str = Form(""),
             due_date: str   = Form(""),
             owner: str      = Form(""),
             user: User = Depends(require_user),
             db: Session = Depends(get_db)):
    if name.strip():
        ts = now_str()
        maxo = db.query(ProjectTask).filter_by(project_id=pid).count()
        db.add(ProjectTask(project_id=pid, name=name.strip(), phase=phase,
                           start_date=start_date, due_date=due_date, owner=owner,
                           progress=0, sort_order=maxo, created_at=ts, updated_at=ts))
        db.commit()
    return RedirectResponse(f"/projects/{pid}/execution", status_code=303)


@router.post("/{pid}/tasks/{tid}/edit")
def task_edit(pid: int, tid: int,
              name: str       = Form(""),
              phase: str      = Form(""),
              start_date: str = Form(""),
              due_date: str   = Form(""),
              progress: str   = Form("0"),
              owner: str      = Form(""),
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    t = db.get(ProjectTask, tid)
    if t and t.project_id == pid:
        t.name = name.strip(); t.phase = phase
        t.start_date = start_date; t.due_date = due_date
        try: t.progress = max(0, min(100, int(float(progress or 0))))
        except Exception: t.progress = 0
        t.owner = owner; t.updated_at = now_str()
        db.commit()
    return RedirectResponse(f"/projects/{pid}/execution", status_code=303)


@router.post("/{pid}/tasks/{tid}/delete")
def task_delete(pid: int, tid: int,
                user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    t = db.get(ProjectTask, tid)
    if t and t.project_id == pid:
        db.delete(t); db.commit()
    return RedirectResponse(f"/projects/{pid}/execution", status_code=303)


# ── Gantt drag: update dates / progress via fetch (JSON) ──────────────────────

@router.post("/{pid}/tasks/{tid}/move")
def task_move(pid: int, tid: int,
              start_date: str = Form(""),
              due_date: str   = Form(""),
              progress: str   = Form(""),
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    t = db.get(ProjectTask, tid)
    if not t or t.project_id != pid:
        return JSONResponse({"ok": False}, status_code=404)
    if start_date: t.start_date = start_date
    if due_date:   t.due_date   = due_date
    if progress != "":
        try: t.progress = max(0, min(100, int(float(progress))))
        except Exception: pass
    t.updated_at = now_str()
    db.commit()
    return JSONResponse({"ok": True})


# ── Documents CRUD ────────────────────────────────────────────────────────────

@router.post("/{pid}/docs/add")
def doc_add(pid: int,
            name: str     = Form(""),
            provider: str = Form("客戶"),
            due_date: str = Form(""),
            user: User = Depends(require_user),
            db: Session = Depends(get_db)):
    if name.strip():
        ts = now_str()
        maxo = db.query(ProjectDocument).filter_by(project_id=pid).count()
        db.add(ProjectDocument(project_id=pid, name=name.strip(), provider=provider,
                               status="未繳", due_date=due_date, sort_order=maxo,
                               created_at=ts, updated_at=ts))
        db.commit()
    return RedirectResponse(f"/projects/{pid}/execution", status_code=303)


@router.post("/{pid}/docs/{did}/status")
def doc_status(pid: int, did: int,
               status: str = Form(""),
               user: User = Depends(require_user),
               db: Session = Depends(get_db)):
    d = db.get(ProjectDocument, did)
    if d and d.project_id == pid and status in DOC_STATUS:
        d.status = status; d.updated_at = now_str()
        db.commit()
    return RedirectResponse(f"/projects/{pid}/execution", status_code=303)


@router.post("/{pid}/docs/{did}/delete")
def doc_delete(pid: int, did: int,
               user: User = Depends(require_user),
               db: Session = Depends(get_db)):
    d = db.get(ProjectDocument, did)
    if d and d.project_id == pid:
        db.delete(d); db.commit()
    return RedirectResponse(f"/projects/{pid}/execution", status_code=303)


# ── Apply program template ────────────────────────────────────────────────────

@router.post("/{pid}/apply-template")
def apply_template(pid: int,
                   start_date: str = Form(""),
                   user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        return RedirectResponse("/projects", status_code=302)
    prog = db.query(SubsidyProgram).filter(SubsidyProgram.name == p.subsidy_type).first()
    if not prog:
        return RedirectResponse(f"/projects/{pid}/execution", status_code=303)

    base = parse_date(start_date) or date.today()
    ts = now_str()

    # tasks
    t_templates = (db.query(ProgramTask).filter_by(program_id=prog.id)
                     .order_by(ProgramTask.sort_order, ProgramTask.id).all())
    base_order = db.query(ProjectTask).filter_by(project_id=pid).count()
    for i, tt in enumerate(t_templates):
        s = base + timedelta(days=tt.offset_days or 0)
        e = s + timedelta(days=max(0, (tt.duration or 1) - 1))
        db.add(ProjectTask(project_id=pid, name=tt.name, phase=tt.phase,
                           start_date=s.isoformat(), due_date=e.isoformat(),
                           progress=0, sort_order=base_order + i,
                           created_at=ts, updated_at=ts))

    # documents
    d_templates = (db.query(ProgramDocument).filter_by(program_id=prog.id)
                     .order_by(ProgramDocument.sort_order, ProgramDocument.id).all())
    base_dorder = db.query(ProjectDocument).filter_by(project_id=pid).count()
    for i, dt in enumerate(d_templates):
        db.add(ProjectDocument(project_id=pid, name=dt.name, provider=dt.provider,
                               status="未繳", sort_order=base_dorder + i,
                               created_at=ts, updated_at=ts))

    db.commit()
    return RedirectResponse(f"/projects/{pid}/execution", status_code=303)


# ══════════════════════════════════════════════════════════════════════════════
# 甘特圖總覽（側邊欄入口）：所有案件一覽，點進去看甘特圖 / 產出客戶圖片
# ══════════════════════════════════════════════════════════════════════════════

@overview_router.get("", response_class=HTMLResponse)
def gantt_overview(request: Request,
                   q: str = "",
                   user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    qry = db.query(Project)
    if q:
        qry = qry.filter(Project.client_name.ilike(f"%{q}%") |
                         Project.project_name.ilike(f"%{q}%"))
    projects = qry.order_by(Project.id.desc()).all()
    rows = []
    for p in projects:
        ts = _tasks(db, p.id)
        starts = [parse_date(t.start_date) for t in ts if parse_date(t.start_date)]
        dues   = [parse_date(t.due_date)   for t in ts if parse_date(t.due_date)]
        rows.append({
            "p": p, "n": len(ts),
            "avg": round(sum(t.progress or 0 for t in ts) / len(ts)) if ts else 0,
            "start": min(starts).isoformat() if starts else "",
            "end":   max(dues).isoformat()   if dues   else "",
        })
    return templates.TemplateResponse(request, "projects/gantt_overview.html", {
        "request": request, "user": user, "rows": rows, "q": q,
        "badge_style": badge_style,
    })


# ══════════════════════════════════════════════════════════════════════════════
# 客戶圖片版甘特圖：乾淨、可直接下載成 PNG 給客戶看
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{pid}/gantt-share", response_class=HTMLResponse)
def gantt_share(pid: int, request: Request,
                user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        return RedirectResponse("/gantt", status_code=302)
    phases = get_phases(db)
    tasks = [t for t in _tasks(db, pid) if parse_date(t.start_date) and parse_date(t.due_date)]
    tasks.sort(key=lambda t: (parse_date(t.start_date), t.sort_order, t.id))

    rows, months, weeks, today_pct, span = [], [], [], None, 0
    gmin = gmax = None
    if tasks:
        gmin = min(parse_date(t.start_date) for t in tasks)
        gmax = max(parse_date(t.due_date)   for t in tasks)
        # 左右各留一點空白；起點對齊到該週週一，圖比較整齊
        gmin = gmin - timedelta(days=gmin.weekday())
        gmax = gmax + timedelta(days=(6 - gmax.weekday()))
        span = (gmax - gmin).days + 1

        def pct(d):  # 日期 → 百分比位置
            return (d - gmin).days / span * 100

        for t in tasks:
            s_, e_ = parse_date(t.start_date), parse_date(t.due_date)
            fg, bg, bd = phase_color(t.phase, phases)
            rows.append({
                "t": t, "fg": fg, "bg": bg, "bd": bd,
                "left": pct(s_), "width": ((e_ - s_).days + 1) / span * 100,
                "label": f"{s_.month}/{s_.day} – {e_.month}/{e_.day}",
            })
        # 月份表頭
        cur = gmin
        while cur <= gmax:
            nxt = (cur.replace(day=1) + timedelta(days=32)).replace(day=1)
            end = min(nxt - timedelta(days=1), gmax)
            months.append({"name": f"{cur.year} / {cur.month} 月" if (cur == gmin or cur.month == 1)
                                   else f"{cur.month} 月",
                           "left": pct(cur), "width": ((end - cur).days + 1) / span * 100})
            cur = nxt
        # 週格線
        d = gmin
        while d <= gmax:
            weeks.append({"left": pct(d), "label": f"{d.month}/{d.day}"})
            d += timedelta(days=7)
        td = date.today()
        if gmin <= td <= gmax:
            today_pct = pct(td) + 0.5 / span * 100

    used = []
    for t in tasks:
        if t.phase and t.phase not in used:
            used.append(t.phase)
    legend = [{"name": n, "fg": phase_color(n, phases)[0], "bg": phase_color(n, phases)[1],
               "bd": phase_color(n, phases)[2]} for n in used]
    avg = round(sum(t.progress or 0 for t in tasks) / len(tasks)) if tasks else 0
    prof = db.query(ConsultantProfile).first()

    return templates.TemplateResponse(request, "projects/gantt_share.html", {
        "request": request, "project": p, "rows": rows, "months": months, "weeks": weeks,
        "today_pct": today_pct, "legend": legend, "avg": avg,
        "range_start": gmin, "range_end": gmax,
        "consultant": (prof.name if prof and prof.name else ""),
        "today": date.today(),
    })
