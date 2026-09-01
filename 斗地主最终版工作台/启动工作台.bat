@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PORT=8765
echo ============================================
echo   Dou Dizhu Workbench - Server + Auto Watch
echo   端口 PORT: %PORT%
echo ============================================
echo.
echo [1/3] 正在启动本地服务...
start "DDZ-Workbench-Server" "C:/Users/15436/.workbuddy/binaries/python/versions/3.13.12.old.84076/python.exe" -m http.server %PORT% --bind 127.0.0.1
echo [2/3] 正在启动文件监听（改动自动刷新工作台，无需手动跑 bat）...
start "DDZ-Workbench-Watcher" "C:/Users/15436/.workbuddy/binaries/python/versions/3.13.12.old.84076/python.exe" "引擎/watchdog.py"
echo [3/3] 2 秒后自动打开浏览器...
timeout /t 2 >nul
start "" "http://127.0.0.1:%PORT%/控制台.html"
echo.
echo 工作台已打开。改动项目文件（backend/frontend/tests）会自动刷新，无需手动操作。
echo 停止：关闭名为 "DDZ-Workbench-Server" 与 "DDZ-Workbench-Watcher" 的 python 窗口，
echo       或在任务管理器结束 python 进程，再关闭本窗口。
echo.
pause
echo 正在停止监听与服务...
taskkill /FI "WINDOWTITLE eq DDZ-Workbench-Server*" >nul 2>&1
taskkill /FI "WINDOWTITLE eq DDZ-Workbench-Watcher*" >nul 2>&1
echo 已停止。
