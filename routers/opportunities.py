from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import User, Opportunity, Client, Project, Setting
from helpers import badge_style, fmt_money

router = APIRouter(prefix="/opportunities")
templates = Jinja2Templates(directory="templates")

# 商機階段（看板欄位，順序固定）
OPP_STAGES = ["潛在", "洽談中", "已報價", "已簽約"]
OPP_COLORS = {"潛在": "#9A948A", "洽談中": "#2E4C6B", "已報價": "#8A6A2F", "已簽約": "#3F6B52"}
ALL_STATUS = OPP_STAGES + ["未成交"]


def _settings(db, cat):
    return [r.value for r in db.query(Setting).filter_by(category=cat, is_active=1)
            .order_by(Setting.sort_order).all()]


@router.get("", response_class=HTMLResponse)
def board(request: Request,
          q: str = "",
          user: User = Depends(require_user),
          db: Session = Depends(get_db)):
    qry = db.query(Opportunity).filter(Opportunity.converted_project_id.is_(None))
    if q:
        qry = qry.filter(
            Opportunity.company_name.ilike(f"%{q}%") |
            Opportunity.contact_name.ilike(f"%{q}%") |
            Opportunity.owner.ilike(f"%{q}%")
        )
    opps = qry.order_by(Opportunity.sort_order, Opportunity.id.desc()).all()

    grouped = {s: [] for s in OPP_STAGES}
    lost = []
    for o in opps:
        if o.status == "未成交":
            lost.append(o)
        else:
            grouped.setdefault(o.status, []).append(o)

    meta = {}
    for s in OPP_STAGES:
        items = grouped.get(s, [])
        meta[s] = {"count": len(items),
                   "total": sum(o.est_amount or 0 for o in items),
                   "color": OPP_COLORS.get(s, "#9CA3AF")}

    total_active = sum(len(grouped.get(s, [])) for s in OPP_STAGES)
    total_value = sum(o.est_amount or 0 for s in OPP_STAGES for o in grouped.get(s, []))

    clients = db.query(Client).order_by(Client.company_name).all()

    return templates.TemplateResponse(request, "opportunities/board.html", {
        "request": request, "user": user,
        "grouped": grouped, "lost": lost,
        "stage_order": OPP_STAGES, "meta": meta,
        "q": q, "total_active": total_active, "total_value": total_value,
        "clients": clients,
        "subsidy_types": _settings(db, "補助類型"),
        "sources": _settings(db, "引薦關係") or ["引薦", "開發", "自來"],
        "badge_style": badge_style, "fmt_money": fmt_money,
    })


@router.post("/add")
def add(client_id: str      = Form(""),
        subsidy_type: str   = Form(""),
        est_amount: str     = Form("0"),
        source: str         = Form(""),
        status: str         = Form("潛在"),
        next_action: str    = Form(""),
        redirect_to: str    = Form(""),
        user: User = Depends(require_user),
        db: Session = Depends(get_db)):
    """客戶優先：商機一定要掛在一個現有客戶底下。"""
    back = redirect_to or "/opportunities"
    cl = db.get(Client, int(client_id)) if (client_id or "").strip().isdigit() else None
    if cl is None:                      # 沒選到有效客戶就不建
        return RedirectResponse(back, status_code=303)
    ts = now_str()
    maxo = db.query(Opportunity).count()
    db.add(Opportunity(
        client_id=cl.id,
        company_name=cl.company_name,           # 公司名跟著客戶
        contact_name=cl.contact_name or "",
        contact_phone=cl.contact_phone or "",
        contact_email=cl.contact_email or "",
        subsidy_type=subsidy_type,
        est_amount=float(est_amount or 0), source=source or "",
        status=status if status in ALL_STATUS else "潛在",
        next_action=next_action or "",
        sort_order=maxo, created_at=ts, updated_at=ts,
    ))
    db.commit()
    return RedirectResponse(back, status_code=303)


@router.post("/{oid}/move")
def move(oid: int,
         status: str = Form(""),
         user: User = Depends(require_user),
         db: Session = Depends(get_db)):
    o = db.get(Opportunity, oid)
    if not o or status not in ALL_STATUS:
        return JSONResponse({"ok": False}, status_code=404)
    o.status = status
    o.updated_at = now_str()
    db.commit()
    return JSONResponse({"ok": True})


