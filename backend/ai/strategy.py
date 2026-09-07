"""
斗地主 - 出牌策略模块（灵活部分）
职责：决定出不出、出什么

策略从 config.json 读取参数，可以调整

包含：
- 手牌结构分析
- 大牌状态追踪
- 炸弹时机判断
- 概率推算（对手手牌估算）
- 拆牌罚分
- 配件浪费罚分
- 控制与反击权衡
- 让牌决策（ai_should_pass_counter）
"""

import json
import os
from ai.pattern import detect_pattern
from ai.state import PLAYER, LEFT, RIGHT
from ai.learning import ai_mem


# ==================== 配置加载 ====================

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
_CFG = {}
if os.path.exists(_CONFIG_PATH):
    with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
        _CFG = json.load(f)

# ==================== 参数层（外置，可被学习覆盖；缺省=当前值，保证行为不变） ====================
_DEFAULTS = {
    "vm_jump_next": 3, "vm_jump_gate": 4, "vm_danger_count": 8,
    "vm_joker_jump_pen": -120,
    "vm_lead_single_max": 9, "lr_no_single_pen": -40, "lr_next_dump_big_pen": -25,
    "bb_finish_hands": 2, "bb_crisis_threat": 3, "bb_big_bomb_pen": -150,
    "pb_override": 99,
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
    # 大牌节流 v2（lead 主动出牌点数分级罚分 + 残局豁免阈值）
    "ls_pen_joker": -70, "ls_pen_two": -45, "ls_pen_a": -22, "ls_endgame_th": 6,
    # 结构大牌早甩罚（进手张守恒，20260907 复盘8局实锤；与 evaluation.py / config.json 同步）
    "ls_struct_entry_pen": -60,
    "ls_land_small_bonus": 24,
    # TASK-C 农民 lead 三改（与 evaluation.py _DEFAULTS 保持同步）
    "ls_single_bias_mult": 0.4, "ls_gate_exempt_hands": 3, "ls_gate_exempt_big": 3,
    "cs_struct_len_bonus": 6, "cs_struct_len_cap": 36,
    "cs_kicker_a_pen": 25, "cs_kicker_k_pen": 15,
    "lt_triple_pen": -90, "ct_danger_cnt": 3,
    # BUG#2 counter 王牌节流独立参数（与 evaluation.py _DEFAULTS 保持同步）
    "cc_pen_joker": -70,
    # BUG#4 飞机带牌打分修正（与 evaluation.py / config.json 保持同步）
    "ap_bare_bonus": 25, "ap_single_bonus": 45, "ap_pair_bonus": 45,
    # 任务C 压队友两条件（20260905）：与 evaluation.py / config.json 保持同步
    "cp_partner_big_pen": -120,
    # 任务E 硬编码普查参数化（20260905）：与 evaluation.py / config.json 保持同步，默认值=原裸数字
    "cp_land_press_l1": 120, "cp_land_press_l2": 95, "cp_land_press_l3": 65,
    "cp_land_press_l4": 30, "cp_land_press_l5": 8,
    "cp_gate_bonus_le6": 30, "cp_gate_bonus_other": 14, "cp_gate_bonus_le2": 60,
    "cp_small_bonus": 8,
    "cp_partner_pen_l1": 70, "cp_partner_pen_l2": 35, "cp_partner_pen_l3": 8,
    "cp_partner_land_l1": 90, "cp_partner_land_l2": 42,
    "cp_partner_rank13_pen": 30, "cp_partner_rank15_pen": 20,
    "cp_finish_bonus": 140,
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
    # Q4·S2（20260906）：C1'送先跑接线 + 下家L=1必顶（与 evaluation.py / config.json 保持同步）
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
    # Q5（20260907 James Wu 拍板）：lead 手数最少化——相对账。同场景存在"走完总步数
    # 更少"的候选时，多走一步冤枉路罚 q5_hands_pen 分；步数相同（喂牌/收权等目的
    # 相同代价）零影响；赢牌出口恒为最小步数天然豁免；counter 域不进场。
    # 尺度=15：300局曲线 pen0/10/15/25/40 → 胜率49.7/53.0/52.7/54.0/56.0%，
    # 取档位拐点（15=疗效足且不过推；25把地主胜率顶出验收带被否）
    "c5_q5_enable": 1, "q5_hands_pen": 15
}
_PCFG = _CFG.get('params', {})
P = {k: _PCFG.get(k, v) for k, v in _DEFAULTS.items()}


# ==================== 辅助函数 ====================


# ==================== _last_player_for_ai ====================
def _last_player_for_ai(gs):
    """返回上一手出牌的玩家，无则 -1"""
    if gs.lastPlay and 'player' in gs.lastPlay:
        return gs.lastPlay['player']
    return -1


# ==================== 第一层：辅助/统计/评分函数 ====================


# ==================== count_ranks ====================
def count_ranks(cards):
    """
    统计各点数张数。
    返回 dict[rank -> count]
    """
    f = {}
    for c in cards:
        r = c['rank']
        f[r] = f.get(r, 0) + 1
    return f



