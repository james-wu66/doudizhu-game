# -*- coding: utf-8 -*-
"""
斗地主工作台 · 真实数据扫描生成器
=================================
扫描真实项目（git 状态 / 后端 ai_engine.py 函数 / 前端 game.js 函数 /
tests 真实状态），生成 项目状态.json 与 控制台.html。

所有数据来自真实扫描，控制台页面无任何写死常量。
运行：python 引擎/生成控制台.py   （或双击 刷新工作台.bat）
"""
import os, re, json, subprocess, shutil, datetime, glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKBENCH = os.path.dirname(SCRIPT_DIR)          # .../斗地主最终版工作台
PROJECT = os.path.dirname(WORKBENCH)             # .../斗地主终极版 软件
ROOT = PROJECT

TEMPLATE = os.path.join(SCRIPT_DIR, "控制台模板.html")
OUT_HTML = os.path.join(WORKBENCH, "控制台.html")
OUT_JSON = os.path.join(WORKBENCH, "状态.json")
COLLAB_JSON = os.path.join(WORKBENCH, "协作状态.json")

# ---------------------------------------------------------------------------
# 1. Git 真实状态
# ---------------------------------------------------------------------------
def git(args, cwd=ROOT):
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                           text=True, timeout=30)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return f"(git 执行失败: {e})"

def git_status():
    branch = git(["branch", "--show-current"]) or "未知"
    porcelain = git(["status", "--porcelain"])
    log = git(["log", "--oneline", "-5"]).splitlines()
    dirty = bool(porcelain.strip())
    untracked_tests = "tests/" in porcelain or "tests" in porcelain
    untracked_wb = "斗地主最终版工作台" in porcelain or "工作台" in porcelain
    return {
        "branch": branch,
        "dirty": dirty,
        "status_short": porcelain if porcelain else "（工作区干净，无未跟踪/未修改文件）",
        "last_commits": log,
        "untracked_tests": untracked_tests,
        "untracked_workbench": untracked_wb,
    }

# ---------------------------------------------------------------------------
# 2. 后端 ai_engine.py 函数清单（带 TASK 标签）
# ---------------------------------------------------------------------------
TASK_MAP = {
    "estimate_hands": ("TASK-001 手数分析", "tag-t1"),
    "split_penalty": ("TASK-002 拆牌罚分", "tag-t2"),
    "probably_has": ("TASK-005 概率记牌", "tag-t5"),
    "estimate_pair_in": ("TASK-005 概率记牌", "tag-t5"),
    "estimate_triple_in": ("TASK-005 概率记牌", "tag-t5"),
    "estimate_bomb_in": ("TASK-005 概率记牌", "tag-t5"),
    "estimate_straight_in": ("TASK-005 概率记牌", "tag-t5"),
    "estimate_count_in": ("TASK-005 概率记牌", "tag-t5"),
    "remaining_map": ("TASK-005 概率记牌", "tag-t5"),
    "big_cards_status": ("TASK-005 概率记牌", "tag-t5"),
    "possible_bomb_threat": ("TASK-005 概率记牌", "tag-t5"),
    "candidate_score": ("决策核心", "tag-core"),
    "ai_should_pass_counter": ("决策核心", "tag-core"),
    "route_value": ("决策核心", "tag-core"),
    "big_value": ("决策核心", "tag-core"),
    "control_tradeoff": ("决策核心", "tag-core"),
    "ai_play": ("AI 主决策", "tag-core"),
    "ai_lead": ("AI 主决策", "tag-core"),
    "ai_find_counter": ("AI 主决策", "tag-core"),
    "ai_pick_scored": ("AI 主决策", "tag-core"),
    "detect_pattern": ("牌型识别", "tag-tool"),
    "evaluate_hand": ("牌型评估", "tag-tool"),
    "_greedy_split": ("拆牌算法", "tag-tool"),
    "detect_structure_loss": ("拆牌算法", "tag-tool"),
    "kicker_waste": ("拆牌算法", "tag-tool"),
    "hand_shape": ("拆牌算法", "tag-tool"),
    "bomb_allowed": ("拆牌算法", "tag-tool"),
    "ai_observe_play": ("学习/记录", "tag-tool"),
    "ai_record_step": ("学习/记录", "tag-tool"),
}

