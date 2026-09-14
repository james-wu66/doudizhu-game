# -*- coding: utf-8 -*-
"""
TASK-009 包A 评测脚本：hybrid_search（新）vs _slice_rules（旧章节路由）对照。
判定口径：
- 宽松命中：返回上下文所属章号与 expect_chapters 有交集，且上下文 <= 6000 字
  （旧逻辑 full_fallback 塞手册全文 >6000 字 → 不算命中，"整本书塞 prompt"不是检索）。
- 输出逐题对照表 + 汇总命中率。
运行：cd backend && python eval_rag.py
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_kb import retriever
from routes.ai_assist import _slice_rules, _domain_hit

CTX_LIMIT = 6000


def legacy_hit(question, expect):
    """旧章节路由：返回 (命中?, 说明)"""
    text, hits, note = _slice_rules(question)
    if note == 'full_fallback':
        return False, 'full_fallback(全文兜底)'
    ok = bool(set(hits) & set(expect))
    ok = ok and text is not None and len(text) <= CTX_LIMIT
    return ok, ('+'.join(hits) if hits else '-')


def new_hit(question, expect):
    ctx, hit_ids = retriever.hybrid_search(question)
    chapters = set()
    for hid in hit_ids:
        parts = hid.split('#')
        if len(parts) >= 3:
            chapters.add(parts[1])
    ok = bool(chapters & set(expect)) and len(ctx) <= CTX_LIMIT
    return ok, ','.join(hit_ids) + '→{' + '+'.join(sorted(chapters)) + '}'


def main():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'knowledge', 'eval_queries.json'), encoding='utf-8') as f:
        ev = json.load(f)
    print('[eval] 重建索引…')
    stats = retriever.rebuild_index()
    print('[eval]', stats)

    n_new = n_old = 0
    rows = []
    for q in ev['domain_queries']:
        e = q['expect_chapters']
        ok_new, d_new = new_hit(q['question'], e)
        ok_old, d_old = legacy_hit(q['question'], e)
        n_new += ok_new
        n_old += ok_old
        rows.append((q['id'], q['kind'], q['question'], '+'.join(e),
                     '√' if ok_new else '×', d_new, '√' if ok_old else '×', d_old))

    print('\n=== 逐题对照（新=混合检索 | 旧=章节关键词路由）===')
    print('id   类型  问题                            期望  新  新命中明细 | 旧  旧说明')
    for r in rows:
        print('%-4s %-4s %-30s %-4s %s  %-40s| %s  %s' % (
            r[0], r[1], r[2][:28], r[3], r[4], r[5][:40], r[6], r[7]))

    total = len(ev['domain_queries'])
    print('\n=== 汇总 ===')
    print('新 hybrid_search: %d/%d (%.1f%%)' % (n_new, total, n_new / total * 100))
    print('旧 _slice_rules : %d/%d (%.1f%%)' % (n_old, total, n_old / total * 100))

    # 无关题：前置拦截验证（_domain_hit=False 即被拦）
    print('\n=== 无关题拦截（_domain_hit 应全部 False）===')
    bad = []
    for q in ev['out_of_domain_queries']:
        passed = _domain_hit(q['question'])
        print('%s: %s -> %s' % (q['id'], q['question'],
                                '漏拦!' if passed else '已拦截'))
        if passed:
            bad.append(q['id'])

    verdict = []
    verdict.append(('新方案命中率>=26/30', n_new >= 26))
    verdict.append(('新方案严格高于旧方案', n_new > n_old))
    verdict.append(('无关题6道全拦截', not bad))
    print('\n=== 判定 ===')
    all_ok = True
    for name, ok in verdict:
        print(('通过' if ok else '未通过'), '-', name)
        all_ok = all_ok and ok
    print('EVAL', 'PASS' if all_ok else 'FAIL')
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
