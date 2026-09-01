"""
斗地主终极版 - Flask 后端（精简主文件）
职责：Flask 初始化、数据库建表、诊断接口、Blueprint 注册、启动
路由已拆分到 routes/ 目录下的 5 个 Blueprint 模块
"""

import os
import json
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

# === 共享工具（数据库/密码/云存储）===
from utils import get_db, hash_password, cloud_download, cloud_upload, USE_MYSQL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_PATH

try:
    import pymysql
except ImportError:
    pymysql = None

# === Flask 初始化 ===
app = Flask(__name__)
CORS(app)

# === 注册 Blueprint ===
from routes.static_views import static_bp
from routes.auth import auth_bp
from routes.user import user_bp
from routes.game_data import game_bp
from routes.ai import ai_bp

app.register_blueprint(static_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(game_bp)
app.register_blueprint(ai_bp)


# === 数据库模式检测 ===
def _ensure_db_mode():
    """启动时测试 MySQL 连接：成功则用 MySQL，失败则回退 SQLite"""
    global USE_MYSQL
    if not USE_MYSQL:
        return
    try:
        probe = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME,
            charset="utf8mb4", connect_timeout=15
        )
        probe.close()
        print("[数据库] MySQL 连接成功")
        return
    except Exception as e:
        err = str(e)
        if '1049' in err or 'Unknown database' in err:
            try:
                print(f"[数据库] 库 {DB_NAME} 不存在，尝试自动创建...")
                bootstrap = pymysql.connect(
                    host=DB_HOST, port=DB_PORT, user=DB_USER,
                    password=DB_PASSWORD, charset="utf8mb4", connect_timeout=15
                )
                cur = bootstrap.cursor()
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4")
                bootstrap.close()
                probe2 = pymysql.connect(
                    host=DB_HOST, port=DB_PORT, user=DB_USER,
                    password=DB_PASSWORD, database=DB_NAME,
                    charset="utf8mb4", connect_timeout=15
                )
                probe2.close()
                print("[数据库] 自动建库 + 连接成功")
                return
            except Exception as e2:
                print(f"[数据库] 自动建库失败，回退 SQLite: {e2}")
                USE_MYSQL = False
                return
        print(f"[数据库] MySQL 连接失败，回退 SQLite: {e}")
        USE_MYSQL = False


# === 数据库建表（启动时运行一次）===
def init_db():
    _ensure_db_mode()
    if USE_MYSQL:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL, token VARCHAR(255),
                avatar_url VARCHAR(255), allow_view_stats INT DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS game_records (
                id INT PRIMARY KEY AUTO_INCREMENT, user_name VARCHAR(255) NOT NULL,
                result VARCHAR(50) NOT NULL, role VARCHAR(50), rounds INT,
                duration_seconds INT, ai_decisions LONGTEXT,
                score_change INT DEFAULT 0, bid_score INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS ai_learning (
                id INT PRIMARY KEY AUTO_INCREMENT, game_id INT, step_number INT,
                hand_state LONGTEXT, action_taken LONGTEXT, action_type VARCHAR(100),
                who VARCHAR(10), bucket VARCHAR(100), result VARCHAR(50),
                score_change FLOAT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        for col in ["round_id TEXT", "who TEXT", "bucket TEXT"]:
            try: c.execute(f"ALTER TABLE ai_learning ADD COLUMN {col}")
            except: pass
        for idx in ["CREATE INDEX idx_ai_learning_round ON ai_learning(round_id)",
                     "CREATE INDEX idx_ai_learning_stat ON ai_learning(action_type, bucket)"]:
            try: c.execute(idx)
            except: pass
        conn.close()
        print("[数据库] MySQL 表初始化完成")
    else:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = get_db()
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS game_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_name TEXT NOT NULL,
            result TEXT NOT NULL, role TEXT, rounds INTEGER,
            duration_seconds INTEGER, ai_decisions TEXT,
            score_change INTEGER DEFAULT 0, bid_score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS ai_learning (
            id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER,
            step_number INTEGER, hand_state TEXT, action_taken TEXT,
            action_type TEXT, who TEXT, bucket TEXT, result TEXT,
            score_change REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        for col in ["round_id TEXT", "who TEXT", "bucket TEXT",
                     "score_change INTEGER DEFAULT 0", "bid_score INTEGER DEFAULT 0",
                     "avatar_url TEXT", "allow_view_stats INTEGER DEFAULT 1"]:
            try: c.execute(f"ALTER TABLE ai_learning ADD COLUMN {col}")
            except: pass
        try: c.execute("CREATE INDEX IF NOT EXISTS idx_ai_learning_round ON ai_learning(round_id)")
        except: pass
        try: c.execute("CREATE INDEX IF NOT EXISTS idx_ai_learning_stat ON ai_learning(action_type, bucket)")
        except: pass
        conn.commit()
        conn.close()


# === 诊断接口 ===
@app.route("/api/diag")
def diag():
    result = {"db_mode": "mysql" if USE_MYSQL else "sqlite", "db_host": DB_HOST,
              "db_name": DB_NAME, "use_mysql_flag": USE_MYSQL, "version": "stage2-606fd08-20260831"}
    mysql_test = {"ok": False, "error": ""}
    try:
        test_conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME, charset="utf8mb4", connect_timeout=15)
        test_conn.close()
        mysql_test["ok"] = True
    except Exception as e:
        mysql_test["error"] = str(e)
    result["mysql_test"] = mysql_test
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) AS n FROM users")
        result["users_count"] = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) AS n FROM game_records")
        result["game_records_count"] = c.fetchone()["n"]
        conn.close()
        result["db_ok"] = True
    except Exception as e:
        result["db_ok"] = False
        result["db_error"] = str(e)
    return jsonify(result)


# === 启动 ===
if __name__ == "__main__":
    init_db()
    cloud_download()
    print(f"========================================")
    print(f"  斗地主后端启动成功！")
    print(f"  数据库模式: {'MySQL' if USE_MYSQL else 'SQLite'}")
    print(f"  http://localhost:8080")
    print(f"========================================")
    app.run(host="0.0.0.0", port=8080, debug=False)