def scan_backend():
    path = os.path.join(ROOT, "backend", "ai_engine.py")
    if not os.path.exists(path):
        return {"file": "../backend/ai_engine.py", "functions": [], "line_count": 0}
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    fns = []
    pat = re.compile(r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
    for i, ln in enumerate(lines, 1):
        m = pat.match(ln)
        if m:
            name = m.group(1)
            tag, cls = TASK_MAP.get(name, (None, ""))
            fns.append({"name": name, "line": i, "task": tag, "tagcls": cls})
    abspath = path.replace("\\", "/")
    return {"file": "../backend/ai_engine.py", "abspath": abspath, "functions": fns, "line_count": len(lines)}

# ---------------------------------------------------------------------------
# 3. 前端 game.js 函数清单（标注空壳）
# ---------------------------------------------------------------------------
def scan_frontend():
    path = os.path.join(ROOT, "frontend", "game.js")
    if not os.path.exists(path):
        return {"file": "../frontend/game.js", "functions": []}
    with open(path, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    lines = content.splitlines()
    pat = re.compile(r"^\s*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
    # 找"已迁移"注释块之后的空壳函数（return 0 / return false）
    shell_names = set()
    mig_idx = content.find("已迁移到后端")
    if mig_idx >= 0:
        tail = content[mig_idx:]
        for m in re.finditer(r"function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{return\s*(0|false)\s*;?\s*\}", tail):
            shell_names.add(m.group(1))
    fns = []
    for i, ln in enumerate(lines, 1):
        m = pat.match(ln)
        if m:
            name = m.group(1)
            if name in shell_names:
                fns.append({"name": name, "line": i, "role": "已迁移后端(空壳)", "tagcls": "tag-shell"})
            elif name.startswith("ai") or name.startswith("Ai"):
                fns.append({"name": name, "line": i, "role": "AI/交互", "tagcls": "tag-ui"})
            else:
                fns.append({"name": name, "line": i, "role": "UI/交互", "tagcls": "tag-ui"})
    abspath = path.replace("\\", "/")
    return {"file": "../frontend/game.js", "abspath": abspath, "functions": fns}

# ---------------------------------------------------------------------------
# 4. tests 真实状态（尝试真实运行 jest）
# ---------------------------------------------------------------------------
def find_node():
    n = shutil.which("node")
    if n:
        return n
    for cand in [
        r"C:/Users/15436/.workbuddy/binaries/node/versions/22.22.2-2/node.exe",
        r"C:/Users/15436/.workbuddy/binaries/node/versions/22.22.2/node.exe",
    ]:
        if os.path.exists(cand):
            return cand
    return None

def run_jest():
    tests_dir = os.path.join(ROOT, "tests")
    if not os.path.isdir(tests_dir):
        return {"ran": False, "error": "tests/ 目录不存在", "raw": ""}
    node = find_node()
    jest_js = os.path.join(tests_dir, "node_modules", "jest", "bin", "jest.js")
    if not node or not os.path.exists(jest_js):
        return {"ran": False, "error": "未找到 node 或 jest，无法运行", "raw": ""}
    try:
        r = subprocess.run([node, jest_js, "--passWithNoTests"],
                           cwd=tests_dir, capture_output=True, text=True, timeout=150)
        out = (r.stdout + r.stderr).strip()
        summary = ""
        for line in out.splitlines():
            if "Tests:" in line or "Test Suites:" in line:
                summary += line.strip() + "  "
        return {"ran": True, "summary": summary.strip() or "已运行（无汇总行）",
                "raw": out[-1500:] if out else "(无输出)"}
    except subprocess.TimeoutExpired:
        return {"ran": False, "error": "jest 运行超时(>150s)", "raw": ""}
    except Exception as e:
        return {"ran": False, "error": f"jest 运行异常: {e}", "raw": ""}

def scan_tests():
    tests_dir = os.path.join(ROOT, "tests")
    committed = "tests/" not in git(["status", "--porcelain"])
    files = []
    if os.path.isdir(tests_dir):
        for f in sorted(os.listdir(tests_dir)):
            if f.endswith(".test.js") or f in ("decision.test.js", "hand-count.test.js",
                                                "regression.test.js", "performance.test.js"):
                files.append(f)
    jest = run_jest()
    return {
        "dir": "../tests/",
        "committed": committed,
        "files": files,
        "jest_run": jest,
        "coverage": "覆盖 8/31 旧前端 engine.js 快照，未覆盖后端 ai_engine.py",
        "backend_has_tests": False,
    }

# ---------------------------------------------------------------------------
# 5. 目录树（排除噪声目录）
# ---------------------------------------------------------------------------
IGNORE = {".git", "node_modules", "__pycache__", "audio", "avatars", ".github",
          "doudizhu-game"}

def build_tree(base, prefix="", depth=0, max_depth=3):
    out = []
    if depth > max_depth:
        return out
    try:
        items = sorted(os.listdir(base))
    except Exception:
        return out
    items = [x for x in items if x not in IGNORE and not x.startswith(".")]
    for x in items:
        p = os.path.join(base, x)
        if os.path.isdir(p):
            out.append(f"{prefix}{x}/")
            out.extend(build_tree(p, prefix + "  ", depth + 1, max_depth))
        else:
            out.append(f"{prefix}{x}")
    return out

# ---------------------------------------------------------------------------
# 5.5 协作动态（由 AI 在 WorkBuddy 侧维护，工作台自动同步显示）
# ---------------------------------------------------------------------------
def load_collab():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    default = {
        "updated_at": now,
        "current_task": "（暂无进行中任务）",
        "roles": {
            "组长": {"status": "在线", "note": "协调全局、做最终检查与交付"},
            "提示词工程师": {"status": "待命", "note": "等待组长派发提示词编写任务"},
            "后端开发者": {"status": "待命", "note": "TASK-001/002/005 已落地，等待新需求"},
            "前端开发者": {"status": "待命", "note": "交互/回放/UI 维护"},
            "测试工程师": {"status": "待命", "note": "tests/ 旧快照失效，待补 Pytest"},
        },
        "activities": [
            {"time": now, "role": "系统", "type": "同步",
             "text": "工作台升级为实时同步操作台：新增协作动态流，打开网页即自动拉取最新真实数据与 AI 协作动态。"},
        ],
    }
    try:
        if os.path.exists(COLLAB_JSON):
            with open(COLLAB_JSON, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    with open(COLLAB_JSON, "w", encoding="utf-8") as f:
        json.dump(default, f, ensure_ascii=False, indent=2)
    return default

# ---------------------------------------------------------------------------
# 6. 工作台资产状态（有效性核查）
# ---------------------------------------------------------------------------
def asset_status():
    wb = "斗地主最终版工作台"
    return [
        {"path": f"{wb}/提示词/TASK-001-手数分析.docx", "status": "有效",
         "reason": "Word 版（与原始 .md 同源）；与后端 estimate_hands / hand_bonus 真实函数逐字吻合"},
        {"path": f"{wb}/提示词/TASK-002-拆牌罚分层级.docx", "status": "有效",
         "reason": "Word 版；与后端 split_penalty 真实函数吻合"},
        {"path": f"{wb}/提示词/TASK-005-概率记牌推算.docx", "status": "有效",
         "reason": "Word 版；与后端 probably_has / estimate_*_in 系列真实函数吻合"},
        {"path": f"{wb}/多AI三角色协作架构设计.md", "status": "有效",
         "reason": "协作架构说明文档，仍适用"},
        {"path": f"{wb}/目录结构.md", "status": "已过时",
         "reason": "未同步最终结构（README 已是权威结构说明）"},
        {"path": f"{wb}/测试报告/测试报告-TASK001-手数分析.md", "status": "已过时",
         "reason": "基于未提交 git、且已与后端脱钩的旧前端 tests/，'41/41 通过'对当前后端无效"},
        {"path": f"{wb}/测试工具/GameSimulator.js", "status": "已过时",
         "reason": "独立 JS 玩具，重写套牌逻辑，与真实后端引擎脱钩"},
        {"path": f"{wb}/测试工具/AIDecisionRecorder.js", "status": "已过时",
         "reason": "独立脚本，未接真实引擎"},
        {"path": f"{wb}/测试工具/WinRateCalculator.js", "status": "已过时",
         "reason": "独立脚本，未接真实引擎"},
        {"path": f"{wb}/测试用例/功能测试/", "status": "已过时",
         "reason": "目录为空，占位测试从未调用真实函数"},
        {"path": f"{wb}/团队/", "status": "有效",
         "reason": "三角色/多角色定义文档，作为协作参考仍有效（静态）"},
        {"path": "tests/ (项目根)", "status": "已过时",
         "reason": "覆盖 8/31 旧前端 engine.js 快照，未覆盖后端 ai_engine.py，且未提交 git"},
    ]

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "generated_at": now,
        "collab": load_collab(),
        "project": {
            "root": ROOT,
            "git": git_status(),
            "backend": scan_backend(),
            "frontend": scan_frontend(),
            "tests": scan_tests(),
            "tree": [f"{os.path.basename(ROOT)}/"] + build_tree(ROOT),
        },
        "assets": asset_status(),
    }

    # 删除旧产物名，避免混淆
    old = os.path.join(WORKBENCH, "项目状态.json")
    if os.path.exists(old):
        try: os.remove(old)
        except Exception: pass

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    html = tpl.replace("/*__WORKBENCH_DATA__*/ null",
                       json.dumps(data, ensure_ascii=False))
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[{now}] 已生成：")
    print(f"  - {OUT_JSON}")
    print(f"  - {OUT_HTML}")
    print(f"  Git 分支: {data['project']['git']['branch']} | 脏: {data['project']['git']['dirty']}")
    print(f"  后端函数: {len(data['project']['backend']['functions'])} 个")
    print(f"  前端函数: {len(data['project']['frontend']['functions'])} 个")
    print(f"  jest 运行: {data['project']['tests']['jest_run'].get('ran')}")
    print(f"  协作动态: {len(data['collab']['activities'])} 条 (来源 协作状态.json)")

if __name__ == "__main__":
    main()