# ==================== consecutive_runs ====================
def consecutive_runs(ranks, min_len):
    """
    找连续点数组合（顺子/连对）。
    ranks: 点数列表
    min_len: 最小连续长度
    返回 list[list[int]]，每个子列表是一段连续点数（仅含 <=14 的牌）
    """
    out = []
    a = sorted(set(r for r in ranks if r <= 14))
    run = []
    for r in a:
        if not run or r == run[-1] + 1:
            run.append(r)
        else:
            if len(run) >= min_len:
                out.append(list(run))
            run = [r]
    if len(run) >= min_len:
        out.append(list(run))
    return out



# ==================== remaining_map ====================
def remaining_map(gs):
    """
    记牌器：返回每种点数还剩多少张（未出现在任何人手中的）。
    初始：每种牌 4 张（王各 1 张），减去当前玩家手牌和所有已出牌。
    """
    rem = {}
    for r in range(3, 18):
        rem[r] = 1 if r >= 16 else 4
    # 减去当前玩家手牌
    for c in gs.hands[gs.current]:
        r = c['rank']
        if rem.get(r, 0) > 0:
            rem[r] -= 1
    # 减去所有已出牌
    played = gs.playedHands if gs.playedHands else [[], [], []]
    for p in range(3):
        for c in (played[p] if played[p] else []):
            r = c['rank']
            if rem.get(r, 0) > 0:
                rem[r] -= 1
    return rem



# ==================== player_distribution ====================


def player_distribution(gs):
    """
    概率记牌系统：返回每个对手持有每种牌的期望概率分布。
    返回 dict: {player_id: {rank: expected_count}}
    算法：从 remaining_map 获取剩余总张数，按手牌张数比例分配，
    用 playedHands 和 pass_streak 做修正。
    """
    rem = remaining_map(gs)
    played = gs.playedHands if gs.playedHands else [[], [], []]
    dist = {}
    
    # 收集所有对手的手牌张数
    opponents = []
    total_opponent_cards = 0
    for p in range(3):
        if p == gs.current:
            continue
        count = len(gs.hands[p]) if p < len(gs.hands) else 0
        opponents.append((p, count))
        total_opponent_cards += count
    
    if total_opponent_cards <= 0:
        return {p: {} for p, _ in opponents}
    
    for p, hand_count in opponents:
        dist[p] = {}
        for rank in range(3, 18):
            remaining = rem.get(rank, 0)
            if remaining <= 0:
                dist[p][rank] = 0
                continue
            
            # 基础比例：按手牌张数分配
            base = remaining * hand_count / total_opponent_cards
            
            # 修正：该玩家已出过几张此rank
            player_played = sum(1 for c in (played[p] or []) if c['rank'] == rank)
            # 已出牌说明之前持有，但现在手牌里没有
            # 如果已出牌多，说明这个人持有此牌的概率降低
            adjustment = 1.0 - (player_played / (remaining + player_played + 0.1)) * 0.3
            
            # 修正（任务B 20260905）：原用 ai_mem.pass_streak——线上无代码更新、
            # 恒 0 死数据；改用请求内 gs.passCount 近似：本轮连续多人过牌
            # 说明各家大牌普遍偏弱，对高 rank 概率打折。
            streak = getattr(gs, 'passCount', 0)
            if streak >= 2 and rank >= 13:
                # 连续过牌 + 高rank = 更可能没大牌
                adjustment *= 0.7
            
            dist[p][rank] = max(0, min(remaining, base * adjustment))
    
    return dist


def prob_in_hand(gs, player, rank):
    """
    返回对手 player 持有 rank 的概率 (0~1)。
    基于 player_distribution 计算。
    """
    dist = player_distribution(gs)
    if player not in dist:
        return 0
    expected = dist[player].get(rank, 0)
    # 转化为概率：expected_count / total_remaining_of_rank
    rem = remaining_map(gs)
    total = rem.get(rank, 0)
    if total <= 0:
        return 0
    return min(1.0, max(0.0, expected / total))


# ==================== big_cards_status ====================
# ==================== big_cards_status ====================
def big_cards_status(gs):
    """
    返回大牌剩余状态。
    返回 dict: {two, A, smallJoker, bigJoker}
    """
    rem = remaining_map(gs)
    return {
        'two': rem.get(15, 0),
        'A': rem.get(14, 0),
        'smallJoker': rem.get(16, 0),
        'bigJoker': rem.get(17, 0),
    }



# ==================== possible_bomb_threat ====================
def possible_bomb_threat(gs):
    """
    炸弹威胁数：记牌器中剩余 >=2 张且手牌中 >=2 张的点数数量。
    """
    rem = remaining_map(gs)
    freq = count_ranks(gs.hands[gs.current])
    threats = 0
    for r in range(3, 16):
        if rem.get(r, 0) >= 2 and freq.get(r, 0) >= 2:
            threats += 1
    return threats



