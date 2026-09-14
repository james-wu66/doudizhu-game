# -*- coding: utf-8 -*-
"""TASK-013 差评回流验收脚本——只打本地 127.0.0.1
覆盖：权限矩阵/归并规则/500条性能/XSS不执行/状态流转+hint+warning/审计kb_debug/ai_usage对账/清理复核。
"""
import json
import os
import sqlite3
import sys
import time
import urllib.request

B = 'http://127.0.0.1:8080'
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'doudizhu.db')
_results = []
_today = time.strftime('%Y-%m-%d', time.localtime())
NPREFIX = 'bc013_'
Q1 = NPREFIX + '接风是什么？'      # 归并组1 变体a
Q2 = NPREFIX + '接风是什么 ？'     # 归并组1 变体b（全角问号+尾空格，必须与a同组）
QX = NPREFIX + "<script>alert('xss013')</script>怎么算春天"


def check(label, ok, detail=''):
    ok = bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', label, (' | ' + str(detail)) if detail else ''))
    _results.append((label, ok))


def post(path, obj=None):
    req = urllib.request.Request(B + path, data=json.dumps(obj or {}).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        t0 = time.time()
        r = urllib.request.urlopen(req, timeout=60)
        return r.status, json.loads(r.read().decode('utf-8', 'ignore')), time.time() - t0
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8', 'ignore')), 0
        except Exception:
            return e.code, {}, 0


def admin_token():
    c = sqlite3.connect(DB)
    t = c.execute("SELECT token FROM users WHERE name='本地1234'").fetchone()[0]
    c.close()
    return t


def insert_down(q, n, answer='答句'):
    """造差评测试行（feedback=down, kind=ask），返回插入条数。"""
    c = sqlite3.connect(DB)
    now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    for i in range(n):
        c.execute("INSERT INTO ai_usage (user_name,kind,session_id,question,answer,tokens,cached,"
                  "feedback,blocked,cache_key,note,cost,created_at) VALUES "
                  "('bc013_user','ask','',?,'答句',10,0,'down',0,'','rag:rules#三#1',0,?)", (q, now))
    c.commit()
    c.close()


def main():
    c = sqlite3.connect(DB)
    baseline = c.execute("SELECT COUNT(*) FROM ai_usage").fetchone()[0]
    maxid0 = c.execute("SELECT COALESCE(MAX(id),0) FROM ai_usage").fetchone()[0]
    bc_norms0 = {r[0] for r in c.execute("SELECT question_norm FROM kb_badcase")} \
        if c.execute("SELECT name FROM sqlite_master WHERE name='kb_badcase'").fetchone() else set()
    c.close()
    print('基线：ai_usage %d 行, maxid %d, kb_badcase 已有组 %d' % (baseline, maxid0, len(bc_norms0)))
    TA = admin_token()

    # 注册普通用户做 403（已存在则登录取 token）
    st, r, _ = post('/api/register', {'name': 'bc013_user', 'password': 'bc1234'})
    TU = r.get('token', '')
    if not TU:
        st, r, _ = post('/api/login', {'name': 'bc013_user', 'password': 'bc1234'})
        TU = r.get('token', '')
    check('普通用户 token 可用', bool(TU))

    print('\n=== 权限矩阵 ===')
    st, r, _ = post('/api/assist/admin/badcases', {})
    check('badcases 无token→401', st == 401, st)
    st, r, _ = post('/api/assist/admin/badcases', {'token': TU})
    check('badcases 普通用户→403', st == 403, st)
    st, r, _ = post('/api/assist/admin/badcase/status', {})
    check('badcase/status 无token→401', st == 401, st)
    st, r, _ = post('/api/assist/admin/badcase/status', {'token': TU, 'badcase_id': 1, 'status': 'open'})
    check('badcase/status 普通用户→403', st == 403, st)
    st, r, _ = post('/api/assist/admin/badcases', {'token': TA})
    check('badcases admin→200', st == 200, st)

    print('\n=== 归并规则 + 500条性能（数值规格1/2） ===')
    insert_down(Q1, 300)
    insert_down(Q2, 200)   # 归并组共 500 条（300+200）
    insert_down(QX, 1)     # XSS 样本行（自成一组）
    st, r, dt = post('/api/assist/admin/badcases', {'token': TA, 'date_from': _today, 'date_to': _today})
    check('badcases admin→200', st == 200, st)
    items = r.get('badcases', [])
    mine = [b for b in items if b['question_norm'].startswith(NPREFIX)]
    g1 = [b for b in mine if b['question_norm'] == NPREFIX + '接风是什么']
    check('全半角问号+首尾空白→归并为一组', len(g1) == 1, '组数=%d' % len(g1))
    if g1:
        check('归并次数=500', g1[0]['down_count'] == 500, g1[0]['down_count'])
    check('XSS 问题自成一组', any(b['question_norm'] == NPREFIX + "<script>alert('xss013')</script>怎么算春天"
                                  for b in mine), len(mine))
    check('性能：500条样本响应≤800ms', dt <= 0.8, '%.0fms' % (dt * 1000))

    print('\n=== XSS 防线（渲染路径静态断言） ===')
    html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'xk-usage.html'),
                encoding='utf-8').read()
    check('样本列表用 textContent 注入', 'li.textContent = s' in html)
    check('表格单元格经 xkEsc 转义', "xkEsc(q)" in html and "xkEsc(note)" in html)
    check('后端返回体含原文（JSON 层面）', any('xss013' in b['question_norm'] for b in mine))

    print('\n=== 状态流转 + hint/warning + 审计 ===')
    bid = g1[0]['id'] if g1 else None
    check('懒插入拿到 badcase id', bool(bid), bid)
    st, r, _ = post('/api/assist/admin/badcase/status',
                    {'token': TA, 'badcase_id': bid, 'status': 'in_progress', 'resolution_note': 'x'})
    check('流转 in_progress→ok', st == 200 and r.get('ok'), r)
    st, r, _ = post('/api/assist/admin/badcase/status',
                    {'token': TA, 'badcase_id': bid, 'status': 'resolved', 'resolution_note': ''})
    check('resolved 空说明→warning', st == 200 and 'warning' in r, r.get('warning', ''))
    check('resolved 样本不在金样集→hint', 'hint' in r, r.get('hint', ''))
    st, r, _ = post('/api/assist/admin/badcase/status', {'token': TA, 'badcase_id': 999999, 'status': 'open'})
    check('不存在 id→not_found', r.get('error') == 'not_found', r)
    st, r, _ = post('/api/assist/admin/badcase/status', {'token': TA, 'badcase_id': bid, 'status': 'bogus'})
    check('非法 status→bad params', r.get('error') == 'bad params', r)
    # 状态筛选
    st, r, _ = post('/api/assist/admin/badcases', {'token': TA, 'status': 'resolved'})
    check('status=resolved 筛选生效', all(b['status'] == 'resolved' for b in r.get('badcases', [])), len(r.get('badcases', [])))
    # 审计行存在
    c = sqlite3.connect(DB)
    audit_rows = c.execute("SELECT COUNT(*) FROM ai_usage WHERE kind='kb_debug' AND id>?", (maxid0,)).fetchone()[0]
    check('审计 kind=kb_debug 已写', audit_rows >= 2, audit_rows)

    print('\n=== 清理与对账 ===')
    c = sqlite3.connect(DB)
    c.execute("DELETE FROM ai_usage WHERE id>?", (maxid0,))          # 测试差评行+审计行一并清
    c.commit()
    left_ai = c.execute("SELECT COUNT(*) FROM ai_usage").fetchone()[0]
    # 误增组核验：权限矩阵调用无日期筛选，把库里既有差评行懒插入属设计行为——
    # 断言误增组均有 id<=maxid0 的既有差评行对应，然后删除还原现场
    c.execute("DELETE FROM kb_badcase WHERE question_norm LIKE ?", (NPREFIX + '%',))
    added = [r[0] for r in c.execute("SELECT question_norm FROM kb_badcase")
             if r[0] not in bc_norms0]
    orphan = []
    for norm in added:
        hit = c.execute("SELECT COUNT(*) FROM ai_usage WHERE kind='ask' AND feedback='down' "
                        "AND id<=? AND TRIM(REPLACE(question,'？','?')) LIKE ?",
                        (maxid0, '%' + norm.replace('?', '') + '%')).fetchone()[0]
        if not hit:
            orphan.append(norm)
    check('误增组均有既有差评行对应（懒插入合法）', not orphan, '孤儿组=%s' % orphan)
    for norm in added:
        c.execute("DELETE FROM kb_badcase WHERE question_norm=?", (norm,))
    c.commit()
    bc_after = {r[0] for r in c.execute("SELECT question_norm FROM kb_badcase")}
    c.close()
    check('ai_usage 对账：清理后=基线', left_ai == baseline, '%d vs %d' % (left_ai, baseline))
    check('kb_badcase 无测试残留', not any(n.startswith(NPREFIX) for n in bc_after))
    check('kb_badcase 还原现场=基线', bc_after == bc_norms0, '基线%d 现存%d' % (len(bc_norms0), len(bc_after)))
    st, r, _ = post('/api/register', {'name': 'bc013_user', 'password': 'bc1234'})
    check('bc013_user 已存在（无需清理用户，验收后手动删）', st in (200, 400), st)

    npass = sum(1 for _, ok in _results if ok)
    print('\n===== 013 验收 %d/%d PASS =====' % (npass, len(_results)))
    sys.exit(0 if npass == len(_results) else 1)


if __name__ == '__main__':
    main()
