"""
静态文件路由：前端页面、CSS/JS、音频、图标、工作台控制台
"""

from flask import Blueprint, send_from_directory

static_bp = Blueprint("static", __name__)


@static_bp.route("/")
def index():
    resp = send_from_directory("../frontend", "index.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

@static_bp.route("/audio/<path:filename>")
def serve_audio(filename):
    from urllib.parse import unquote
    return send_from_directory("../audio", unquote(filename))

@static_bp.route("/sound.js")
def serve_sound_js():
    return send_from_directory("../frontend", "sound.js")

@static_bp.route("/style.css")
def serve_style_css():
    return send_from_directory("../frontend", "style.css")

@static_bp.route("/js/<path:filename>")
def serve_js(filename):
    from urllib.parse import unquote
    return send_from_directory("../frontend/js", unquote(filename))

@static_bp.route("/manifest.json")
def serve_manifest():
    return send_from_directory("../frontend", "manifest.json")

@static_bp.route("/sw.js")
def serve_sw():
    return send_from_directory("../frontend", "sw.js")

@static_bp.route("/icons/<path:filename>")
def serve_icons(filename):
    return send_from_directory("../frontend/icons", filename)

@static_bp.route("/lobby")
def lobby():
    resp = send_from_directory("../frontend", "lobby.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

@static_bp.route("/workbench")
@static_bp.route("/workbench/")
def workbench_index():
    resp = send_from_directory("../斗地主最终版工作台", "控制台.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

@static_bp.route("/workbench/<path:filename>")
def workbench_file(filename):
    resp = send_from_directory("../斗地主最终版工作台", filename)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp
