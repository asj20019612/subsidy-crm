"""一次性：把本機 SQLite 的資料搬到雲端 PostgreSQL。

用法（在 web/ 目錄下）：
    set DATABASE_URL=postgresql://...（Railway 給的連線字串）
    python tools_migrate_to_pg.py

特性：
- 保留原本的 id
- 依外鍵順序搬（先父後子）
- 搬完自動修正 Postgres 的 id 序列，避免之後新增撞號
"""
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, select, insert, text
from models import (
    Base, User, ConsultantProfile, Setting, SubsidyProgram,
    Client, Contract, Project, WritingProgress, ContactRecord,
    Attachment, PaymentLog,
)

SQLITE_PATH = Path(__file__).parent.parent / "data" / "tracker.db"
SQLITE_URL = f"sqlite:///{SQLITE_PATH}"

PG = os.environ.get("DATABASE_URL")
if not PG:
    sys.exit("✗ 請先設定環境變數 DATABASE_URL（Railway Postgres 連線字串）")
if PG.startswith("postgres://"):
    PG = PG.replace("postgres://", "postgresql://", 1)

if not SQLITE_PATH.exists():
    sys.exit(f"✗ 找不到本機資料庫：{SQLITE_PATH}")

# 依外鍵相依順序：先父表後子表
MODELS = [
    User, ConsultantProfile, Setting, SubsidyProgram,   # 無外鍵
    Client,                                             # 無外鍵
    Contract,                                           # → client
    Project,                                            # → client, contract
    WritingProgress, ContactRecord, Attachment, PaymentLog,  # → project / client
]

src = create_engine(SQLITE_URL)
dst = create_engine(PG)

print("→ 在雲端建立資料表…")
Base.metadata.create_all(dst)

print("→ 搬移資料…")
with src.connect() as s, dst.begin() as d:
    for M in MODELS:
        t = M.__table__
        rows = [dict(r._mapping) for r in s.execute(select(t))]
        if rows:
            d.execute(insert(t), rows)
        print(f"   {t.name:20s} {len(rows):4d} 筆")

    print("→ 修正 id 序列…")
    for M in MODELS:
        name = M.__table__.name
        try:
            d.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{name}','id'), "
                f"COALESCE((SELECT MAX(id) FROM {name}), 1))"
            ))
        except Exception as e:
            print(f"   （略過 {name}：{e}）")

print("✓ 完成！雲端資料庫已就緒。")