# ==================== estimate_count_in ====================
def estimate_count_in(gs, player, rank):
    """
    推算玩家 player 手里 rank 的期望张数。
    使用概率分布系统 + 多因子加权修正。
    """
    try:
        # 优先使用概率分布系统
        dist = player_distribution(gs)
        if player in dist:
            expected = dist[player].get(rank, 0)
            if expected > 0:
                return max(0, min(4, expected))
        
        # 兜底：使用传统方法
        rem = remaining_map(gs)
        n = rem.get(rank, 0)
        if n <= 0:
            return 0

        land_count = gs.get_landlord_count()
        farm_count = gs.get_teammate_count(player)
        both = land_count + farm_count
        if both <= 0:
            return 0

        own = land_count if player == gs.landlord else farm_count
        base_ratio = n * own / both

        played = gs.playedHands if gs.playedHands else [[], [], []]
        played_count = [0, 0, 0]
        for q in range(3):
            played_count[q] = sum(1 for c in (played[q] or []) if c['rank'] == rank)
        total_played = played_count[0] + played_count[1] + played_count[2] + 0.1
        play_factor = 1 - played_count[player] / total_played

        est = n * (base_ratio * 0.5 + play_factor * 0.5)
        return max(0, min(4, est))
    except Exception:
        return 0



# ==================== probably_has ====================
def probably_has(gs, player, rank, threshold=0.5):
    """推算玩家是否大概率持有某点数"""
    return estimate_count_in(gs, player, rank) >= threshold



# ==================== estimate_pair_in ====================
def estimate_pair_in(gs, player, rank):
    """
    推算玩家 player 手里有对子的概率。
    使用概率分布系统 + 二项分布近似。
    返回 0~1 之间的浮点数。
    """
    try:
        # 如果能看到手牌，直接查
        own_freq = count_ranks(gs.hands[player] if player < len(gs.hands) else [])
        own_count = own_freq.get(rank, 0)
        if own_count >= 2:
            return 1

        # 用概率分布系统估算
        dist = player_distribution(gs)
        if player in dist:
            expected = dist[player].get(rank, 0)
            # 用泊松/二项近似：P(X>=2) ≈ 1 - P(X=0) - P(X=1)
            # lambda = expected
            import math
            lam = max(0.01, expected)
            p0 = math.exp(-lam)
            p1 = lam * math.exp(-lam)
            pair_prob = max(0, min(1, 1 - p0 - p1))
            return pair_prob
        
        # 兜底
        rem = remaining_map(gs)
        n = rem.get(rank, 0)
        if n < 2:
            return 0

        land_count = gs.get_landlord_count()
        farm_count = gs.get_teammate_count(player)
        both = land_count + farm_count
        if both <= 0:
            return 0

        own = land_count if player == gs.landlord else farm_count
        base_ratio = n / 2 * own / both
        est = min(1, base_ratio * 0.5 + 0.3)
        return max(0, est)
    except Exception:
        return 0



# ==================== estimate_triple_in ====================
def estimate_triple_in(gs, player, rank):
    """
    推算玩家 player 手里有三条的概率。
    返回 0~1 之间的浮点数。
    """
    try:
        rem = remaining_map(gs)
        n = rem.get(rank, 0)
        if n < 3:
            return 0

        other_farmer = -1
        for q in (PLAYER, LEFT, RIGHT):
            if q != gs.landlord and q != gs.current:
                other_farmer = q
                break

        land_count = gs.get_landlord_count()
        farm_count = gs.get_teammate_count(player)
        both = land_count + farm_count
        if both <= 0:
            return 0

        own = land_count if player == gs.landlord else farm_count
        own_freq = count_ranks(gs.hands[player] if player < len(gs.hands) else [])
        own_count = own_freq.get(rank, 0)
        if own_count >= 3:
            return 1

        base_ratio = n / 3 * own / both

        played = gs.playedHands if gs.playedHands else [[], [], []]
        played_count = [0, 0, 0]
        for q in range(3):
            played_count[q] = sum(1 for c in (played[q] or []) if c['rank'] == rank)
        total_played = played_count[0] + played_count[1] + played_count[2] + 0.1
        play_factor = 1 - played_count[player] / total_played

        est = min(1, base_ratio * 0.4 + play_factor * 0.3 + 0.3)
        return max(0, est)
    except Exception:
        return 0



# ==================== estimate_bomb_in ====================
def estimate_bomb_in(gs, player, rank):
    """
    推算玩家 player 手里有炸弹（四张同点）的概率。
    返回 0~1 之间的浮点数。
    """
    try:
        rem = remaining_map(gs)
        n = rem.get(rank, 0)
        if n < 4:
            return 0

        other_farmer = -1
        for q in (PLAYER, LEFT, RIGHT):
            if q != gs.landlord and q != gs.current:
                other_farmer = q
                break

        land_count = gs.get_landlord_count()
        farm_count = gs.get_teammate_count(player)
        both = land_count + farm_count
        if both <= 0:
            return 0

        own = land_count if player == gs.landlord else farm_count
        own_freq = count_ranks(gs.hands[player] if player < len(gs.hands) else [])
        own_count = own_freq.get(rank, 0)
        if own_count >= 4:
            return 1

        base_ratio = n / 4 * own / both

        played = gs.playedHands if gs.playedHands else [[], [], []]
        played_count = [0, 0, 0]
        for q in range(3):
            played_count[q] = sum(1 for c in (played[q] or []) if c['rank'] == rank)
        total_played = played_count[0] + played_count[1] + played_count[2] + 0.1
        play_factor = 1 - played_count[player] / total_played

        bomb_tendency = 1.2 if rank >= 15 else 0.8
        est = min(1, (base_ratio * 0.4 + play_factor * 0.3 + 0.3) * bomb_tendency)
        return max(0, est)
    except Exception:
        return 0



