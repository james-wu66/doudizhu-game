"""
游戏数据路由：战绩统计、结算记录、排行榜、对局回放
"""

import json
from urllib.parse import unquote
from flask import Blueprint, request, jsonify
from utils import get_db, cloud_upload

game_bp = Blueprint("game", __name__)


@game_bp.route("/api/stats/<name>")
def get_stats(name):
    name = unquote(name)
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN result = 'lose' THEN 1 ELSE 0 END) as losses
        FROM game_records WHERE user_name = %s
    """, (name,))
    row = c.fetchone()
    total = row["total"] or 0
    wins = row["wins"] or 0
    losses = row["losses"] or 0
    win_rate = round(wins / total * 100, 1) if total > 0 else 0
    c.execute("SELECT result FROM game_records WHERE user_name = %s ORDER BY created_at DESC LIMIT 20", (name,))
    recent = [r["result"] for r in c.fetchall()]
    streak = 0
    for r in recent:
        if r == "win": streak += 1
        else: break
    conn.close()
    return jsonify({"name": name, "total": total, "wins": wins, "losses": losses, "win_rate": win_rate, "streak": streak})


@game_bp.route("/api/game/end", methods=["POST"])
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (name, result, role, rounds, duration, ai_decisions, score_change, bid_score))
    game_id = c.lastrowid
    conn.commit()
    conn.close()
    try: cloud_upload()
    except: pass
    return jsonify({"success": True, "game_id": game_id})


@game_bp.route("/api/leaderboard")
def leaderboard():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT u.name, COUNT(g.id) as total,
               SUM(CASE WHEN g.result = 'win' THEN 1 ELSE 0 END) as wins,
               ROUND(SUM(CASE WHEN g.result = 'win' THEN 1 ELSE 0 END) * 100.0 / COUNT(g.id), 1) as win_rate
        FROM users u LEFT JOIN game_records g ON u.name = g.user_name
        GROUP BY u.name HAVING total > 0 ORDER BY win_rate DESC, wins DESC LIMIT 20
    """)
    rows = c.fetchall()
    conn.close()
    result = []
    for i, row in enumerate(rows, 1):
        result.append({"rank": i, "name": row["name"], "total": row["total"], "wins": row["wins"], "win_rate": row["win_rate"] or 0})
    return jsonify(result)


@game_bp.route("/api/games/<int:game_id>/replay")
def get_game_replay(game_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, user_name, result, role, bid_score, score_change, ai_decisions, rounds, created_at
        FROM game_records WHERE id = %s
    """, (game_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "对局不存在"}), 404
    c.execute("SELECT id FROM game_records WHERE user_name = %s ORDER BY created_at DESC LIMIT 3", (row["user_name"],))
    recent_ids = [r["id"] for r in c.fetchall()]
    conn.close()
    if game_id not in recent_ids:
        return jsonify({"error": "只保留最近3局的回放数据"}), 404
    try: moves = json.loads(row["ai_decisions"]) if row["ai_decisions"] else []
    except: moves = []
    return jsonify({
        "success": True, "game_id": game_id, "user_name": row["user_name"],
        "result": row["result"], "role": row["role"], "bid_score": row["bid_score"],
        "score_change": row["score_change"], "rounds": row["rounds"] if row["rounds"] is not None else 0,
        "created_at": row["created_at"], "moves": moves
    })
