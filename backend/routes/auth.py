"""
用户认证路由：注册、登录、自动登录、注销账号
"""

import secrets
from flask import Blueprint, request, jsonify
from utils import get_db, hash_password, cloud_upload

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/register", methods=["POST"])
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
    c.execute("SELECT id FROM users WHERE name = %s", (name,))
    if c.fetchone():
        conn.close()
        return jsonify({"error": "这个名字已经被用了"}), 400
    token = secrets.token_hex(16)
    c.execute("INSERT INTO users (name, password_hash, token) VALUES (%s, %s, %s)",
              (name, hash_password(password), token))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "token": token, "name": name})


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.json
    name = data.get("name", "").strip()
    password = data.get("password", "")
    if not name or not password:
        return jsonify({"error": "请输入名字和密码"}), 400
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE name = %s AND password_hash = %s",
              (name, hash_password(password)))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "名字或密码不对"}), 400
    # 复用已有 token：避免同一账号在多设备登录时互相踢下线，
    # 导致旧设备 token 失效后被降级为游客、战绩静默丢失
    token = user["token"] or secrets.token_hex(16)
    if not user["token"]:
        c.execute("UPDATE users SET token = %s WHERE id = %s", (token, user["id"]))
        conn.commit()
    conn.close()
    return jsonify({"success": True, "token": token, "name": name})


@auth_bp.route("/api/auto-login", methods=["POST"])
def auto_login():
    data = request.json
    token = data.get("token", "")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM users WHERE token = %s", (token,))
    user = c.fetchone()
    conn.close()
    if user:
        return jsonify({"success": True, "name": user["name"]})
    return jsonify({"success": False}), 400


@auth_bp.route("/api/delete-account", methods=["POST"])
def delete_account():
    data = request.json
    name = data.get("name", "").strip()
    password = data.get("password", "")
    if not name or not password:
        return jsonify({"error": "请输入用户名和密码"}), 400
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, password_hash FROM users WHERE name = %s", (name,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "用户不存在"}), 404
    if user["password_hash"] != hash_password(password):
        conn.close()
        return jsonify({"error": "密码错误"}), 400
    c.execute("DELETE FROM ai_learning WHERE game_id IN (SELECT id FROM game_records WHERE user_name = %s)", (name,))
    c.execute("DELETE FROM game_records WHERE user_name = %s", (name,))
    c.execute("DELETE FROM users WHERE id = %s", (user["id"],))
    conn.commit()
    conn.close()
    try:
        cloud_upload()
    except: pass
    return jsonify({"success": True, "message": "账号已注销"})
