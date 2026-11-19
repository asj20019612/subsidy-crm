from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import User, Client, Setting, Project, Opportunity
from helpers import badge_style, fmt_money

router = APIRouter(prefix="/clients")
templates = Jinja2Templates(directory="templates")


def _settings(db, cat):
    return [r.value for r in db.query(Setting).filter_by(category=cat, is_active=1).order_by(Setting.sort_order).all()]


def _referrers_by_client(db) -> dict[int, list[dict]]:
    """Aggregate distinct referrers from each client's projects."""
    rows = (db.query(Project.client_id, Project.referred_by, Project.referral_relation)
              .filter(Project.client_id.isnot(None),
                      Project.referred_by.isnot(None),
                      Project.referred_by != "")
              .all())
    out: dict[int, list[dict]] = {}
    seen: dict[int, set] = {}
    for cid, name, relation in rows:
        if cid is None or not name:
            continue
        seen.setdefault(cid, set())
        if name in seen[cid]:
            continue
        seen[cid].add(name)
        out.setdefault(cid, []).append({"name": name, "relation": relation or ""})
    return out


@router.get("", response_class=HTMLResponse)
def list_clients(request: Request,
                 q: str = "",
                 user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    qry = db.query(Client)
    referrers = _referrers_by_client(db)

    if q:
        # match company / contact / own referrer, OR clients whose projects were referred by `q`
        ref_client_ids = [cid for cid, refs in referrers.items()
                          if any(q.lower() in r["name"].lower() for r in refs)]
        cond = (Client.company_name.ilike(f"%{q}%") |
                Client.contact_name.ilike(f"%{q}%") |
                Client.referred_by.ilike(f"%{q}%"))
        if ref_client_ids:
            cond = cond | Client.id.in_(ref_client_ids)
        qry = qry.filter(cond)

    clients = qry.order_by(Client.client_grade, Client.company_name).all()
    return templates.TemplateResponse(request, "clients/list.html", {
        "request": request, "user": user,
        "clients": clients, "q": q,
        "referrers": referrers,
        "grades": _settings(db, "客戶等級") or ["A", "B", "C", "D"],
        "badge_style": badge_style,
    })


@router.get("/add", response_class=HTMLResponse)
def add_form(request: Request,
             user: User = Depends(require_user),
             db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "clients/form.html", {
        "request": request, "user": user, "client": None,
        "grades":    _settings(db, "客戶等級"),
        "rel_opts":  _settings(db, "關係狀態"),
        "ref_relations": _settings(db, "引薦關係"),
    })


@router.post("/add")
def add_save(company_name: str      = Form(""),
             rep_name: str          = Form(""),
             tax_id: str            = Form(""),
             address: str           = Form(""),
             contact_name: str      = Form(""),
             contact_phone: str     = Form(""),
             contact_email: str     = Form(""),
             client_grade: str      = Form("C"),
             relationship_status: str = Form(""),
             summary: str           = Form(""),
             next_follow_up_date: str = Form(""),
             referred_by: str       = Form(""),
             referral_relation: str = Form(""),
             notes: str             = Form(""),
             user: User             = Depends(require_user),
             db: Session            = Depends(get_db)):
    ts = now_str()
    db.add(Client(
        company_name=company_name, rep_name=rep_name, tax_id=tax_id,
        address=address, contact_name=contact_name,
        contact_phone=contact_phone, contact_email=contact_email,
        client_grade=client_grade, relationship_status=relationship_status,
        summary=summary, next_follow_up_date=next_follow_up_date,
        referred_by=referred_by,
        referral_relation=referral_relation if referral_relation != "—" else "",
        notes=notes, created_at=ts, updated_at=ts,
    ))
    db.commit()
    return RedirectResponse("/clients", status_code=303)


@router.get("/{cid}/edit", response_class=HTMLResponse)
def edit_form(cid: int, request: Request,
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    c = db.get(Client, cid)
    if not c:
        return RedirectResponse("/clients", status_code=302)
    from routers.files import attachments_for_client
    opps = (db.query(Opportunity)
              .filter(Opportunity.client_id == cid)
              .order_by(Opportunity.id.desc()).all())
    return templates.TemplateResponse(request, "clients/form.html", {
        "request": request, "user": user, "client": c,
        "grades":    _settings(db, "客戶等級"),
        "rel_opts":  _settings(db, "關係狀態"),
        "ref_relations": _settings(db, "引薦關係"),
        "attachments": attachments_for_client(db, cid),
        "opps": opps,
        "subsidy_types": _settings(db, "補助類型"),
        "opp_sources": _settings(db, "引薦關係") or ["引薦", "開發", "自來"],
        "badge_style": badge_style, "fmt_money": fmt_money,
    })


@router.post("/{cid}/edit")
def edit_save(cid: int,
              company_name: str      = Form(""),
              rep_name: str          = Form(""),
              tax_id: str            = Form(""),
              address: str           = Form(""),
              contact_name: str      = Form(""),
              contact_phone: str     = Form(""),
              contact_email: str     = Form(""),
              client_grade: str      = Form("C"),
              relationship_status: str = Form(""),
              summary: str           = Form(""),
              next_follow_up_date: str = Form(""),
              referred_by: str       = Form(""),
              referral_relation: str = Form(""),
              notes: str             = Form(""),
              user: User             = Depends(require_user),
              db: Session            = Depends(get_db)):
    c = db.get(Client, cid)
    if not c:
        return RedirectResponse("/clients", status_code=302)
    c.company_name        = company_name
    c.rep_name            = rep_name
    c.tax_id              = tax_id
    c.address             = address
    c.contact_name        = contact_name
    c.contact_phone       = contact_phone
    c.contact_email       = contact_email
    c.client_grade        = client_grade
    c.relationship_status = relationship_status
    c.summary             = summary
    c.next_follow_up_date = next_follow_up_date
    c.referred_by         = referred_by
    c.referral_relation   = referral_relation if referral_relation != "—" else ""
    c.notes               = notes
    c.updated_at          = now_str()
    db.commit()
    return RedirectResponse("/clients", status_code=303)


@router.post("/{cid}/delete")
def delete_client(cid: int,
                  user: User = Depends(require_user),
                  db: Session = Depends(get_db)):
    c = db.get(Client, cid)
    if c:
        from models import Contract, Attachment
        from routers.files import UPLOAD_DIR
        # 清掉外鍵關聯，避免刪除失敗：
        # 商機（未轉案的）一併刪除；合約/案件只解除關聯，不刪
        for o in db.query(Opportunity).filter_by(client_id=cid).all():
            if o.converted_project_id:
                o.client_id = None
            else:
                db.delete(o)
        db.query(Contract).filter_by(client_id=cid).update({"client_id": None})
        for a in db.query(Attachment).filter_by(client_id=cid).all():
            try: (UPLOAD_DIR / a.filename).unlink(missing_ok=True)
            except Exception: pass
            db.delete(a)
        db.delete(c)
        db.commit()
    return RedirectResponse("/clients", status_code=303)
