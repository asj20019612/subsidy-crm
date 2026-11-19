"""SQLAlchemy models — mirrors existing tracker.db schema + adds users."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Float, ForeignKey, Integer, String, Text, DateTime
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True)
    username   = Column(String(50), unique=True, nullable=False)
    name       = Column(String(100), default="")
    password   = Column(String(200), nullable=False)
    is_active  = Column(Boolean, default=True)
    created_at = Column(String(30))


class Setting(Base):
    __tablename__ = "settings"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    category   = Column(String(50), nullable=False)
    value      = Column(String(100), nullable=False)
    sort_order = Column(Integer, default=0)
    is_active  = Column(Integer, default=1)


class ConsultantProfile(Base):
    __tablename__ = "consultant_profile"
    id      = Column(Integer, primary_key=True)
    name    = Column(String(100), default="")
    address = Column(String(200), default="")
    bank    = Column(String(100), default="")
    account = Column(String(100), default="")


class Opportunity(Base):
    """商機（潛在客戶 / 洽談中 / 報價 / 簽約），成交後可轉成正式案件。"""
    __tablename__ = "opportunities"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    company_name  = Column(String(200), nullable=False)
    client_id     = Column(Integer, ForeignKey("clients.id"))   # 若已是客戶可關聯
    contact_name  = Column(String(100), default="")
    contact_phone = Column(String(50),  default="")
    contact_email = Column(String(100), default="")
    subsidy_type  = Column(String(50),  default="")             # 想申請的補助
    source        = Column(String(50),  default="")             # 來源：引薦/開發/自來
    est_amount    = Column(Float,       default=0)              # 預估金額
    status        = Column(String(20),  default="潛在")          # 潛在/洽談中/已報價/已簽約/未成交
    owner         = Column(String(100), default="")
    next_action   = Column(Text,        default="")
    next_date     = Column(String(20),  default="")
    notes         = Column(Text,        default="")
    converted_project_id = Column(Integer, ForeignKey("projects.id"))  # 轉案後記錄
    sort_order    = Column(Integer,     default=0)
    created_at    = Column(String(30))
    updated_at    = Column(String(30))

    client_obj = relationship("Client", foreign_keys=[client_id])


class Client(Base):
    __tablename__ = "clients"
    id                  = Column(Integer, primary_key=True, autoincrement=True)
    company_name        = Column(String(200), nullable=False)
    rep_name            = Column(String(100), default="")
    tax_id              = Column(String(20),  default="")
    address             = Column(String(300), default="")
    contact_name        = Column(String(100), default="")
    contact_phone       = Column(String(50),  default="")
    contact_email       = Column(String(100), default="")
    client_grade        = Column(String(5),   default="C")
    relationship_status = Column(String(50),  default="")
    summary             = Column(String(300), default="")
    next_follow_up_date = Column(String(20),  default="")
    referred_by         = Column(String(100), default="")
    referral_relation   = Column(String(50),  default="")
    notes               = Column(Text,        default="")
    created_at          = Column(String(30))
    updated_at          = Column(String(30))

    projects = relationship("Project", back_populates="client_obj",
                            foreign_keys="Project.client_id")
    contacts = relationship("ContactRecord", back_populates="client_obj",
                            foreign_keys="ContactRecord.client_id")


class Contract(Base):
    __tablename__ = "contracts"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    client_id     = Column(Integer, ForeignKey("clients.id"))
    contract_type = Column(String(20), default="單案")
    start_date    = Column(String(20), default="")
    end_date      = Column(String(20), default="")
    signed_date   = Column(String(20), default="")
    fee_per_case  = Column(Float, default=65000)
    case_count    = Column(Integer, default=1)
    retainer_paid = Column(Float, default=0)
    notes         = Column(Text, default="")
    created_at    = Column(String(30))
    updated_at    = Column(String(30))

    client_obj = relationship("Client", foreign_keys=[client_id])


class Project(Base):
    __tablename__ = "projects"
    id                   = Column(Integer, primary_key=True, autoincrement=True)
    client_id            = Column(Integer, ForeignKey("clients.id"))
    contract_id          = Column(Integer, ForeignKey("contracts.id"))
    client_name          = Column(String(200), default="")
    project_name         = Column(String(300), nullable=False)
    subsidy_type         = Column(String(50),  default="")
    work_type            = Column(String(50),  default="")
    current_stage        = Column(String(50),  default="新名單")
    status               = Column(String(30),  default="未開始")
    priority             = Column(String(20),  default="中")
    owner                = Column(String(100), default="")
    client_contact       = Column(String(100), default="")
    next_action          = Column(Text, default="")
    next_deadline        = Column(String(20), default="")
    last_contact_date    = Column(String(20), default="")
    submission_deadline  = Column(String(20), default="")
    estimated_fee        = Column(Float, default=0)
    deal_status          = Column(String(30), default="未成交")
    contract_amount      = Column(Float, default=0)
    received_amount      = Column(Float, default=0)
    pending_amount       = Column(Float, default=0)
    writing_fee          = Column(Float, default=0)
    writing_fee_paid     = Column(Float, default=0)
    approved_subsidy     = Column(Float, default=0)
    success_fee_rate     = Column(Float, default=15.0)
    success_fee_s1_rate  = Column(Float, default=6.0)
    success_fee_s2_rate  = Column(Float, default=6.0)
    success_fee_s3_rate  = Column(Float, default=3.0)
    success_fee_s1_paid  = Column(Float, default=0)
    success_fee_s2_paid  = Column(Float, default=0)
    success_fee_s3_paid  = Column(Float, default=0)
    referred_by          = Column(String(100), default="")
    referral_relation    = Column(String(50),  default="")
    referral_notes       = Column(Text, default="")
    notes                = Column(Text, default="")
    created_at           = Column(String(30))
    updated_at           = Column(String(30))

    client_obj      = relationship("Client",   back_populates="projects", foreign_keys=[client_id])
    contract_obj    = relationship("Contract", foreign_keys=[contract_id])
    writing_sections = relationship("WritingProgress", back_populates="project",
                                    cascade="all, delete-orphan")
    contact_records  = relationship("ContactRecord", back_populates="project",
                                    foreign_keys="ContactRecord.project_id",
                                    cascade="all, delete-orphan")


class WritingProgress(Base):
    __tablename__ = "writing_progress"
    id                   = Column(Integer, primary_key=True, autoincrement=True)
    project_id           = Column(Integer, ForeignKey("projects.id"), nullable=False)
    section_name         = Column(String(100), nullable=False)
    status               = Column(String(30), default="未開始")
    notes                = Column(Text, default="")
    blocker              = Column(Text, default="")
    needs_client_data    = Column(Text, default="")
    estimated_completion = Column(String(20), default="")
    updated_at           = Column(String(30))

    project = relationship("Project", back_populates="writing_sections")


class ContactRecord(Base):
    __tablename__ = "contact_records"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    project_id     = Column(Integer, ForeignKey("projects.id"))
    client_id      = Column(Integer, ForeignKey("clients.id"))
    record_type    = Column(String(50), default="一般聯繫")
    contact_date   = Column(String(20), default="")
    summary        = Column(Text, default="")
    our_next_step  = Column(Text, default="")
    client_pending = Column(Text, default="")
    deadline       = Column(String(20), default="")
    status         = Column(String(20), default="處理中")
    created_at     = Column(String(30))
    updated_at     = Column(String(30))

    project    = relationship("Project",  back_populates="contact_records", foreign_keys=[project_id])
    client_obj = relationship("Client",   back_populates="contacts",        foreign_keys=[client_id])


class SubsidyProgram(Base):
    __tablename__ = "subsidy_programs"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(50),  nullable=False)   # 簡稱 e.g. SBIR
    full_name  = Column(String(150), default="")        # 全名
    agency     = Column(String(100), default="")        # 主辦單位
    purpose    = Column(Text, default="")               # 精神 / 目的
    target     = Column(Text, default="")               # 補助對象
    amount     = Column(Text, default="")               # 補助金額 / 比例
    items      = Column(Text, default="")               # 補助項目
    key_points = Column(Text, default="")               # 撰寫重點
    timing     = Column(Text, default="")               # 申請期程
    url        = Column(String(300), default="")        # 官方連結
    notes      = Column(Text, default="")               # 備註
    sort_order = Column(Integer, default=0)
    created_at = Column(String(30))
    updated_at = Column(String(30))


class ProjectTask(Base):
    """專案的工作任務（甘特圖的來源資料）"""
    __tablename__ = "project_tasks"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    project_id  = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name        = Column(String(200), nullable=False)
    phase       = Column(String(50),  default="")      # 階段分類
    start_date  = Column(String(20),  default="")
    due_date    = Column(String(20),  default="")
    progress    = Column(Integer,     default=0)        # 0-100
    owner       = Column(String(100), default="")
    notes       = Column(Text,        default="")
    sort_order  = Column(Integer,     default=0)
    created_at  = Column(String(30))
    updated_at  = Column(String(30))

    project = relationship("Project", foreign_keys=[project_id])


class ProjectDocument(Base):
    """專案的文件清單（客戶/我方要交的文件，可打勾追蹤）"""
    __tablename__ = "project_documents"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    project_id  = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name        = Column(String(200), nullable=False)
    provider    = Column(String(20),  default="客戶")   # 客戶 / 我方
    status      = Column(String(20),  default="未繳")   # 未繳 / 已繳 / 不需要
    due_date    = Column(String(20),  default="")
    notes       = Column(Text,        default="")
    sort_order  = Column(Integer,     default=0)
    created_at  = Column(String(30))
    updated_at  = Column(String(30))

    project = relationship("Project", foreign_keys=[project_id])


class ProgramTask(Base):
    """補助計畫的任務範本（建案件時自動帶入 ProjectTask）"""
    __tablename__ = "program_tasks"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    program_id  = Column(Integer, ForeignKey("subsidy_programs.id"), nullable=False)
    name        = Column(String(200), nullable=False)
    phase       = Column(String(50),  default="")
    offset_days = Column(Integer,     default=0)        # 相對專案起始日第幾天開始
    duration    = Column(Integer,     default=7)        # 持續天數
    sort_order  = Column(Integer,     default=0)


class ProgramDocument(Base):
    """補助計畫的文件範本（建案件時自動帶入 ProjectDocument）"""
    __tablename__ = "program_documents"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    program_id  = Column(Integer, ForeignKey("subsidy_programs.id"), nullable=False)
    name        = Column(String(200), nullable=False)
    provider    = Column(String(20),  default="客戶")
    sort_order  = Column(Integer,     default=0)


class Attachment(Base):
    __tablename__ = "attachments"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    project_id    = Column(Integer, ForeignKey("projects.id"))
    client_id     = Column(Integer, ForeignKey("clients.id"))
    contract_id   = Column(Integer, ForeignKey("contracts.id"))
    filename      = Column(String(255), nullable=False)   # stored name on disk
    original_name = Column(String(255), nullable=False)   # display name
    file_size     = Column(Integer, default=0)
    uploaded_by   = Column(String(100), default="")
    uploaded_at   = Column(String(30))


class PaymentLog(Base):
    __tablename__ = "payment_logs"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    project_id   = Column(Integer, ForeignKey("projects.id"))
    payment_type = Column(String(50), nullable=False)
    amount       = Column(Float, nullable=False, default=0)
    payment_date = Column(String(20), nullable=False)
    notes        = Column(Text, default="")
    created_at   = Column(String(30))

    project = relationship("Project", foreign_keys=[project_id])