# ==================== estimate_straight_in ====================
def estimate_straight_in(gs, player, start, length):
    """
    推算玩家 player 手里有从 start 开始长度 length 的顺子的概率。
    返回 0~1 之间的浮点数。
    """
    try:
        min_prob = 1.0
        for i in range(length):
            prob = estimate_count_in(gs, player, start + i)
            if prob < 0.3:
                return 0
            min_prob = min(min_prob, prob)
        return min_prob
    except Exception:
        return 0



# ==================== split_penalty ====================
def split_penalty(cards, freq, hand_size=13):
    """
    拆牌罚分（精细化版本）。
    cards: 本次出的牌
    freq: 当前手牌的点数统计 {rank: count}
    hand_size: 当前手牌张数（用于判断游戏阶段）
    返回罚分（整数）
    """
    # 统计本次用了多少张各点数
    used = {}
    for c in cards:
        r = c['rank']
        used[r] = used.get(r, 0) + 1

    # 牌值权重：高值牌拆牌代价更大
    rank_weight = {
        3: P['sp_rank_weight_3'], 4: P['sp_rank_weight_4'], 5: P['sp_rank_weight_5'],
        6: P['sp_rank_weight_6'], 7: P['sp_rank_weight_7'], 8: P['sp_rank_weight_8'],
        9: P['sp_rank_weight_9'], 10: P['sp_rank_weight_10'], 11: P['sp_rank_weight_11'],
        12: P['sp_rank_weight_12'], 13: P['sp_rank_weight_13'], 14: P['sp_rank_weight_14'],
        15: P['sp_rank_weight_15'],  # 2
        16: P['sp_rank_weight_16'],  # 小王
        17: P['sp_rank_weight_17']   # 大王
    }

    # 游戏阶段因子：残局拆牌更亏
    if hand_size >= 10:
        stage_factor = P['sp_stage_early']   # 早期：手牌多，拆一拆无所谓
    elif hand_size >= 5:
        stage_factor = P['sp_stage_mid']   # 中期：标准
    else:
        stage_factor = P['sp_stage_late']   # 残局：手牌少，拆牌代价大

    p = 0
    for r, n_used in used.items():
        n = freq.get(r, 0)
        w = rank_weight.get(r, 1.0)

        # 拆四张（炸弹）
        if n >= 4 and n_used < 4:
            p += int(P['sp_pen_bomb'] * w * stage_factor)

        # 拆王（王的特殊处理）
        if r in (16, 17) and n > n_used:
            p += int(P['sp_pen_two'] * w * stage_factor)

        # 拆三条
        if n == 3 and n_used < 3:
            p += int(P['sp_pen_triple'] * w * stage_factor)

        # 拆对子
        if n == 2 and n_used < 2:
            p += int(P['sp_pen_pair'] * w * stage_factor)

    # 拆死顺子罚分（TASK-B）。判定基准=「这手牌打完后，全手还在不在 ≥5 连」，
    # 而非「出的这张碰没碰顺子成员」。三条件：孤张 + 属某条 ≥5 连(仅 3~A) +
    # 出完全手无 ≥5 连。整条顺子作为结构一起打出属正常消耗，不算拆散（该连的
    # 成员已全部离场则豁免）。不设残局豁免：stage_factor 已让残局拆牌罚得更重，
    # 且反例用例（5 张手牌拆断腰）在 ≤6 豁免下必失败——提示词该句与用例自相
    # 矛盾，执行时按单测口径去掉豁免（2026-09-04 交付报告披露）。
    if P.get('sp_pen_run', 0):
        runs_before = consecutive_runs([r for r in freq if freq[r] > 0], 5)
        if runs_before:
            after = {r: (freq.get(r, 0) - n_used) for r, n_used in used.items()}
            for r in freq:
                if freq[r] > 0 and r not in used:
                    after[r] = freq[r]
            after_ranks = [r for r in after if after[r] > 0]
            if not consecutive_runs(after_ranks, 5):  # 出完后已无任何五连
                for r, n_used in used.items():
                    if n_used != 1 or freq.get(r, 0) != 1 or not (3 <= r <= 14):
                        continue  # 非孤张 / 王与2 不参与顺子 → 不罚
                    if not any(r in run for run in runs_before):
                        continue  # 该张本就不在任何五连里
                    members = set().union(*[set(run) for run in runs_before if r in run])
                    if not (members & set(after_ranks)):
                        continue  # 相关顺子成员已整条打出（正常消耗），豁免
                    p += int(P['sp_pen_run'] * rank_weight.get(r, 1.0) * stage_factor)

    return p



