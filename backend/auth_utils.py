# -*- coding: utf-8 -*-
"""
TASK-014b 安全地基：token 统一鉴权公共设施
逻辑照搬问答助手 ai_assist 的 _lookup_user/_identify：token 反查 users 表得真实用户名；
查不到=未登录(401)；自报名与反查不符=冒名(403, 写 ai_usage 审计 note=impersonation)。
红线：不重构 ai_assist，仅复用其审计写入函数；注册/登录/自动登录三接口不经过本模块。
"""

from flask import request, jsonify
from utils import get_db


def lookup_user(token):
    """token 反查真实用户名；无效/空 token 返回 None。"""
    if not token:
        return None
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE token = %s", (token,))
        row = c.fetchone()
        return row["name"] if row else None
    finally:
        conn.close()


def _audit_impersonation(real, claimed):
    """冒名审计：与问答助手同款（kind=ask, cached=2, blocked=1, note=impersonation）。失败不影响主流程。"""
    try:
        from routes.ai_assist import _insert_usage
        _insert_usage(real, 'ask', '', '[冒名:' + (claimed or '')[:20] + ']',
                      'forbidden', 0, 0, 2, blocked=1, note='impersonation')
    except Exception as e:
        print('[auth_utils] 冒名审计写入失败:', type(e).__name__, e, flush=True)


def _request_token():
    """统一取 token：JSON 请求体 → URL 查询参数 → multipart 表单；全空则空串。"""
    data = request.get_json(silent=True) or {}
    token = data.get('token') or request.args.get('token') or ''
    if not token and request.form:
        token = request.form.get('token') or ''
    return token.strip()


def identify(claim_field='name'):
    """写接口入口鉴权。返回 (real_name, error_response)。
    - 无/无效 token → (None, 401)
    - 自报身份(默认取请求体 name；URL 路径参数用 caller 传入的 claim) 与 token 反查不符 → (None, 403+冒名审计)
    - 通过 → (真实用户名, None)；后续一律用真实用户名，绝不再信自报名。
    调用方负责在开头取 claim：claim 可为 None（不宣称）或字符串。"""
    token = _request_token()
    real = lookup_user(token)
    if real is None:
        return None, (jsonify({'success': False, 'error': 'unauthorized'}), 401)
    data = request.get_json(silent=True) or {}
    claimed = (data.get(claim_field) or '').strip() if claim_field else ''
    if claimed and claimed != real:
        _audit_impersonation(real, claimed)
        return None, (jsonify({'success': False, 'error': 'forbidden'}), 403)
    return real, None


def viewer_identity():
    """读接口用：不拦截，只尽力识别访问者。返回真实用户名或 None（游客/无效 token）。
    取 token 途径：查询参数 token（前端 GET 带 ?token=）或 JSON 体。"""
    token = request.args.get('token') or ''
    if not token:
        data = request.get_json(silent=True) or {}
        token = data.get('token') or ''
    return lookup_user(token.strip()) if token else None


def esc(s):
    """昵称 HTML 转义：& < > \" ' 转实体。非字符串安全转字符串，None 原样返回。"""
    if s is None:
        return s
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;'))
