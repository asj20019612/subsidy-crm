"""Shared template/route helpers."""
from __future__ import annotations
from datetime import date, datetime


DONE_STATUSES = {"已完成", "暫停", "已結案"}

# 暖色低飽和調色盤（ConsultantOS 設計系統）
# slate 藍 #2E4C6B/#ECF1F6 · 綠 #3F6B52/#EAF1EC · 琥珀 #8A6A2F/#F6F0E1
# 磚紅 #9E4A40/#F5E8E5 · 灰 #6B675E/#EFEDE7
BADGE_COLORS: dict[str, tuple[str, str]] = {
    # — Status —
    "未開始":    ("#6B675E", "#EFEDE7"),
    "進行中":    ("#2E4C6B", "#ECF1F6"),
    "等待對方":  ("#8A6A2F", "#F6F0E1"),
    "需追蹤":    ("#9E4A40", "#F5E8E5"),
    "已完成":    ("#3F6B52", "#EAF1EC"),
    "暫停":      ("#6B675E", "#EFEDE7"),
    # — Priority —
    "緊急": ("#9E4A40", "#F5E8E5"),
    "高":   ("#A0603C", "#F6EDE4"),
    "中":   ("#2E4C6B", "#ECF1F6"),
    "低":   ("#6B675E", "#EFEDE7"),
    # — Deal —
    "未成交": ("#6B675E", "#EFEDE7"),
    "已報價": ("#8A6A2F", "#F6F0E1"),
    "已成交": ("#3F6B52", "#EAF1EC"),
    "流案":   ("#9A948A", "#F3F1EC"),
    # — Opportunity 商機狀態 —
    "潛在":   ("#6B675E", "#EFEDE7"),
    "洽談中": ("#2E4C6B", "#ECF1F6"),
    "已簽約": ("#3F6B52", "#EAF1EC"),
    # — Grade —
    "A": ("#2E4C6B", "#ECF1F6"),
    "B": ("#6B675E", "#EFEDE7"),
    "C": ("#9A948A", "#F3F1EC"),
    "D": ("#9A948A", "#F3F1EC"),
    # — Stage (current 7-stage pipeline) —
    "已洽談":     ("#4B5563", "#F3F4F6"),
    "已洽談":     ("#6B675E", "#EFEDE7"),
    "已提供合約": ("#2E4C6B", "#ECF1F6"),
    "撰寫中":     ("#35655F", "#E9F0EE"),
    "書面審查":   ("#8A6A2F", "#F6F0E1"),
    "簡報審查":   ("#A0603C", "#F6EDE4"),
    "待核定":     ("#5A5578", "#EFEDF3"),
    "獲補助":     ("#3F6B52", "#EAF1EC"),
    # — Stage (legacy, kept for any old data) —
    "新名單":       ("#6B7280", "#F9FAFB"),
    "已初談":       ("#1E40AF", "#EFF6FF"),
    "待報價":       ("#92400E", "#FFFBEB"),
    "已報價":       ("#9A3412", "#FFF7ED"),
    "等待客戶資料": ("#5B21B6", "#F5F3FF"),
    "資料整理中":   ("#0E7490", "#F0FDFA"),
    "架構撰寫中":   ("#0C4A6E", "#F0F9FF"),
    "計畫書撰寫中": ("#065F46", "#ECFDF5"),
    "內部審稿":     ("#14532D", "#F0FDF4"),
    "客戶確認":     ("#78350F", "#FFFBEB"),
    "已送件":       ("#92400E", "#FFFBEB"),
    "審查中":       ("#9A3412", "#FFF7ED"),
    "待回覆委員":   ("#831843", "#FDF2F8"),
    "已核定":       ("#065F46", "#ECFDF5"),
    "未通過/暫停":  ("#991B1B", "#FEF2F2"),
    "已結案":       ("#4B5563", "#F3F4F6"),
    # — Subsidy —
    "SBIR":       ("#2E4C6B", "#ECF1F6"),
    "CITD":       ("#2E4C6B", "#ECF1F6"),
    "SITI":       ("#2E4C6B", "#ECF1F6"),
    "SIIR":       ("#2E4C6B", "#ECF1F6"),
    "台北市產發局": ("#2E4C6B", "#ECF1F6"),
    "其他":       ("#6B675E", "#EFEDE7"),
    # — Contact —
    "處理中": ("#2E4C6B", "#ECF1F6"),
    "待回覆": ("#8A6A2F", "#F6F0E1"),
    "取消":   ("#9A948A", "#F3F1EC"),
}


def badge_style(text: str) -> str:
    tc, bg = BADGE_COLORS.get(str(text), ("#6B675E", "#EFEDE7"))
    return f"background:{bg};color:{tc};border:1px solid {tc}22"


def parse_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return datetime.strptime(val.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def days_until(s: str | None) -> int | None:
    d = parse_date(s)
    return (d - date.today()).days if d else None


def days_since(s: str | None) -> int | None:
    d = parse_date(s)
    return (date.today() - d).days if d else None


def is_overdue(deadline: str | None, status: str) -> bool:
    if status in DONE_STATUSES:
        return False
    d = parse_date(deadline)
    return d is not None and d < date.today()


def fmt_money(val) -> str:
    try:
        v = float(val or 0)
        return f"${v:,.0f}" if v else "—"
    except Exception:
        return "—"


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


# ── 工作階段（統一設定於 系統設定 → 下拉選單「工作階段」）────────────────────────
DEFAULT_PHASES = ["洽談簽約", "資料蒐集", "計畫書撰寫", "送件", "書面審查",
                  "簡報審查", "核定", "執行管考", "結案請款"]

# 低飽和、與整體設計一致的階段色盤：(主色, 淺底, 邊框)
PHASE_PALETTE = [
    ("#2E4C6B", "#ECF1F6", "#AEC0D5"),   # 深藍
    ("#35655F", "#E8F1EF", "#9CC0BA"),   # 青綠
    ("#8A6A2F", "#F6F0E1", "#D9C393"),   # 琥珀
    ("#A0603C", "#F7ECE5", "#DDB59C"),   # 赭紅
    ("#5A5578", "#EEEDF4", "#B9B5D0"),   # 灰紫
    ("#3F6B52", "#EAF1EC", "#9DBDAB"),   # 森綠
    ("#4F6F8A", "#EBF1F5", "#A9BFCE"),   # 灰藍
    ("#7A5C48", "#F3EDE8", "#CDB6A6"),   # 棕
]
_PHASE_NONE = ("#6B675E", "#EFEDE7", "#CFC9BF")


def phase_color(name: str, phases: list) -> tuple:
    """依階段在『工作階段』清單中的順序給固定顏色；未設定/不在清單 → 灰色。"""
    try:
        i = phases.index(name)
    except ValueError:
        return _PHASE_NONE
    return PHASE_PALETTE[i % len(PHASE_PALETTE)]
