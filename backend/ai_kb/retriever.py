# -*- coding: utf-8 -*-
"""
ai_kb.retriever — 混合检索模块（TASK-009 包A；TASK-010 包B 扩展多文档/可见性）
流程：向量召回(余弦 top12, 阈值0.30) + BM25召回(top12) → RRF(常数60) 融合
     → 取 top3 子块 → 回传父章块完整文本（按融合分降序、去重、截断6000字）。
索引常驻内存，启动/重建时全量载入。
增量：按 content_hash 比对，只重算新增/变化块 embedding，删除已消失块。
双buffer：重建成功才原子换指针，失败旧索引继续服务。
包B 扩展：sync_document/remove_document 管理上传文档块；internal 块默认不进问答检索池
（红线2：包A 32题金样检索行为不得退化——rules 路径逻辑与常量零改动，仅提炼共用函数）。
"""

import os
import re
import threading
import time
import zlib
from array import array

import numpy as np

# === 数值规格（包A 验收写死，一字不动） ===
VECTOR_TOP_K = 12
VECTOR_THRESHOLD = 0.30
BM25_TOP_K = 12
RRF_K = 60
FINAL_TOP_K = 3
CONTEXT_MAX_CHARS = 6000
DEFAULT_DOC = 'rules'

_KNOWN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'knowledge')
_KBDOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'kb_docs')
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
    _add_visibility_col(conn, is_sqlite)
    return is_sqlite


def _add_visibility_col(conn, is_sqlite):
    """包B：kb_chunk 幂等补 visibility 列（默认 public）；已存在则静默。"""
    try:
        if is_sqlite:
            conn.execute("ALTER TABLE kb_chunk ADD COLUMN visibility TEXT DEFAULT 'public'")
            conn.commit()
        else:
            conn.cursor().execute(
                "ALTER TABLE kb_chunk ADD COLUMN visibility VARCHAR(16) DEFAULT 'public'")
    except Exception:
        pass  # 列已存在


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
        self.chunks = chunks          # 可检索子块 dict 列表（id/parent_id/text/visibility...）
        self.matrix = matrix          # 归一化 float32 矩阵 (n, dim)
        self.parents = parents        # parent_id -> 父块 dict
        self.bm25 = None
        self.build_ms = 0.0

    def build_bm25(self):
        from rank_bm25 import BM25Okapi
        corpus = [tokenize(c['text'] + ' ' + (c.get('title') or '')) for c in self.chunks]
        self.bm25 = BM25Okapi(corpus if corpus else [['空']])


# ---------------- 从库里读出全部块 ----------------
_COLS = ("id, doc_name, chapter_no, title, parent_id, seq, is_parent,"
         " text, content_hash, embedding, dim, COALESCE(visibility,'public') visibility")


def _fetch_all(conn, is_sqlite):
    if is_sqlite:
        rows = conn.execute("SELECT " + _COLS + " FROM kb_chunk").fetchall()
        return [dict(r) for r in rows] if rows and not isinstance(rows[0], dict) else \
            [dict(zip(['id', 'doc_name', 'chapter_no', 'title', 'parent_id', 'seq',
                       'is_parent', 'text', 'content_hash', 'embedding', 'dim',
                       'visibility'], r))
             for r in rows]
    cur = conn.cursor()
    cur.execute("SELECT " + _COLS + " FROM kb_chunk")
    return list(cur.fetchall())


