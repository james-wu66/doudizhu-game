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
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "doudizhu.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO game_records (user_name, result, role, rounds, duration_seconds, ai_decisions)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, result, role, rounds, duration, ai_decisions))
    game_id = c.lastrowid
    conn.commit()
    conn.close()
    
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


if __name__ == "__main__":
    init_db()
    print("=" * 40)
    print("  斗地主后端启动成功！")
    print("  http://localhost:5000")
    print("=" * 40)
    app.run(host="0.0.0.0", port=5000, debug=True)