# ==================== kicker_waste ====================
def kicker_waste(cards, pattern, is_counter):
    """
    配件浪费罚分。
    cards: 本次出的牌
    pattern: 牌型 dict {type, main, len}
    is_counter: 是否跟牌（压牌），跟牌时罚分减半
    返回罚分（int）
    """
    freq = {}
    for c in cards:
        r = c['rank']
        freq[r] = freq.get(r, 0) + 1

    main_r = int(pattern['main'])
    waste = 0
    mult = P['kw_counter_mult'] if is_counter else P['kw_lead_mult']

    def add(r, n):
        nonlocal waste
        if n <= 0:
            return
        if r == 17:
            waste += int(n * P['kw_rank_17'] * mult)
        elif r == 16:
            waste += int(n * P['kw_rank_16'] * mult)
        elif r == 15:
            waste += int(n * P['kw_rank_15'] * mult)
        elif r == 14:
            waste += int(n * P['kw_rank_14'] * mult)
        elif r == 13:
            waste += int(n * P['kw_rank_13'] * mult)
        elif r == 12:
            waste += int(n * P['kw_rank_12'] * mult)

    ptype = pattern['type']
    for r, n in freq.items():
        payload = 0
        if ptype in ('TRIPLE_ONE', 'TRIPLE_TWO'):
            payload = 3 if r == main_r else 0
        elif ptype == 'FOUR_TWO':
            payload = 4 if r == main_r else 0
        elif ptype in ('AIRPLANE_SINGLE', 'AIRPLANE_PAIR'):
            plen = pattern.get('len', 0)
            payload = 3 if (r >= main_r and r < main_r + plen) else 0
        else:
            payload = n
        add(r, n - payload)

    return waste



# ==================== hand_shape ====================
def hand_shape(cards):
    """
    手牌结构分析。
    返回 dict: {groups, singles, pairs, bombs}
    """
    freq = count_ranks(cards)
    ranks = list(freq.keys())
    groups = 0
    for r in ranks:
        if freq[r] in (2, 3, 4):
            groups += 1
    singles = sum(1 for r in ranks if freq[r] == 1)
    pairs = sum(1 for r in ranks if freq[r] == 2)
    bombs = sum(1 for r in ranks if freq[r] == 4)
    return {'groups': groups, 'singles': singles, 'pairs': pairs, 'bombs': bombs}



# ==================== big_value ====================
def pattern_main_ge15(x):
    """TASK-G 小节4：判定炸弹候选主牌是否为 2（main>=15，即大炸）。"""
    return (x.get('pattern') or {}).get('main', 0) >= 15


def big_value(gs, x, hand, who, last, mode):
    """
    炸弹价值评分。
    x: 候选出牌 dict {cards: list, pattern: dict}
    hand: 当前手牌
    who: 当前玩家编号
    last: 上一手牌 pattern dict
    mode: 'counter' 或 'lead'
    返回整数评分
    """
    if x['pattern']['type'] not in ('BOMB', 'ROCKET'):
        return 0

    from ai.evaluation import estimate_hands  # 局部import：防模块级循环（同 evaluate_hand 惯例）

    role = gs.get_role(who)
    after = [c for c in hand if not any(y['id'] == c['id'] for y in x['cards'])]
    landlord_count = gs.get_landlord_count()
    partner = gs.get_partner(who)
    partner_count = gs.get_teammate_count(who) if partner >= 0 else 99
    last_player = _last_player_for_ai(gs)

    if not after:
        return P['bv_finish']

    # counter 模式：压地主的牌
    if mode == 'counter' and role != 'landlord' and last_player == gs.landlord:
        # TASK-G 小节4（20260906 James Wu 拍板）：大炸(2222)/王炸非必胜不扔——
        # 地主未到危机线(>bb_crisis_threat)且炸完不能两脚内走完 → 重罚（宁可拆成
        # 普通牌用）。小/中炸维持原打分，尺度由 BOMB 桶学习随真实局纠正。
        # 终结豁免：炸完直接赢（上面 not after 已 +bv_finish 返回，进不到这）。
        if (x['pattern']['type'] == 'ROCKET' or
                (x['pattern']['type'] == 'BOMB' and pattern_main_ge15(x))):
            if landlord_count > P['bb_crisis_threat'] and \
                    estimate_hands(after) > P['bb_finish_hands']:
                return P['bb_big_bomb_pen']
        if landlord_count <= 3:
            return P['bv_c_land_le3']
        if landlord_count <= 6:
            return P['bv_c_land_le6']
        if last and last['type'] == 'BOMB' and x['pattern']['type'] == 'BOMB':
            return P['bv_c_bomb']
        return P['bv_c_else']

    # counter 模式：压队友的牌
    if mode == 'counter' and role != 'landlord' and last_player == partner:
        return P['bv_c_part_le3'] if partner_count <= 3 else P['bv_c_part_else']

    # counter 模式：地主角色
    if mode == 'counter' and role == 'landlord':
        threat = gs.get_teammate_count(gs.current)
        if threat <= 3:
            return P['bv_c_land_threat_le3']
        if last and last['type'] == 'BOMB':
            return P['bv_c_land_bomb']
        return P['bv_c_land_else']

    # TASK-G 小节4：农民主动甩大炸/王炸——非两脚内走完不甩（同上口径，仅农民）
    if role != 'landlord' and (x['pattern']['type'] == 'ROCKET' or
            (x['pattern']['type'] == 'BOMB' and pattern_main_ge15(x))):
        if estimate_hands(after) > P['bb_finish_hands']:
            return P['bb_big_bomb_pen']

    # 农民方且地主牌少
    if role != 'landlord' and landlord_count <= 3:
        return P['bv_farmer_land_le3']

    if len(hand) <= 6:
        return P['bv_hand_le6']
    return P['bv_hand_else']



