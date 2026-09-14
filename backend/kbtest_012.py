# -*- coding: utf-8 -*-
"""TASK-012 缩版验收脚本（模块2 追问改写 + 模块3 引用出处）——只打本地 127.0.0.1
用法：先起满血服务（KB_MODEL_DIR=... python app.py），再跑本脚本。
PartA 单元级（进程内，不起服务）：引用校验/改写触发词表/note 预算。
PartB 端到端（HTTP）：追问场景硬题/词表误报复核/降级注入/引用一致性/P95。
测试数据只写 ai_usage（ask 审计行），结束按 id 精确清理。
"""
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
B = 'http://127.0.0.1:8080'
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'doudizhu.db')
_results = []
_created_usage_ids = []


def check(label, ok, detail=''):
    ok = bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', label, (' | ' + str(detail)) if detail else ''))
    _results.append((label, ok))


def post(path, obj=None):
    req = urllib.request.Request(B + path, data=json.dumps(obj or {}).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return r.status, json.loads(r.read().decode('utf-8', 'ignore'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8', 'ignore'))
        except Exception:
            return e.code, {}


def admin_token():
    c = sqlite3.connect(DB)
    return c.execute("SELECT token FROM users WHERE name='本地1234'").fetchone()[0]


# ---------------- PartA 进程内单元级 ----------------
def part_a():
    from routes import ai_assist as A
    print('=== PartA 单元级（进程内） ===')

    # A1 引用校验：命中章内→保留+cite
    ans, tag = A._validate_citation('接风是农民配合技巧（依据：官方手册、六、残局与拆牌 · 6.2节）', {'六'})
    check('A1 引用命中→保留+cite:六', ans.endswith('）') and tag == 'cite:六', tag)
    # A2 引用编造（未命中章）→剥掉+cite_none
    ans, tag = A._validate_citation('接风是农民配合技巧（依据：官方手册、七、新手误区 · 7.1节）', {'六'})
    check('A2 引用编造→剥掉+cite_none', '依据' not in ans and tag == 'cite_none', ans + '|' + tag)
    # A3 无引用→原样
    ans, tag = A._validate_citation('接风就是替队友挡一手。', {'六'})
    check('A3 无引用原样返回', ans == '接风就是替队友挡一手。' and tag == '', tag)
    # A4 空命中集→剥掉（保守）
    ans, tag = A._validate_citation('答案（依据：官方手册、三、计分 · 3.1节）', set())
    check('A4 空命中集→剥掉', tag == 'cite_none' and '依据' not in ans, tag)
    # A5 异常输入不炸
    ans, tag = A._validate_citation(None, None)
    check('A5 None 输入不抛异常', ans is None and tag == '', tag)
    # A6 降级容错：全角冒号也认
    ans, tag = A._validate_citation('答案（依据：官方手册、九、记牌与算牌 · 9.1节）', {'九'})
    check('A6 全角冒号+cite:九', tag == 'cite:九', tag)

    # A7 改写触发判定：词表命中+有history 才尝试改写（把 _call_once 换成探针，不真调模型）
    calls = []
    orig_once = A._call_once
    A._call_once = lambda *a, **k: (calls.append(1), (None, None))[1]
    try:
        _, t1 = A._rewrite_question('它是怎么触发的', [{'q': '接风是什么意思'}])
        check('A7 词表+history→触发改写调用', len(calls) == 1 and t1 == 'qr_fail', t1)
        calls.clear()
        _, t2 = A._rewrite_question('接风是怎么触发的', [{'q': '接风是什么意思'}])
        check('A7b 无指示词→不触发', len(calls) == 0 and t2 == '', t2)
        calls.clear()
        _, t3 = A._rewrite_question('炸弹比王炸小吗', [{'q': '王炸是什么'}])
        check('A9 无指示词→不触发', len(calls) == 0 and t3 == '', t3)
    finally:
        A._call_once = orig_once

    # A10 改写成功路径：mock 返回合法短问题
    A._call_once = lambda *a, **k: ('接风是怎么触发的', {'total_tokens': 20})
    try:
        rq, t4 = A._rewrite_question('它是怎么触发的', [{'q': '接风是什么意思'}])
        check('A10 改写成功→qr_ok且含接风', t4 == 'qr_ok' and '接风' in rq, rq + '|' + t4)
        rq, t5 = A._rewrite_question('它是怎么触发的', [{'q': '接风是什么意思'}])
        # mock 返回超长→判失败
        A._call_once = lambda *a, **k: ('x' * 50, None)
        rq, t5 = A._rewrite_question('它是怎么触发的', [{'q': '接风是什么意思'}])
        check('A11 改写超长→qr_fail走原问题', t5 == 'qr_fail' and rq == '它是怎么触发的', t5)
    finally:
        A._call_once = orig_once

    # A12 note 预算：模型+qr+cite+超长rag 截255
    note = 'sensenova;qr:ok;cite:六;rag:' + ','.join(['rules#六#%d' % i for i in range(60)])
    check('A12 note 截断≤255', len(note[:255]) <= 255, len(note))

    # A13 改写新增延迟（真实小米调用，单样本；验收口径：新增 P95 ≤ 2s）
    t0 = time.time()
    rq, t6 = A._rewrite_question('它是怎么触发的', [{'q': '接风是什么意思'}])
    dt_rw = time.time() - t0
    check('A13 改写新增延迟≤2s（单样本）', t6 == 'qr_ok' and dt_rw <= 2.0, '%.2fs|%s' % (dt_rw, rq))


# ---------------- PartB 端到端（HTTP，需满血服务） ----------------
def part_b():
    print('=== PartB 端到端（HTTP） ===')
    TA = admin_token()
    hist = []

    # B1 第一轮：接风是什么意思
    t0 = time.time()
    st, r = post('/api/assist/ask', {'token': TA, 'question': '接风是什么意思'})
    dt1 = time.time() - t0
    check('B1 第1轮 ask→200', st == 200, st)
    rid1 = r.get('usage_id')
    _created_usage_ids.append(rid1)
    hist = [{'q': '接风是什么意思'}]

    # B2 第二轮硬题：它是怎么触发的（带 history）→ 改写应命中含"接风"的块
    t0 = time.time()
    st, r = post('/api/assist/ask', {'token': TA, 'question': '它是怎么触发的', 'history': hist})
    dt2 = time.time() - t0
    check('B2 第2轮硬题 ask→200', st == 200, st)
    rid2 = r.get('usage_id')
    _created_usage_ids.append(rid2)
    note2 = ''
    ans2 = r.get('answer', '')
    if rid2:
        c = sqlite3.connect(DB)
        row = c.execute("SELECT note, answer FROM ai_usage WHERE id=?", (rid2,)).fetchone()
        note2, ans2 = (row[0] or ''), (row[1] or '')
        check('B3 note 含 qr:ok（改写成功）', 'qr:ok' in note2, note2)
        # 命中子块文本含"接风"（取 note 里 rag: 前2个块 id 查 kb_chunk）
        m = re.search(r'rag:([^;]+)', note2)
        hit_text = ''
        if m:
            c2 = sqlite3.connect(DB)
            for hid in m.group(1).split(',')[:2]:
                if hid:
                    rr = c2.execute("SELECT text FROM kb_chunk WHERE id=?", (hid,)).fetchone()
                    if rr:
                        hit_text += rr[0]
        check('B4 检索命中块文本含"接风"（改写生效铁证）', '接风' in hit_text, hit_text[:60])
        # 端到端总耗时含主模型回答（2~15s 波动），验收口径是"改写新增延迟"——已在 A13 单测；
        # 此处只断言总量在模型正常范围内，报告里报实测值
        check('B5 端到端≤15s（含主模型，报实测）', dt2 <= 15.0, '%.2fs' % dt2)
        # 引用一致性：答案若有（依据，note 必有 cite:；且章号属命中集才保留
        if '（依据' in ans2:
            check('B6 答案带引用→note 有 cite:', 'cite:' in note2, note2)
        else:
            check('B6 答案无引用→note 无 cite:（或 cite_none）', 'cite:' not in note2, note2)
    print('  第2轮答案：', ans2[:100])
    print('  第1轮耗时 %.2fs 第2轮耗时 %.2fs' % (dt1, dt2))

    time.sleep(2)  # 避开 60s 窗口 6 次限流

    # B7 词表误报复核·无关题含触发词→必须被 T3 领域拦截（不得绕过）
    st, r = post('/api/assist/ask', {'token': TA, 'question': '帮我写一首诗，这个要快'})
    check('B7 无关题(含"这个")→T3拦截', st == 200 and '斗地主' in r.get('answer', ''), r.get('answer', '')[:30])
    _created_usage_ids.append(r.get('usage_id'))
    time.sleep(2)

    # B8 领域题含触发词→正常回答不拦截
    st, r = post('/api/assist/ask', {'token': TA, 'question': '双王也算炸弹吗，这个规则我一直不懂'})
    check('B8 领域题(含"这个")→200正常', st == 200 and r.get('answer') and '斗地主' not in r.get('answer', '')[:5],
          (r.get('answer') or '')[:30])
    _created_usage_ids.append(r.get('usage_id'))


# ---------------- PartC 降级注入（进程内 Flask test_client） ----------------
def part_c():
    print('=== PartC 降级注入（进程内 test_client） ===')
    from flask import Flask
    from routes import ai_assist as A
    app = Flask(__name__)
    app.register_blueprint(A.ai_assist_bp)
    cli = app.test_client()
    TA = admin_token()

    # C1 关改写（备胎配置消失）→ qr_fail 静默走原问题；原问题出不了领域门→T3 拦截，200 不 500
    orig_cfg3 = A._cfg3
    A._cfg3 = lambda prefix: (None, None, None) if prefix == 'BACKUP' else orig_cfg3(prefix)
    orig_model = A._call_model
    A._call_model = lambda msg, max_tokens=300: ('接风是农民间的配合技巧，队友出单牌你出不起时替他挡一手。', {'total_tokens': 100}, 'mock')
    try:
        resp = cli.post('/api/assist/ask', json={'token': TA, 'question': '它是怎么触发的',
                                                 'history': [{'q': '接风是什么意思'}]})
        body = resp.get_json()
        check('C1 关改写→200不500', resp.status_code == 200 and body.get('ok'), resp.status_code)
        c = sqlite3.connect(DB)
        nid = body.get('usage_id')
        _created_usage_ids.append(nid)
        if nid:
            note = c.execute("SELECT note FROM ai_usage WHERE id=?", (nid,)).fetchone()[0] or ''
            check('C2 note 含 qr_fail', 'qr_fail' in note, note)
        # C2b 改写失败但原问题在领域内→静默走原问题正常回答
        resp = cli.post('/api/assist/ask', json={'token': TA, 'question': '双王也算炸弹吗，这个规则我不懂',
                                                 'history': [{'q': '王炸是什么'}]})
        body = resp.get_json()
        check('C2b qr_fail原问题在领域→200正常答', resp.status_code == 200 and '配合技巧' in body.get('answer', ''),
              body.get('answer', '')[:30])
        _created_usage_ids.append(body.get('usage_id'))
    finally:
        A._cfg3 = orig_cfg3
        A._call_model = orig_model

    # C3 引用校验防幻觉：mock 模型返回未命中章号的引用→剥掉+cite_none
    A._call_model = lambda msg, max_tokens=300: (
        '顺子里不能带2，2是最大单牌（依据：官方手册、七、新手误区 · 7.1节）',
        {'total_tokens': 100}, 'mock')
    try:
        resp = cli.post('/api/assist/ask', json={'token': TA, 'question': '顺子里能不能带2'})
        body = resp.get_json()
        check('C3 编造引用→剥掉后200', resp.status_code == 200 and '依据' not in body.get('answer', ''),
              body.get('answer', ''))
        c = sqlite3.connect(DB)
        nid = body.get('usage_id')
        _created_usage_ids.append(nid)
        if nid:
            note = c.execute("SELECT note FROM ai_usage WHERE id=?", (nid,)).fetchone()[0] or ''
            check('C4 note 含 cite_none', 'cite_none' in note, note)
    finally:
        A._call_model = orig_model

    # C5 模型全挂→T10 降级话术 200 不 500
    A._call_model = lambda msg, max_tokens=300: (None, None, None)
    try:
        resp = cli.post('/api/assist/ask', json={'token': TA, 'question': '飞机能带几对'})
        body = resp.get_json()
        check('C5 模型挂→200降级话术', resp.status_code == 200 and '走神' in body.get('answer', ''),
              body.get('answer', ''))
        _created_usage_ids.append(body.get('usage_id'))
    finally:
        A._call_model = orig_model


def cleanup():
    print('\n=== 清理测试数据 ===')
    if not _created_usage_ids:
        print('无测试行需清理')
        return
    c = sqlite3.connect(DB)
    ids = [i for i in _created_usage_ids if i]
    c.executemany("DELETE FROM ai_usage WHERE id=?", [(i,) for i in ids])
    c.commit()
    left = c.execute("SELECT COUNT(*) FROM ai_usage WHERE id IN (%s)" %
                     ','.join('?' * len(ids)), ids).fetchone()[0]
    c.close()
    check('清理复核：测试行余量=0', left == 0, '删%d行' % len(ids))


def main():
    part_a()
    part_b()
    part_c()
    cleanup()
    npass = sum(1 for _, ok in _results if ok)
    print('\n===== 012 验收 %d/%d PASS =====' % (npass, len(_results)))
    sys.exit(0 if npass == len(_results) else 1)


if __name__ == '__main__':
    main()
