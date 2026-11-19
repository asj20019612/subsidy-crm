import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, Form, UploadFile, File, Request
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from sqlalchemy.orm import Session
from database import get_db, now_str
from auth import require_user
from models import User, Attachment

router = APIRouter(prefix="/files")

# 預設存本機 data/uploads；雲端部署時用環境變數 UPLOAD_DIR 指向 Railway Volume
UPLOAD_DIR = Path(os.environ.get(
    "UPLOAD_DIR",
    str(Path(__file__).parent.parent.parent / "data" / "uploads"),
))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 25 * 1024 * 1024  # 25 MB


def attachments_for_project(db, pid: int):
    return (db.query(Attachment)
              .filter(Attachment.project_id == pid)
              .order_by(Attachment.uploaded_at.desc())
              .all())


def attachments_for_client(db, cid: int):
    return (db.query(Attachment)
              .filter(Attachment.client_id == cid)
              .order_by(Attachment.uploaded_at.desc())
              .all())


def attachments_for_contract(db, cid: int):
    return (db.query(Attachment)
              .filter(Attachment.contract_id == cid)
              .order_by(Attachment.uploaded_at.desc())
              .all())


def human_size(n: int) -> str:
    n = float(n or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@router.post("/upload")
async def upload(request: Request,
                 project_id: str = Form(""),
                 client_id: str  = Form(""),
                 contract_id: str = Form(""),
                 redirect_to: str = Form("/"),
                 file: UploadFile = File(...),
                 user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    if not file or not file.filename:
        return RedirectResponse(redirect_to, status_code=303)

    data = await file.read()
    if len(data) > MAX_BYTES:
        return RedirectResponse(redirect_to + "?err=size", status_code=303)

    ext = os.path.splitext(file.filename)[1][:12]
    stored = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / stored).write_bytes(data)

    db.add(Attachment(
        project_id=int(project_id) if project_id.isdigit() else None,
        client_id=int(client_id) if client_id.isdigit() else None,
        contract_id=int(contract_id) if contract_id.isdigit() else None,
        filename=stored,
        original_name=file.filename[:255],
        file_size=len(data),
        uploaded_by=user.name or user.username,
        uploaded_at=now_str(),
    ))
    db.commit()
    return RedirectResponse(redirect_to, status_code=303)


@router.get("/{aid}/download")
def download(aid: int,
             user: User = Depends(require_user),
             db: Session = Depends(get_db)):
    a = db.get(Attachment, aid)
    if not a:
        return JSONResponse({"error": "not found"}, status_code=404)
    path = UPLOAD_DIR / a.filename
    if not path.exists():
        return JSONResponse({"error": "file missing"}, status_code=404)
    return FileResponse(str(path), filename=a.original_name)


@router.post("/{aid}/delete")
def delete(aid: int,
           redirect_to: str = Form("/"),
           user: User = Depends(require_user),
           db: Session = Depends(get_db)):
    a = db.get(Attachment, aid)
    if a:
        try:
            (UPLOAD_DIR / a.filename).unlink(missing_ok=True)
        except Exception:
            pass
        db.delete(a)
        db.commit()
    return RedirectResponse(redirect_to, status_code=303)
