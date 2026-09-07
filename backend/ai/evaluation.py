"""
斗地主 - 价值评估模块（高手级）
职责：给候选出牌打分，选最优

包含：
- 手牌评估（叫地主用）
- 手数估算
- 候选打分
- 路线价值
- 2步前瞻选择最优出牌
"""

import json
import os
from ai.pattern import detect_pattern
from ai.candidates import generate_candidates
from ai.strategy import hand_shape, big_cards_status, remaining_map, count_ranks, _last_player_for_ai, split_penalty, kicker_waste, estimate_count_in, big_value, control_tradeoff, ai_should_pass_counter, possible_bomb_threat, consecutive_runs
from ai.learning import _learn_adjust, ai_mem
from ai.state import PLAYER, LEFT, RIGHT


# ==================== 配置加载 ====================

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
_CFG = {}
if os.path.exists(_CONFIG_PATH):
    with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
        _CFG = json.load(f)

# ==================== 参数层（外置，可被学习覆盖；缺省=当前值，保证行为不变） ====================
_DEFAULTS = {
    'vm_jump_next': 3, 'vm_jump_gate': 4, 'vm_danger_count': 8,
    'vm_joker_jump_pen': -120,
    'pb_override': 99,
    'vm_lead_single_max': 9, 'lr_no_single_pen': -40, 'lr_next_dump_big_pen': -25,
    'bb_finish_hands': 2, 'bb_crisis_threat': 3, 'bb_big_bomb_pen': -150,
    "sp_rank_weight_3": 0.6, "sp_rank_weight_4": 0.6, "sp_rank_weight_5": 0.7,
    "sp_rank_weight_6": 0.7, "sp_rank_weight_7": 0.8, "sp_rank_weight_8": 0.8,
    "sp_rank_weight_9": 0.9, "sp_rank_weight_10": 1.0, "sp_rank_weight_11": 1.0,
    "sp_rank_weight_12": 1.1, "sp_rank_weight_13": 1.2, "sp_rank_weight_14": 1.3,
    "sp_rank_weight_15": 1.5, "sp_rank_weight_16": 1.8, "sp_rank_weight_17": 2.0,
    "sp_stage_early": 0.8, "sp_stage_mid": 1.0, "sp_stage_late": 1.3,
    "sp_pen_bomb": 60, "sp_pen_two": 30, "sp_pen_triple": 50, "sp_pen_pair": 30,
    "sp_pen_run": 40,
    "kw_rank_17": 35, "kw_rank_16": 28, "kw_rank_15": 22, "kw_rank_14": 18,
    "kw_rank_13": 12, "kw_rank_12": 5, "kw_counter_mult": 0.5, "kw_lead_mult": 1.0,
    "bv_finish": 180, "bv_c_land_le3": 150, "bv_c_land_le6": 80, "bv_c_bomb": 100,
    "bv_c_else": -80, "bv_c_part_le3": -90, "bv_c_part_else": -25,
    "bv_c_land_threat_le3": 120, "bv_c_land_bomb": 100, "bv_c_land_else": -80,
    "bv_farmer_land_le3": 120, "bv_hand_le6": 70, "bv_hand_else": -70,
    "ct_main15_le5": -18, "ct_main15_le8": -8, "ct_main15_else": 0,
    "ct_main16_17_gt8": -20, "ct_main16_17_le3": 8, "ct_main16_17_else": 0,
    "ct_type_non_single": 1.2, "ct_type_single": 1.0,
    "eh_card_17": 14, "eh_card_16": 10, "eh_card_15": 6, "eh_card_14": 4,
    "eh_card_13": 3, "eh_card_12": 2.5, "eh_card_11": 2, "eh_card_10": 1.8,
    "eh_card_9": 1.5, "eh_card_8": 1.2, "eh_card_else": 1,
    "eh_combo_bomb": 12, "eh_combo_triple": 4, "eh_combo_pair": 2, "eh_combo_rocket": 16,  # S4.9: 王炸>炸弹>2>A
    "eh_straight_base": 4, "eh_straight_perlen": 0.5, "eh_pairrun_base": 4,
    "eh_pairrun_perlen": 1, "eh_triplerun_base": 6, "eh_triplerun_perlen": 2,
    "eh_len_penalty": 1.5, "eh_single_penalty": 1.5,
    "rv_group": -7, "rv_single": -3, "rv_can_finish": 90, "rv_maxlen_mult": 4,
    "rv_hands_base": 5,
    "cs_base_single": 5, "cs_base_pair": 8, "cs_base_other": 18,
    "cs_struct_straight_pair_airplane": 12, "cs_four_two": 10, "cs_four_two_bomb_main": -30,
    "cs_endgame_big_weight": 8, "cs_delta_ge2": 15, "cs_delta_eq1": 8, "cs_delta_lt0": 12,
    "cs_core5_single_two": 10, "cs_core5_single_K_noA": 5,
    # 大牌节流 v2（lead 主动出牌点数分级罚分 + 残局豁免阈值）——与 strategy.py _DEFAULTS 保持同步
    "ls_pen_joker": -70, "ls_pen_two": -45, "ls_pen_a": -22, "ls_endgame_th": 6,
    "ls_land_small_bonus": 24,
    # TASK-C 农民 lead 三改（与 strategy.py _DEFAULTS 保持同步）
    "ls_single_bias_mult": 0.4, "ls_gate_exempt_hands": 3, "ls_gate_exempt_big": 3,
    "cs_struct_len_bonus": 6, "cs_struct_len_cap": 36,
    "cs_kicker_a_pen": 25, "cs_kicker_k_pen": 15,
    "lt_triple_pen": -90, "ct_danger_cnt": 3,
    # BUG#2 counter 王牌节流独立参数（与 lead 的 ls_pen_joker 同值但可分别调/消融）
    "cc_pen_joker": -70,
    # BUG#4 飞机带牌打分修正（与 strategy.py / config.json 保持同步）：
    # 原裸飞+45/带对+45/带单+25，裸飞对带单占优20分导致"飞机裸奔"；
    # 改为带单/带对 ≥ 裸飞，让拆两条三条清零的带牌变体胜出。
    "ap_bare_bonus": 25, "ap_single_bonus": 45, "ap_pair_bonus": 45,
    # 任务C 压队友两条件（20260905）：牌含2/王且非卡位非自救时的重罚
    "cp_partner_big_pen": -120,
    # 任务E 硬编码普查参数化（20260905）：counter 段（cp_）——默认值=原裸数字，行为零变化
    "cp_land_press_l1": 120, "cp_land_press_l2": 95, "cp_land_press_l3": 65,
    "cp_land_press_l4": 30, "cp_land_press_l5": 8,
    "cp_gate_bonus_le6": 30, "cp_gate_bonus_other": 14, "cp_gate_bonus_le2": 60,
    "cp_small_bonus": 8,
    "cp_partner_pen_l1": 70, "cp_partner_pen_l2": 35, "cp_partner_pen_l3": 8,
    "cp_partner_land_l1": 90, "cp_partner_land_l2": 42,
    "cp_partner_rank13_pen": 30, "cp_partner_rank15_pen": 20,
    "cp_finish_bonus": 140,
    # 任务E lead 段（lp_）
    "lp_finish_bonus": 120, "lp_short_len_bonus": 14, "lp_short_big_pen": 25,
    "lp_triple_one_bonus": 8, "lp_triple_two_bonus": 12, "lp_kicker_big_pen": 40,
    "lp_pairrun_bonus_big": 50, "lp_pairrun_bonus_mid": 25, "lp_pairrun_pen_big": 15,
    "lp_run_bonus_big": 40, "lp_run_pen_big": 10,
    "lp_recover_bonus": 8, "lp_recover_pen": 12,
    "lp_send_big_pen": 70, "lp_send_single_bonus": 40, "lp_send_pair_bonus": 30,
    "lp_softsend_single_bonus": 34, "lp_softsend_pair_bonus": 20,
    "lp_farmer_bomb_danger_bonus": 24,
    "lp_landlord_nonsingle_bonus": 10, "lp_landlord_split_pen": 10,
    "lp_landlord_rush_len_bonus": 8, "lp_landlord_pair2_bonus": 25,
    # 方案A 甲（20260906）：农民夺权/接风 lead 结构牌整手节奏价值按张加分（配合丁 LEADSEIZE 桶）
    "lp_lead_dump_bonus": 60,
    # Q4·S2（20260906）：C1'送先跑接线 + 下家L=1必顶（与 strategy.py / config.json 保持同步）
    # pm_feed_bonus=尺度参数（喂型加多少分），S5 学习桶校准，不写死
    "c1_enable": 1, "pm_send_max": 4, "vm_next_must_top_L1": 1, "pm_feed_bonus": 40,
    # Q4·S3（20260906）：C2 方向闸门——门板领出喂下家默认禁，地主压过概率≤c2_send_max_p才放行
    "c2_enable": 1, "c2_send_max_p": 0.25,
    # Q4·S4（20260906 James Wu 口径）：门板底线必顶+下家兜底+压队友须卡死；数字全活进参数
    "c3_enable": 1, "s4_gate_top_single": 9, "s4_gate_top_pair": 8, "s4_next_cover_le": 8, "s4_next_cover_floor": 11, "s4_seal_max_p": 0.25, "s4_gate_top_ceiling": 13, "s4_gate_big_le": 5,
    # Q4·S4.5/S4.6（20260906 James Wu）：vm接记牌器（农民压放问牌账）+ 地主lead接牌账（过牌安全度）
    "vm_card_counter": 1, "ll_card_counter": 1, "ll_safe_bonus": 12,
    # Q4·S4.8（20260907 James Wu 拍板序）：门板成本模型（深算区三本账合成顶/放；独立函数先影子对拍不接线）
    "c48_enable": 1, "s48_deep_le": 10, "s48_w1": 1.0, "s48_w2": 1.0, "s48_w3": 1.0,
    "s48_gain_base": 10.0, "s48_hand_pen": 10.0, "s48_prob_scale": 100.0,
    # S4.8乙 接队友出口（James Wu 20260907 拍板：队友小牌牌权悬着要接，勾圈级省火力）
    "c48_partner": 1, "s48_partner_top_single": 9, "s48_partner_top_pair": 8,
    # Q5（20260907 James Wu 拍板）：lead 手数最少化相对账，详见 strategy._DEFAULTS 注释
    "c5_q5_enable": 1, "q5_hands_pen": 15
}
_PCFG = _CFG.get('params', {})
P = {k: _PCFG.get(k, v) for k, v in _DEFAULTS.items()}



