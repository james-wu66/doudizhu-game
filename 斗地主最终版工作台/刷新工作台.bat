@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   斗地主工作台 · 刷新真实数据
echo   本脚本扫描真实项目并重新生成 控制台.html
echo ============================================
"C:/Users/15436/.workbuddy/binaries/python/versions/3.13.12.old.84076/python.exe" "引擎/生成控制台.py"
echo.
echo 已完成。请在浏览器中按 F5 刷新 控制台.html 查看最新真实数据。
pause