# ---------------- 块集与库 diff 同步（包B 提炼：删除+增量 upsert，规则同包A） ----------------
def _sync_chunks_to_db(conn, chunks, is_sqlite):
    """把 chunks（同 doc_name 一批）与库内旧块 diff：消失块删除；新增/变化/改可见性块
    重算 embedding 后 upsert。返回 (recomputed, removed, all_rows)。"""
    from ai_kb import embedder
    from datetime import datetime
    doc_name = chunks[0]['doc_name']
    have = {r['id']: r for r in _fetch_all(conn, is_sqlite) if r['doc_name'] == doc_name}
    want = {c['id']: c for c in chunks}

    removed = 0
    for cid in [k for k in have if k not in want]:
        if is_sqlite:
            conn.execute("DELETE FROM kb_chunk WHERE id=?", (cid,))
        else:
            conn.cursor().execute("DELETE FROM kb_chunk WHERE id=%s", (cid,))
        removed += 1

    stale = [c for cid, c in want.items()
             if cid not in have or have[cid]['content_hash'] != c['content_hash']
             or have[cid].get('visibility', 'public') != c.get('visibility', 'public')]
    recomputed = 0
    if stale:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        vectors = embedder.embed_documents([c['text'] for c in stale])
        assert vectors, 'embedding 结果为空'
        assert len(vectors[0]) in (384, 512), '维度异常: %d' % len(vectors[0])
        for c, v in zip(stale, vectors):
            blob = _vec_to_blob(v)
            vis = c.get('visibility', 'public')
            if is_sqlite:
                conn.execute(
                    "INSERT OR REPLACE INTO kb_chunk"
                    " (id,doc_name,chapter_no,title,parent_id,seq,is_parent,"
                    " text,content_hash,embedding,dim,created_at,visibility)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (c['id'], doc_name, c['chapter_no'], c['title'], c['parent_id'],
                     c['seq'], c['is_parent'], c['text'], c['content_hash'],
                     blob, len(v), now, vis))
            else:
                cur = conn.cursor()
                try:
                    cur.execute(
                        "INSERT INTO kb_chunk (id,doc_name,chapter_no,title,"
                        "parent_id,seq,is_parent,text,content_hash,embedding,"
                        "dim,created_at,visibility,_openid) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE text=VALUES(text),"
                        "content_hash=VALUES(content_hash),"
                        "embedding=VALUES(embedding),dim=VALUES(dim),"
                        "visibility=VALUES(visibility)",
                        (c['id'], doc_name, c['chapter_no'], c['title'],
                         c['parent_id'], c['seq'], c['is_parent'], c['text'],
                         c['content_hash'], blob, len(v), now, vis, ''))
                except Exception:
                    cur.execute(
                        "INSERT INTO kb_chunk (id,doc_name,chapter_no,title,"
                        "parent_id,seq,is_parent,text,content_hash,embedding,"
                        "dim,created_at,visibility) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE text=VALUES(text),"
                        "content_hash=VALUES(content_hash),"
                        "embedding=VALUES(embedding),dim=VALUES(dim),"
                        "visibility=VALUES(visibility)",
                        (c['id'], doc_name, c['chapter_no'], c['title'],
                         c['parent_id'], c['seq'], c['is_parent'], c['text'],
                         c['content_hash'], blob, len(v), now, vis))
            recomputed += 1
        if is_sqlite:
            conn.commit()
    all_rows = _fetch_all(conn, is_sqlite)
    return recomputed, removed, all_rows


# ---------------- 内存索引构建（双 buffer 的新 buffer，失败不动旧指针） ----------------
def _build_index(all_rows, target_docs):
    subs, parents = [], {}
    for r in all_rows:
        if r['doc_name'] not in target_docs:
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
              chapter_no=r['chapter_no'], title=r['title'],
              visibility=r.get('visibility') or 'public') for r in subs],
        mat / norm, parents)
    idx.build_bm25()
    return idx


def index_target_docs(extra=None):
    """索引文档集 = rules + kb_chunk 表里出现过的全部 doc_name（DB 即索引真相源，
    重部署后运行期 approve 的文档块仍在库里、继续可检索）。"""
    docs = {DEFAULT_DOC}
    try:
        from utils import get_db
        conn = get_db()
        try:
            _c = conn.cursor()
            # 同病同治：execute 返回 int 不是 cursor（案例E同款，20260915）
            _c.execute("SELECT DISTINCT doc_name FROM kb_chunk")
            rows = _c.fetchall()
            docs.update(r['doc_name'] for r in rows)
        finally:
            conn.close()
    except Exception:
        pass
    if extra:
        docs.update(extra)
    return docs


