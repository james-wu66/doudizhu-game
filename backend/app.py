"""
斗地主终极版 - Flask后端
功能：用户登录注册、战绩统计、排行榜、AI学习数据收集
"""

import os
import json
import hashlib
import secrets
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import uuid
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "doudizhu.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn



# === 云存储备份/恢复 ===
import subprocess as _subprocess
CLOUD_PATH = "doudizhu-backup/doudizhu.db"

def cloud_download():
    """从云存储下载数据库（启动时调用）"""
    try:
        result = _subprocess.run(
            ["tcb", "storage", "download", CLOUD_PATH, DB_PATH,
             "--env-id", os.environ.get("TCB_ENV_ID", "")],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("[云存储] 数据库下载成功")
        else:
            print(f"[云存储] 下载失败（首次运行正常）: {result.stderr[:100]}")
    except Exception as e:
        print(f"[云存储] 下载异常: {e}")

def cloud_upload():
    """上传数据库到云存储（每次保存战绩后调用）"""
    try:
        result = _subprocess.run(
            ["tcb", "storage", "upload", DB_PATH, CLOUD_PATH,
             "--env-id", os.environ.get("TCB_ENV_ID", "")],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("[云存储] 数据库上传成功")
        else:
            print(f"[云存储] 上传失败: {result.stderr[:100]}")
    except Exception as e:
        print(f"[云存储] 上传异常: {e}")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            result TEXT NOT NULL,
            role TEXT,
            rounds INTEGER,
            duration_seconds INTEGER,
            ai_decisions TEXT,
            score_change INTEGER DEFAULT 0,
            bid_score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_learning (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER,
            step_number INTEGER,
            hand_state TEXT,
            action_taken TEXT,
            action_type TEXT,
            result TEXT,
            score_change REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 迁移：给老数据库补字段（已存在则忽略）
    try:
        c.execute("ALTER TABLE game_records ADD COLUMN score_change INTEGER DEFAULT 0")
    except: pass
    try:
        c.execute("ALTER TABLE game_records ADD COLUMN bid_score INTEGER DEFAULT 0")
    except: pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    except: pass
    # 隐私：是否允许他人查看自己的战绩（1=允许，0=不允许），老用户默认允许
    try:
        c.execute("ALTER TABLE users ADD COLUMN allow_view_stats INTEGER DEFAULT 1")
    except: pass

    conn.commit()
    conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


@app.route("/")
def index():
    return send_from_directory("../frontend", "index.html")

@app.route("/audio/<path:filename>")
def serve_audio(filename):
    from urllib.parse import unquote
    filename = unquote(filename)
    return send_from_directory("../audio", filename)

@app.route("/sound.js")
def serve_sound_js():
    return send_from_directory("../frontend", "sound.js")

@app.route("/manifest.json")
def serve_manifest():
    return send_from_directory("../frontend", "manifest.json")

@app.route("/sw.js")
def serve_sw():
    return send_from_directory("../frontend", "sw.js")

@app.route("/icons/<path:filename>")
def serve_icons(filename):
    return send_from_directory("../frontend/icons", filename)

@app.route("/lobby")
def lobby():
    return send_from_directory("../frontend", "lobby.html")


@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name", "").strip()
    password = data.get("password", "")
    
    if not name:
        return jsonify({"error": "请输入名字"}), 400
    if len(password) < 4:
        return jsonify({"error": "密码至少4位"}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE name = ?", (name,))
    if c.fetchone():
        conn.close()
        return jsonify({"error": "这个名字已经被用了"}), 400
    
    token = secrets.token_hex(16)
    c.execute("INSERT INTO users (name, password_hash, token) VALUES (?, ?, ?)",
              (name, hash_password(password), token))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "token": token, "name": name})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    name = data.get("name", "").strip()
    password = data.get("password", "")
    
    if not name or not password:
        return jsonify({"error": "请输入名字和密码"}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE name = ? AND password_hash = ?",
              (name, hash_password(password)))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return jsonify({"error": "名字或密码不对"}), 400
    
    token = secrets.token_hex(16)
    c.execute("UPDATE users SET token = ? WHERE id = ?", (token, user["id"]))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "token": token, "name": name})


@app.route("/api/auto-login", methods=["POST"])
def auto_login():
    data = request.json
    token = data.get("token", "")
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM users WHERE token = ?", (token,))
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({"success": True, "name": user["name"]})
    return jsonify({"success": False}), 400


