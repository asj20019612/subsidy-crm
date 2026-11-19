from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import User, SubsidyProgram, ProgramTask, ProgramDocument

router = APIRouter(prefix="/programs")
templates = Jinja2Templates(directory="templates")


# ── Seed a few common programs on first run (names only — content filled by user) ──
SEED = [
    {"name": "SBIR", "full_name": "小型企業創新研發計畫", "agency": "經濟部產業技術司",
     "purpose": "鼓勵國內中小企業從事創新技術或產品研發，提升技術能力與市場競爭力。"},
    {"name": "CITD", "full_name": "協助傳統產業技術開發計畫", "agency": "經濟部產業發展署",
     "purpose": "協助傳統產業及中小企業進行產品、技術、設計或品牌之創新開發。"},
    {"name": "SITI", "full_name": "", "agency": "",
     "purpose": ""},
    {"name": "台北市產發局", "full_name": "臺北市產業發展獎勵補助", "agency": "臺北市政府產業發展局",
     "purpose": ""},
]


def seed_programs(db: Session):
    if db.query(SubsidyProgram).count() == 0:
        ts = now_str()
        for i, s in enumerate(SEED):
            db.add(SubsidyProgram(sort_order=i, created_at=ts, updated_at=ts, **s))
        db.commit()


@router.get("", response_class=HTMLResponse)
def list_programs(request: Request,
                  user: User = Depends(require_user),
                  db: Session = Depends(get_db)):
    programs = db.query(SubsidyProgram).order_by(SubsidyProgram.sort_order, SubsidyProgram.id).all()
    rows = []
    for p in programs:
        rows.append({
            "p": p,
            "n_tasks": db.query(ProgramTask).filter_by(program_id=p.id).count(),
            "n_docs":  db.query(ProgramDocument).filter_by(program_id=p.id).count(),
        })
    return templates.TemplateResponse(request, "programs/list.html", {
        "request": request, "user": user, "rows": rows,
    })


@router.get("/add", response_class=HTMLResponse)
def add_form(request: Request,
             user: User = Depends(require_user),
             db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "programs/form.html", {
        "request": request, "user": user, "program": None,
    })


@router.get("/{pid}/edit", response_class=HTMLResponse)
def edit_form(pid: int, request: Request,
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    p = db.get(SubsidyProgram, pid)
    if not p:
        return RedirectResponse("/programs", status_code=302)
    prog_tasks = (db.query(ProgramTask).filter_by(program_id=pid)
                    .order_by(ProgramTask.sort_order, ProgramTask.id).all())
    prog_docs  = (db.query(ProgramDocument).filter_by(program_id=pid)
                    .order_by(ProgramDocument.sort_order, ProgramDocument.id).all())
    return templates.TemplateResponse(request, "programs/form.html", {
        "request": request, "user": user, "program": p,
        "prog_tasks": prog_tasks, "prog_docs": prog_docs,
        "phases": __import__("routers.execution", fromlist=["get_phases"]).get_phases(db),
    })


def _apply(p, form):
    p.name       = form.get("name", "").strip()
    p.full_name  = form.get("full_name", "")
    p.agency     = form.get("agency", "")
    p.purpose    = form.get("purpose", "")
    p.target     = form.get("target", "")
    p.amount     = form.get("amount", "")
    p.items      = form.get("items", "")
    p.key_points = form.get("key_points", "")
    p.timing     = form.get("timing", "")
    p.url        = form.get("url", "")
    p.notes      = form.get("notes", "")


@router.post("/add")
async def add_save(request: Request,
                   user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    form = await request.form()
    if not form.get("name", "").strip():
        return RedirectResponse("/programs/add", status_code=303)
    ts = now_str()
    maxo = db.query(SubsidyProgram).count()
    p = SubsidyProgram(sort_order=maxo, created_at=ts, updated_at=ts)
    _apply(p, form)
    db.add(p)
    db.commit()
    return RedirectResponse("/programs", status_code=303)


@router.post("/{pid}/edit")
async def edit_save(pid: int, request: Request,
                    user: User = Depends(require_user),
                    db: Session = Depends(get_db)):
    p = db.get(SubsidyProgram, pid)
    if not p:
        return RedirectResponse("/programs", status_code=302)
    form = await request.form()
    _apply(p, form)
    p.updated_at = now_str()
    db.commit()
    return RedirectResponse("/programs", status_code=303)


@router.post("/{pid}/delete")
def delete_program(pid: int,
                   user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    p = db.get(SubsidyProgram, pid)
    if p:
        db.delete(p)
        db.commit()
    return RedirectResponse("/programs", status_code=303)


# ── Template: tasks ───────────────────────────────────────────────────────────

@router.post("/{pid}/tpl-task/add")
def tpl_task_add(pid: int,
                 name: str        = Form(""),
                 phase: str       = Form(""),
                 offset_days: str = Form("0"),
                 duration: str    = Form("7"),
                 user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    if name.strip():
        maxo = db.query(ProgramTask).filter_by(program_id=pid).count()
        db.add(ProgramTask(program_id=pid, name=name.strip(), phase=phase,
                           offset_days=int(offset_days or 0), duration=int(duration or 1),
                           sort_order=maxo))
        db.commit()
    return RedirectResponse(f"/programs/{pid}/edit#tpl", status_code=303)


@router.post("/{pid}/tpl-task/{tid}/delete")
def tpl_task_del(pid: int, tid: int,
                 user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    t = db.get(ProgramTask, tid)
    if t and t.program_id == pid:
        db.delete(t); db.commit()
    return RedirectResponse(f"/programs/{pid}/edit#tpl", status_code=303)


# ── Template: documents ───────────────────────────────────────────────────────

@router.post("/{pid}/tpl-doc/add")
def tpl_doc_add(pid: int,
                name: str     = Form(""),
                provider: str = Form("客戶"),
                user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    if name.strip():
        maxo = db.query(ProgramDocument).filter_by(program_id=pid).count()
        db.add(ProgramDocument(program_id=pid, name=name.strip(), provider=provider, sort_order=maxo))
        db.commit()
    return RedirectResponse(f"/programs/{pid}/edit#tpl", status_code=303)


@router.post("/{pid}/tpl-doc/{did}/delete")
def tpl_doc_del(pid: int, did: int,
                user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    d = db.get(ProgramDocument, did)
    if d and d.program_id == pid:
        db.delete(d); db.commit()
    return RedirectResponse(f"/programs/{pid}/edit#tpl", status_code=303)
