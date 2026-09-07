# -*- coding: utf-8 -*-
"""Q4·S4.8 门板成本模型（接线版，20260907 James Wu 口径定稿）

术语（James Wu 原话为准）：
  顶地主 = 不让他过小牌（地主领出，抬一手）——force 纪律：够着底线必顶，
           哪怕被收是"运气账"；顶哪张 = 成本账选最便宜。
  压队友(浪费) = 队友出勾圈级大牌我还烧Q/K —— 禁止（省火力）。
  接队友(不浪费) = 队友出小牌（单≤9/对≤8 起步线，活参数），牌权悬着
           （地主随便一张就收回），我用便宜牌接住保牌权 —— 要接。
  地主≤5张 = 疯狂顶窗口（seal 纪律），原样保留不碰。

成本(候选x) = w1·拆自己牌型 + w2·x自身牌值 + w3·地主收回概率×scale − 卡位收益
三本账全复用现成件：
  ① split_penalty + estimate_hands 手数净增(s48_hand_pen/张)
  ② kw_rank_* + 控制牌火力罚(复用 ls_pen_* 已 bless 账)
  ③ landlord_beat_prob(单张 S3 bless) / landlord_pair_beat_prob(对子 S4.8)
写死的方向（不进参数）：
  · 概率线只当"放→接/顶"的升级判据，永不否决必顶纪律(force)
  · 天花板：A/2/王(main>ceil) 仅地主<=big_le 危机线内可当顶牌；接队友永不烧
  · 拆顺：非拆顺候选优先，只有"不拆就完全放权"才用拆顺候选
  · 区外(L>s48_deep_le，牌账不清)→ 不接管，调用方走已bless老逻辑
  · 队友线以上(勾圈级领出)→ 接队友出口不触发
学习兼容（用户点名检查项）：
  · 所有尺度=活参数(P 现读，_st.P)；方向=写死纪律。S5 网格可拧的键：
    s48_deep_le/w1/w2/w3/gain_base/hand_pen/prob_scale/s4_seal_max_p/
    partner_top_single/partner_top_pair + c48_enable/c48_partner 回滚闸。
  · pb_override 学习插座保留在 vm 的"放"出口（strategy.py 原挂点），
    本模块不改写其语义；接队友/成本选牌=新机制，S5a 登记候选新插座（暂不挂）。
"""

from ai import strategy as _st   # 模块级引用读 _st.P 现值（from import P = 启动快照坑）


# ==================== 小工具（本地纯函数） ====================

def _freq(cards):
    f = {}
    for c in cards:
        f[c['rank']] = f.get(c['rank'], 0) + 1
    return f


def _has_straight(freq):
    """手内是否存在现成顺子（>=5连，2及王不进）——与探针 W1 同口径。"""
    rs = sorted(r for r in freq if r <= 14)
    run = 1
    for i in range(1, len(rs)):
        if rs[i] == rs[i - 1] + 1:
            run += 1
            if run >= 5:
                return True
        else:
            run = 1
    return False


def _big_pen(main):
    """控制牌火力罚：量纲复用已 bless 的 ls_pen_*（不造第二套轮子）。"""
    P = _st.P
    if main >= 16:
        return abs(P['ls_pen_joker'])
    if main == 15:
        return abs(P['ls_pen_two'])
    if main == 14:
        return abs(P['ls_pen_a'])
    return 0.0


# ==================== 账本内核 ====================

