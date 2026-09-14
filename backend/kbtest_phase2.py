# -*- coding: utf-8 -*-
"""TASK-010 本地验收脚本（阶段2：状态机全链路/internal隔离/增量/reject/delete/限流）
前置：阶段1已跑过，kbtest_doc / kbtest_docx / kbtest_pdf 处于 pending。只打 127.0.0.1。"""
import json
import time
import sqlite3
import urllib.request
import sys

B = 'http://127.0.0.1:8080'
DB = r'C:\hermes 斗地主终极版 软件\backend\database\doudizhu.db'


def post(path, obj=None):
    req = urllib.request.Request(B + path, data=json.dumps(obj or {}).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=180)
        return r.status, r.read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'ignore')


def check(label, got, want):
    ok = str(got) == str(want)
    print('%s %s: got=%s want=%s' % ('PASS' if ok else 'FAIL', label, got, want))
    return ok


def dbq(sql, args=()):
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, args)]
    finally:
        c.close()


def main():
    TA = dbq("SELECT token FROM users WHERE name='本地1234'")[0]['token']
    results = []

    print('=== 状态机：pending → approve → 检索命中 ===')
    st, r = post('/api/kb/approve', {'token': TA, 'doc_name': 'kbtest_doc'})
    d = json.loads(r)
    results.append(check('approve kbtest_doc→200', st, 200))
    results.append(check('approve 重算块数>0', d.get('recomputed', 0) > 0, True))
    print('  ', r[:200])
    rows = dbq("SELECT COUNT(*) n FROM kb_chunk WHERE doc_name='kbtest_doc'")
    results.append(check('kb_chunk 落库>0', rows[0]['n'] > 0, True))
    st, r = post('/api/kb/search', {'token': TA, 'query': '青龙偃月刀加倍是多少'})
    hits = json.loads(r).get('hits', [])
    results.append(check('search 命中 kbtest_doc 块', any('kbtest_doc#' in h for h in hits), True))
    print('   hits:', hits[:3])

    print('\n=== 增量：改3字重传 → pending → 再approve → 新内容可检索 ===')
    md_text2 = open(r'C:\hermes 斗地主终极版 软件\backend\kb_docs\kbtest_doc.txt', encoding='utf-8').read()
    md_text2 = md_text2.replace('底分乘三', '底分乘四')
    st, r = post('/api/kb/upload', {'token': TA, 'doc_name': 'kbtest_doc', 'title': '青龙偃月刀', 'text': md_text2})
    d = json.loads(r)
    results.append(check('改文重传 unchanged=False', d.get('unchanged', False), False))
    st, r = post('/api/kb/list', {'token': TA})
    doc1 = [x for x in json.loads(r)['docs'] if x['doc_name'] == 'kbtest_doc'][0]
    results.append(check('改文后状态回到 pending', doc1['status'], 'pending'))
    st, r = post('/api/kb/approve', {'token': TA, 'doc_name': 'kbtest_doc'})
    results.append(check('二次approve 200', st, 200))
    st, r = post('/api/kb/search', {'token': TA, 'query': '青龙偃月刀 底分乘四'})
    ctx = json.loads(r).get('context', '')
    results.append(check('检索上下文含改后文本"乘四"', '乘四' in ctx, True))

    print('\n=== internal 隔离（规格7）===')
    internal_text = ('# 内部运营口径\n\n## 一、返奖率\n青龙偃月刀内部测试期返奖率按百分之九十七点五控制，'
                     '该口径仅限运营内部使用不参与对外问答。' * 6 +
                     '\n\n## 二、灰度名单\n灰度期间只有白名单账号可见该加倍玩法，对外口径统一为趣味赛实验规则。' * 6)
    st, r = post('/api/kb/upload', {'token': TA, 'doc_name': 'kbtest_internal',
                                    'title': '内部口径', 'visibility': 'internal', 'text': internal_text})
    results.append(check('internal 文档上传 200', st, 200))
    st, r = post('/api/kb/approve', {'token': TA, 'doc_name': 'kbtest_internal'})
    results.append(check('internal approve 200', st, 200))
    st, r = post('/api/kb/search', {'token': TA, 'query': '青龙偃月刀返奖率灰度名单'})
    hits_pub = json.loads(r).get('hits', [])
    results.append(check('默认检索不含 internal 块', any('kbtest_internal' in h for h in hits_pub), False))
    st, r = post('/api/kb/search', {'token': TA, 'query': '青龙偃月刀返奖率灰度名单', 'include_internal': True})
    hits_int = json.loads(r).get('hits', [])
    results.append(check('include_internal=True 可命中', any('kbtest_internal' in h for h in hits_int), True))

    print('\n=== reject：kbtest_pdf 拒绝后不进索引 ===')
    st, r = post('/api/kb/reject', {'token': TA, 'doc_name': 'kbtest_pdf'})
    results.append(check('reject 200', st, 200))
    doc3 = [x for x in json.loads(post('/api/kb/list', {'token': TA})[1])['docs'] if x['doc_name'] == 'kbtest_pdf'][0]
    results.append(check('状态=rejected', doc3['status'], 'rejected'))
    n3 = dbq("SELECT COUNT(*) n FROM kb_chunk WHERE doc_name='kbtest_pdf'")[0]['n']
    results.append(check('rejected 文档无块入库', n3, 0))

    print('\n=== delete：kbtest_docx 逻辑删+块移除 ===')
    st, r = post('/api/kb/approve', {'token': TA, 'doc_name': 'kbtest_docx'})
    results.append(check('approve kbtest_docx 200', st, 200))
    st, r = post('/api/kb/delete', {'token': TA, 'doc_name': 'kbtest_docx'})
    results.append(check('delete 200→archived', json.loads(r).get('status'), 'archived'))
    n2 = dbq("SELECT COUNT(*) n FROM kb_chunk WHERE doc_name='kbtest_docx'")[0]['n']
    results.append(check('删除后块数=0', n2, 0))

    print('\n=== rules 保护：不可删除 ===')
    st, r = post('/api/kb/delete', {'token': TA, 'doc_name': 'rules'})
    results.append(check('delete rules→400', st, 400))

    print('\n=== ask 链路命中新文档（真实模型1次）===')
    st, r = post('/api/assist/ask', {'token': TA, 'question': '青龙偃月刀加倍的时候底分要乘几呀'})
    d = json.loads(r)
    results.append(check('ask 200', st, 200))
    results.append(check('ask 非降级回答', d.get('degraded', False), False))
    print('   answer:', (d.get('answer') or '')[:80])

    print('\n=== 限流：第7次/分钟 rate_limited（用 kbtest_user）===')
    # IP 维度限流与账户共用窗口，先等满 60s+ 清零，避免上面 admin 的 ask 计入同 IP
    print('   等待限流窗口清零 65s ...')
    time.sleep(65)
    st, r = post('/api/register', {'name': 'kbtest_user', 'password': 'kb1234'})
    TU = json.loads(r).get('token', '')
    if not TU:
        st, r = post('/api/login', {'name': 'kbtest_user', 'password': 'kb1234'})
        TU = json.loads(r).get('token', '')
    answers = []
    for i in range(7):
        st, r = post('/api/assist/ask', {'token': TU, 'question': '今天天气怎么样%d' % i})
        answers.append(json.loads(r))
    sixth = answers[5].get('answer', '')
    seventh = answers[6]
    aud = dbq("SELECT note, COUNT(*) n FROM ai_usage WHERE user_name='kbtest_user' GROUP BY note")
    rl = [x for x in aud if x['note'] == 'rate_limited']
    results.append(check('第7次审计 note=rate_limited', len(rl) >= 1, True))
    results.append(check('第7次被限流(降级)', seventh.get('degraded'), True))
    print('   第6次回复:', sixth[:40], '| 第7次回复:', (seventh.get('answer') or '')[:40])

    print('\n阶段2汇总: %d/%d PASS' % (sum(results), len(results)))
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
