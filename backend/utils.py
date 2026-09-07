"""
斗地主终极版 - 共享工具模块
提供数据库连接、密码哈希、云存储、文件工具等，被所有 Blueprint 路由 import。
"""

import os
import hashlib
import sqlite3
import time
import subprocess as _subprocess

# === MySQL 可选依赖 ===
try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    pymysql = None
    DictCursor = None

# === 数据库配置（全部从环境变量读取，禁止硬编码凭据）===
# 本地开发可在 backend/config_local.py 中覆盖（该文件已在 .gitignore 中）
# config_local.LOCAL_SQLITE=True → 本机强制 sqlite，绝不写线上库（部署机无此文件，互不影响）
try:
    from config_local import (  # type: ignore
        DB_HOST as _LOCAL_HOST, DB_PORT as _LOCAL_PORT, DB_USER as _LOCAL_USER,
        DB_PASSWORD as _LOCAL_PASSWORD, DB_NAME as _LOCAL_NAME,
    )
except ImportError:
    _LOCAL_HOST = _LOCAL_USER = _LOCAL_PASSWORD = _LOCAL_NAME = None
    _LOCAL_PORT = None

try:
    from config_local import LOCAL_SQLITE as _LOCAL_SQLITE  # type: ignore
except (ImportError, AttributeError):
    _LOCAL_SQLITE = False

DB_HOST = os.environ.get("DB_HOST") or _LOCAL_HOST or ""
DB_PORT = int(os.environ.get("DB_PORT") or _LOCAL_PORT or 3306)
DB_USER = os.environ.get("DB_USER") or _LOCAL_USER or "doudizhu_game"
DB_PASSWORD = os.environ.get("DB_PASSWORD") or _LOCAL_PASSWORD or ""
DB_NAME = os.environ.get("DB_NAME") or _LOCAL_NAME or "james-wu-d2gcojd404e6b8137"
# 环境变量 DB_HOST 显式注入优先于本地开关（线上部署走环境变量，不受 LOCAL_SQLITE 影响）
USE_MYSQL = bool(DB_HOST) and pymysql is not None and not (
    _LOCAL_SQLITE and not os.environ.get("DB_HOST"))
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "doudizhu.db")

# === SQLite 兼容包装器（让 SQLite 用 %s 占位符，和 MySQL 保持一致）===
class _SQLiteCursor:
    def __init__(self, cursor):
        self._c = cursor
    def execute(self, query, params=None):
        if params and '%s' in query:
            query = query.replace('%s', '?')
        return self._c.execute(query, params) if params else self._c.execute(query)
    def executemany(self, query, params_list):
        if '%s' in query:
            query = query.replace('%s', '?')
        return self._c.executemany(query, params_list)
    def fetchone(self): return self._c.fetchone()
    def fetchall(self): return self._c.fetchall()
    @property
    def lastrowid(self): return self._c.lastrowid
    def __getattr__(self, name): return getattr(self._c, name)

class _SQLiteConn:
    def __init__(self, conn):
        self._conn = conn
    def cursor(self): return _SQLiteCursor(self._conn.cursor())
    def commit(self): return self._conn.commit()
    def close(self): return self._conn.close()
    def __getattr__(self, name): return getattr(self._conn, name)

_mysql_retry_after = 0.0

def get_db():
    """根据配置自动选择 MySQL 或 SQLite；MySQL 连接失败时自动回退 SQLite 并冷却 5 分钟"""
    global _mysql_retry_after
    if USE_MYSQL and time.time() >= _mysql_retry_after:
        try:
            conn = pymysql.connect(
                host=DB_HOST, port=DB_PORT, user=DB_USER,
                password=DB_PASSWORD, database=DB_NAME,
                charset="utf8mb4", cursorclass=DictCursor,
                connect_timeout=20, read_timeout=60, write_timeout=60,
                autocommit=True,
                init_command="SET time_zone='+08:00'"
            )
            _mysql_retry_after = 0.0
            return conn
        except Exception as e:
            _mysql_retry_after = time.time() + 300
            print(f"[数据库] MySQL 连接失败({type(e).__name__}: {e})，5 分钟内自动走 SQLite，之后自动重试", flush=True)
    else:
        if USE_MYSQL:
            print(f"[数据库] MySQL 处于冷却期，剩余 {int(_mysql_retry_after - time.time())}s，本次走 SQLite", flush=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return _SQLiteConn(conn)


# === 时间戳统一（20260907 时区修复）===
# sqlite 的 CURRENT_TIMESTAMP 恒为 UTC，导致本地库 created_at 比北京时间早 8 小时。
# 所有 INSERT 改为显式写入北京时间的字面值，与线上 MySQL（SET time_zone='+08:00'）语义一致。
# 用 UTC+8 计算，不依赖本机时区设置。
def beijing_now_str():
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")


def fmt_created_at(v):
    """接口输出统一 created_at 格式。
    pymysql 取回的 datetime 对象会被 Flask 序列化成 RFC822 英文日期（"Tue, 01 Sep 2026 ... GMT"），
    与本地 sqlite 的 "YYYY-MM-DD HH:MM:SS" 字符串不一致，前端 substring 截取会错位。
    此处把 datetime 转回同格式字符串（线上库本身存的就是北京时间字面值）。"""
    from datetime import datetime as _dt
    if isinstance(v, _dt):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v or ""


# === 密码哈希 ===
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# === 云存储备份/恢复 ===
CLOUD_PATH = "doudizhu-backup/doudizhu.db"

def cloud_download():
    """从云存储下载数据库（启动时调用）"""
    if USE_MYSQL:
        print("[云存储] MySQL 模式，跳过云存储下载")
        return
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
    if USE_MYSQL:
        return
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


# === 头像文件工具 ===
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatars")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 2 * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
