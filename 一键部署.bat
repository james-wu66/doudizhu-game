@echo off
chcp 65001 >nul
echo ========================================
echo   一键部署到腾讯云
echo ========================================
echo.

:: 1. 推代码到GitHub
echo [1/2] 推送代码到GitHub...
git add -A
git commit -m "更新 %date% %time%"
git push origin master:main
echo ✅ 代码已推送
echo.

:: 2. 设置云端环境变量（确保MySQL连接不丢失）
echo [2/2] 设置云端环境变量...
cloudbase env update james-wu-d2gcojd404e6b8137 --env-id james-wu-d2gcojd404e6b8137 --env-vars PORT=8080,DB_HOST=172.17.0.2,DB_PORT=3306,DB_USER=doudizhu_game,DB_PASSWORD=wzm13002104610.,DB_NAME=james-wu-d2gcojd404e6b8137
echo ✅ 环境变量已设置
echo.
echo ========================================
echo   部署完成！等待1-2分钟生效
echo   访问: https://doudizhu-game-294184-6-1420872702.sh.run.tcloudbase.com
echo ========================================
pause
