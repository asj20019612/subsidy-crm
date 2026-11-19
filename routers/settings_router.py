from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user, hash_password
from models import User, Setting, ConsultantProfile
from helpers import badge_style, DEFAULT_PHASES

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory="templates")

MANAGE_CATS = ["工作階段","補助類型","工作類型","目前階段","狀態","優先級",
               "成交狀態","客戶等級","關係狀態","聯繫類型","引薦關係","計畫書段落"]


@router.get("", response_class=HTMLResponse)
def index(request: Request,
          user: User = Depends(require_user),
          db: Session = Depends(get_db)):
    all_settings = db.query(Setting).order_by(Setting.category, Setting.sort_order).all()
    cats = {}
    for s in all_settings:
        cats.setdefault(s.category, []).append(s)

    profile = db.query(ConsultantProfile).first()
    users   = db.query(User).all()

    return templates.TemplateResponse(request, "settings/index.html", {
        "request": request, "user": user,
        "cats": cats, "manage_cats": MANAGE_CATS,
        "profile": profile,
        "users": users,
        "badge_style": badge_style,
    })


@router.post("/dropdown/add")
def add_option(category: str = Form(""),
               value: str    = Form(""),
               user: User    = Depends(require_user),
               db: Session   = Depends(get_db)):
    if value.strip():
        max_o = db.query(Setting).filter_by(category=category).count()
        db.add(Setting(category=category, value=value.strip(), sort_order=max_o))
        db.commit()
    return RedirectResponse("/settings#dropdowns", status_code=303)


@router.post("/dropdown/{sid}/delete")
def delete_option(sid: int,
                  user: User = Depends(require_user),
                  db: Session = Depends(get_db)):
    s = db.get(Setting, sid)
    if s:
        db.delete(s)
        db.commit()
    return RedirectResponse("/settings#dropdowns", status_code=303)


@router.post("/profile/save")
def save_profile(name: str    = Form(""),
                 address: str = Form(""),
                 bank: str    = Form(""),
                 account: str = Form(""),
                 user: User   = Depends(require_user),
                 db: Session  = Depends(get_db)):
    p = db.query(ConsultantProfile).first()
    if p:
        p.name = name; p.address = address; p.bank = bank; p.account = account
    else:
        db.add(ConsultantProfile(id=1, name=name, address=address, bank=bank, account=account))
    db.commit()
    return RedirectResponse("/settings#profile", status_code=303)


@router.post("/users/add")
def add_user(username: str  = Form(""),
             name: str      = Form(""),
             password: str  = Form(""),
             current_user: User = Depends(require_user),
             db: Session    = Depends(get_db)):
    if username.strip() and password.strip():
        existing = db.query(User).filter_by(username=username).first()
        if not existing:
            db.add(User(
                username=username.strip(),
                name=name.strip(),
                password=hash_password(password),
                is_active=True,
                created_at=now_str(),
            ))
            db.commit()
    return RedirectResponse("/settings#users", status_code=303)


@router.post("/users/{uid}/toggle")
def toggle_user(uid: int,
                current_user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if u and u.id != current_user.id:
        u.is_active = not u.is_active
        db.commit()
    return RedirectResponse("/settings#users", status_code=303)


@router.post("/users/{uid}/password")
def change_password(uid: int,
                    new_password: str = Form(""),
                    current_user: User = Depends(require_user),
                    db: Session = Depends(get_db)):
    """改密碼（自己或重設同事的）。至少 8 碼。"""
    u = db.get(User, uid)
    if u and len(new_password.strip()) >= 8:
        u.password = hash_password(new_password.strip())
        db.commit()
        return RedirectResponse("/settings?pw=ok#users", status_code=303)
    return RedirectResponse("/settings?pw=short#users", status_code=303)


def seed_phases(db: Session):
    """第一次啟動時放入預設「工作階段」；已有資料就不動（冪等）。"""
    if db.query(Setting).filter_by(category="工作階段").count() == 0:
        for i, v in enumerate(DEFAULT_PHASES):
            db.add(Setting(category="工作階段", value=v, sort_order=i, is_active=1))
        db.commit()