def _build_table(gs, who, hand, last_pattern, candidates, use_prob=True):
    """给非炸同型可压候选记三本账。返回 (table, ctx)。"""
    P = _st.P
    lt = last_pattern.get('type')
    lm = last_pattern.get('main', 0)
    L = gs.get_landlord_count()

    from ai.strategy import split_penalty
    from ai.partner_model import landlord_beat_prob, landlord_pair_beat_prob
    from ai.evaluation import estimate_hands

    freq = _freq(hand)
    n = len(hand)
    hands_before = estimate_hands(hand)
    pmax = P['s4_seal_max_p']
    ceil = P['s4_gate_top_ceiling']
    big_le = P['s4_gate_big_le']
    scale = P['s48_prob_scale']
    gain = (P['s48_gain_base'] * (1.0 + (P['s48_deep_le'] - L) / float(P['s48_deep_le']))
            if use_prob else 0.0)

    table = []
    for x in candidates:
        pt = x['pattern']['type']
        if pt in ('BOMB', 'ROCKET'):
            continue                     # 炸归炸弹闸门
        pm = x['pattern']['main']
        if pt != lt or pm <= lm:
            continue                     # 只比同型合法可压
        after = [c for c in hand if not any(y['id'] == c['id'] for y in x['cards'])]
        af = _freq(after)
        dh = estimate_hands(after) - hands_before
        if lt == 'SINGLE':
            dh -= 1                      # 单张顶出天然消一手
        c1 = split_penalty(x['cards'], freq, n) + max(0, dh) * P['s48_hand_pen']
        break_run = _has_straight(freq) and not _has_straight(af)
        # 牌值账：kw_rank_*(12~17有表)；表外小牌用单调外推 (rank-9)*1.5
        #   ——C1接线教训: 兜底 pm*1.5 会让 J=16.5>K=12，账把贵的判便宜
        c2 = (P.get('kw_rank_%d' % pm) if P.get('kw_rank_%d' % pm) is not None
              else max(0.0, (pm - 9) * 1.5)) + _big_pen(pm)
        if use_prob:
            p = (landlord_beat_prob(gs, who, 'SINGLE', pm) if lt == 'SINGLE'
                 else landlord_pair_beat_prob(gs, who, pm))
        else:
            p = 0.0
        c3 = p * scale
        total = P['s48_w1'] * c1 + P['s48_w2'] * c2 + P['s48_w3'] * c3 - gain
        table.append({'main': pm, 'type': pt, 'c1': round(c1, 1), 'c2': round(c2, 1),
                      'p': round(p, 3), 'c3': round(c3, 1), 'gain': round(gain, 1),
                      'total': round(total, 1), 'over_p': p > pmax,
                      'break_run': break_run,
                      'ceil_block': (pm > ceil) and (L > big_le)})
    return table


def _pick(table, candidates, rows, reason):
    """拆顺优先避开 → 成本最小；找回候选对象。"""
    non_break = [t for t in rows if not t['break_run']]
    use = non_break if non_break else rows
    best = min(use, key=lambda t: t['total'])
    act = next(x for x in candidates
               if x['pattern']['type'] == best['type'] and x['pattern']['main'] == best['main'])
    return {'action': act, 'reason': reason, 'table': table}


# ==================== 对外三口 ====================

def _in_scope(P, last_pattern, L):
    lt = last_pattern.get('type')
    if not P.get('c48_enable') or lt not in ('SINGLE', 'PAIR'):
        return False
    if L > P['s48_deep_le']:
        return False                     # 区外：牌账不清不猜
    return True