# ==================== evaluate_hand ====================
def evaluate_hand(cards, config=None):
    """
    手牌综合评分。
    返回 dict: {score: float, bombs: int, rocket: int, singles: int}
    """
    freq = count_ranks(cards)
    score = 0.0
    bombs = 0
    rocket = 0

    # 每张牌的基础分（外置到 params.eh_card_* ；缺省=当前值，行为不变）
    for c in cards:
        r = c['rank']
        if r == 17:
            score += P['eh_card_17']
        elif r == 16:
            score += P['eh_card_16']
        elif r == 15:
            score += P['eh_card_15']
        elif r == 14:
            score += P['eh_card_14']
        elif r == 13:
            score += P['eh_card_13']
        elif r == 12:
            score += P['eh_card_12']
        elif r == 11:
            score += P['eh_card_11']
        elif r == 10:
            score += P['eh_card_10']
        elif r == 9:
            score += P['eh_card_9']
        elif r == 8:
            score += P['eh_card_8']
        else:
            score += P['eh_card_else']

    # 组合加分
    for r, cnt in freq.items():
        if cnt == 4:
            score += P['eh_combo_bomb']
            bombs += 1
        elif cnt == 3:
            score += P['eh_combo_triple']
        elif cnt == 2:
            score += P['eh_combo_pair']

    # 火箭加分
    if freq.get(16, 0) and freq.get(17, 0):
        score += P['eh_combo_rocket']
        rocket = 1

    # 顺子加分
    runs = consecutive_runs(list(freq.keys()), 5)
    for run in runs:
        if len(run) >= 5:
            score += P['eh_straight_base'] + min(len(run), 10) * P['eh_straight_perlen']

    # 连对加分
    pair_runs = consecutive_runs([r for r in freq if freq[r] >= 2], 3)
    for run in pair_runs:
        if len(run) >= 3:
            score += P['eh_pairrun_base'] + len(run) * P['eh_pairrun_perlen']

    # 飞机加分
    triple_runs = consecutive_runs([r for r in freq if freq[r] >= 3], 2)
    for run in triple_runs:
        if len(run) >= 2:
            score += P['eh_triplerun_base'] + len(run) * P['eh_triplerun_perlen']

    # 张数惩罚
    score -= max(0, len(cards) - 17) * P['eh_len_penalty']

    # 散牌过多惩罚
    singles = sum(1 for r in freq if freq[r] == 1)
    if singles >= 5:
        score -= (singles - 4) * P['eh_single_penalty']

    return {
        'score': max(0, min(100, score)),
        'bombs': bombs,
        'rocket': rocket,
        'singles': singles,
    }