# ---------------- rules 重建（包A 原语义：读 knowledge/rules.txt diff + 换指针） ----------------
def rebuild_index(doc_name=DEFAULT_DOC, log=None):
    """把 knowledge/<doc_name>.txt 与 kb_chunk 表比对同步，只重算变化块 embedding，
    构建新内存索引后原子换指针。返回统计 dict。线程安全。"""
    global _INDEX
    from ai_kb.chunker import slice_chunks
    from utils import get_db
    t0 = time.time()
    log = log or (lambda *a: None)

    path = os.path.join(_KNOWN, doc_name + '.txt')
    with open(path, encoding='utf-8') as f:
        chunks = slice_chunks(f.read(), doc_name=doc_name)
    for c in chunks:
        c['visibility'] = 'public'

    conn = get_db()
    try:
        is_sqlite = ensure_table(conn)
        recomputed, removed, all_rows = _sync_chunks_to_db(conn, chunks, is_sqlite)
        log('[ai_kb] rebuild: 重算embedding块数=%d 删除=%d' % (recomputed, removed))
    finally:
        try:
            conn.close()
        except Exception:
            pass

    t1 = time.time()
    idx = _build_index(all_rows, index_target_docs({doc_name}))
    idx.build_ms = (time.time() - t0) * 1000
    log('[ai_kb] bm25索引构建 %.0fms 总重建 %.0fms' % ((time.time() - t1) * 1000, idx.build_ms))
    _INDEX = idx  # 双 buffer：一切成功才换指针
    sub = len([c for c in idx.chunks if c['id'].startswith(doc_name + '#')])
    par = len([p for p in idx.parents if p.startswith(doc_name + '#')])
    return dict(chunks=sub + par, sub=sub, parent=par,
                recomputed=recomputed, removed=removed,
                elapsed_ms=int(idx.build_ms))


# ---------------- 包B：上传文档 approve 同步 / delete 移除 ----------------
def sync_document(doc_name, text, visibility='public'):
    """切片（有中文章号结构走包A切片器，否则通用切片）→ diff 同步 → 全量重建内存索引换指针。
    返回统计 dict；任何异常上抛，旧索引继续服务。"""
    global _INDEX
    from ai_kb.chunker import slice_chunks, slice_chunks_generic
    from utils import get_db
    t0 = time.time()
    chunks = slice_chunks(text, doc_name=doc_name) or slice_chunks_generic(text, doc_name)
    if not chunks:
        raise ValueError('切片结果为空')
    for c in chunks:
        c['visibility'] = visibility
    conn = get_db()
    try:
        is_sqlite = ensure_table(conn)
        recomputed, removed, all_rows = _sync_chunks_to_db(conn, chunks, is_sqlite)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    with _LOCK:
        idx = _build_index(all_rows, index_target_docs({doc_name}))
        idx.build_ms = (time.time() - t0) * 1000
        _INDEX = idx
    return dict(chunks=sum(1 for c in chunks if not c['is_parent']),
                recomputed=recomputed, removed=removed,
                elapsed_ms=int(idx.build_ms))


def remove_document(doc_name):
    """物理删除该文档全部块并即时重建索引（kb_document 行逻辑删除由 pipeline 负责）。"""
    global _INDEX
    from utils import get_db
    if doc_name == DEFAULT_DOC:
        raise ValueError('rules 不可移除')
    conn = get_db()
    try:
        is_sqlite = ensure_table(conn)
        if is_sqlite:
            n = conn.cursor().execute("SELECT COUNT(*) c FROM kb_chunk WHERE doc_name=%s",
                                      (doc_name,)).fetchone()['c']
            conn.execute("DELETE FROM kb_chunk WHERE doc_name=?", (doc_name,))
            conn.commit()
        else:
            cur = conn.cursor()
            # ⚠️ pymysql execute 返回 int(rowcount) 不是 cursor——必须拆开取（James Wu / 案例E同款，20260915 删除路径 500 根因）
            cur.execute("SELECT COUNT(*) c FROM kb_chunk WHERE doc_name=%s", (doc_name,))
            n = cur.fetchone()['c']
            cur.execute("DELETE FROM kb_chunk WHERE doc_name=%s", (doc_name,))
        all_rows = _fetch_all(conn, is_sqlite)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    with _LOCK:
        idx = _build_index(all_rows, index_target_docs() - {doc_name})
        _INDEX = idx
    return dict(doc_name=doc_name, removed=n)


