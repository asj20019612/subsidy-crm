from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import User, ContactRecord, Project, Client, Setting
from helpers import badge_style

router = APIRouter(prefix="/contacts")
templates = Jinja2Templates(directory="templates")


def _settings(db, cat):
    return [r.value for r in db.query(Setting).filter_by(category=cat, is_active=1).order_by(Setting.sort_order).all()]


@router.get("", response_class=HTMLResponse)
def list_contacts(request: Request,
                  q: str = "",
                  rec_type: str = "",
                  rec_status: str = "",
                  user: User = Depends(require_user),
                  db: Session = Depends(get_db)):
    qry = db.query(ContactRecord)
    if q:
        qry = qry.filter(ContactRecord.summary.ilike(f"%{q}%"))
    if rec_type:
        qry = qry.filter(ContactRecord.record_type == rec_type)
    if rec_status:
        qry = qry.filter(ContactRecord.status == rec_status)
    records  = qry.order_by(ContactRecord.contact_date.desc()).all()
    projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    clients  = db.query(Client).order_by(Client.company_name).all()
    return templates.TemplateResponse(request, "contacts/list.html", {
        "request": request, "user": user,
        "records": records, "q": q,
        "sel_type": rec_type, "sel_status": rec_status,
        "rec_types":    _settings(db, "聯繫類型"),
        "rec_statuses": ["處理中","待回覆","已完成","取消"],
        "projects": projects,
        "clients":  clients,
        "badge_style": badge_style,
    })


@router.post("/add")
def add(project_id: str    = Form(""),
        client_id: str     = Form(""),
        record_type: str   = Form("一般聯繫"),
        contact_date: str  = Form(""),
        summary: str       = Form(""),
        our_next_step: str = Form(""),
        client_pending: str = Form(""),
        deadline: str      = Form(""),
        status: str        = Form("處理中"),
        user: User         = Depends(require_user),
        db: Session        = Depends(get_db)):
    ts = now_str()
    db.add(ContactRecord(
        project_id=int(project_id) if project_id.isdigit() else None,
        client_id=int(client_id)   if client_id.isdigit()  else None,
        record_type=record_type, contact_date=contact_date,
        summary=summary, our_next_step=our_next_step,
        client_pending=client_pending, deadline=deadline,
        status=status, created_at=ts, updated_at=ts,
    ))
    db.commit()
    return RedirectResponse("/contacts", status_code=303)


@router.post("/{rid}/edit")
def edit(rid: int,
         record_type: str   = Form(""),
         contact_date: str  = Form(""),
         summary: str       = Form(""),
         our_next_step: str = Form(""),
         client_pending: str = Form(""),
         deadline: str      = Form(""),
         status: str        = Form(""),
         user: User         = Depends(require_user),
         db: Session        = Depends(get_db)):
    r = db.get(ContactRecord, rid)
    if r:
        r.record_type    = record_type
        r.contact_date   = contact_date
        r.summary        = summary
        r.our_next_step  = our_next_step
        r.client_pending = client_pending
        r.deadline       = deadline
        r.status         = status
        r.updated_at     = now_str()
        db.commit()
    return RedirectResponse("/contacts", status_code=303)


@router.post("/{rid}/delete")
def delete(rid: int,
           user: User = Depends(require_user),
           db: Session = Depends(get_db)):
    r = db.get(ContactRecord, rid)
    if r:
        db.delete(r)
        db.commit()
    return RedirectResponse("/contacts", status_code=303)