# ==================== estimate_hands ====================
def estimate_hands(cards):
    """
    手数分析（精确还原旧版JS estimateHands）。
    估算一手牌要打几手才能出完：贪心保留结构（王炸→炸弹→三根/飞机→连对→顺子→对子→单牌）
    """
    if not cards or not len(cards):
        return 0

    freq = count_ranks(cards)
    hands = 0

    # 王炸
    if freq.get(16, 0) and freq.get(17, 0):
        hands += 1
        freq[16] = 0
        freq[17] = 0

    # 炸弹
    bomb_ranks = [r for r in list(freq.keys()) if freq[r] == 4]
    for r in bomb_ranks:
        hands += 1
        freq[r] = 0

    # 三张/飞机
    triples = sorted([r for r in freq if freq[r] >= 3 and r <= 14])
    triple_groups = 0
    t = 0
    while t < len(triples):
        j = t
        while j + 1 < len(triples) and triples[j + 1] == triples[j] + 1:
            j += 1
        triple_groups += 1
        for k in range(t, j + 1):
            freq[triples[k]] -= 3
        t = j + 1
    hands += triple_groups

    # 连对
    pairs = sorted([r for r in freq if freq[r] >= 2 and r <= 14])
    p = 0
    while p < len(pairs):
        j = p
        while j + 1 < len(pairs) and pairs[j + 1] == pairs[j] + 1:
            j += 1
        if j - p + 1 >= 3:
            hands += 1
            for k in range(p, j + 1):
                freq[pairs[k]] -= 2
        p = j + 1

    # 顺子
    singles = sorted([r for r in freq if freq[r] > 0 and r <= 14])
    s = 0
    while s < len(singles):
        j = s
        while j + 1 < len(singles) and singles[j + 1] == singles[j] + 1:
            j += 1
        if j - s + 1 >= 5:
            hands += 1
            for k in range(s, j + 1):
                freq[singles[k]] -= 1
        s = j + 1

    # 统计剩余单牌和对子
    single_count = 0
    pair_count = 0
    for r in freq:
        n = freq[r]
        pair_count += n // 2
        single_count += n % 2

    # 三带/飞机带翅膀：每手三根可带走1个散单或1个对子（不增加手数）
    carry = triple_groups
    carry_singles = min(single_count, carry)
    single_count -= carry_singles
    carry -= carry_singles
    carry_pairs = min(pair_count, carry)
    pair_count -= carry_pairs
    carry -= carry_pairs
    hands += single_count + pair_count

    return hands



# ==================== candidate_score ====================
def _struct_lead_ok(gs, hand, who, x, last, mode, config):
    """TASK-G 3b 判定：当前候选之外，手中还存在可领出的结构型候选
    （对子/三带/顺子/连对，且拆损可接受）。用于'有结构不出、偏领单张'罚分。"""
    if mode == 'counter' or last is not None:
        return False   # 仅自由领出时判
    from ai.candidates import generate_candidates
    try:
        cands = generate_candidates(hand, None)
    except Exception:
        return False
    from ai.strategy import split_penalty, count_ranks
    freq = count_ranks(hand)
    played = [c['id'] for c in x['cards']]
    for c in cands:
        if c['pattern']['type'] == 'SINGLE':
            continue
        if c['pattern']['type'] in ('BOMB', 'ROCKET'):
            continue
        if sorted(q['id'] for q in c['cards']) == sorted(played):
            continue   # 就是当前候选（不会，当前是SINGLE）——防御
        if split_penalty(c['cards'], freq, len(hand)) <= 10:
            return True
    return False


