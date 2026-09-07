"""
斗地主 - AI 学习机制模块
职责：记录对局数据、分桶统计、修正分计算

包含：
- AIMemory 类（AI记忆状态）
- _learn 全局学习数据
- _learn_query（查询学习桶数据）
- _learn_adjust（修正分计算）
- _learn_pass_bias（PASS专用双桶对照）
- load_learn_from_db（从数据库加载学习数据）
- ai_observe_play（观测已出牌型）
- ai_record_step（记录学习数据）
"""

import json
import os
import time

class AIMemory:
    round_token = ''
    patterns = [{}, {}, {}]
    pass_streak = [0, 0, 0]
    pass_total = [0, 0, 0]
    last_play_key = ''
    played_types = [[], [], []]

ai_mem = AIMemory()

# 学习数据（简化，替代前端 LEARN 全局变量）
_learn = {
    'loaded': True,
    'step': 0,
    'base': {},
    'buckets': {},
}

ai_mem = AIMemory()


# ==================== _learn_query ====================
def _learn_query(action_type, bucket):
    """查询学习桶数据"""
    if not _learn.get('loaded', True):
        return None
    key = action_type + '|' + bucket
    return _learn.get('buckets', {}).get(key) or _learn.get('buckets', {}).get(key) or None




# ==================== _learn_adjust ====================
def _learn_adjust(action_type, bucket):
    """
    修正分 = (桶胜率 - 基准胜率) × 200，钳制 ±20，乘渐进系数 min(1, total/100)
    """
    b = _learn_query(action_type, bucket)
    if not b or b.get('total', 0) < 30:
        return 0
    base_wr = (_learn.get('base', {}).get(action_type) or _learn.get('base', {}).get(action_type) or {}).get('win_rate')
    if base_wr is None:
        return 0
    raw = (b.get('win_rate', 0) - base_wr) * 200
    clamped = max(-20, min(20, raw))
    return clamped * min(1, b.get('total', 0) / 100)




# ==================== _learn_pass_bias ====================
def _learn_pass_bias(role, landlord_count):
    """
    PASS 专用：让牌 vs 压牌 双桶对照。正=更愿压，负=更愿让
    """
    band = 'lt3' if landlord_count <= 3 else ('lt8' if landlord_count <= 8 else 'gt8')
    beat = _learn_query('PASS', 'beat:' + role + ':' + band)
    pass_b = _learn_query('PASS', 'pass:' + role + ':' + band)
    if not beat and not pass_b:
        return 0
    base_wr = (_learn.get('base', {}).get('PASS') or _learn.get('base', {}).get('PASS') or {}).get('win_rate')
    bias = 0.0
    if beat and pass_b:
        bias = (beat.get('win_rate', 0) - pass_b.get('win_rate', 0)) * 200
    elif beat:
        bias = (beat.get('win_rate', 0) - (base_wr if base_wr is not None else 0.5)) * 200
    elif pass_b:
        bias = -((pass_b.get('win_rate', 0) - (base_wr if base_wr is not None else 0.5)) * 200)
    clamped = max(-20, min(20, bias))
    min_total = min(beat.get('total', 999) if beat else 999, pass_b.get('total', 999) if pass_b else 999)
    return clamped * min(1, min_total / 100)


# 学习数据缓存（60 秒刷新一次，避免每步出牌都查库拖慢）
_learn_loaded_at = 0.0
_LEARN_CACHE_SECONDS = 60




# ==================== load_learn_from_db ====================
def load_learn_from_db():
    """
    从数据库加载学习胜率到 _learn['base'] 和 _learn['buckets']。
    供 _learn_query/_learn_adjust 使用。带 60 秒内存缓存；数据库连接失败静默跳过。
    返回 True 表示加载成功/已有缓存，False 表示失败（不影响出牌）。
    """
    global _learn_loaded_at
    import time
    now = time.time()
    # 缓存未过期则直接跳过（数据已在内存）
    if _learn_loaded_at and (now - _learn_loaded_at) < _LEARN_CACHE_SECONDS:
        return True
    try:
        from utils import get_db
        conn = get_db()
        c = conn.cursor()
        # 基准胜率：按 action_type 分组（排除 NORMAL 纯出牌类型）
        c.execute("""
            SELECT action_type,
                   SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS win_rate,
                   COUNT(*) AS total
            FROM ai_learning
            WHERE result IN ('win','lose') AND action_type != '' AND action_type != 'NORMAL'
            GROUP BY action_type
        """)
        base = {}
        for r in c.fetchall():
            base[r['action_type']] = {'win_rate': round(r['win_rate'], 4), 'total': r['total']}
        # 桶级胜率：按 action_type + bucket 分组，只保留条数 >= 30 的桶
        c.execute("""
            SELECT action_type, bucket,
                   SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS win_rate,
                   COUNT(*) AS total
            FROM ai_learning
            WHERE result IN ('win','lose') AND action_type != '' AND bucket != ''
            GROUP BY action_type, bucket HAVING COUNT(*) >= 30
        """)
        buckets = {}
        for r in c.fetchall():
            key = r['action_type'] + '|' + r['bucket']
            buckets[key] = {'win_rate': round(r['win_rate'], 4), 'total': r['total']}
        conn.close()
        _learn['base'] = base
        _learn['buckets'] = buckets
        _learn['loaded'] = True
        _learn_loaded_at = now
        return True
    except Exception as e:
        # 数据库失败静默跳过，不影响出牌
        print(f"[AI学习] 加载失败，本次跳过: {type(e).__name__}: {e}", flush=True)
        _learn_loaded_at = now  # 冷却，避免每步都重试
        return False




# ==================== ai_observe_play ====================
def ai_observe_play(gs):
    """
    观测已出牌型：记录每个玩家出过的牌的详细信息。
    played_types[p] 存储字典列表，每个字典包含：
      rank: 实际点数
      category: JOKER/TWO/FACE/NUMBER
    """
    played = gs.playedHands if gs.playedHands else [[], [], []]
    for p in range(3):
        ai_mem.played_types[p] = []
        for c in (played[p] if played[p] else []):
            rank = c['rank']
            if rank >= 16:
                cat = 'JOKER'
            elif rank == 15:
                cat = 'TWO'
            elif rank >= 13:
                cat = 'FACE'
            else:
                cat = 'NUMBER'
            ai_mem.played_types[p].append({'rank': rank, 'category': cat})




# ==================== ai_record_step ====================
def ai_record_step(gs, action_type, who):
    """
    记录学习数据（简化版）。
    更新 ai_mem 中的 pass_streak 等统计。
    """
    if action_type == 'PASS':
        ai_mem.pass_streak[who] += 1
        ai_mem.pass_total[who] += 1
    else:
        ai_mem.pass_streak[who] = 0


