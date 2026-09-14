# -*- coding: utf-8 -*-
"""TASK-010 本地验收脚本（阶段1：权限矩阵/格式矩阵/保留名）——只打本地 127.0.0.1"""
import json
import time
import urllib.request
import sqlite3
import os
import sys

B = 'http://127.0.0.1:8080'
TMP = r'C:\Users\15436\AppData\Local\Temp\kbtest'
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'doudizhu.db')


def post(path, obj=None, token=None, files=None, raw_body=None):
    url = B + path
    if files:
        boundary = '----kbtest789'
        body = b''
        for k, v in (obj or {}).items():
            body += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (boundary, k, v)).encode('utf-8')
        for k, (fn, data) in files.items():
            body += ('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: application/octet-stream\r\n\r\n' % (boundary, k, fn)).encode('utf-8')
            body += data + b'\r\n'
        body += ('--%s--\r\n' % boundary).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
    else:
        req = urllib.request.Request(url, data=json.dumps(obj or {}).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=120)
        return r.status, r.read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'ignore')


def admin_token():
    c = sqlite3.connect(DB)
    return c.execute("SELECT token FROM users WHERE name='本地1234'").fetchone()[0]


def check(label, got, want):
    ok = str(got) == str(want)
    print('%s %s: got=%s want=%s' % ('PASS' if ok else 'FAIL', label, got, want))
    return ok


def main():
    TA = admin_token()
    # 注册普通用户
    st, r = post('/api/register', {'name': 'kbtest_user', 'password': 'kb1234'})
    TU = json.loads(r).get('token', '')
    print('普通用户 token ok:', bool(TU))
    results = []

    print('\n=== 权限矩阵（规格5）===')
    st, _ = post('/api/kb/list', {})
    results.append(check('kb/list 无token→401', st, 401))
    st, _ = post('/api/kb/list', {'token': TU})
    results.append(check('kb/list 普通用户→403', st, 403))
    st, _ = post('/api/kb/list', {'token': TU, 'user_name': '本地1234'})
    results.append(check('普通token冒名admin→403', st, 403))
    st, r = post('/api/kb/list', {'token': TA})
    results.append(check('kb/list admin→200', st, 200))
    for ep in ['/api/kb/upload', '/api/kb/preview', '/api/kb/approve', '/api/kb/reject', '/api/kb/delete', '/api/kb/search']:
        st, _ = post(ep, {'token': 'invalid_xxx'})
        results.append(check('%s 无效token→401' % ep, st, 401))

    print('\n=== 保留名（规格6）===')
    st, r = post('/api/register', {'name': '本地1234', 'password': 'pw1234'})
    results.append(check('重注册"本地1234"被拒', st, 400))
    st, _ = post('/api/register', {'name': 'admin', 'password': 'pw1234'})
    results.append(check('注册 admin 被拒', st, 400))

    print('\n=== 格式矩阵（规格1，全部 admin）===')
    md_text = ('# 青龙偃月刀加倍规则\n\n## 一、总则\n' +
               '青龙偃月刀加倍是趣味赛模式，地主打出首牌为黑桃A时触发，本局底分乘三。' * 8 +
               '\n\n## 二、结算\n' + '触发青龙偃月刀加倍后，春天与反春天不再重复翻倍，按取高原则结算一次。' * 8)
    st, r = post('/api/kb/upload', {'token': TA, 'doc_name': 'kbtest_doc', 'title': '青龙偃月刀', 'text': md_text})
    results.append(check('md文本上传→200', st, 200))
    print('  ', r[:150])
    with open(TMP + '\\test_docx.docx', 'rb') as f:
        docx_bytes = f.read()
    st, r = post('/api/kb/upload', {'token': TA, 'doc_name': 'kbtest_docx'}, files={'file': ('test_docx.docx', docx_bytes)})
    results.append(check('docx上传→200', st, 200))
    print('  ', r[:150])
    with open(TMP + '\\test_text.pdf', 'rb') as f:
        pdf_bytes = f.read()
    st, r = post('/api/kb/upload', {'token': TA, 'doc_name': 'kbtest_pdf'}, files={'file': ('test_text.pdf', pdf_bytes)})
    results.append(check('文字版PDF上传→200', st, 200))
    print('  ', r[:150])
    with open(TMP + '\\test_scanned.pdf', 'rb') as f:
        scan_bytes = f.read()
    st, r = post('/api/kb/upload', {'token': TA}, files={'file': ('test_scanned.pdf', scan_bytes)})
    results.append(check('扫描件PDF→scanned_pdf_unsupported', json.loads(r).get('error') if st == 400 else st, 'scanned_pdf_unsupported'))
    print('  ', st, r[:120])
    with open(TMP + '\\test.zip', 'rb') as f:
        zip_bytes = f.read()
    st, r = post('/api/kb/upload', {'token': TA}, files={'file': ('test.zip', zip_bytes)})
    results.append(check('zip→unsupported_type', json.loads(r).get('error') if st == 400 else st, 'unsupported_type'))

    print('\n=== unchanged 秒判（规格3）===')
    t0 = time.time()
    st, r = post('/api/kb/upload', {'token': TA, 'doc_name': 'kbtest_doc', 'title': '青龙偃月刀', 'text': md_text})
    dt = time.time() - t0
    d = json.loads(r)
    results.append(check('重复上传 unchanged=True', d.get('unchanged'), True))
    results.append(check('耗时<100ms(本地放宽到1500含网络)', dt < 1.5, True))
    print('   实际 %.0fms' % (dt * 1000))

    print('\n阶段1汇总: %d/%d PASS' % (sum(results), len(results)))
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