def candidate_score(gs, x, hand, who, mode, last, last_pattern=None, config=None):
    """
    核心评分函数，给每个候选出牌打分。
    x: dict {'cards': [...], 'pattern': {...}}
    hand: list[card]（当前手牌）
    who: int（出牌玩家）
    mode: str（'counter'=跟牌，'lead-xxx'=主动出牌策略）
    last: dict{'type', 'main', 'len'} or None（上家牌型）
    返回 int 评分
    """
    role = gs.get_role(who)
    pattern = x['pattern']
    after = [c for c in hand if not any(y['id'] == c['id'] for y in x['cards'])]
    shape = hand_shape(after)
    landlord_count = gs.get_landlord_count()
    partner = gs.get_partner(who)
    partner_count = gs.get_teammate_count(who) if partner >= 0 else 99
    last_player = _last_player_for_ai(gs)
    freq = count_ranks(hand)
    big = big_cards_status(gs)

    # === Core 1: base score ===
    if pattern['type'] == 'SINGLE':
        score = P['cs_base_single']
    elif pattern['type'] == 'PAIR':
        score = P['cs_base_pair']
    else:
        score = P['cs_base_other']

    if pattern['type'] in ('STRAIGHT', 'STRAIGHT_PAIR') or pattern['type'].startswith('AIRPLANE'):
        score += P['cs_struct_straight_pair_airplane']
    if pattern['type'] == 'FOUR_TWO':
        score += P['cs_four_two']
    if pattern['type'] == 'FOUR_TWO' and freq.get(pattern['main'], 0) == 4 and len(after) > 0:
        score += P['cs_four_two_bomb_main']  # 整副炸弹拆当四带二主牌罚分（参数为负值；原 -= 双负得正成奖励，属符号bug，20260904 修复；清空手牌除外）

    # === Core 2: structure value (route_value + split penalty) ===
    # route_value 只在主动出牌 lead 模式计算；跟牌 counter 跳过（否则"出大牌剩余结构好"
    # 会误导 AI 甩大牌压小牌，跟牌应优先出最小能压的牌）
    if mode != 'counter':
        score += route_value(gs, hand, x, who)
    _sp = split_penalty(x['cards'], freq, len(hand))
    score -= _sp * 1.25
    if _sp > 0:
        if _sp <= 6:
            pen_band = 'p6'
        elif _sp <= 10:
            pen_band = 'p10'
        elif _sp <= 25:
            pen_band = 'p25'
        else:
            pen_band = 'p30'
        hand_band = 'h8' if len(gs.hands[who]) <= 8 else 'hm'
        score += _learn_adjust('SPLIT', pen_band + ':' + hand_band)
    score -= kicker_waste(x['cards'], pattern, mode == 'counter')
    


    # === 残局优先级：手牌<=3张时，大牌加分（确保控制权） ===
    if len(hand) <= 3 and pattern['type'] not in ('BOMB', 'ROCKET'):
        score += (pattern['main'] - 3) * P['cs_endgame_big_weight']  # 残局大牌优先（权重高）
    
    # === Core 3: hand count delta（仅主动出牌 lead 模式计算；跟牌 counter 跳过，
    #      避免"甩大牌减手数"误导 AI 浪费控制牌） ===
    if mode != 'counter':
        hands_before = estimate_hands(hand)
        hands_after = estimate_hands(after)
        delta = hands_before - hands_after
        if delta >= 2:
            score += P['cs_delta_ge2']
        elif delta == 1:
            score += P['cs_delta_eq1']
        elif delta == 0:
            pass
        else:
            score -= P['cs_delta_lt0']

    # === Core 5: tracker integration ===
    if mode != 'counter' or not last:
        if big['bigJoker'] == 0 and big['smallJoker'] == 0:
            pass
        elif pattern['type'] == 'SINGLE' and pattern['main'] == 15:
            score -= P['cs_core5_single_two']
        if big['A'] == 0 and pattern['type'] == 'SINGLE' and pattern['main'] == 13:
            score += P['cs_core5_single_K_noA']

    # === Counter mode ===
    if mode == 'counter':
        score += big_value(gs, x, hand, who, last, mode)
        if pattern['type'] in ('BOMB', 'ROCKET'):
            _threat = gs.get_threat_count(who)
            threat_band = 't3' if _threat <= 3 else ('t4' if _threat <= 4 else 't5')
            hand_band = 'h5' if len(hand) <= 5 else ('h10' if len(hand) <= 10 else 'hm')
            score += _learn_adjust('BOMB', threat_band + ':' + hand_band)
        score += control_tradeoff(gs, x, hand, who, last, mode)
        landlord_play = (role != 'landlord' and last_player == gs.landlord)
        partner_play = (role != 'landlord' and last_player == partner)
        if landlord_play:
            if landlord_count <= 2:
                score += P['cp_land_press_l1']
            elif landlord_count <= 3:
                score += P['cp_land_press_l2']
            elif landlord_count <= 5:
                score += P['cp_land_press_l3']
            elif landlord_count <= 8:
                score += P['cp_land_press_l4']
            else:
                score += P['cp_land_press_l5']
            if role == 'farmerPrev':
                score += P['cp_gate_bonus_le6'] if landlord_count <= 6 else P['cp_gate_bonus_other']
            if role == 'farmerPrev' and landlord_count <= 2:
                score += P['cp_gate_bonus_le2']
            if pattern['type'] == 'SINGLE' and pattern['main'] <= 10:
                score += P['cp_small_bonus']
        if partner_play:
            if partner_count <= 2:
                score -= P['cp_partner_pen_l1']
            elif partner_count <= 4:
                score -= P['cp_partner_pen_l2']
            else:
                score -= P['cp_partner_pen_l3']
            if landlord_count <= 3:
                score += P['cp_partner_land_l1']
            elif landlord_count <= 6:
                score += P['cp_partner_land_l2']
            if pattern['type'] not in ('BOMB', 'ROCKET'):
                max_rank = max(c['rank'] for c in x['cards'])
                if max_rank >= 13:
                    score -= P['cp_partner_rank13_pen']
                if max_rank >= 15:
                    score -= P['cp_partner_rank15_pen']
                # 任务C（20260905）压队友两条件收紧——用户规则：压队友仅两种合法：
                # (a) 门板卡位：地主快跑(<=危险线)且门板手里没有能顺过的中等单张(10-13)，
                #     需要压大牌禁止地主过小牌；
                # (b) 夺权自救：自己 ≤2 手走完且地主压不起该点数（概率推算）。
                # 牌含 2/王 且两条件都不满足 → 重罚 cp_partner_big_pen。
                # （原 landlord_count<=3 时无条件 +90 过宽——game43[40] 门板拿小王压
                # 队友单J 的病灶就在上面这条加分，本罚分项抵消其误导。）
                if max_rank >= 15 and last:
                    gate_block = (role == 'farmerPrev' and
                                  landlord_count <= P['ct_danger_cnt'] and
                                  not any(r > last['main'] and freq.get(r, 0) == 1
                                          for r in range(10, 14)))
                    self_save = (estimate_hands(after) <= 2 and
                                 sum(estimate_count_in(gs, gs.landlord, rr)
                                     for rr in range(pattern['main'] + 1, 18)) < 0.8)
                    if not (gate_block or self_save):
                        score += P['cp_partner_big_pen']
        if len(after) == 0:
            score += P['cp_finish_bonus']
        # BUG#2 修复（20260904）：counter 模式补王牌节流——手里牌还多时用王（含
        # 带王的组合）压牌，在非终结、非炸弹时罚 cc_pen_joker（原 counter
        # 段无此约束，地主敢拿大王吃单 6）。作用域限地主：农民压王属 BUG#4 队友
        # 配合规则管辖，此处不介入（消融证明罚农民会把拆顺子探针 7→10）。
        # 只罚王不罚 2：罚 2 会把跟牌推去拆顺子顶（6→20），2 留作正当"最后一道闸"。
        # 豁免：一手出完（上面 +140 链）、炸弹/王炸（big_value 单独裁量）。
        if (role == 'landlord' and len(after) > 0
                and pattern['type'] not in ('BOMB', 'ROCKET')
                and len(hand) > P['ls_endgame_th']
                and any(c['rank'] >= 16 for c in x['cards'])):
            score += P['cc_pen_joker']
        # TASK-G 小节2补（20260906）：农民压地主禁跳王——一格压一格（James Wu：
        # 大王的天职是压小王；地主出A我有2不顶、拿小王跳2档=浪费）。
        # 场景限定防冲突：仅 农民 & last是地主出的 & 候选是含王的单张 & 手中有
        # 非王牌能压 时罚；王压王(跳1)无便宜替代自然豁免；队友出牌域零接触
        # （旧消融教训：无差别罚农民王会把拆顺子7→10）。
        if (role != 'landlord' and last is not None and
                _last_player_for_ai(gs) == gs.landlord and
                pattern['type'] == 'SINGLE' and pattern['main'] >= 16 and
                len(after) > 0 and
                any(r > last['main'] and r <= 15 and freq.get(r, 0) >= 1
                    for r in range(last['main'] + 1, 16))):
            score += P['vm_joker_jump_pen']
        # 任务D（20260905）：COUNTER 分桶学习修正（与 routes/ai.py 记录侧同口径：
        # bucket=角色:威胁档；桶样本<30 时 _learn_adjust 返回 0，行为不变）。
        _threat_c = gs.get_threat_count(who)
        _tb_c = 't3' if _threat_c <= 3 else ('t4' if _threat_c <= 4 else 't5')
        score += _learn_adjust('COUNTER', str(role) + ":" + _tb_c)
    else:
        # === Lead mode ===
        score += big_value(gs, x, hand, who, last, mode)
        if pattern['type'] in ('BOMB', 'ROCKET'):
            _threat2 = gs.get_threat_count(who)
            threat_band2 = 't3' if _threat2 <= 3 else ('t4' if _threat2 <= 4 else 't5')
            hand_band2 = 'h5' if len(hand) <= 5 else ('h10' if len(hand) <= 10 else 'hm')
            score += _learn_adjust('BOMB', threat_band2 + ':' + hand_band2)
        if len(after) == 0:
            score += P['lp_finish_bonus']
        if len(hand) <= 6:
            if len(after) == 0:
                score += len(x['cards']) * P['lp_short_len_bonus']
            elif pattern['main'] >= 14 and pattern['type'] not in ('BOMB', 'ROCKET'):
                score -= P['lp_short_big_pen']
            else:
                score += len(x['cards']) * P['lp_short_len_bonus']
        # 控制牌保留（大牌节流 v2：lead 阶段按点数分级重罚 A/2/王，残局豁免，
        # 参数外置到 P 表可被后续学习覆盖；替换原单一 -25 平罚）
        if (len(after) > 0 and len(hand) > P['ls_endgame_th'] and
                pattern['type'] in ('SINGLE', 'PAIR') and
                pattern['type'] not in ('BOMB', 'ROCKET')):
            if pattern['main'] >= 16:
                score += P['ls_pen_joker']   # 主动甩王（最重）
            elif pattern['main'] == 15:
                score += P['ls_pen_two']     # 主动甩2
            elif pattern['main'] == 14:
                score += P['ls_pen_a']       # 主动甩A
        # 带牌更优
        if pattern['type'] == 'TRIPLE_ONE':
            score += P['lp_triple_one_bonus']
        if pattern['type'] == 'TRIPLE_TWO':
            score += P['lp_triple_two_bonus']
        # 带牌不带大牌
        if (len(after) > 0 and pattern['type'] in ('TRIPLE_ONE', 'TRIPLE_TWO', 'AIRPLANE_SINGLE', 'AIRPLANE_PAIR')):
            main_cnt = sum(1 for c in x['cards'] if c['rank'] == pattern['main'])
            kicker_big = any(c['rank'] >= 15 and not (c['rank'] == pattern['main'] and main_cnt >= 3) for c in x['cards'])
            if kicker_big:
                score -= P['lp_kicker_big_pen']
        # BUG#3 修复（20260904）：lead 模式三张2（222/222带）在非终结、非紧急下重罚——
        # 用户规则：控制牌只在 (a)一手出完 (b)对手进危险区(<=3张) 时才允许扔。
        # 紧急指标沿用 get_threat_count（地主视角=两农民较小张数，前端真实传入）。
        if (len(after) > 0 and pattern['type'] in ('TRIPLE', 'TRIPLE_ONE', 'TRIPLE_TWO') and
                pattern['main'] >= 15 and gs.get_threat_count(who) > P['ct_danger_cnt']):
            score += P['lt_triple_pen']
        # TASK-C 改动三：农民三带一/三带二的带牌按最高点数分级罚（带2/王维持上方
        # 现有罚40不变；三档不叠加只取最高档）。走牌纪律：三带都带小牌。
        if role != 'landlord' and pattern['type'] in ('TRIPLE_ONE', 'TRIPLE_TWO'):
            kicker_ranks = [c['rank'] for c in x['cards'] if c['rank'] != pattern['main']]
            if kicker_ranks:
                kmax = max(kicker_ranks)
                if kmax == 14:
                    score -= P['cs_kicker_a_pen']
                elif kmax == 13:
                    score -= P['cs_kicker_k_pen']
        # 大牌型整合奖励
        if pattern['type'] == 'STRAIGHT_PAIR' and pattern['len'] >= 5 and pattern['main'] + pattern['len'] - 1 <= 11:
            score += P['lp_pairrun_bonus_big']
        elif pattern['type'] == 'STRAIGHT_PAIR' and pattern['len'] >= 3 and pattern['main'] + pattern['len'] - 1 <= 11:
            score += P['lp_pairrun_bonus_mid']
        elif pattern['type'] == 'STRAIGHT_PAIR' and pattern['main'] + pattern['len'] - 1 >= 12:
            score -= P['lp_pairrun_pen_big']
        if pattern['type'] == 'STRAIGHT' and pattern['len'] >= 5 and pattern['main'] + pattern['len'] - 1 <= 13:
            score += P['lp_run_bonus_big']
        elif pattern['type'] == 'STRAIGHT' and pattern['main'] + pattern['len'] - 1 >= 14:
            score -= P['lp_run_pen_big']
        if pattern['type'] == 'AIRPLANE':
            score += P['ap_bare_bonus']
        if pattern['type'] == 'AIRPLANE_PAIR':
            score += P['ap_pair_bonus']
        elif pattern['type'] == 'AIRPLANE_SINGLE':
            score += P['ap_single_bonus']
        # TASK-C 改动二：农民结构牌按张数补基础奖励（只做叠加，不改上方现有封顶
        # 条件奖励本身；地主不适用）。目的：让 778899 这类多张结构翻过单张。
        if (role != 'landlord' and pattern['type'] in ('STRAIGHT', 'STRAIGHT_PAIR',
                'AIRPLANE', 'AIRPLANE_SINGLE', 'AIRPLANE_PAIR')):
            score += min(len(x['cards']) * P['cs_struct_len_bonus'], P['cs_struct_len_cap'])
        # 方案A 甲+丁（20260906）：夺权/接风 lead（last 为空且非地主，首攻恒地主故排除；
        # 且限真实决策排除 lookahead，避免前瞻重复计分）场景下，农民好不容易压回先手，
        # 不该甩小单张白送牌权。作用域 _seize_lead 同时用于甲加分与丁两桶，与记录侧同口径。
        # 甲 lp_lead_dump_bonus：结构牌整手"节奏价值"按张加分（小单张不加）——A1 根因即
        #   结构牌被 split_penalty×1.25 全价计收压到 -10~-132，小单张却 54~88。
        # 丁 LEADSEIZE:角色:{struct|clean}：结构牌(含拆共享卡)落 :struct，干净非炸牌(sp==0)
        #   落 :clean；两桶按实战胜率各自微调，两桶给不同修正→累积≥30样本能真正重排。
        _m = mode or ''
        _seize_lead = (last is None and role != 'landlord'
                       and _m.startswith('lead') and 'lookahead' not in _m)
        if _seize_lead:
            if pattern['type'] in ('STRAIGHT', 'STRAIGHT_PAIR', 'AIRPLANE',
                                   'AIRPLANE_SINGLE', 'AIRPLANE_PAIR'):
                score += len(x['cards']) * P['lp_lead_dump_bonus']
                score += _learn_adjust('LEADSEIZE', str(role) + ":struct")
            elif _sp == 0 and pattern['type'] not in ('BOMB', 'ROCKET'):
                score += _learn_adjust('LEADSEIZE', str(role) + ":clean")
        # 回收能力
        if (len(after) > 0 and pattern['type'] not in ('BOMB', 'ROCKET')):
            next_cands = generate_candidates(after)
            recover = any(
                (c['pattern']['type'] == pattern['type'] and
                 c['pattern']['len'] == pattern['len'] and
                 c['pattern']['main'] > pattern['main']) or
                c['pattern']['type'] in ('BOMB', 'ROCKET')
                for c in next_cands
            )
            if recover:
                score += P['lp_recover_bonus']
            else:
                score -= P['lp_recover_pen']
        # 送牌三原则
        if role != 'landlord' and partner >= 0 and partner_count <= 2 and partner == _ai_next(who):
            if (pattern['type'] in ('SINGLE', 'PAIR')) and pattern['main'] >= 15:
                score -= P['lp_send_big_pen']
            send_ok = ((partner_count == 1 and pattern['type'] == 'SINGLE') or
                       (partner_count == 2 and pattern['type'] in ('SINGLE', 'PAIR')))
            if send_ok:
                send_split = split_penalty(x['cards'], freq, len(hand))
                max_send_rank = max(c['rank'] for c in x['cards'])
                send_good = send_split < 8 and max_send_rank < 14 and len(after) > 0
                if send_good and landlord_count <= 2 and pattern['type'] == 'SINGLE':
                    send_good = False
                if send_good:
                    if pattern['type'] == 'SINGLE':
                        score += P['lp_send_single_bonus']
                    elif pattern['type'] == 'PAIR':
                        score += P['lp_send_pair_bonus']
        elif (role != 'landlord' and 3 <= partner_count <= 5 and partner_count < len(hand)):
            # 队友牌还多(3~5张)：温和倾向出小牌送（队友≤2张时走严格送牌，不在此）
            if pattern['type'] == 'SINGLE' and pattern['main'] <= 6:
                score += P['lp_softsend_single_bonus']
            if pattern['type'] == 'PAIR' and pattern['main'] <= 8:
                score += P['lp_softsend_pair_bonus']
        if role != 'landlord' and landlord_count <= 5 and pattern['type'] in ('BOMB', 'ROCKET'):
            score += P['lp_farmer_bomb_danger_bonus']
        if role == 'landlord' and pattern['type'] != 'SINGLE':
            score += P['lp_landlord_nonsingle_bonus']
        # === TASK-G 小节3b（20260906 James Wu：顶不回手）===
        # 农民领单张前先想"地主拿回牌权我接不接得回"：
        # 手中有结构（对子/三带可领，候选里非SINGLE存在）却领单张给地主过牌机会 → 重罚
        # （地主剩牌<=vm_lead_single_max 时生效；地主牌多属正常走牌不清罚）。
        _has_struct_lead = _struct_lead_ok(gs, hand, who, x, last, mode, config)
        if (role != 'landlord' and pattern['type'] == 'SINGLE' and
                landlord_count <= P['vm_lead_single_max'] and _has_struct_lead):
            score += P['lr_no_single_pen']
        # 下家甩大单张(>=15)且手牌还多：2/王是留给顶地主的子弹，不许当走牌甩
        if (role == 'farmerNext' and pattern['type'] == 'SINGLE' and
                pattern['main'] >= 15 and len(after) > 2 and landlord_count > 1):
            score += P['lr_next_dump_big_pen']
        # 地主 AI 专属策略
        if role == 'landlord':
            if len(hand) > 8:
                # 小牌先走激励（外置；大牌罚分统一走上方"大牌节流 v2"，避免双重扣分）
                if pattern['type'] == 'SINGLE' and pattern['main'] <= 7:
                    score += P['ls_land_small_bonus']
            if len(hand) > 10 and split_penalty(x['cards'], freq, len(hand)) > 0:
                score -= P['lp_landlord_split_pen']
            if len(hand) <= 5 and len(after) > 0:
                score += len(x['cards']) * P['lp_landlord_rush_len_bonus']
            if len(hand) == 2 and pattern['type'] == 'PAIR':
                min_farm = gs.get_teammate_count(gs.current)
                if min_farm <= 2:
                    score += P['lp_landlord_pair2_bonus']
        # 基本排序
        if pattern['type'] not in ('BOMB', 'ROCKET'):
            _bias = (14 - pattern['main']) * 2
            # TASK-C 改动一：农民的单张/对子基本排序打折扣（削弱"越小越加分"的系统性
            # 偏向）；门板位牌非常好（手数少且 A/2/王大牌多）时豁免恢复原始加分——
            # 对应"牌非常好才允许走小牌赌地主不接"。地主与结构牌不受影响。
            if (role != 'landlord' and pattern['type'] in ('SINGLE', 'PAIR')
                    and P['ls_single_bias_mult'] != 1.0):
                big_cnt = sum(1 for c in hand if c['rank'] >= 14)  # 手里 A/2/王 合计张数
                gate_exempt = (role == 'farmerPrev'
                               and estimate_hands(hand) <= P['ls_gate_exempt_hands']
                               and big_cnt >= P['ls_gate_exempt_big'])
                if not gate_exempt:
                    _bias *= P['ls_single_bias_mult']
            score += _bias
        # 位置修正
        if role == 'farmerPrev':
            if pattern['type'] == 'SINGLE':
                if 7 <= pattern['main'] <= 11:
                    score += 21 - 3 * (pattern['main'] - 7)
                if pattern['main'] <= 6:
                    score -= 8
                if pattern['main'] >= 12:
                    score -= 18
                if landlord_count <= 2 and pattern['main'] >= 13:
                    score += 25
            if pattern['type'] == 'PAIR':
                if 7 <= pattern['main'] <= 11:
                    score += 18 - 3 * (pattern['main'] - 7)
                if pattern['main'] <= 6:
                    score -= 8
                if pattern['main'] >= 12:
                    score -= 15
                if landlord_count <= 2 and pattern['main'] >= 13:
                    score += 20
            if len(hand) <= 3:
                score += 30
        if role == 'farmerNext':
            if pattern['type'] == 'SINGLE':
                if pattern['main'] >= 14:
                    score -= 15
                if landlord_count <= 2 and 8 <= pattern['main'] <= 14:
                    score += 20
            if pattern['type'] == 'PAIR':
                if pattern['main'] >= 14:
                    score -= 12
                if landlord_count <= 2 and pattern['main'] >= 8:
                    score += 15
            if len(hand) <= 3:
                score += 30

    return score


