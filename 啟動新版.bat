@echo off
cd /d "%~dp0"
echo ============================================
echo   補助顧問管理系統 (新版)
echo ============================================
echo   網址: http://localhost:8000
echo   帳號: admin
echo   密碼: admin1234
echo --------------------------------------------
echo   瀏覽器將在數秒後自動開啟...
echo   關閉本視窗或按 Ctrl+C 即可停止系統
echo ============================================
echo.

REM 每次開啟系統前，先自動備份一次（本機 + OneDrive）
echo [備份] 正在備份資料...
python "%~dp0..\backup.py"
echo.

REM 等 3 秒讓伺服器先啟動，再自動開瀏覽器
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8000"

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
