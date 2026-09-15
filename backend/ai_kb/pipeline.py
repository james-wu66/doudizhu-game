# -*- coding: utf-8 -*-
"""
ai_kb.pipeline — 知识库文档状态机（TASK-010 包B）
kb_document: pending → published / rejected；delete → archived（逻辑删除，文本保留可恢复）。
rules 内置手册特殊存储：正文文件 knowledge/rules.txt，本表记 status；
pending 期间旧版文件继续服务，approve 才写回文件并增量重建。
approved 文档正文统一落 backend/kb_docs/{doc_name}.txt（随 backend/ 进 Docker 镜像；
knowledge/ 目录被 .dockerignore 排除 *.md，所以只用 .txt 后缀）。
"""

import hashlib
import os
import re

from utils import get_db, beijing_now_str

_KBDOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kb_docs')
_KNOWN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'knowledge')
RULES_PATH = os.path.join(_KNOWN, 'rules.txt')

DOC_NAME_RE = re.compile(r'^[a-z0-9_]{3,48}$')   # doc_name 只许小写字母数字下划线，防注入


def ensure_tables(conn):
    """幂等建表，SQLite/MySQL 双方言（MySQL 侧本机未实测，交付报告标"未验证"）。"""
    try:
        import pymysql  # noqa
        from utils import USE_MYSQL
        is_sqlite = not USE_MYSQL
    except ImportError:
        is_sqlite = True
    if is_sqlite:
        conn.execute("""CREATE TABLE IF NOT EXISTS kb_document (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_name TEXT UNIQUE NOT NULL, title TEXT,
            source_filename TEXT, doc_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            visibility TEXT NOT NULL DEFAULT 'public',
            text TEXT NOT NULL, pages INTEGER, chars INTEGER,
            uploader TEXT, reviewer TEXT,
            created_at TEXT, updated_at TEXT)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_document_status ON kb_document(status)")
        conn.commit()
    else:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS kb_document (
            id INT PRIMARY KEY AUTO_INCREMENT,
            doc_name VARCHAR(48) UNIQUE NOT NULL, title VARCHAR(128),
            source_filename VARCHAR(255), doc_hash VARCHAR(32) NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            visibility VARCHAR(16) NOT NULL DEFAULT 'public',
            text MEDIUMTEXT NOT NULL, pages INT, chars INT,
            uploader VARCHAR(255), reviewer VARCHAR(255),
            created_at DATETIME, updated_at DATETIME)
            ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        try:
            c.execute("CREATE INDEX idx_kb_document_status ON kb_document(status)")
        except Exception:
            pass
    return is_sqlite


def doc_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:32]


def normalize_doc_name(name, raw):
    """校验/生成 doc_name：合法直接用；否则从标题或文件名 hash 生成 doc_<10位>。"""
    n = (name or '').strip().lower()
    if n == 'rules':
        return 'rules'
    if DOC_NAME_RE.match(n):
        return n
    seed = doc_hash((raw or n or os.urandom(8).hex()))[:10]
    return 'doc_' + seed


def get_doc(doc_name):
    conn = get_db()
    try:
        ensure_tables(conn)
        c = conn.cursor()
        c.execute("SELECT * FROM kb_document WHERE doc_name = %s", (doc_name,))
        r = c.fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def list_docs():
    conn = get_db()
    try:
        ensure_tables(conn)
        c = conn.cursor()
        c.execute("""SELECT id, doc_name, title, source_filename, status, visibility,
                     pages, chars, uploader, reviewer, created_at, updated_at
                     FROM kb_document ORDER BY id""")
        rows = [dict(r) for r in c.fetchall()]
        c.execute("SELECT doc_name, COUNT(*) cnt FROM kb_chunk GROUP BY doc_name")
        cnt = {r['doc_name']: r['cnt'] for r in c.fetchall()}
        for row in rows:
            row['chunks'] = cnt.get(row['doc_name'], 0)
        return rows
    finally:
        conn.close()


def create_or_update(doc_name, title, text, filename, uploader, visibility='public'):
    """上传/贴文本入口 → status=pending。rules 与普通文档同走此门（红线5）。
    返回 (row, unchanged)。unchanged=True 表示整文档 hash 与当前记录一致，秒判返回。"""
    ensure_safe_name(doc_name)
    h = doc_hash(text)
    vis = visibility if visibility in ('public', 'internal') else 'public'
    conn = get_db()
    try:
        ensure_tables(conn)
        c = conn.cursor()
        c.execute("SELECT * FROM kb_document WHERE doc_name = %s", (doc_name,))
        old = c.fetchone()
        now = beijing_now_str()
        if old and old['doc_hash'] == h and old['status'] in ('pending', 'published'):
            return dict(old), True
        if old:
            c.execute("""UPDATE kb_document SET title=%s, source_filename=%s, doc_hash=%s,
                         status='pending', visibility=%s, text=%s, pages=%s, chars=%s,
                         uploader=%s, updated_at=%s WHERE doc_name=%s""",
                      (title, filename, h, vis, text, None, len(text), uploader, now, doc_name))
        else:
            c.execute("""INSERT INTO kb_document
                         (doc_name,title,source_filename,doc_hash,status,visibility,
                          text,pages,chars,uploader,created_at,updated_at)
                         VALUES (%s,%s,%s,%s,'pending',%s,%s,%s,%s,%s,%s,%s)""",
                      (doc_name, title, filename, h, vis, text, None, len(text), uploader, now, now))
        conn.commit()
        c.execute("SELECT * FROM kb_document WHERE doc_name = %s", (doc_name,))
        return dict(c.fetchone()), False
    finally:
        conn.close()


def ensure_safe_name(doc_name):
    if doc_name != 'rules' and not DOC_NAME_RE.match(doc_name or ''):
        raise ValueError('非法 doc_name')


def _persist_body(doc_name, text):
    """approved 文档正文落盘（rules 写回 knowledge/rules.txt，其余写 kb_docs/）。"""
    os.makedirs(_KBDOCS, exist_ok=True)
    path = RULES_PATH if doc_name == 'rules' else os.path.join(_KBDOCS, doc_name + '.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return path


def preview(doc_name):
    """切片预览：块数 + 每块前 80 字（父块不计入预览列表）。
    full_text：整份原文截前 20000 字（管理员"看全内容再批准"用，20260915 jameswu 拍板）。"""
    d = get_doc(doc_name)
    if not d:
        return None
    return {'doc_name': doc_name, 'status': d['status'],
            'visibility': d.get('visibility'),
            'chunks': chunk_preview(d['text'], doc_name, d['status']),
            'full_text': (d['text'] or '')[:20000],
            'full_truncated': len(d['text'] or '') > 20000}


def chunk_preview(text, doc_name, status):
    """有中文章号结构走包A切片器，否则通用切片（与 sync_document 同规则）。"""
    from ai_kb.chunker import slice_chunks, slice_chunks_generic
    chunks = slice_chunks(text, doc_name=doc_name) or slice_chunks_generic(text, doc_name)
    return [dict(id=c['id'], title=c['title'], chars=len(c['text']),
                 head=c['text'][:80].replace('\n', ' '))
            for c in chunks if not c['is_parent']]


def approve(doc_name, reviewer):
    """pending → published：落盘正文 + 增量重算 embedding + 原子换内存索引。
    返回统计 dict（含 recomputed/elapsed_ms）。失败抛异常，状态保持 pending、旧版继续服务。"""
    import time
    from ai_kb import retriever
    d = get_doc(doc_name)
    if not d:
        raise ValueError('文档不存在')
    if d['status'] == 'published' and d['visibility'] in ('public', 'internal'):
        return {'doc_name': doc_name, 'unchanged': True, 'recomputed': 0, 'elapsed_ms': 0}
    t0 = time.time()
    _persist_body(doc_name, d['text'])
    if doc_name == 'rules':
        stat = retriever.rebuild_index('rules')
    else:
        stat = retriever.sync_document(doc_name, d['text'], visibility=d['visibility'])
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("UPDATE kb_document SET status='published', reviewer=%s, updated_at=%s WHERE doc_name=%s",
                  (reviewer, beijing_now_str(), doc_name))
        conn.commit()
    finally:
        conn.close()
    stat['doc_name'] = doc_name
    stat['elapsed_ms'] = int((time.time() - t0) * 1000)
    return stat


def reject(doc_name, reviewer):
    d = get_doc(doc_name)
    if not d:
        return False
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("UPDATE kb_document SET status='rejected', reviewer=%s, updated_at=%s WHERE doc_name=%s",
                  (reviewer, beijing_now_str(), doc_name))
        conn.commit()
    finally:
        conn.close()
    return True


def delete_doc(doc_name):
    """逻辑删除：archived + 索引即时移除（物理删块与文本，文本保留=是，行不删）。"""
    from ai_kb import retriever
    ensure_safe_name(doc_name)
    # rules 保护必须先于查库判断：内置手册不在 kb_document 表，否则会先 404 短路
    if doc_name == 'rules':
        raise ValueError('rules 内置手册不可删除')
    d = get_doc(doc_name)
    if not d:
        return False
    retriever.remove_document(doc_name)
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("UPDATE kb_document SET status='archived', updated_at=%s WHERE doc_name=%s",
                  (beijing_now_str(), doc_name))
        conn.commit()
    finally:
        conn.close()
    return True