# ==================== 第五层：让牌决策函数 ====================


# ==================== ai_pick_scored ====================
def ai_pick_scored(gs, scored, who):
    """
    从评分集合里选最优出牌（含 2 步前瞻）。
    scored: list[dict] 每个 dict 有 'x' 和 'score' 字段
    返回最优出牌的 cards 列表，或 None
    """
    if not scored:
        return None
    scored.sort(key=lambda v: (-v['score'], -len(v['x']['cards'])))
    top_n = scored[:10]
    rem = remaining_map(gs)
    current_hand = gs.hands[gs.current]

    for i in range(len(top_n)):
        try:
            v = top_n[i]
            after = [c for c in current_hand if not any(y['id'] == c['id'] for y in v['x']['cards'])]
            if not after:
                v['score'] += 60
                continue
            bonus = 0
            # Step 2
            c2 = generate_candidates(after)
            if not c2:
                continue
            s2 = [{'x': cx, 'score': candidate_score(gs, cx, after, gs.current, 'lead-lookahead', None, None, None)} for cx in c2]
            s2.sort(key=lambda v: -v['score'])
            best2 = s2[0]
            if not best2:
                continue
            safe2 = all((rem.get(int(r), 0) <= 0 or
                         not any(str(c['rank']) == r for c in best2['x']['cards']))
                        for r in rem)
            after2 = [c for c in after if not any(y['id'] == c['id'] for y in best2['x']['cards'])]
            if not after2:
                bonus += 50 + (5 if safe2 else 0)
            else:
                bonus += 30
                # Step 3
                c3 = generate_candidates(after2)
                if c3:
                    s3 = [{'x': cx, 'score': candidate_score(gs, cx, after2, gs.current, 'lead-lookahead', None, None, None)} for cx in c3]
                    s3.sort(key=lambda v: -v['score'])
                    best3 = s3[0]
                    if best3:
                        after3 = [c for c in after2 if not any(y['id'] == c['id'] for y in best3['x']['cards'])]
                        if not after3:
                            bonus += 20
                        else:
                            bonus += 10
            # Penalty for risky plays
            max_rank = max(c['rank'] for c in v['x']['cards'])
            if max_rank >= 15 and v['x']['pattern']['type'] not in ('BOMB', 'ROCKET'):
                joker_out = rem.get(16, 0) + rem.get(17, 0)
                if joker_out > 0:
                    bonus -= 8
            v['score'] += bonus
        except Exception:
            pass

    top_n.sort(key=lambda v: (-v['score'], -len(v['x']['cards'])))
    top_score = top_n[0]['score']
    near = [v for v in top_n if v['score'] >= top_score - 1]
    import random
    return random.choice(near)['x']['cards']


