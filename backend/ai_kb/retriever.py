# -*- coding: utf-8 -*-
"""
ai_kb.retriever — 混合检索模块（TASK-009 包A）
流程：向量召回(余弦 top12, 阈值0.30) + BM25召回(top12) → RRF(常数60) 融合
     → 取 top3 子块 → 回传父章块完整文本（按融合分降序、去重、截断6000字）。
索引常驻内存（当前约70块×512维 float32 ≈150KB），启动/重建时全量载入。
增量：按 content_hash 比对，只重算新增/变化块 embedding，删除已消失块。
双buffer：重建成功才原子换指针，失败旧索引继续服务。
"""

import json
import os
import re
import threading
import time
import zlib
from array import array

import numpy as np

# === 数值规格 ===
VECTOR_TOP_K = 12
VECTOR_THRESHOLD = 0.30
BM25_TOP_K = 12
RRF_K = 60
FINAL_TOP_K = 3
CONTEXT_MAX_CHARS = 6000
DEFAULT_DOC = 'rules'

_KNOWN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'knowledge')
_LOCK = threading.Lock()
_INDEX = None  # 当前服务索引（双 buffer 的读指针）


# ---------------- 建表（幂等，SQLite/MySQL 双方言） ----------------
def ensure_table(conn):
    try:
        import pymysql  # noqa
    except ImportError:
        is_sqlite = True
    else:
        from utils import USE_MYSQL
        is_sqlite = not USE_MYSQL
    if is_sqlite:
        conn.execute("""CREATE TABLE IF NOT EXISTS kb_chunk (
            id TEXT PRIMARY KEY, doc_name TEXT NOT NULL, chapter_no TEXT,
            title TEXT, parent_id TEXT, seq INTEGER DEFAULT 0,
            is_parent INTEGER DEFAULT 0, text TEXT NOT NULL,
            content_hash TEXT NOT NULL, embedding BLOB, dim INTEGER,
            created_at TEXT)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_chunk_doc ON kb_chunk(doc_name)")
        conn.commit()
    else:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS kb_chunk (
            id VARCHAR(128) PRIMARY KEY, doc_name VARCHAR(64) NOT NULL,
            chapter_no VARCHAR(16), title VARCHAR(128), parent_id VARCHAR(128),
            seq INT DEFAULT 0, is_parent TINYINT DEFAULT 0, text MEDIUMTEXT NOT NULL,
            content_hash VARCHAR(32) NOT NULL, embedding LONGBLOB, dim INT,
            created_at DATETIME) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        try:
            c.execute("CREATE INDEX idx_kb_chunk_doc ON kb_chunk(doc_name)")
        except Exception:
            pass
    return is_sqlite


def _vec_to_blob(v):
    return zlib.compress(array('f', v).tobytes(), 6)


def _blob_to_vec(b):
    return np.frombuffer(zlib.decompress(bytes(b)), dtype=np.float32)


# ---------------- 中文简易分词（2-gram + 单字 + 数字字母整串） ----------------
_TOKEN_RE = re.compile(r'[a-zA-Z0-9]+|[\u4e00-\u9fff]')


def tokenize(text):
    toks = []
    chars = text
    runs = _TOKEN_RE.findall(chars)
    cjk_buf = []
    for r in runs:
        if re.match(r'[\u4e00-\u9fff]', r):
            cjk_buf.append(r)
        else:
            if cjk_buf:
                toks.extend(_cjk_grams(cjk_buf)); cjk_buf = []
            toks.append(r.lower())
    if cjk_buf:
        toks.extend(_cjk_grams(cjk_buf))
    return toks


def _cjk_grams(buf):
    out = []
    for i, ch in enumerate(buf):
        out.append(ch)
        if i + 1 < len(buf):
            out.append(ch + buf[i + 1])
    return out


# ---------------- 索引对象 ----------------
class _Index:
    def __init__(self, chunks, matrix, parents):
        self.chunks = chunks          # 可检索子块 dict 列表（含 id/parent_id/text）
        self.matrix = matrix          # 归一化 float32 矩阵 (n, dim)
        self.parents = parents        # parent_id -> 父块 dict
        self.bm25 = None
        self.build_ms = 0.0

    def build_bm25(self):
        from rank_bm25 import BM25Okapi
        corpus = [tokenize(c['text'] + ' ' + (c.get('title') or '')) for c in self.chunks]
        self.bm25 = BM25Okapi(corpus if corpus else [['空']])


# ---------------- 从库里读出全部块 ----------------
def _fetch_all(conn, is_sqlite):
    if is_sqlite:
        rows = conn.execute(
            "SELECT id, doc_name, chapter_no, title, parent_id, seq, is_parent,"
            " text, content_hash, embedding, dim FROM kb_chunk").fetchall()
        return [dict(r) for r in rows] if rows and not isinstance(rows[0], dict) else \
            [dict(zip(['id', 'doc_name', 'chapter_no', 'title', 'parent_id', 'seq',
                       'is_parent', 'text', 'content_hash', 'embedding', 'dim'], r))
             for r in rows]
    from utils import get_db  # noqa - 仅占位
    cur = conn.cursor()
    cur.execute("SELECT id, doc_name, chapter_no, title, parent_id, seq, is_parent,"
                " text, content_hash, embedding, dim FROM kb_chunk")
    return list(cur.fetchall())


# ---------------- 重建索引（增量） ----------------
def rebuild_index(doc_name=DEFAULT_DOC, log=None):
    """把 knowledge/<doc_name>.txt 与 kb_chunk 表比对同步，只重算变化块 embedding，
    构建新内存索引后原子换指针。返回统计 dict。线程安全。"""
    global _INDEX
    from ai_kb import embedder
    from ai_kb.chunker import slice_chunks, content_hash as chash
    from utils import get_db
    t0 = time.time()
    log = log or (lambda *a: None)

    path = os.path.join(_KNOWN, doc_name + '.txt')
    with open(path, encoding='utf-8') as f:
        chunks = slice_chunks(f.read(), doc_name=doc_name)
    want = {c['id']: c for c in chunks}

    conn = get_db()
    try:
        is_sqlite = ensure_table(conn)
        have = {r['id']: r for r in _fetch_all(conn, is_sqlite)
                if r['doc_name'] == doc_name}

        # 删除已消失块
        removed = 0
        for cid in [k for k in have if k not in want]:
            if is_sqlite:
                conn.execute("DELETE FROM kb_chunk WHERE id=?", (cid,))
            else:
                conn.cursor().execute("DELETE FROM kb_chunk WHERE id=%s", (cid,))
            removed += 1

        # 需重算 embedding 的块 = 新增 + 变化
        stale = [c for cid, c in want.items()
                 if cid not in have or have[cid]['content_hash'] != c['content_hash']]
        recomputed = 0
        if stale:
            from datetime import datetime
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            texts = [c['text'] for c in stale]
            vectors = embedder.embed_documents(texts)
            assert vectors, 'embedding 结果为空'
            assert len(vectors[0]) in (384, 512), '维度异常: %d' % len(vectors[0])
            for c, v in zip(stale, vectors):
                blob = _vec_to_blob(v)
                if is_sqlite:
                    conn.execute(
                        "INSERT OR REPLACE INTO kb_chunk"
                        " (id,doc_name,chapter_no,title,parent_id,seq,is_parent,"
                        " text,content_hash,embedding,dim,created_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (c['id'], doc_name, c['chapter_no'], c['title'], c['parent_id'],
                         c['seq'], c['is_parent'], c['text'], c['content_hash'],
                         blob, len(v), now))
                else:
                    cur = conn.cursor()
                    try:
                        cur.execute(
                            "INSERT INTO kb_chunk (id,doc_name,chapter_no,title,"
                            "parent_id,seq,is_parent,text,content_hash,embedding,"
                            "dim,created_at,_openid) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                            "ON DUPLICATE KEY UPDATE text=VALUES(text),"
                            "content_hash=VALUES(content_hash),"
                            "embedding=VALUES(embedding),dim=VALUES(dim)",
                            (c['id'], doc_name, c['chapter_no'], c['title'],
                             c['parent_id'], c['seq'], c['is_parent'], c['text'],
                             c['content_hash'], blob, len(v), now, ''))
                    except Exception:
                        cur.execute(
                            "INSERT INTO kb_chunk (id,doc_name,chapter_no,title,"
                            "parent_id,seq,is_parent,text,content_hash,embedding,"
                            "dim,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                            "ON DUPLICATE KEY UPDATE text=VALUES(text),"
                            "content_hash=VALUES(content_hash),"
                            "embedding=VALUES(embedding),dim=VALUES(dim)",
                            (c['id'], doc_name, c['chapter_no'], c['title'],
                             c['parent_id'], c['seq'], c['is_parent'], c['text'],
                             c['content_hash'], blob, len(v), now))
                recomputed += 1
            if is_sqlite:
                conn.commit()
        log('[ai_kb] rebuild: 重算embedding块数=%d 删除=%d' % (recomputed, removed))

        all_rows = _fetch_all(conn, is_sqlite)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    subs, parents = [], {}
    for r in all_rows:
        if r['doc_name'] != doc_name:
            continue
        if r['is_parent']:
            parents[r['id']] = r
        elif r['embedding']:
            subs.append(r)
    if not subs:
        raise RuntimeError('索引为空，重建中止（旧索引继续服务）')

    dim = subs[0]['dim'] or len(_blob_to_vec(subs[0]['embedding']))
    mat = np.zeros((len(subs), dim), dtype=np.float32)
    for i, r in enumerate(subs):
        mat[i] = _blob_to_vec(r['embedding'])
    norm = np.linalg.norm(mat, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    idx = _Index(
        [dict(id=r['id'], parent_id=r['parent_id'], text=r['text'],
              chapter_no=r['chapter_no'], title=r['title']) for r in subs],
        mat / norm, parents)
    t1 = time.time()
    idx.build_bm25()
    idx.build_ms = (time.time() - t0) * 1000
    log('[ai_kb] bm25索引构建 %.0fms 总重建 %.0fms' % ((time.time()-t1)*1000, idx.build_ms))
    _INDEX = idx  # 双 buffer：一切成功才换指针
    return dict(chunks=len(subs) + len(parents), sub=len(subs), parent=len(parents),
                recomputed=recomputed, removed=removed,
                elapsed_ms=int(idx.build_ms))


def ensure_ready():
    global _INDEX
    if _INDEX is None:
        with _LOCK:
            if _INDEX is None:
                rebuild_index()


def _scores():
    return _INDEX


# ---------------- 混合检索 ----------------
def hybrid_search(query, top_k=FINAL_TOP_K):
    """返回 (上下文字符串, 命中子块id列表)。异常由调用方兜底。"""
    ensure_ready()
    from ai_kb import embedder
    idx = _INDEX
    if idx is None or not idx.chunks:
        raise RuntimeError('index not ready')

    qv = np.asarray(embedder.embed_query(query), dtype=np.float32)
    qv = qv / (np.linalg.norm(qv) or 1.0)
    sims = idx.matrix @ qv                      # 归一化点积 = 余弦
    vec_order = [i for i in np.argsort(-sims) if sims[i] >= VECTOR_THRESHOLD][:VECTOR_TOP_K]

    qt = tokenize(query)
    bm_scores = idx.bm25.get_scores(qt) if qt else np.zeros(len(idx.chunks))
    bm_order = list(np.argsort(-bm_scores))[:BM25_TOP_K]
    bm_order = [i for i in bm_order if bm_scores[i] > 0]

    rrf = {}
    for rank, i in enumerate(vec_order):
        rrf[i] = rrf.get(i, 0.0) + 1.0 / (RRF_K + rank + 1)
    for rank, i in enumerate(bm_order):
        rrf[i] = rrf.get(i, 0.0) + 1.0 / (RRF_K + rank + 1)
    ranked = sorted(rrf.items(), key=lambda kv: -kv[1])[:top_k]

    # 父块回传 + 去重 + 截断
    seen_parent, texts, hit_ids = set(), [], []
    for i, _score in ranked:
        c = idx.chunks[i]
        pid = c['parent_id']
        hit_ids.append(c['id'])
        if pid in seen_parent:
            continue
        seen_parent.add(pid)
        p = idx.parents.get(pid)
        if p is not None:
            texts.append(p['text'])
        else:
            texts.append(c['text'])
        if sum(len(t) for t in texts) > CONTEXT_MAX_CHARS:
            break
    ctx = '\n\n'.join(texts)[:CONTEXT_MAX_CHARS]
    if not ctx:
        raise RuntimeError('no hit')
    return ctx, hit_ids
