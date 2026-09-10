@echo off
title AIREAD - Grok Web Automation Server (Port 8020)
cd /d "%~dp0"
echo =========================================================================
echo       🚀 DANG KHOI CHAY GROK WEB AUTOMATION SERVER (PORT 8020)...
echo =========================================================================
echo  [!] HUONG DAN:
echo      - Server nay ket noi Edge Browser de dich qua giao dien Grok Web.
echo      - Trinh duyet Edge se mo ra, vui long dang nhap Grok neu chua co session.
echo      - Giu cua so nay chay ngam khi chon Provider "Grok Web Automation" tren AIREAD.
echo =========================================================================
echo.

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" tools\grok_server\server.py
) else (
    python tools\grok_server\server.py
)

echo.
echo [!] Server da dung. Nhan phim bat ky de thoat...
pause > nul
