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

# ==================== 修正幅度上限（20260909 接线） ====================
# 原先 ±20 写死在 _learn_adjust/_learn_pass_bias 内，config.json 的
# thresholds.learning_max_correction 无人读取。现接线为统一开关：
# 平时保持 20（行为不变）；A/B 对照测 B 组临时设 0 = 等效关闭全部学习修正，
# 测完必须改回 20。读不到配置时兜底 20，绝不影响决策。
# 每次取用时现读模块变量，进程内如需换档由重启 Flask 生效（灌桶脚本每组独立进程）。
_LEARN_CLAMP = 20
try:
    with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r', encoding='utf-8') as _lc_f:
        _LEARN_CLAMP = json.load(_lc_f).get('thresholds', {}).get('learning_max_correction', 20)
except Exception:
    pass

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
    clamped = max(-_LEARN_CLAMP, min(_LEARN_CLAMP, raw))
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
    clamped = max(-_LEARN_CLAMP, min(_LEARN_CLAMP, bias))
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


# ==================== TASK-011：PASS 监督模型推理（20260914） ====================
# 试点制：只换 PASS 一个切入点。模型由 tools/train_pass_model.py 离线训练
# （sklearn 只在训练脚本里用），系数导出为纯 JSON（ai/model_pass/pass_model.json），
# 本文件推理纯 Python 点分 + sigmoid，禁止 import sklearn。
# 静态文件：模型不随 load_learn_from_db 刷新，重训 = 换文件 + 重启进程。
# 兜底：开关关 / 模型缺失 / 加载失败 / 预测异常，一律无声回退 _learn_pass_bias，
# 决策链路绝不报错、绝不返回 None。修正分钳制复用顶部 _LEARN_CLAMP，不另设上限。

_PASS_MODEL = {'enabled': None, 'ok': None, 'model': None}


def _pass_model_config_enabled():
    """读 config.json 的 model_pass.enabled。进程内读一次缓存（开关切换需重启）。"""
    if _PASS_MODEL['enabled'] is None:
        _enabled = False
        try:
            with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r', encoding='utf-8') as f:
                _enabled = bool(json.load(f).get('model_pass', {}).get('enabled', False))
        except Exception:
            _enabled = False
        _PASS_MODEL['enabled'] = _enabled
    return _PASS_MODEL['enabled']


def _pass_model_load():
    """懒加载模型 JSON，进程内一次。任何失败记 ok=False（不反复重试拖慢决策）。"""
    if _PASS_MODEL['ok'] is not None:
        return _PASS_MODEL['ok']
    try:
        with open(os.path.join(os.path.dirname(__file__), 'model_pass', 'pass_model.json'),
                  'r', encoding='utf-8') as f:
            m = json.load(f)
        coefs = [float(x) for x in m['coef']]
        feats = list(m['feature_order'])
        if len(coefs) != len(feats):
            raise ValueError('coef/feature_order 长度不一致')
        _PASS_MODEL['model'] = {
            'coefs': dict(zip(feats, coefs)),
            'intercept': float(m['intercept']),
        }
        _PASS_MODEL['ok'] = True
    except Exception as e:
        _PASS_MODEL['ok'] = False
        print(f"[PASS模型] 加载失败，回退线性修正: {type(e).__name__}: {e}", flush=True)
    return _PASS_MODEL['ok']


def pass_model_ready():
    """开关 true 且模型文件可加载才算 ready；否则调用方走 _learn_pass_bias。"""
    return _pass_model_config_enabled() and _pass_model_load()


def _pass_model_prob(feats):
    """sigmoid(w·x + b)，纯 Python。feats 为特征名 -> 值的 dict。"""
    m = _PASS_MODEL['model']
    z = m['intercept']
    for k, v in feats.items():
        z += m['coefs'].get(k, 0.0) * v
    if z >= 0:
        return 1.0 / (1.0 + pow(2.718281828459045, -z))
    e = pow(2.718281828459045, z)
    return e / (1.0 + e)


def _pass_model_features(role, landlord_count, hand_count):
    """与 tools/train_pass_model.py 的 FEATURE_ORDER 严格一致（训练/推理同构）。"""
    return {
        'is_beat': 0.0,
        'role_farmerPrev': 1.0 if role == 'farmerPrev' else 0.0,
        'role_farmerNext': 1.0 if role == 'farmerNext' else 0.0,
        'role_landlord': 1.0 if role == 'landlord' else 0.0,
        'band_lt3': 1.0 if landlord_count <= 3 else 0.0,
        'band_lt8': 1.0 if 4 <= landlord_count <= 8 else 0.0,
        'band_gt8': 1.0 if landlord_count > 8 else 0.0,
        'hand_norm': hand_count / 20.0,
        'hand_le4': 1.0 if hand_count <= 4 else 0.0,
    }


def pass_model_adjust(gs, role, landlord_count):
    """
    PASS 监督模型修正分（与 _learn_pass_bias 同签名语义，正=更愿压，负=更愿让）。

    公式：bias = (p_beat - p_pass) × 200，钳制 ±_LEARN_CLAMP。
      p_beat = 模型对"此处选择压牌"的整局胜率预测（is_beat=1）
      p_pass = 模型对"此处选择让牌"的同局面反事实预测（is_beat=0）
      两者其余特征完全相同，差值只由 is_beat 系数驱动，天然单调：
      压牌预测胜率高于让牌基准 → 正修正（倾向否决让牌），反之负。
      与线性版 (beat桶胜率-桶胜率)×200 同构，但按 role/地主剩牌档/自身手数
      连续平滑，且不依赖 60 秒桶缓存。
    """
    if not pass_model_ready():
        return _learn_pass_bias(role, landlord_count)
    try:
        hand_count = 20
        try:
            cur = gs.current
            if cur is not None and 0 <= cur < len(gs.hands) and gs.hands[cur]:
                hand_count = len(gs.hands[cur])
        except Exception:
            hand_count = 20
        base = _pass_model_features(role, landlord_count, hand_count)
        x_pass = dict(base)
        x_beat = dict(base)
        x_pass['is_beat'] = 0.0
        x_beat['is_beat'] = 1.0
        p_pass = _pass_model_prob(x_pass)
        p_beat = _pass_model_prob(x_beat)
        raw = (p_beat - p_pass) * 200.0
        return max(-_LEARN_CLAMP, min(_LEARN_CLAMP, raw))
    except Exception as e:
        print(f"[PASS模型] 预测异常，回退线性修正: {type(e).__name__}: {e}", flush=True)
        return _learn_pass_bias(role, landlord_count)


