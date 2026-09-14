# -*- coding: utf-8 -*-
"""
TASK-010 包B：知识库管理路由（全部 POST，token 进 body，admin only）
kb/list | kb/upload | kb/preview | kb/approve | kb/reject | kb/delete | kb/search
红线：不碰 routes/ai.py、backend/ai/、任何前端；SQL 全参数占位；
文件只收白名单后缀（.txt .md .docx .pdf）、单文件 ≤20MB、临时目录 uploads/kb_inbox/、
文件名服务端 uuid 重命名，绝不用用户原始名拼路径。
"""

import os
import time
import uuid

from flask import Blueprint, request, jsonify

from auth_utils import require_admin
from ai_kb import pipeline
from ai_kb.ingest import parse_upload, IngestError, MAX_FILE_SIZE

kb_bp = Blueprint("kb", __name__)

_INBOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'uploads', 'kb_inbox')

# ---------------- 管理接口防爆破（第六节第2条） ----------------
# token/权限校验失败按 IP 计数：10 分钟内 ≥20 次 → 封该 IP 的 kb 路由 30 分钟。
# 内存 dict，进程重启清零可接受。
_fail_hits = {}          # ip -> [ts, ...]
_ban_until = {}          # ip -> 解禁时间戳
_FAIL_WINDOW = 600.0     # 10 分钟
_FAIL_LIMIT = 20
_BAN_SECONDS = 1800.0    # 30 分钟


def _ip_guard():
    ip = request.remote_addr or 'unknown'
    now = time.time()
    until = _ban_until.get(ip)
    if until and now < until:
        return (jsonify({'success': False, 'error': 'forbidden'}), 403)
    return None


def _ip_fail_record():
    ip = request.remote_addr or 'unknown'
    now = time.time()
    hits = [t for t in _fail_hits.get(ip, []) if now - t < _FAIL_WINDOW]
    hits.append(now)
    _fail_hits[ip] = hits
    if len(hits) >= _FAIL_LIMIT:
        _ban_until[ip] = now + _BAN_SECONDS
        _fail_hits[ip] = []


def _admin_gate():
    """防爆破 → token+role 双重校验。返回 (real, error_response)。"""
    blocked = _ip_guard()
    if blocked:
        return None, blocked
    real, err = require_admin()
    if err:
        _ip_fail_record()
        return None, err
    return real, None


# ---------------- 1. 文档列表 ----------------
@kb_bp.route('/api/kb/list', methods=['POST'])
def kb_list():
    _, err = _admin_gate()
    if err:
        return err
    return jsonify({'success': True, 'docs': pipeline.list_docs()})


