@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   一键推送到GitHub
echo ========================================
echo.

git add .
git commit -m "更新 %date% %time%"
git push origin master:main

echo.
echo ========================================
echo   推送完成！Render会自动部署
echo   等1-2分钟刷新手机就能看到更新
echo ========================================
echo.
pause
