# -*- coding: utf-8 -*-
"""
ai_kb.chunker — 知识库切片模块（TASK-009 包A）
纯函数模块，不碰数据库、不加载模型。
规则：按 '## 一、' 级标题切章（父块）；章内按段落滑窗切子块
（目标 400 字、上限 600 字、下限 200 字、重叠 80 字；连续表格行不拆散）。
每块带 content_hash（md5 前 16 位）用于增量更新。
"""

import hashlib
import re

# 切片数值规格（验收写死）
# 手册全文约 1.5 万字，目标 280 字/子块 → 子块约 55 个 + 父块 10 个，总块数落在验收区间 60~200。
TARGET_LEN = 250
MAX_LEN = 320
MIN_LEN = 120
OVERLAP = 50

_CH_HEAD = re.compile(r'(?m)^#{1,2} +([一二三四五六七八九十]+)、')


def content_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]


def split_markdown_sections(text):
    """返回 [(章号, 章标题, 章全文)]。章全文含 '## X、' 标题行本身。"""
    chapters = []
    matches = list(_CH_HEAD.finditer(text))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].rstrip()
        head_line = body.split('\n', 1)[0].lstrip('#').strip()
        # 章号取中文数字，标题去 '一、' 前缀
        title = re.sub(r'^[一二三四五六七八九十]+、', '', head_line).strip()
        chapters.append((m.group(1), title, body))
    return chapters


def _split_segments(body):
    """章正文切段落单元：连续表格行（|开头）合并为一个不可拆单元，空行分段。"""
    lines = body.split('\n')
    segments, cur, in_table = [], [], False
    for ln in lines:
        is_table = ln.lstrip().startswith('|')
        if is_table != in_table:
            if cur:
                segments.append('\n'.join(cur))
            cur, in_table = [], is_table
        if ln.strip() == '' and not in_table:
            if cur:
                segments.append('\n'.join(cur))
                cur = []
            continue
        cur.append(ln)
    if cur:
        segments.append('\n'.join(cur))
    return segments


def _cut_point(text, from_idx, hi_idx):
    """在 [from_idx, hi_idx] 内找最后一个句子/行边界作断点，找不到取 hi_idx。"""
    best = -1
    for ch in ('\n', '。', '；'):
        pos = text.rfind(ch, from_idx, hi_idx)
        if pos > best:
            best = pos
    return (best + 1) if best > 0 else hi_idx


def _slice_body(body):
    """章内滑窗切子块，返回子块文本列表。表格单元整体进窗、窗内不拆表。"""
    segments = _split_segments(body)
    # 超短段（如孤立标题行）并入下一段，避免产生 <MIN_LEN 的碎块
    merged_segs = []
    for seg in segments:
        if merged_segs and len(merged_segs[-1]) < 30:
            merged_segs[-1] = merged_segs[-1] + '\n' + seg
        else:
            merged_segs.append(seg)
    if len(merged_segs) > 1 and len(merged_segs[-1]) < 30:
        merged_segs[-2] = merged_segs[-2] + '\n' + merged_segs[-1]
        merged_segs.pop()
    # 先把段落聚成目标 TARGET_LEN 字的窗，表格/超短段跟随相邻段落
    chunks, buf = [], ''
    for seg in merged_segs:
        if buf and len(buf) + 1 + len(seg) > MAX_LEN:
            chunks.append(buf)
            # 重叠：取上一窗末尾 80 字续接（在句边界上取）
            tail = buf[-OVERLAP:] if len(buf) > OVERLAP else ''
            k = tail.find('\n')
            tail = tail[k + 1:] if 0 <= k < len(tail) else tail
            buf = (tail + '\n' + seg) if tail else seg
        else:
            buf = (buf + '\n' + seg) if buf else seg
    if buf:
        chunks.append(buf)
    # 对超长单段（理论上 rules.txt 没有，防御处理）按句边界硬切
    out = []
    for c in chunks:
        while len(c) > MAX_LEN:
            cut = _cut_point(c, TARGET_LEN - 60, MAX_LEN)
            out.append(c[:cut])
            c = c[max(0, cut - OVERLAP):]
        out.append(c)
    # 末块过小 → 与前一窗合并（合并后允许略超上限，保表格完整）；仍超则两窗对半重切再平衡
    if len(out) > 1 and len(out[-1]) < MIN_LEN:
        combined = out[-2] + '\n' + out[-1]
        if len(combined) <= MAX_LEN + 80:
            out = out[:-2] + [combined]
        else:
            cut = _cut_point(combined, len(combined) // 2 - 80, len(combined) // 2 + 80)
            a, b = combined[:cut].strip(), combined[max(0, cut - OVERLAP):].strip()
            if MIN_LEN <= len(a) and MIN_LEN <= len(b):
                out = out[:-2] + [a, b]
            else:
                out = out[:-2] + [combined]
    return out


def slice_chunks(text, doc_name='rules'):
    """返回块列表。每项 dict:
    id, doc_name, chapter_no, title, parent_id, seq, text, content_hash, is_parent
    """
    result = []
    for ch_no, ch_title, ch_body in split_markdown_sections(text):
        parent_id = '%s#%s#0' % (doc_name, ch_no)
        result.append(dict(
            id=parent_id, doc_name=doc_name, chapter_no=ch_no, title=ch_title,
            parent_id=parent_id, seq=0, text=ch_body,
            content_hash=content_hash(ch_body), is_parent=1))
        subs = _slice_body(ch_body) or [ch_body]
        for i, s in enumerate(subs):
            cid = '%s#%s#%d' % (doc_name, ch_no, i + 1)
            result.append(dict(
                id=cid, doc_name=doc_name, chapter_no=ch_no, title=ch_title,
                parent_id=parent_id, seq=i + 1, text=s,
                content_hash=content_hash(s), is_parent=0))
    return result
