# -*- coding: utf-8 -*-
"""
斗地主工作台 · 协作动态写入 CLI（轻量 B）
==========================================
任何 agent / 用户完成任务后调用，往 协作状态.json 追加一条 activity。
打开着的工作台页面每 8 秒自动 fetch 并显示，无需手动刷新。

用法：
  python 引擎/log_activity.py --role 后端开发者 --type 交付 --text "完成 TASK-006 原型"
  python 引擎/log_activity.py --role 测试工程师 --type 修复 --text "jest 回归 40/41 通过" --task "TASK-006 收尾"

--role 可选：组长 / 提示词工程师 / 后端开发者 / 前端开发者 / 测试工程师 / 系统
--type 可选：交付 / 同步 / 任务 / 评审 / 修复 / 其他
"""
import os, sys, json, argparse, datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKBENCH = os.path.dirname(SCRIPT_DIR)
COLLAB = os.path.join(WORKBENCH, "协作状态.json")

VALID_ROLES = ["组长", "提示词工程师", "后端开发者", "前端开发者", "测试工程师", "系统"]
VALID_TYPES = ["交付", "同步", "任务", "评审", "修复", "其他"]
MAX_ACTIVITIES = 50


def load():
    if os.path.exists(COLLAB):
        try:
            with open(COLLAB, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"updated_at": "", "current_task": "", "roles": {}, "activities": []}


def save(data):
    data["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(COLLAB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser(description="往协作状态.json追加一条协作动态")
    p.add_argument("--role", default="系统", help="角色：" + " / ".join(VALID_ROLES))
    p.add_argument("--type", default="任务", help="类型：" + " / ".join(VALID_TYPES))
    p.add_argument("--text", required=True, help="动态内容")
    p.add_argument("--task", default=None, help="可选：同步设置 current_task（进行中任务）")
    args = p.parse_args()

    role = args.role if args.role in VALID_ROLES else "系统"
    typ = args.type if args.type in VALID_TYPES else "其他"

    data = load()
    if args.task:
        data["current_task"] = args.task
    act = {
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "role": role,
        "type": typ,
        "text": args.text,
    }
    data.setdefault("activities", []).insert(0, act)
    data["activities"] = data["activities"][:MAX_ACTIVITIES]
    save(data)
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 已记录协作动态 [{role}/{typ}]: {args.text}")


if __name__ == "__main__":
    main()
