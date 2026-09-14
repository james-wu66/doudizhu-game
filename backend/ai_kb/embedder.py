# -*- coding: utf-8 -*-
"""
ai_kb.embedder — 本地向量化模块（TASK-009 包A）
模型：fastembed 的 BAAI/bge-small-zh-v1.5（ONNX 推理，CPU，约100MB）。
懒加载：禁止 import 时加载模型（防拖慢 Flask 启动）。
bge 用法：查询侧加指令前缀，文档侧不加。
缓存目录：环境变量 KB_MODEL_DIR，未设则系统临时目录/kb_models。
"""

import os
import tempfile

_MODEL_NAME = 'BAAI/bge-small-zh-v1.5'
_QUERY_PREFIX = '为这个句子生成表示以用于检索相关文章：'
_embedder = None
_dim = None


def _cache_dir():
    d = os.environ.get('KB_MODEL_DIR')
    if not d:
        d = os.path.join(tempfile.gettempdir(), 'kb_models')
    os.makedirs(d, exist_ok=True)
    return d


def _get_embedder():
    global _embedder, _dim
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(model_name=_MODEL_NAME,
                                  cache_dir=_cache_dir(), threads=2)
        _dim = None  # 首批产出时校准
    return _embedder


def embed_documents(texts, batch_size=16):
    """文档侧向量化（不加指令前缀）。返回 list[list[float]]。"""
    m = _get_embedder()
    out = [list(v) for v in m.embed(list(texts), batch_size=batch_size)]
    _calibrate_dim(out)
    return out


def embed_query(text):
    """查询侧向量化（bge 指令前缀）。返回 list[float]。"""
    m = _get_embedder()
    out = [list(v) for v in m.embed([_QUERY_PREFIX + text])]
    _calibrate_dim(out)
    return out[0]


def _calibrate_dim(vectors):
    global _dim
    if vectors and _dim is None:
        _dim = len(vectors[0])
        print('[ai_kb] embedding 维度=%d' % _dim, flush=True)


def dim():
    return _dim