# ---------------- 包B 启动对账：镜像自带文档首启无块则补同步 ----------------
def sync_all_published(log=None):
    """扫 kb_docs/*.txt：published 状态的文档若 kb_chunk 无块（全新库首启）则补切片同步。
    异常吞掉不影响启动（降级精神）。"""
    from ai_kb.chunker import slice_chunks, slice_chunks_generic
    from utils import get_db
    log = log or (lambda *a: None)
    if not os.path.isdir(_KBDOCS):
        return
    for fn in sorted(os.listdir(_KBDOCS)):
        if not fn.endswith('.txt'):
            continue
        n = fn[:-4]
        try:
            conn = get_db()
            try:
                is_sqlite = ensure_table(conn)
                # pymysql execute 返回 int 不是 cursor——链式取必炸后被本函数 except 吞掉，
                # 导致启动对账在 MySQL 上静默失效（20260915 全后端链式扫描发现，拆开取）
                _cc = conn.cursor()
                _cc.execute("SELECT COUNT(*) c FROM kb_chunk WHERE doc_name=%s", (n,))
                cnt = _cc.fetchone()['c']
                if cnt:
                    continue
                _cc.execute("SELECT status FROM kb_document WHERE doc_name=%s", (n,))
                st = _cc.fetchone()
                if not st or st['status'] != 'published':
                    continue
                text = open(os.path.join(_KBDOCS, fn), encoding='utf-8').read()
                chunks = slice_chunks(text, doc_name=n) or slice_chunks_generic(text, n)
                vis = _doc_visibility(n)
                for c in chunks:
                    c['visibility'] = vis
                _sync_chunks_to_db(conn, chunks, is_sqlite)
                log('[ai_kb] startup sync %s: %d blocks' % (n, len(chunks)))
            finally:
                conn.close()
        except Exception as e:
            print('[ai_kb] startup sync 失败(忽略):', n, type(e).__name__, e, flush=True)


def _doc_visibility(doc_name):
    try:
        from utils import get_db
        conn = get_db()
        try:
            # 同款 pymysql 语义坑：execute 返回 int，链式 fetchone 必炸并被本 except 吞→永远 'public'
            _cv = conn.cursor()
            _cv.execute("SELECT visibility FROM kb_document WHERE doc_name=%s", (doc_name,))
            r = _cv.fetchone()
            return (r['visibility'] if r and r['visibility'] else 'public')
        finally:
            conn.close()
    except Exception:
        return 'public'


def ensure_ready():
    global _INDEX
    if _INDEX is None:
        with _LOCK:
            if _INDEX is None:
                rebuild_index()


def _scores():
    return _INDEX


# ---------------- 混合检索 ----------------
def hybrid_search(query, top_k=FINAL_TOP_K, include_internal=False):
    """返回 (上下文字符串, 命中子块id列表)。异常由调用方兜底。
    include_internal=False（默认，普通问答路径）：internal 块不参与召回与上下文（规格第7条隔离）。"""
    ensure_ready()
    from ai_kb import embedder
    idx = _INDEX
    if idx is None or not idx.chunks:
        raise RuntimeError('index not ready')

    qv = np.asarray(embedder.embed_query(query), dtype=np.float32)
    qv = qv / (np.linalg.norm(qv) or 1.0)
    sims = idx.matrix @ qv                      # 归一化点积 = 余弦
    vec_order = [i for i in np.argsort(-sims)
                 if sims[i] >= VECTOR_THRESHOLD
                 and (include_internal or idx.chunks[i].get('visibility') != 'internal')][:VECTOR_TOP_K]

    qt = tokenize(query)
    bm_scores = idx.bm25.get_scores(qt) if qt else np.zeros(len(idx.chunks))
    bm_order = list(np.argsort(-bm_scores))[:BM25_TOP_K]
    bm_order = [i for i in bm_order
                if bm_scores[i] > 0
                and (include_internal or idx.chunks[i].get('visibility') != 'internal')]

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
        if not include_internal and c.get('visibility') == 'internal':
            continue
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
