"""
用户信息路由：个人主页、战绩列表、隐私设置、头像上传/获取
"""

import os
import uuid
from urllib.parse import unquote
from flask import Blueprint, request, jsonify, send_from_directory
from utils import get_db, UPLOAD_FOLDER, allowed_file, MAX_FILE_SIZE

user_bp = Blueprint("user", __name__)

DEFAULT_AVATAR_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><circle cx="50" cy="38" r="18" fill="#374151"/><ellipse cx="50" cy="80" rx="28" ry="22" fill="#374151"/></svg>'


@user_bp.route("/api/users/<name>")
def get_user_profile(name):
    name = unquote(name)
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins
        FROM game_records WHERE user_name = %s
    """, (name,))
    row = c.fetchone()
    total = row["total"] or 0
    wins = row["wins"] or 0
    win_rate = round(wins / total * 100, 1) if total > 0 else 0

    c.execute("SELECT result FROM game_records WHERE user_name = %s ORDER BY created_at DESC", (name,))
    results = [r["result"] for r in c.fetchall()]
    max_streak = 0
    current_streak = 0
    for r in results:
        if r == "win":
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    c.execute("SELECT allow_view_stats FROM users WHERE name = %s", (name,))
    urow = c.fetchone()
    allow_view = urow["allow_view_stats"] if urow and urow["allow_view_stats"] is not None else 1
    conn.close()
    return jsonify({"success": True, "name": name, "allow_view_stats": allow_view, "stats": {"total": total, "wins": wins, "win_rate": win_rate, "streak": max_streak}})


@user_bp.route("/api/users/<name>/games")
def get_user_games(name):
    name = unquote(name)
    viewer = request.args.get('viewer', '')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT allow_view_stats FROM users WHERE name = %s", (name,))
    urow = c.fetchone()
    allow = urow["allow_view_stats"] if urow and urow["allow_view_stats"] is not None else 1
    is_self = (viewer == name)
    if not is_self and allow == 0:
        conn.close()
        return jsonify({"success": True, "games": [], "hidden": True})
    c.execute("""
        SELECT id, result, role, score_change, bid_score, created_at
        FROM game_records WHERE user_name = %s
        ORDER BY created_at DESC LIMIT 50
    """, (name,))
    rows = c.fetchall()
    conn.close()
    games = []
    for row in rows:
        games.append({
            "game_id": row["id"], "result": row["result"], "mode": "经典新手场",
            "role": row["role"] or "", "score_change": row["score_change"] or 0,
            "bid_score": row["bid_score"] or 0, "created_at": row["created_at"] or ""
        })
    return jsonify({"success": True, "games": games})


@user_bp.route("/api/users/<name>/privacy", methods=["POST"])
def update_privacy(name):
    name = unquote(name)
    data = request.get_json(silent=True) or {}
    viewer = data.get('viewer', '') or ''
    if viewer != name:
        return jsonify({"success": False, "error": "无权修改他人隐私设置"}), 403
    allow_view = 1 if data.get('allow_view', True) else 0
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET allow_view_stats = %s WHERE name = %s", (allow_view, name))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@user_bp.route("/api/users/<name>/avatar", methods=["POST"])
def upload_avatar(name):
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
        except: pass
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET avatar_url = %s WHERE name = %s", (filename, name))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "avatar_url": "/api/users/" + name + "/avatar"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@user_bp.route("/api/users/<name>/avatar")
def get_avatar(name):
    name = unquote(name)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT avatar_url FROM users WHERE name = %s", (name,))
    user = c.fetchone()
    conn.close()
    if not user or not user["avatar_url"]:
        return DEFAULT_AVATAR_SVG, 200, {"Content-Type": "image/svg+xml"}
    filepath = os.path.join(UPLOAD_FOLDER, user["avatar_url"])
    if not os.path.exists(filepath):
        return DEFAULT_AVATAR_SVG, 200, {"Content-Type": "image/svg+xml"}
    return send_from_directory(UPLOAD_FOLDER, user["avatar_url"])
