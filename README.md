# 補助顧問管理系統（ConsultantOS）

給政府補助顧問使用的 CRM / 專案管理系統：客戶、商機、案件 Pipeline、合約、專案任務與甘特圖。
介面為繁體中文，目標使用者是顧問本人與其 5 人團隊。

技術棧：**FastAPI + Jinja2（伺服器端渲染）+ SQLAlchemy + SQLite / PostgreSQL**，前端用 Tailwind（CDN）、Lucide 圖示、少量原生 JS，沒有打包流程。

> 這個倉庫只含程式碼，**不含任何客戶資料或資料庫**。

---

## 快速開始（本機）

需要 Python 3.12 以上。

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

開啟 http://localhost:8000
第一次啟動會自動建立資料表，並建立預設帳號 `admin` / `admin1234`（僅限開發用；設 `ADMIN_PASSWORD` 環境變數可指定初始密碼）。

### 資料存放位置
- 資料庫預設為 SQLite：`<本倉庫資料夾的上一層>/data/tracker.db`
- 附件預設存：`<本倉庫資料夾的上一層>/data/uploads/`
- 這兩個位置在倉庫之外（上一層），是歷史原因，用 `.gitignore` 也已排除 `data/`、`*.db`。
  第一次啟動時會自動建立資料夾。

---

## 環境變數

| 變數 | 說明 | 預設 |
|------|------|------|
| `DATABASE_URL` | 資料庫連線字串，`postgres://` 會自動轉成 `postgresql://` | 本機 SQLite |
| `SECRET_KEY` | Session 簽章金鑰。**設了 `DATABASE_URL` 卻沒設它，程式會拒絕啟動** | 僅本機用的預設值 |
| `ADMIN_PASSWORD` | 資料庫沒有任何使用者時，建立 admin 的初始密碼 | `admin1234` |
| `UPLOAD_DIR` | 附件存放路徑（雲端請指向持久化 Volume） | `../data/uploads` |

---

## 專案結構

```
main.py              進入點：註冊 router、Jinja 全域函式、啟動時 seed 預設資料
models.py            SQLAlchemy 模型
database.py          引擎、init_db()、冪等遷移（_add_columns_if_missing）
auth.py              登入、bcrypt 密碼雜湊、require_user 依賴
helpers.py           badge 顏色、日期工具、金額格式、甘特圖階段配色
routers/             各功能路由（見下表）
templates/           Jinja2 範本（base.html 含整套設計 token 與側邊欄）
static/              靜態檔
tools_migrate_to_pg.py   一次性把 SQLite 資料搬到 Postgres
部署上線步驟.md          Railway 部署手冊（給非技術使用者）
```

### 啟用中的功能（router）

| 檔案 | 功能 |
|------|------|
| `dashboard.py` | 今日工作台、催詢訊息產生器 |
| `opportunities.py` | 商機看板（必須隸屬於某客戶），可一鍵轉為案件 |
| `projects.py` | 案件 Pipeline 看板（7 階段、可拖拉）與表格檢視 |
| `clients.py` | 客戶管理（含引薦人、該客戶的商機） |
| `contracts.py` | 合約管理與合約附件 |
| `programs.py` | 計畫範本（補助計畫的任務／文件範本） |
| `execution.py` | 專案任務、文件清單、互動甘特圖、`/gantt` 總覽、`/gantt-share` 客戶用圖片版 |
| `files.py` | 附件上傳／下載／刪除（單檔 25MB） |
| `settings_router.py` | 帳號、顧問資訊、下拉選單（含「工作階段」） |
| `auth_router.py` | 登入／登出 |

`analytics.py`、`calendar_router.py`、`contacts.py`、`finance.py`、`writing.py` 為**已停用**模組：
程式保留，但沒有在 `main.py` 以 `include_router` 註冊，路由會回 404。要恢復只需註冊並補回側邊欄選單。

---

## 開發注意事項

1. **新欄位要寫遷移**：`create_all` 不會替既有資料表加欄位，請在 `database.py` 的 `_add_columns_if_missing` 補上，並保持冪等。
2. **SQLite 開了外鍵**（`PRAGMA foreign_keys=ON`）：新增帶外鍵的表時，要同步補進刪除流程（`projects.py` / `clients.py` / `contracts.py` 的 delete），先清子資料再刪父資料，否則會 500。
3. **密碼雜湊用 `bcrypt` 直接呼叫**，不要換回 passlib（passlib 1.7.4 與 bcrypt 5.x 在 import 時就會崩潰）。
4. **Starlette 新版 `TemplateResponse` 的第一個參數是 `request`**：`templates.TemplateResponse(request, "x.html", {...})`。
5. 儀表板彈窗使用原生 Popover API（卡片有 `overflow:hidden`，絕對定位會被裁切）。
6. 甘特圖階段來自 `Setting` 表（category=`工作階段`），顏色依階段在清單中的順序取自 `helpers.PHASE_PALETTE`。
7. 「下載甘特圖 PNG」在瀏覽器端用 html2canvas（CDN）產生，需要網路。

---

## 已知限制 / 待辦

- **沒有角色權限**：所有登入者權限相同，任何人都能重設他人密碼。
- **沒有資料隔離**：所有使用者共用同一份客戶／案件資料。
- **沒有自動化測試**；目前以 in-process ASGI（`httpx.ASGITransport`）手動 smoke test 驗證。
- **沒有稽核紀錄**（誰改了什麼）、也沒有階段轉換歷史。
- 雲端備份尚未規劃（`backup.py` 只備份本機 SQLite，且不在這個倉庫內）。
- 任務留言／子任務、LINE 提醒、合約 Word/PDF 產生等尚未實作。

---

## 部署

目標平台為 Railway：`Procfile` 啟動 `uvicorn`，資料庫用 Railway Postgres，附件掛 Volume 並設 `UPLOAD_DIR`。
完整步驟見 [部署上線步驟.md](部署上線步驟.md)。