# ==================== control_tradeoff ====================
def control_tradeoff(gs, x, hand, who, last, mode):
    """
    控制与反击权衡。
    只在 counter 模式下有效。
    返回整数评分调整。
    """
    if mode != 'counter' or not last:
        return 0

    role = gs.get_role(who)
    lp = _last_player_for_ai(gs)
    freq = count_ranks(hand)

    if (role == 'landlord' or lp != gs.landlord or
            last['main'] < 13):
        return 0

    # 非单张类型（对子、三条等）反击力度 ×1.2
    type_factor = P['ct_type_non_single'] if last['type'] != 'SINGLE' else P['ct_type_single']

    landlord_count = gs.get_landlord_count()
    has_pair_two = freq.get(15, 0) >= 2
    has_joker = freq.get(16, 0) > 0 or freq.get(17, 0) > 0

    if not has_pair_two or not has_joker:
        return 0

    main = x['pattern']['main']
    if main == 15:
        if landlord_count <= 5:
            return int(P['ct_main15_le5'] * type_factor)
        elif landlord_count <= 8:
            return int(P['ct_main15_le8'] * type_factor)
        else:
            return P['ct_main15_else']
    if main == 16 or main == 17:
        if landlord_count > 8:
            return int(P['ct_main16_17_gt8'] * type_factor)
        elif landlord_count <= 3:
            return int(P['ct_main16_17_le3'] * type_factor)
        else:
            return P['ct_main16_17_else']
    return 0


# ==================== 第三层：学习修正函数 ====================


# ==================== vm_counter_vs_landlord（TASK-G 小节2, 20260906） ====================
# 价值匹配引擎：地主出牌时农民跟牌"要不要"的唯一入口。
# 取代旧「省大牌」L901 / Lv4 / Lv4.5 / Lv5 / Lv5.5 / Lv8（James Wu 拍板：
# 首要目标=不让地主无缘无故拿牌权；接牌挑跳档最小最便宜的；要不起就是
# 要不起，不猜队友；地主牌少先顶、牌多可放一轮）。
# 返回 True=让牌；False=压牌。具体压哪张由 score_candidates 在候选内选
# （花色/最小拆损）——本引擎只裁"要不要+跳档档位"，不越权选牌。
def vm_counter_vs_landlord(gs, hand, last, who, candidates):
    role = gs.get_role(who)
    L = gs.get_landlord_count()
    danger = (L <= P['vm_danger_count'])

    if last['type'] == 'SINGLE':
        legal = [x for x in candidates
                 if x['pattern']['type'] == 'SINGLE' and x['pattern']['main'] > last['main']]
        jumpf = lambda x: x['pattern']['main'] - last['main']
        capjump = lambda cap: cap
    elif last['type'] == 'PAIR':
        legal = [x for x in candidates
                 if x['pattern']['type'] == 'PAIR' and x['pattern']['main'] > last['main']]
        # TASK-I-Q3甲（20260906 James Wu 拍板）：对子跳档与单张同尺，删除旧×2折算
        # （旧口径给对子一倍宽限，门板对6→对9被算成6档>门槛4而放过，实测27次/500局
        #  "该顶不顶"。首要目标=不让地主拿牌权，4档门槛拍板时未区分单双对。）
        jumpf = lambda x: x['pattern']['main'] - last['main']
        capjump = lambda cap: cap
    else:
        return False   # 结构型跟牌不进价值匹配域，维持原打分链路

    if not legal:
        return not danger   # 只剩炸弹能压：非危机线让（炸留给打分域）

    minjump = min(jumpf(x) for x in legal)
    cap = P['vm_jump_next'] if role == 'farmerNext' else P['vm_jump_gate']
    tier = minjump if minjump <= cap else cap + 1
    if danger:
        tier = 0   # 地主牌少：必须顶，零门槛

    if role == 'farmerNext':
        # 下家：有便宜牌（跳档在门槛内）就顺手压；否则放，留给门板兜底
        res = not any(jumpf(x) <= capjump(cap) for x in legal)
        # Q4·S2 C1'规则1"能接就接"（20260906 James Wu 拍板，vm_next_must_top_L1）：
        # 地主只剩最后1张，本轮放过去=让他随便走完。凡有可压候选必压（超档也压），
        # 堵 g59 同源病根：下家分支原先只读 vm_jump_next 不看张数，L=1 漏放=白走。
        if (res and P['vm_next_must_top_L1'] and L == 1):
            res = False
    else:
        # 门板：档位内必顶；超档只在地主牌多时可放一轮（PASS桶可见，bias可否决）
        res = tier > cap and not danger

    # （'只剩炸弹'出口在上方已 early-return，不经 bias 否决——强制炸违炸纪律）
    # === Q4·S4.8 对 S4.5 的分域接管（20260907）===
    # 门板(farmerPrev)放出口：旧块已物理删除，由 engine ai_gate_decision 的
    #   gate_top_cost auto 重判接管（区内三本账/区外seal兜底），此处不留分支
    #   ——防新旧并存打架。
    # 下家(farmerNext)：三件套"能压必压"seal通道原样保留（E3 bless锁），
    #   下家不装成本模型（James Wu 拍板：门板没有顶队友动作，下家管跑得快）。
    if (res and role == 'farmerNext' and P['vm_card_counter']
            and last['type'] == 'SINGLE'):
        try:
            from ai.partner_model import landlord_beat_prob
            _sm = min(x['pattern']['main'] for x in legal)   # 最便宜的能压牌
            if landlord_beat_prob(gs, who, 'SINGLE', _sm) <= P['s4_seal_max_p']:
                res = False
        except Exception:
            pass
    # === TASK-G 小节5（20260906）：学习否决——判'过'时听 beat/pass 双桶 bias ===
    # pb_override=99 出厂关（bias 钳制±20 够不到）；启用=真实局 beat 数据攒够后
    # 把 config 的 pb_override 调到 5~8（James Wu 三步流程，不碰代码）。
    # 只否决'让牌'，且在本函数（地主分支）内——队友域物理隔绝，永不受此影响。
    if res:
        try:
            from ai.learning import _learn_pass_bias
            _bias = _learn_pass_bias(role, L)
            if _bias >= P['pb_override']:
                res = False   # 数据证明这种局面让牌赢率低 → 强制顶（出哪张仍按价值匹配）
        except Exception:
            pass
    return res


