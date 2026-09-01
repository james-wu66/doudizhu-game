# -*- coding: utf-8 -*-
"""
斗地主工作台 · 文件监听自动刷新（零第三方依赖）
================================================
轮询项目关键文件的修改时间（mtime），一旦变化就自动重跑 生成控制台.py，
使 状态.json / 控制台.html 始终反映最新真实代码。

页面本身每 8 秒 fetch 状态.json，所以本脚本触发重生成后，
打开着的工作台会在数秒内自动显示最新内容——无需手动刷新、无需提交。

监听范围（在 ROOT = 斗地主终极版 软件 下）：
  backend/app.py, backend/ai_engine.py
  frontend/index.html, frontend/game.js
  tests/ 目录
  {WORKBENCH}/协作状态.json  （agent 写协作动态也会触发一次重生成）

注意：本脚本只监听"源文件"，不监听自己生成的 状态.json / 控制台.html，
因此重生成不会反向触发自己，不会死循环。

运行：python 引擎/watchdog.py   （启动工作台.bat 会自动在后台起它）
退出：Ctrl+C，或关闭 启动工作台.bat 拉起的 "斗地主工作台监听" 窗口。
"""
import os, time, subprocess, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKBENCH = os.path.dirname(SCRIPT_DIR)          # .../斗地主最终版工作台
ROOT = os.path.dirname(WORKBENCH)                # .../斗地主终极版 软件
GEN = os.path.join(SCRIPT_DIR, "生成控制台.py")
PY = sys.executable

# 相对 ROOT 的源文件；协作状态.json 在工作台目录
WATCH_REL = [
    ("ROOT", "backend/app.py"),
    ("ROOT", "backend/ai_engine.py"),
    ("ROOT", "frontend/index.html"),
    ("ROOT", "frontend/game.js"),
    ("ROOT", "tests"),
    ("WB", "协作状态.json"),
]

POLL_SEC = 2


def resolve(kind, rel):
    base = ROOT if kind == "ROOT" else WORKBENCH
    return os.path.join(base, rel)


def mtime(path):
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0


def snapshot():
    return {resolve(k, r): mtime(resolve(k, r)) for k, r in WATCH_REL}


def run_gen():
    try:
        subprocess.run([PY, GEN], cwd=SCRIPT_DIR,
                       capture_output=True, timeout=180)
        print(f"[{time.strftime('%H:%M:%S')}] 已重新生成工作台数据")
    except subprocess.TimeoutExpired:
        print(f"[{time.strftime('%H:%M:%S')}] 生成超时(>180s)，跳过本次")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 生成失败: {e}")


def main():
    print("工作台 watchdog 启动，监听文件变化（Ctrl+C 退出）...")
    print(f"  监听根目录: {ROOT}")
    print(f"  轮询间隔: {POLL_SEC}s")
    last = snapshot()
    while True:
        time.sleep(POLL_SEC)
        changed = [r for (k, r), p in zip(WATCH_REL, last)
                   if mtime(resolve(k, r)) != last[p]]
        if changed:
            for r in changed:
                print(f"[{time.strftime('%H:%M:%S')}] 检测到变更: {r}")
                last[resolve(*next(x for x in WATCH_REL if x[1] == r))] = \
                    mtime(resolve(*next(x for x in WATCH_REL if x[1] == r)))
            run_gen()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nwatchdog 已停止")