# ==================== 第七层：高级决策函数 ====================




# ==================== route_value ====================
def route_value(gs, hand, candidate, who):
    """
    路线价值（拆牌/手数分析）。
    candidate: dict {cards: list, pattern: dict}
    返回整数评分
    """
    after = [c for c in hand if not any(x['id'] == c['id'] for x in candidate['cards'])]
    if not after:
        return 180

    next_cands = generate_candidates(after)
    if not next_cands:
        return -80

    shape = hand_shape(after)
    value = -shape['groups'] * P['rv_group'] - shape['singles'] * P['rv_single']

    if any(len(x['cards']) == len(after) for x in next_cands):
        value += P['rv_can_finish']

    value += max((len(x['cards']) for x in next_cands), default=0) * P['rv_maxlen_mult']

    # 手数分析（旧版JS: (5-Math.min(5,hands))*5）
    hands = estimate_hands(after)
    value += (P['rv_hands_base'] - min(P['rv_hands_base'], hands)) * P['rv_hands_base']

    # 队友偏好加成
    partner = gs.get_partner(who)
    if partner >= 0 and partner < len(ai_mem.patterns):
        pref = ai_mem.patterns[partner]
        ptype = candidate['pattern']['type']
        if ptype in pref:
            value += min(18, pref[ptype] * 3)

    return value