@router.get("/{oid}/edit", response_class=HTMLResponse)
def edit_form(oid: int, request: Request,
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    o = db.get(Opportunity, oid)
    if not o:
        return RedirectResponse("/opportunities", status_code=302)
    return templates.TemplateResponse(request, "opportunities/form.html", {
        "request": request, "user": user, "opp": o,
        "statuses": ALL_STATUS,
        "clients": db.query(Client).order_by(Client.company_name).all(),
        "subsidy_types": _settings(db, "補助類型"),
        "sources": _settings(db, "引薦關係") or ["引薦", "開發", "自來"],
    })


@router.post("/{oid}/edit")
def edit_save(oid: int,
              client_id: str     = Form(""),
              contact_name: str  = Form(""),
              contact_phone: str = Form(""),
              contact_email: str = Form(""),
              subsidy_type: str  = Form(""),
              source: str        = Form(""),
              est_amount: str    = Form("0"),
              status: str        = Form("潛在"),
              owner: str         = Form(""),
              next_action: str   = Form(""),
              next_date: str     = Form(""),
              notes: str         = Form(""),
              user: User = Depends(require_user),
              db: Session = Depends(get_db)):
    o = db.get(Opportunity, oid)
    if not o:
        return RedirectResponse("/opportunities", status_code=302)
    # 關聯客戶（必填）；換客戶時公司名跟著更新
    cl = db.get(Client, int(client_id)) if (client_id or "").strip().isdigit() else None
    if cl is not None:
        o.client_id = cl.id
        o.company_name = cl.company_name
    o.contact_name=contact_name
    o.contact_phone=contact_phone; o.contact_email=contact_email
    o.subsidy_type=subsidy_type; o.source=source
    o.est_amount=float(est_amount or 0)
    o.status=status if status in ALL_STATUS else o.status
    o.owner=owner; o.next_action=next_action; o.next_date=next_date
    o.notes=notes; o.updated_at=now_str()
    db.commit()
    return RedirectResponse("/opportunities", status_code=303)


@router.post("/{oid}/delete")
def delete(oid: int,
           user: User = Depends(require_user),
           db: Session = Depends(get_db)):
    o = db.get(Opportunity, oid)
    if o:
        db.delete(o)
        db.commit()
    return RedirectResponse("/opportunities", status_code=303)


@router.post("/{oid}/convert")
def convert(oid: int,
            user: User = Depends(require_user),
            db: Session = Depends(get_db)):
    """成交 → 建立客戶（若無）+ 建立案件，並標記商機已轉案。"""
    o = db.get(Opportunity, oid)
    if not o or o.converted_project_id:
        return RedirectResponse("/opportunities", status_code=303)
    ts = now_str()

    # 1) 客戶：有關聯就用，沒有就找同名，再沒有就新建
    cid = o.client_id
    if not cid:
        existing = db.query(Client).filter(Client.company_name == o.company_name).first()
        if existing:
            cid = existing.id
        else:
            cl = Client(company_name=o.company_name, contact_name=o.contact_name,
                        contact_phone=o.contact_phone, contact_email=o.contact_email,
                        referred_by="" , created_at=ts, updated_at=ts)
            db.add(cl); db.flush()
            cid = cl.id

    # 2) 案件
    p = Project(
        client_id=cid, client_name=o.company_name,
        project_name=f"{o.company_name} {o.subsidy_type}案".strip(),
        subsidy_type=o.subsidy_type, current_stage="已洽談",
        status="進行中", deal_status="已成交", owner=o.owner,
        client_contact=o.contact_name, writing_fee=o.est_amount or 0,
        next_action="（由商機轉入，請確認執行計畫）",
        created_at=ts, updated_at=ts,
    )
    db.add(p); db.flush()

    # 3) 標記商機
    o.converted_project_id = p.id
    o.status = "已簽約"
    o.updated_at = ts
    db.commit()
    return RedirectResponse(f"/projects/{p.id}/execution", status_code=303)