@app.route("/api/stats/<name>")
def get_stats(name):
    from urllib.parse import unquote
    name = unquote(name)
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN result = 'lose' THEN 1 ELSE 0 END) as losses
        FROM game_records WHERE user_name = ?
    """, (name,))
    row = c.fetchone()
    
    total = row["total"] or 0
    wins = row["wins"] or 0
    losses = row["losses"] or 0
    win_rate = round(wins / total * 100, 1) if total > 0 else 0
    
    c.execute("SELECT result FROM game_records WHERE user_name = ? ORDER BY created_at DESC LIMIT 20", (name,))
    recent = [r["result"] for r in c.fetchall()]
    streak = 0
    for r in recent:
        if r == "win":
            streak += 1
        else:
            break
    
    conn.close()
    return jsonify({"name": name, "total": total, "wins": wins, "losses": losses, "win_rate": win_rate, "streak": streak})


@app.route("/api/game/end", methods=["POST"])
def record_game():
    data = request.json
    name = data.get("name")
    result = data.get("result")
    role = data.get("role", "")
    rounds = data.get("rounds", 0)
    duration = data.get("duration", 0)
    ai_decisions = json.dumps(data.get("ai_decisions", []), ensure_ascii=False)
    score_change = data.get("score_change", 0)
    bid_score = data.get("bid_score", 0)
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO game_records (user_name, result, role, rounds, duration_seconds, ai_decisions, score_change, bid_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, result, role, rounds, duration, ai_decisions, score_change, bid_score))
    game_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # 每次保存战绩后自动上传到云存储
    try:
        cloud_upload()
    except: pass

    return jsonify({"success": True, "game_id": game_id})


@app.route("/api/leaderboard")
def leaderboard():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT u.name, COUNT(g.id) as total,
               SUM(CASE WHEN g.result = 'win' THEN 1 ELSE 0 END) as wins,
               ROUND(CAST(SUM(CASE WHEN g.result = 'win' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(g.id) * 100, 1) as win_rate
        FROM users u
        LEFT JOIN game_records g ON u.name = g.user_name
        GROUP BY u.name
        HAVING total > 0
        ORDER BY win_rate DESC, wins DESC
        LIMIT 20
    """)
    rows = c.fetchall()
    conn.close()
    
    result = []
    for i, row in enumerate(rows, 1):
        result.append({"rank": i, "name": row["name"], "total": row["total"], "wins": row["wins"], "win_rate": row["win_rate"] or 0})
    return jsonify(result)


@app.route("/api/ai/record", methods=["POST"])
def record_ai_step():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO ai_learning (game_id, step_number, hand_state, action_taken, action_type, result, score_change)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (data.get("game_id"), data.get("step"),
          json.dumps(data.get("hand_state", []), ensure_ascii=False),
          json.dumps(data.get("action", {}), ensure_ascii=False),
          data.get("action_type", ""), data.get("result", ""), data.get("score_change", 0)))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/ai/insights")
def ai_insights():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT action_type, COUNT(*) as total,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
               AVG(score_change) as avg_score
        FROM ai_learning WHERE action_type != ''
        GROUP BY action_type HAVING total >= 3
        ORDER BY avg_score DESC
    """)
    rows = c.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append({
            "action_type": row["action_type"], "total": row["total"], "wins": row["wins"],
            "win_rate": round(row["wins"] / row["total"] * 100, 1) if row["total"] > 0 else 0,
            "avg_score": round(row["avg_score"], 2)
        })
    return jsonify(result)





@app.route("/api/users/<name>")
def get_user_profile(name):
    from urllib.parse import unquote
    name = unquote(name)
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins
        FROM game_records WHERE user_name = ?
    """, (name,))
    row = c.fetchone()
    total = row["total"] or 0
    wins = row["wins"] or 0
    win_rate = round(wins / total * 100, 1) if total > 0 else 0

    # 最高连胜：从历史记录中计算
    c.execute("SELECT result FROM game_records WHERE user_name = ? ORDER BY created_at DESC", (name,))
    results = [r["result"] for r in c.fetchall()]
    max_streak = 0
    current_streak = 0
    for r in results:
        if r == "win":
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    c.execute("SELECT allow_view_stats FROM users WHERE name = ?", (name,))
    urow = c.fetchone()
    allow_view = urow["allow_view_stats"] if urow and urow["allow_view_stats"] is not None else 1

    conn.close()
    return jsonify({"success": True, "name": name, "allow_view_stats": allow_view, "stats": {"total": total, "wins": wins, "win_rate": win_rate, "streak": max_streak}})


