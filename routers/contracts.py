from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import User, Contract, Client
from helpers import badge_style, fmt_money, parse_date

router = APIRouter(prefix="/contracts")
templates = Jinja2Templates(directory="templates")

CONTRACT_TYPES = ["單案", "雙案", "顧問服務", "其他"]


@router.get("", response_class=HTMLResponse)
def list_contracts(request: Request,
                   user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    rows = (db.query(Contract, Client)
              .outerjoin(Client, Contract.client_id == Client.id)
              .order_by(Contract.signed_date.desc(), Contract.id.desc())
              .all())
    contracts = []
    total_fee = 0
    total_paid = 0
    for c, cl in rows:
        fee_total = (c.fee_per_case or 0) * (c.case_count or 1)
        total_fee += fee_total
        total_paid += (c.retainer_paid or 0)
        contracts.append({"c": c, "client": cl, "fee_total": fee_total})
    return templates.TemplateResponse(request, "contracts/list.html", {
        "request": request, "user": user,
        "contracts": contracts,
        "total_fee": total_fee, "total_paid": total_paid,
        "count": len(contracts),
        "fmt_money": fmt_money, "badge_style": badge_style,
    })


@router.get("/add", response_class=HTMLResponse)
def add_form(request: Request,
             client_id: str = "",
             user: User = Depends(require_user),
             db: Session = Depends(get_db)):
    clients = db.query(Client).order_by(Client.company_name).all()
    return templates.TemplateResponse(request, "contracts/form.html", {
        "request": request, "user": user, "contract": None,
        "clients": clients, "types": CONTRACT_TYPES,
        "preset_client": client_id,
        "attachments": [],
    })


@router.post("/add")
def add_save(client_id: str      = Form(""),
             contract_type: str  = Form("單案"),
             signed_date: str    = Form(""),
             start_date: str     = Form(""),
             end_date: str       = Form(""),
             fee_per_case: str   = Form("0"),
             case_count: str     = Form("1"),
             retainer_paid: str  = Form("0"),
             notes: str          = Form(""),
             user: User = Depends(require_user),
             db: Session = Depends(get_db)):
    ts = now_str()
    c = Contract(
        client_id=int(client_id) if client_id.isdigit() else None,
        contract_type=contract_type, signed_date=signed_date,
        start_date=start_date, end_date=end_date,
        fee_per_case=float(fee_per_case or 0),
        case_count=int(float(case_count or 1)),
        retainer_paid=float(retainer_paid or 0),
        notes=notes, created_at=ts, updated_at=ts,
    )
    db.add(c)
    db.commit()
    return RedirectResponse(f"/contracts/{c.id}/edit", status_code=303)


@router.get("/{cid}/edit", response_class=HTMLResponse)
def edit_form(cid: int, request: Request,
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    c = db.get(Contract, cid)
    if not c:
        return RedirectResponse("/contracts", status_code=302)
    clients = db.query(Client).order_by(Client.company_name).all()
    from routers.files import attachments_for_contract
    return templates.TemplateResponse(request, "contracts/form.html", {
        "request": request, "user": user, "contract": c,
        "clients": clients, "types": CONTRACT_TYPES,
        "preset_client": "",
        "attachments": attachments_for_contract(db, cid),
    })


@router.post("/{cid}/edit")
def edit_save(cid: int,
              client_id: str      = Form(""),
              contract_type: str  = Form("單案"),
              signed_date: str    = Form(""),
              start_date: str     = Form(""),
              end_date: str       = Form(""),
              fee_per_case: str   = Form("0"),
              case_count: str     = Form("1"),
              retainer_paid: str  = Form("0"),
              notes: str          = Form(""),
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    c = db.get(Contract, cid)
    if not c:
        return RedirectResponse("/contracts", status_code=302)
    c.client_id     = int(client_id) if client_id.isdigit() else None
    c.contract_type = contract_type
    c.signed_date   = signed_date
    c.start_date    = start_date
    c.end_date      = end_date
    c.fee_per_case  = float(fee_per_case or 0)
    c.case_count    = int(float(case_count or 1))
    c.retainer_paid = float(retainer_paid or 0)
    c.notes         = notes
    c.updated_at    = now_str()
    db.commit()
    return RedirectResponse("/contracts", status_code=303)


@router.post("/{cid}/delete")
def delete_contract(cid: int,
                    user: User = Depends(require_user),
                    db: Session = Depends(get_db)):
    c = db.get(Contract, cid)
    if c:
        from models import Project, Attachment
        from routers.files import UPLOAD_DIR
        db.query(Project).filter_by(contract_id=cid).update({"contract_id": None})
        for a in db.query(Attachment).filter_by(contract_id=cid).all():
            try: (UPLOAD_DIR / a.filename).unlink(missing_ok=True)
            except Exception: pass
            db.delete(a)
        db.delete(c)
        db.commit()
    return RedirectResponse("/contracts", status_code=303)
