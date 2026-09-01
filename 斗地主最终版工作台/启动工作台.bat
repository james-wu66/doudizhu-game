@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PORT=8765
echo ============================================
echo   斗地主工作台 · 本地实时同步服务
echo   端口：%PORT%
echo ============================================
echo.
echo [1/2] 正在启动本地服务（双击关闭不会停止，需结束 python 进程）...
start "斗地主工作台服务" "C:/Users/15436/.workbuddy/binaries/python/versions/3.13.12.old.84076/python.exe" -m http.server %PORT% --bind 127.0.0.1
echo [2/2] 2 秒后自动打开浏览器...
timeout /t 2 >nul
start "" "http://127.0.0.1:%PORT%/控制台.html"
echo.
echo 工作台已打开。页面每 8 秒自动同步最新数据。
echo 停止服务：关闭名为"斗地主工作台服务"的 python 窗口，或在任务管理器结束 python 进程。
echo.
pause
