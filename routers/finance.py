from datetime import date
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import User, Project, PaymentLog
from helpers import fmt_money, badge_style

router = APIRouter(prefix="/finance")
templates = Jinja2Templates(directory="templates")

PAYMENT_TYPES = ["計畫書費","成功酬金（第1期）","成功酬金（第2期）","成功酬金（第3期）","其他"]


def _calc(projects):
    rows = []
    for p in projects:
        wf   = p.writing_fee or 0
        wfp  = p.writing_fee_paid or 0
        sub  = p.approved_subsidy or 0
        s1r  = p.success_fee_s1_rate or 6
        s2r  = p.success_fee_s2_rate or 6
        s3r  = p.success_fee_s3_rate or 3
        s1e  = sub * s1r / 100
        s2e  = sub * s2r / 100
        s3e  = sub * s3r / 100
        sf_total = s1e + s2e + s3e
        sf_coll  = (p.success_fee_s1_paid or 0) + (p.success_fee_s2_paid or 0) + (p.success_fee_s3_paid or 0)
        rows.append({
            "project": p,
            "wf": wf, "wfp": wfp, "wf_pend": wf - wfp,
            "sf_total": sf_total, "sf_coll": sf_coll, "sf_pend": sf_total - sf_coll,
            "s1e": s1e, "s2e": s2e, "s3e": s3e,
        })
    return rows


@router.get("", response_class=HTMLResponse)
def index(request: Request,
          year: int = 0,
          user: User = Depends(require_user),
          db: Session = Depends(get_db)):
    cur_year = date.today().year
    if not year:
        year = cur_year

    active = [p for p in db.query(Project).all()
              if p.status not in {"已結案", "流案"}]
    rows   = _calc(active)

    total_wfee      = sum(r["wf"]       for r in rows)
    total_wfee_paid = sum(r["wfp"]      for r in rows)
    total_wfee_pend = sum(r["wf_pend"]  for r in rows)
    total_sf_total  = sum(r["sf_total"] for r in rows)
    total_sf_coll   = sum(r["sf_coll"]  for r in rows)
    total_sf_pend   = sum(r["sf_pend"]  for r in rows)

    # Monthly income
    logs = (db.query(PaymentLog)
              .filter(PaymentLog.payment_date.like(f"{year}-%"))
              .all())
    monthly: dict[int, dict] = {m: {"wf": 0.0, "sf": 0.0} for m in range(1, 13)}
    for lg in logs:
        try:
            m = int(lg.payment_date[5:7])
            key = "wf" if lg.payment_type == "計畫書費" else "sf"
            monthly[m][key] += lg.amount or 0
        except Exception:
            pass
    monthly_rows = [{"month": m, "label": f"{m}月",
                     "wf": monthly[m]["wf"],
                     "sf": monthly[m]["sf"],
                     "total": monthly[m]["wf"] + monthly[m]["sf"]}
                    for m in range(1, 13)]
    ytd = sum(r["total"] for r in monthly_rows)

    # Recent logs
    recent_logs = (db.query(PaymentLog)
                     .order_by(PaymentLog.payment_date.desc(), PaymentLog.id.desc())
                     .limit(40).all())

    projects_all = db.query(Project).order_by(Project.updated_at.desc()).all()

    return templates.TemplateResponse(request, "finance/index.html", {
        "request": request, "user": user,
        "rows": rows,
        "total_wfee": total_wfee, "total_wfee_paid": total_wfee_paid, "total_wfee_pend": total_wfee_pend,
        "total_sf_total": total_sf_total, "total_sf_coll": total_sf_coll, "total_sf_pend": total_sf_pend,
        "grand_pending": total_wfee_pend + total_sf_pend,
        "monthly_rows": monthly_rows,
        "ytd": ytd, "year": year, "cur_year": cur_year,
        "recent_logs": recent_logs,
        "projects_all": projects_all,
        "payment_types": PAYMENT_TYPES,
        "fmt_money": fmt_money,
        "badge_style": badge_style,
    })


@router.post("/payment/add")
def add_payment(project_id: str   = Form(""),
                payment_type: str = Form(""),
                amount: str       = Form("0"),
                payment_date: str = Form(""),
                notes: str        = Form(""),
                user: User        = Depends(require_user),
                db: Session       = Depends(get_db)):
    db.add(PaymentLog(
        project_id=int(project_id) if project_id.isdigit() else None,
        payment_type=payment_type,
        amount=float(amount or 0),
        payment_date=payment_date,
        notes=notes,
        created_at=now_str(),
    ))
    db.commit()
    return RedirectResponse("/finance", status_code=303)


@router.post("/payment/{lid}/delete")
def delete_payment(lid: int,
                   user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    lg = db.get(PaymentLog, lid)
    if lg:
        db.delete(lg)
        db.commit()
    return RedirectResponse("/finance", status_code=303)


@router.post("/projects/{pid}/update-fees")
def update_fees(pid: int,
                success_fee_s1_rate: str = Form("6"),
                success_fee_s2_rate: str = Form("6"),
                success_fee_s3_rate: str = Form("3"),
                success_fee_s1_paid: str = Form("0"),
                success_fee_s2_paid: str = Form("0"),
                success_fee_s3_paid: str = Form("0"),
                writing_fee_paid: str    = Form("0"),
                user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if p:
        s1r = float(success_fee_s1_rate or 6)
        s2r = float(success_fee_s2_rate or 6)
        s3r = float(success_fee_s3_rate or 3)
        p.success_fee_s1_rate = s1r
        p.success_fee_s2_rate = s2r
        p.success_fee_s3_rate = s3r
        p.success_fee_rate    = s1r + s2r + s3r
        p.success_fee_s1_paid = float(success_fee_s1_paid or 0)
        p.success_fee_s2_paid = float(success_fee_s2_paid or 0)
        p.success_fee_s3_paid = float(success_fee_s3_paid or 0)
        p.writing_fee_paid    = float(writing_fee_paid or 0)
        p.updated_at          = now_str()
        db.commit()
    return RedirectResponse("/finance#sf", status_code=303)