# ---------------- 2. 上传（multipart 文件或 JSON 贴文本二选一） ----------------
@kb_bp.route('/api/kb/upload', methods=['POST'])
def kb_upload():
    real, err = _admin_gate()
    if err:
        return err
    title = ''
    visibility = request.form.get('visibility') if request.form else None
    if request.files.get('file'):
        f = request.files['file']
        cl = request.content_length or 0
        if cl > MAX_FILE_SIZE + 64 * 1024:
            return jsonify({'success': False, 'error': 'too_large',
                            'msg': '文件超过20MB上限'}), 400
        raw = f.read()
        title = os.path.splitext(f.filename or '')[0][:60]
        # 落盘一律 uuid 重命名（红线5：禁止用户原始名拼路径），解析完即删，防垃圾堆积
        os.makedirs(_INBOX, exist_ok=True)
        store = os.path.join(_INBOX, uuid.uuid4().hex)
        try:
            with open(store, 'wb') as out:
                out.write(raw)
            try:
                parsed = parse_upload(f.filename, raw)
            finally:
                try:
                    os.remove(store)
                except OSError:
                    pass
        except IngestError as e:
            return jsonify({'success': False, 'error': e.code, 'msg': e.msg}), 400
        text, pages = parsed['text'], parsed['pages']
        doc_name = pipeline.normalize_doc_name(
            request.form.get('doc_name'), f.filename)
        visibility = visibility or 'public'
    else:
        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        title = (data.get('title') or '').strip()[:60]
        visibility = data.get('visibility') or 'public'
        doc_name = pipeline.normalize_doc_name(data.get('doc_name'), text)
        if not text:
            return jsonify({'success': False, 'error': 'empty_text',
                            'msg': 'text 或 file 必须二选一'}), 400
        try:
            from ai_kb.ingest import clean_text
            text = clean_text(text)
        except Exception:
            pass
        pages = None
        if len(text.encode('utf-8')) > MAX_FILE_SIZE:
            return jsonify({'success': False, 'error': 'too_large',
                            'msg': '文本超过20MB上限'}), 400
        if len(text) < 50:
            return jsonify({'success': False, 'error': 'parse_error',
                            'msg': '正文不足50字，疑似空文档'}), 400

    try:
        row, unchanged = pipeline.create_or_update(
            doc_name, title or doc_name, text,
            (request.files.get('file').filename if request.files.get('file') else 'paste'),
            real, visibility)
    except ValueError as e:
        return jsonify({'success': False, 'error': 'bad_doc_name', 'msg': str(e)}), 400
    if unchanged:  # 规格第3条：重复上传秒判 <100ms、重算块数 0
        return jsonify({'success': True, 'unchanged': True, 'doc_id': row['id'],
                        'doc_name': doc_name, 'status': row['status'], 'recomputed': 0})
    from ai_kb.chunker import slice_chunks, slice_chunks_generic
    est = slice_chunks(text, doc_name=doc_name) or slice_chunks_generic(text, doc_name)
    return jsonify({'success': True, 'doc_id': row['id'], 'doc_name': doc_name,
                    'status': row['status'],
                    'summary': {'pages': pages, 'chars': len(text),
                                'est_chunks': sum(1 for c in est if not c['is_parent'])}})


# ---------------- 3. 切片预览 ----------------
@kb_bp.route('/api/kb/preview', methods=['POST'])
def kb_preview():
    _, err = _admin_gate()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    pv = pipeline.preview((data.get('doc_name') or '').strip())
    if not pv:
        return jsonify({'success': False, 'error': 'not_found'}), 404
    return jsonify({'success': True, **pv})


# ---------------- 4. approve / 5. reject ----------------
@kb_bp.route('/api/kb/approve', methods=['POST'])
def kb_approve():
    real, err = _admin_gate()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    doc_name = (data.get('doc_name') or '').strip()
    try:
        stat = pipeline.approve(doc_name, real)
    except Exception as e:
        return jsonify({'success': False, 'error': 'approve_failed',
                        'msg': type(e).__name__ + ': ' + str(e)[:200]}), 500
    return jsonify({'success': True, **stat})


@kb_bp.route('/api/kb/reject', methods=['POST'])
def kb_reject():
    real, err = _admin_gate()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    ok = pipeline.reject((data.get('doc_name') or '').strip(), real)
    if not ok:
        return jsonify({'success': False, 'error': 'not_found'}), 404
    return jsonify({'success': True, 'status': 'rejected'})


# ---------------- 6. 逻辑删除（rules 拒绝） ----------------
@kb_bp.route('/api/kb/delete', methods=['POST'])
def kb_delete():
    _, err = _admin_gate()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    doc_name = (data.get('doc_name') or '').strip()
    try:
        ok = pipeline.delete_doc(doc_name)
    except ValueError as e:
        return jsonify({'success': False, 'error': 'forbidden_doc', 'msg': str(e)}), 400
    if not ok:
        return jsonify({'success': False, 'error': 'not_found'}), 404
    return jsonify({'success': True, 'status': 'archived'})


# ---------------- 7. 管理员检索调试（唯一可用 include_internal 的口子） ----------------
@kb_bp.route('/api/kb/search', methods=['POST'])
def kb_search():
    _, err = _admin_gate()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    q = (data.get('query') or data.get('question') or '').strip()[:200]
    if not q:
        return jsonify({'success': False, 'error': 'empty query'}), 400
    from ai_kb import retriever
    try:
        ctx, hits = retriever.hybrid_search(
            q, include_internal=bool(data.get('include_internal')))
    except Exception as e:
        return jsonify({'success': False, 'error': 'search_failed',
                        'msg': type(e).__name__}), 500
    return jsonify({'success': True, 'hits': hits, 'context_len': len(ctx),
                    'context': ctx[:2000]})