def gate_top_cost(gs, who, hand, last_pattern, candidates, mode=None):
    """顶地主两出口。mode: 'force'=换牌不判放；'extend'=放局改判顶。
    None/'full'=单测合成口径。返回 None=不接管（调用方老逻辑）。"""
    P = _st.P
    if not P.get('c48_enable'):
        return None
    lt = last_pattern.get('type')
    if lt not in ('SINGLE', 'PAIR'):
        return None
    L = gs.get_landlord_count()
    if L > P['s48_deep_le']:
        return None

    table = _build_table(gs, who, hand, last_pattern, candidates)
    if mode == 'auto':
        # 接线统一口径（engine 用）：底线牌在场=纪律必顶（旧S4域），只是换牌
        # 走成本账；无底线牌=旧放域 → extend（概率线升级判据）。
        cap = P['vm_jump_gate']
        lm = last_pattern.get('main', 0)
        vm_rows = [x for x in table if x['main'] - lm <= cap and not x['ceil_block']]
        if vm_rows:                       # vm门槛内在场=老链路自己顶，照抄最便宜
            best = min(vm_rows, key=lambda x: x['main'])
            act = next(x for x in candidates
                       if x['pattern']['type'] == best['type']
                       and x['pattern']['main'] == best['main'])
            return {'action': act, 'reason': 'auto:vm门槛内照抄', 'table': table}
        line = (P['s4_gate_top_single'] if lt == 'SINGLE'
                else P['s4_gate_top_pair'])
        base = [x for x in table if x['main'] >= line and not x['ceil_block']]
        if base:
            return _pick(table, candidates, base, 'auto:底线必顶成本最小')
        ok = [x for x in table if not x['over_p'] and not x['ceil_block']]
        if not ok:
            return {'action': None,
                    'reason': 'auto:无底线牌且无过线候选(=放)', 'table': table}
        return _pick(table, candidates, ok, 'auto:放域概率线升级顶')
    if mode == 'force':
        # A域=老码必顶的局：纪律凌驾概率线，只优化"顶哪张"。
        # vm门槛内照抄锁：有跳档<=gate的候选=vm老链路自己会挑最便宜（seed508锁）
        cap = P['vm_jump_gate']
        lm = last_pattern.get('main', 0)
        vm_rows = [t for t in table
                   if t['main'] - lm <= cap and not t['ceil_block']]
        if vm_rows:
            best = min(vm_rows, key=lambda t: t['main'])
            act = next(x for x in candidates
                       if x['pattern']['type'] == best['type']
                       and x['pattern']['main'] == best['main'])
            return {'action': act, 'reason': 'force:vm门槛内照抄', 'table': table}
        elig = [t for t in table if not t['ceil_block']]
        if not elig:
            return {'action': None, 'reason': 'force:只剩超天花板且非危机(同老码放)',
                    'table': table}
        return _pick(table, candidates, elig, 'force:纪律必顶成本最小')

    # extend / full
    if not table:
        return {'action': None, 'reason': '无可压候选(炸除外)', 'table': []}
    ok = [t for t in table if not t['over_p'] and not t['ceil_block']]
    if not ok:
        if mode == 'full':
            elig = [t for t in table if not t['ceil_block']]
            if not elig:
                return {'action': None, 'reason': '无过线候选且天花板全挡', 'table': table}
            return _pick(table, candidates, elig, 'full:纪律兜底顶')
        return {'action': None, 'reason': '无过线候选(收得回/天花板)', 'table': table}
    return _pick(table, candidates, ok, 'extend:成本最小')


def gate_extend_after_pass(gs, who, hand, last_pattern, candidates):
    """S4.5 继任出口（vm 判放后咨询）：深算区内'放'改判顶。
    单张域行为覆盖旧S4.5（同内核同线）；对子域=新增（旧版恒1.0不触发）。
    返回候选 or None(=维持放)。仅门板用（下家三件套不碰）。"""
    if gs.get_role(who) != 'farmerPrev':
        return None
    lp = (gs.lastPlay or {}).get('player', -1)
    if lp != gs.landlord:
        return None
    out = gate_top_cost(gs, who, hand, last_pattern, candidates, mode='extend')
    return out['action'] if out else None


def gate_partner_accept(gs, who, hand, last_pattern, candidates):
    """接队友出口：队友(下家)领出小牌、牌权悬着 → 门板便宜牌接住。
    触发（全满足）：c48_partner 开 / 上家=下家队友 / 地主>5张(<=5走疯狂顶
    老窗口不碰) / 队友牌 <= 接队友线(单 s48_partner_top_single、对
    s48_partner_top_pair)。
    接法：同账挑最便宜（A/2/王永不烧=浪费；拆顺避开；不赌收回概率——
    接小牌本身零成本抬价，James Wu 例：对4→有对9对10对圈→出对9）。
    返回候选 or None(=维持放)。"""
    P = _st.P
    if not P.get('c48_enable') or not P.get('c48_partner'):
        return None
    lt = last_pattern.get('type')
    if lt not in ('SINGLE', 'PAIR'):
        return None
    L = gs.get_landlord_count()
    if L <= P['s4_gate_big_le']:
        return None                      # 后期=疯狂顶老窗口(seal)，原样(线=活参数,非写死5)
    lp = (gs.lastPlay or {}).get('player', -1)
    if lp == gs.landlord:
        return None                      # 地主领出=顶地主域，不在这
    line = (P['s48_partner_top_single'] if lt == 'SINGLE'
            else P['s48_partner_top_pair'])
    if last_pattern.get('main', 0) > line:
        return None                      # 勾圈级=牌权稳，不浪费
    table = _build_table(gs, who, hand, last_pattern, candidates, use_prob=False)
    rows = [t for t in table if not t['ceil_block']]
    if not rows:
        return None
    return _pick(table, candidates, rows, 'partner:便宜接')['action']