# ==================== ai_should_pass_counter ====================
def ai_should_pass_counter(gs, hand, last, who, candidates):
    """
    判断是否应该让牌（不出）。
    返回 True 表示应该让牌（pass），False 表示应该出牌。
    """
    role = gs.get_role(who)
    partner = gs.get_partner(who)
    lp = _last_player_for_ai(gs)
    landlord_count = gs.get_landlord_count()
    partner_count = gs.get_teammate_count(who) if partner >= 0 else 99

    other_farmer = -1
    if role != 'landlord':
        for p in (PLAYER, LEFT, RIGHT):
            if p != who and p != gs.landlord:
                other_farmer = p
                break

    partner_play = (role != 'landlord' and lp == partner)
    dangerous_landlord = (landlord_count <= 3)

    # ============================================================
    # 让牌三原则（优先级从高到低）:
    # 1. 位置原则：地主上家(farmerPrev)是"门板"，必须挡住地主出牌节奏
    #              地主下家(farmerNext)是"辅助"，只在效率高时压牌
    # 2. 牌型原则：同类型牌优先压（如对压对），不同类型牌慎重（如单压对）
    #              顺子/连对等多张结构牌优先压（打出节奏差）
    # 3. 代价原则：拆牌代价高（split_penalty>30）时让牌
    #              代价低（split_penalty<10）时压牌
    # ============================================================

    # [修复Lv0] 删除原来的无条件 partner_play→return True
    # 队友出牌时的让牌/接力/配合逻辑已在下方 Lv3~Lv7 中处理
    # 函数末尾有 partner_play 默认 PASS 兜底

    # 地主专属策略：激进控制 + 冲刺
    if role == 'landlord':
        freq = count_ranks(hand)
        # 冲刺模式：手牌<=6张，几乎不放过任何出牌机会
        if len(hand) <= 6:
            return False
        # 控制模式：手牌>6张
        # 如果对手快出完了(<=3张)，必须压
        farmer_min = min((len(gs.hands[p]) for p in range(3) 
                         if p != who and len(gs.hands[p]) > 0), default=99)
        if farmer_min <= 3:
            return False
        # 常规：有正常牌就出，没有就让
        normal = [x for x in candidates
                  if x['pattern']['type'] not in ('BOMB', 'ROCKET') and
                  x['pattern']['main'] <= 14 and
                  split_penalty(x['cards'], freq, len(hand)) < 25]
        threat = gs.get_teammate_count(gs.current)
        if not normal and threat > 3:
            return True
        return False

    can_finish_all = any(len(x['cards']) == len(hand) for x in candidates)
    freq = count_ranks(hand)

    def is_big(x):
        return (x['pattern']['type'] in ('BOMB', 'ROCKET') or
                any(c['rank'] >= 15 for c in x['cards']))

    can_use_mid = any(not is_big(x) for x in candidates)
    all_top = all(is_big(x) for x in candidates)

    # Lv1: can finish all in one play
    if can_finish_all:
        return False

    # Lv1.5: 放水送队友
    if (lp == gs.landlord and role == 'farmerNext' and partner_count <= 2):
        if partner_count == 1 and last['type'] == 'SINGLE':
            catch_p = 0
            for r in range(last['main'] + 1, 18):
                catch_p += estimate_count_in(gs, partner, r)
            if catch_p >= 0.8:
                return True
        elif partner_count == 2 and last['type'] == 'SINGLE' and last['main'] <= 8:
            return True

    # Lv2: 地主快走完(≤2张)必须压死——仅当地主出牌时（与旧版JS一致，队友出牌不触发，保护配合）
    if lp == gs.landlord and role != 'landlord' and landlord_count <= 3:
        return False

    # === vm 价值匹配引擎（TASK-G 小节2, 20260906 James Wu 拍板）===
    # 地主出牌时的顶/让唯一裁决：取代旧「省大牌」/Lv4/Lv4.5/Lv5/Lv5.5/Lv8。
    # Lv1/Lv1.5/Lv2（一把走完/放水/危机<=3必压）保留在前。结构型跟牌 vm 直通打分链路。
    if lp == gs.landlord:
        return vm_counter_vs_landlord(gs, hand, last, who, candidates)

    # Lv3: partner <=1 card
    if partner_play and partner_count <= 1:
        return True

    # Lv3.4: 上家接力（仅在队友出"小单张/小对子"这类能互相顺牌的型时接力，帮队友控牌）
    # 修复：只对 SINGLE/PAIR 小牌接力；若队友出的是顺子/连对/飞机等多张结构牌，不该压队友
    #（那是"农民压队友/抢领出"，会互相消耗）。接力仅当队友手牌还多、地主牌多时才做。
    if (partner_play and role == 'farmerPrev' and
            last['type'] in ('SINGLE', 'PAIR') and
            last['main'] <= 8 and landlord_count > 5 and
            partner_count > 4 and not can_finish_all):
        return False

    # Lv3.5: 队友出牌且地主牌还多（排除 Lv3.4 已处理的上家接力场景，避免规则冲突）
    if partner_play and not can_finish_all and landlord_count > 5:
        if not (role == 'farmerPrev' and last['type'] in ('SINGLE', 'PAIR') and
                last['main'] <= 8 and partner_count > 4):
            return True

    # Lv3.6: 队友快出完且地主未到危险线
    if partner_play and not can_finish_all and partner_count <= 4 and landlord_count > 3:
        return True

    # Lv6: partner played big card, mid cards available
    if partner_play and last['main'] >= 13:
        if can_use_mid:
            return False
        if all_top:
            return True

    # Lv7: partner close to finish, only top cards
    if partner_play and partner_count <= 6 and landlord_count > 5 and all_top:
        return True

    # bomb takeover
    if partner_play and last['type'] not in ('BOMB', 'ROCKET'):
        bomb_cands = [x for x in candidates if x['pattern']['type'] in ('BOMB', 'ROCKET')]
        win_after_bomb = any((len(hand) - len(x['cards'])) <= 3 for x in bomb_cands)
        partner_can_win = partner_count <= 2 and last['main'] <= 12
        if win_after_bomb and not partner_can_win and landlord_count <= 5:
            return False

    # Hard rule: never bomb partner unless can finish immediately
    if partner_play:
        has_bomb = any(x['pattern']['type'] in ('BOMB', 'ROCKET') for x in candidates)
        if has_bomb:
            bomb_finish = any((x['pattern']['type'] in ('BOMB', 'ROCKET') and
                               (len(hand) - len(x['cards'])) <= 1)
                              for x in candidates)
            if not bomb_finish:
                return True

    # Special: both partner and landlord close to finish
    if partner_play and partner_count <= 3 and landlord_count <= 3:
        return False

    # farmerNext take back when partner led medium cards and landlord passed
    # 任务B（20260905）接风渡牌：原用 pass_streak[landlord]>0（恒 0 永不触发）
    # → 改请求字段组合：last 是队友领出（lp==partner）且地主本轮已 pass 过
    # （passCount>=1；地主 pass 后轮到 farmerNext 决策时正是此状态）。
    if (role == 'farmerNext' and partner >= 0 and lp == partner and
            last is not None and getattr(gs, 'passCount', 0) >= 1):
        if 7 <= last['main'] <= 11:
            has_mid = any(x['pattern']['type'] not in ('BOMB', 'ROCKET') and
                          7 <= x['pattern']['main'] <= 11
                          for x in candidates)
            if has_mid:
                return False

    # [修复Lv0] 队友出牌默认让牌（兜底）
    # 如果上面所有 partner_play 规则都没匹配到，默认 PASS
    if partner_play:
        return True

    # TASK-G 小节5（20260906）：原"死尾bias"已迁入 vm_counter_vs_landlord 内部
    # （地主分支判'过'时经 pb_override 否决）。此处不再重复——旧块位于所有硬规则
    # return 之后，历史上从未送达决策（断点B2），保留只会误导后续维护者。

    # Default: play normally
    return False


# ==================== 第六层：最优出牌选择函数 ====================