@app.route("/api/users/<name>/games")
def get_user_games(name):
    from urllib.parse import unquote
    name = unquote(name)
    viewer = request.args.get('viewer', '')
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT allow_view_stats FROM users WHERE name = ?", (name,))
    urow = c.fetchone()
    allow = urow["allow_view_stats"] if urow and urow["allow_view_stats"] is not None else 1

    # 隐私：非本人且对方关闭战绩可见，返回空列表并标记 hidden（临时鉴权：viewer 由前端传当前用户名，P2 接入 token）
    is_self = (viewer == name)
    if not is_self and allow == 0:
        conn.close()
        return jsonify({"success": True, "games": [], "hidden": True})

    c.execute("""
        SELECT id, result, role, score_change, bid_score, created_at
        FROM game_records WHERE user_name = ?
        ORDER BY created_at DESC LIMIT 50
    """, (name,))
    rows = c.fetchall()
    conn.close()

    games = []
    for row in rows:
        games.append({
            "game_id": row["id"],
            "result": row["result"],
            "mode": "经典新手场",
            "role": row["role"] or "",
            "score_change": row["score_change"] or 0,
            "bid_score": row["bid_score"] or 0,
            "created_at": row["created_at"] or ""
        })
    return jsonify({"success": True, "games": games})


@app.route("/api/users/<name>/privacy", methods=["POST"])
def update_privacy(name):
    # 临时鉴权：当前无 token，用前端传入的 viewer 身份校验（P2 阶段接入 token 鉴权）
    from urllib.parse import unquote
    name = unquote(name)
    data = request.get_json(silent=True) or {}
    viewer = data.get('viewer', '') or ''
    if viewer != name:
        return jsonify({"success": False, "error": "无权修改他人隐私设置"}), 403
    allow_view = 1 if data.get('allow_view', True) else 0
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET allow_view_stats = ? WHERE name = ?", (allow_view, name))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/games/<int:game_id>/replay")
def get_game_replay(game_id):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT id, user_name, result, role, bid_score, score_change, ai_decisions, rounds, created_at
        FROM game_records WHERE id = ?
    """, (game_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "对局不存在"}), 404

    # 检查是否是该用户最近3局
    c.execute("SELECT id FROM game_records WHERE user_name = ? ORDER BY created_at DESC LIMIT 3", (row["user_name"],))
    recent_ids = [r["id"] for r in c.fetchall()]
    conn.close()

    if game_id not in recent_ids:
        return jsonify({"error": "只保留最近3局的回放数据"}), 404

    try:
        moves = json.loads(row["ai_decisions"]) if row["ai_decisions"] else []
    except:
        moves = []

    return jsonify({
        "success": True,
        "game_id": game_id,
        "user_name": row["user_name"],
        "result": row["result"],
        "role": row["role"],
        "bid_score": row["bid_score"],
        "score_change": row["score_change"],
        "rounds": row["rounds"] if row["rounds"] is not None else 0,
        "created_at": row["created_at"],
        "moves": moves
    })




UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatars")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/api/users/<name>/avatar", methods=["POST"])
def upload_avatar(name):
    from urllib.parse import unquote
    name = unquote(name)

    if 'file' not in request.files:
        return jsonify({"success": False, "error": "没有文件"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "没有选择文件"}), 400
    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "不支持的文件格式"}), 400

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return jsonify({"success": False, "error": "文件大小超过2MB"}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{name}_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    try:
        file.save(filepath)
        try:
            from PIL import Image
            img = Image.open(filepath)
            img = img.resize((200, 200), Image.Resampling.LANCZOS)
            img.save(filepath, quality=85)
        except:
            pass

        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET avatar_url = ? WHERE name = ?", (filename, name))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "avatar_url": "/api/users/" + name + "/avatar"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/users/<name>/avatar")
def get_avatar(name):
    from urllib.parse import unquote
    name = unquote(name)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT avatar_url FROM users WHERE name = ?", (name,))
    user = c.fetchone()
    conn.close()

    if not user or not user["avatar_url"]:
        return "", 404

    filepath = os.path.join(UPLOAD_FOLDER, user["avatar_url"])
    if not os.path.exists(filepath):
        return "", 404

    return send_from_directory(UPLOAD_FOLDER, user["avatar_url"])


if __name__ == "__main__":
    init_db()
    cloud_download()
    print("=" * 40)
    print("  斗地主后端启动成功！")
    print("  http://localhost:5000")
    print("=" * 40)
    import os as _os
    port = int(_os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