# ==================== score_candidates ====================

def _ai_next(who):
    """返回 who 的下家（逆时针下一个出牌者）"""
    return (who + 2) % 3

def score_candidates(candidates, gs, who, last_pattern, config):
    """
    给所有候选出牌打分，返回排序后的列表
    
    参数：
        candidates: list[dict] - 候选出牌列表
        gs: GameState - 游戏状态
        who: int - 当前玩家
        last_pattern: dict or None - 上家牌型
        config: dict - AI配置
    
    返回：
        list[dict] - 按分数排序的候选出牌
    """
    if not candidates:
        return []
    
    # 判断是跟牌还是主动出牌
    mode = 'counter' if last_pattern else 'lead'

    # === Q4·S2 C1' 送先跑（20260906 James Wu 定稿"送前先验跑动"）===
    # 我领出且队友张数≤pm_send_max → partner_runnable 枚举其可能手牌推算"跑不跑得动"：
    #   runnable → 命中 send(type,main) 的候选加 pm_feed_bonus（喂他走）
    #   stuck/unknown → 不干预，正常自打链路（"跑不动就自己打，门板下家同规矩"）
    # 循环外只算一次（枚举毫秒级，避免逐候选重复）；红线：不碰赢牌出口与炸弹闸门。
    # === Q4·S3 C2 方向硬约束（设计v2 §2/§4-C2）===
    #   下家领出→门板紧跟 = safe，喂型直接生效（C1'对称规矩本就双向）；
    #   门板领出→地主插队→才轮下家 = blocked，默认禁送（S2 bless 时门板喂型是
    #   双向裸跑的，S3 补上这道闸）：仅当推算"地主压不过这手"
    #   （landlord_beat_prob ≤ c2_send_max_p）才放行，否则宁可不喂。
    # 红线：不碰赢牌出口与炸弹闸门（engine 层更前）。
    # === Q5 lead 手数最少化（20260907 James Wu 拍板：相对账）===
    # 本场景候选里"走完总步数"的最小值 = 基准；比基准多走一步 = 冤枉路，罚一步差×pen。
    # 步数相同（喂牌/收权等"同价换控制"）零影响；一手出完恒为基准天然豁免；counter 不进场。
    # 参数读 _stq.P（strategy 字典，与 engine 同一事实源，测试/学习拧开关瞬时生效——
    # 教训#2"from import 快照坑"；evaluation.P 是独立对象不可用作 Q5 开关）
    import ai.strategy as _stq
    _q5_min = None
    if _stq.P.get('c5_q5_enable') and mode == 'lead' and len(candidates) > 1:
        try:
            _q5_min = min(
                estimate_hands([c for c in gs.hands[who]
                                if not any(y['id'] == c['id'] for y in cd['cards'])]) + 1
                for cd in candidates)
        except Exception:
            _q5_min = None

    _c1_send = None
    _c1_dir = None
    if P['c1_enable'] and mode == 'lead' and gs.get_role(who) != 'landlord':
        try:
            from ai.partner_model import partner_runnable, send_direction
            _pr = partner_runnable(gs, who, pm_send_max=P['pm_send_max'])
            if _pr['state'] == 'runnable' and _pr['send']:
                _c1_send = _pr['send']
                _c1_dir = send_direction(gs, who)
        except Exception:
            _c1_send = None
    if _c1_send and _c1_dir == 'blocked':
        if not P['c2_enable']:
            _c1_send = None            # C2关=门板方向一律不喂（可单项回滚）
        else:
            try:
                from ai.partner_model import landlord_beat_prob
                if landlord_beat_prob(gs, who, _c1_send[0], _c1_send[1]) > P['c2_send_max_p']:
                    _c1_send = None    # 地主压得过=喂牌等于送地主牌权，禁
            except Exception:
                _c1_send = None

    scored = []
    
    for cand in candidates:
        cards = cand['cards']
        pattern = cand['pattern']
        hand = gs.hands[who]
        
        # 获取角色信息
        role = gs.get_role(who)
        partner = gs.get_partner(who)
        
        # === 学习修正：LEAD 桶 ===
        learn_bonus = 0
        if mode == 'lead' and role != 'landlord':
            try:
                from ai.learning import _learn_adjust
                learn_bonus = _learn_adjust('LEAD', role)
            except Exception:
                pass
        partner_count = gs.get_teammate_count(who) if partner >= 0 else 99
        
        # 使用核心评分函数
        score = candidate_score(gs, cand, hand, who, mode, last_pattern, None, config)
        
        # === 地主专属加分 ===
        if role == 'landlord':
            # Q4·S4.6 地主接记牌器（20260906 James Wu："三个角色都需要推算"）：
            # lead 单张按"农民压不回"概率加分——同样过牌，先出冲线安全的。
            if P['ll_card_counter'] and mode == 'lead' and pattern['type'] == 'SINGLE':
                try:
                    from ai.partner_model import farmer_beat_prob
                    _fb = farmer_beat_prob(gs, who, 'SINGLE', pattern['main'])
                    score += round(P['ll_safe_bonus'] * (1.0 - _fb))
                except Exception:
                    pass
            # 地主出顺子/连对/飞机等多张结构牌 → 加分（消耗手牌快）
            if pattern['type'] in ('STRAIGHT', 'STRAIGHT_PAIR', 'AIRPLANE', 'AIRPLANE_SINGLE', 'AIRPLANE_PAIR'):
                score += P.get("cs_landlord_struct_bonus", 15)
            # 地主手牌少时（<=8张），优先出大牌建立控制
            if len(gs.hands[who]) <= 8 and pattern['type'] not in ('BOMB', 'ROCKET'):
                main_val = pattern.get('main', 0)
                if main_val >= 13:
                    score += P.get("cs_landlord_big_bonus", 10)
            # 地主剩<=5张且能出完 → 大幅加分
            if len(gs.hands[who]) <= 5 and len(cards) == len(gs.hands[who]):
                score += P.get("cs_landlord_finish_bonus", 50)
            # 地主出炸弹/火箭控制局面（对手剩<=3张时）
            if pattern['type'] in ('BOMB', 'ROCKET'):
                # 后端 hands 仅含地主自己手牌，对手张数取 teammate_count_override（见 routes/ai.py）
                opp_counts = [len(gs.hands[p]) for p in range(3)
                              if p != who and len(gs.hands[p]) > 0]
                if not opp_counts and gs.teammate_count_override >= 0:
                    opp_counts = [gs.teammate_count_override]
                opponent_min = min(opp_counts) if opp_counts else 99
                if opponent_min <= 3:
                    score += P.get("cs_landlord_bomb_bonus", 30)  # 关键时刻炸弹加分
        
        # === 农民专属加分 ===
        elif role != 'landlord':
            # Q4·S2 C1' 喂型加分（score_candidates 循环外已判定，见 _c1_send）
            if _c1_send is not None and (pattern['type'], pattern['main']) == _c1_send:
                score += P['pm_feed_bonus']
            # 农民配合：出小牌送队友（如果队友手牌少）
            if partner >= 0 and partner_count <= 3 and pattern['type'] in ('SINGLE', 'PAIR'):
                main_val = pattern.get('main', 0)
                if main_val <= 10:
                    score += 8  # 送小牌给队友

        # TASK-A 改动五：接通 LEAD 学习修正分（原先算完即丢的死代码）
        score += learn_bonus

        # Q5 相对账（基准步数在循环外已算，此处只算本候选步数差）
        if _q5_min is not None:
            try:
                _after_q5 = [c for c in hand if not any(y['id'] == c['id'] for y in cards)]
                _steps_q5 = estimate_hands(_after_q5) + 1
                if _steps_q5 > _q5_min:
                    score -= (_steps_q5 - _q5_min) * _stq.P['q5_hands_pen']
                    cand['q5_steps'] = _steps_q5
            except Exception:
                pass

        cand['score'] = score
        scored.append(cand)
    
    # 按分数降序；TASK-B 改动二：同分平手三级排序——分数降序 → 拆牌罚分小者优先
    # → 张数多者优先（原先稳定排序让"单张先生成"永远赢过同分的顺子等结构牌）
    _tie_hand = gs.hands[who]
    _tie_freq = count_ranks(_tie_hand)
    _tie_size = len(_tie_hand)
    scored.sort(key=lambda x: (-x.get('score', 0),
                               split_penalty(x['cards'], _tie_freq, _tie_size),
                               -len(x['cards'])))
    
    return scored
