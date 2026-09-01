@echo off
chcp 65001 >nul
title 欢乐斗地主服务器

echo ========================================
echo   欢乐斗地主 - 启动中...
echo ========================================
echo.

cd /d "%~dp0backend"

:: 尝试找到可用的 python
where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=python
) else (
    where python3 >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON=python3
    ) else (
        :: 常见安装路径
        if exist "C:\Python3132\python.exe" (
            set PYTHON=C:\Python3132\python.exe
        ) else if exist "C:\Python313\python.exe" (
            set PYTHON=C:\Python313\python.exe
        ) else (
            echo [错误] 找不到 Python！
            echo 请先安装 Python: https://www.python.org/downloads/
            echo 安装时勾选 "Add Python to PATH"
            pause
            exit /b 1
        )
    )
)

echo 使用 Python: %PYTHON%
%PYTHON% --version

:: 获取本机IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"') do (
    set LOCAL_IP=%%a
)
set LOCAL_IP=%LOCAL_IP: =%

echo.
echo 电脑访问: http://localhost:8080
echo 手机访问: http://%LOCAL_IP%:8080
echo.
echo 请确保手机和电脑连同一个WiFi
echo.
echo ========================================
echo   启动完成！浏览器会自动打开
echo ========================================
echo.

:: 自动打开浏览器
start http://localhost:8080

:: 启动服务器
%PYTHON% app.py

pause
