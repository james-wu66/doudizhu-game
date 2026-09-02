"""
斗地主 AI 引擎 - 底层辅助函数

从前端 index.html 的 JS AI 函数等价翻译。
所有函数的第一个参数是 gs: GameState（替代 JS 全局 G）。
card 对象格式: {'id': int, 'rank': int, 'suit': int}
pattern 对象格式: {'type': str, 'main': int, 'len': int}
"""

import json
from ai_state import GameState, PLAYER, LEFT, RIGHT

# AI 记忆状态（AI_MEMORY）
class AIMemory:
    round_token = ''
    patterns = [{}, {}, {}]
    pass_streak = [0, 0, 0]
    pass_total = [0, 0, 0]
    last_play_key = ''
    played_types = [[], [], []]
    _learn = {'base': {}, 'buckets': {}}

    @classmethod
    def reset(cls, round_token=''):
        """开局重置：ai_mem 是全局单例（多用户共享），新一局必须清空过牌计数等状态"""
        cls.round_token = round_token or ''
        cls.patterns = [{}, {}, {}]
        cls.pass_streak = [0, 0, 0]
        cls.pass_total = [0, 0, 0]
        cls.last_play_key = ''
        cls.played_types = [[], [], []]

ai_mem = AIMemory()

# 学习数据（简化，替代前端 LEARN 全局变量）
_learn = {
    'loaded': True,
    'step': 0,
    'base': {},
    'buckets': {},
}


# ==================== 牌型检测与辅助函数 ====================

def detect_pattern(cards):
    """
    判断牌型。
    返回 dict: {'type': str, 'main': int, 'len': int}
    """
    if not cards:
        return None
    
    freq = {}
    for c in cards:
        r = c['rank']
        freq[r] = freq.get(r, 0) + 1
    
    ranks = sorted(freq.keys())
    n = len(cards)
    
    # 火箭：大小王
    if n == 2 and 16 in freq and 17 in freq:
        return {'type': 'ROCKET', 'main': 17, 'len': 2}
    
    # 炸弹：四张同点
    if n == 4 and len(freq) == 1 and list(freq.values())[0] == 4:
        r = list(freq.keys())[0]
        return {'type': 'BOMB', 'main': r, 'len': 4}
    
    # 单张
    if n == 1:
        r = list(freq.keys())[0]
        return {'type': 'SINGLE', 'main': r, 'len': 1}
    
    # 对子
    if n == 2 and len(freq) == 1:
        r = list(freq.keys())[0]
        return {'type': 'PAIR', 'main': r, 'len': 2}
    
    # 三条
    if n == 3 and len(freq) == 1:
        r = list(freq.keys())[0]
        return {'type': 'TRIPLE', 'main': r, 'len': 3}
    
    # 三带一
    if n == 4 and len(freq) == 2:
        for r, cnt in freq.items():
            if cnt == 3:
                return {'type': 'TRIPLE_ONE', 'main': r, 'len': 4}
    
    # 三带二
    if n == 5 and len(freq) == 2:
        for r, cnt in freq.items():
            if cnt == 3:
                other_r = [k for k in freq.keys() if k != r][0]
                if freq[other_r] == 2:
                    return {'type': 'TRIPLE_TWO', 'main': r, 'len': 5}
    
    # 顺子：5张及以上连续单牌，不含2和王
    if n >= 5 and all(cnt == 1 for cnt in freq.values()):
        if all(3 <= r <= 14 for r in ranks):
            if ranks == list(range(ranks[0], ranks[0] + n)):
                return {'type': 'STRAIGHT', 'main': ranks[0], 'len': n}
    
    # 连对：3对及以上连续对子
    if n >= 6 and n % 2 == 0:
        if all(cnt == 2 for cnt in freq.values()):
            if all(3 <= r <= 14 for r in ranks):
                if ranks == list(range(ranks[0], ranks[0] + len(ranks))):
                    return {'type': 'STRAIGHT_PAIR', 'main': ranks[0], 'len': len(ranks)}
    
    # 飞机相关
    triples = [r for r, cnt in freq.items() if cnt == 3]
    triples.sort()
    
    if len(triples) >= 2:
        if all(3 <= r <= 14 for r in triples):
            if triples == list(range(triples[0], triples[0] + len(triples))):
                total = len(cards)
                if total == 3 * len(triples):
                    return {'type': 'AIRPLANE', 'main': triples[0], 'len': len(triples)}
                elif total == 4 * len(triples):
                    other = [r for r, cnt in freq.items() if r not in triples]
                    if len(other) == len(triples):
                        if all(freq[r] == 1 for r in other):
                            return {'type': 'AIRPLANE_SINGLE', 'main': triples[0], 'len': len(triples)}
                elif total == 5 * len(triples):
                    other = [r for r, cnt in freq.items() if r not in triples]
                    if len(other) == len(triples):
                        if all(freq[r] == 2 for r in other):
                            return {'type': 'AIRPLANE_PAIR', 'main': triples[0], 'len': len(triples)}
    
    # 四带二（单）
    if n == 6:
        for r, cnt in freq.items():
            if cnt == 4:
                other = [k for k, v in freq.items() if k != r]
                if len(other) == 2 and all(freq[k] == 1 for k in other):
                    return {'type': 'FOUR_TWO', 'main': r, 'len': 6}
    
    # 四带二（对）
    if n == 8:
        for r, cnt in freq.items():
            if cnt == 4:
                other = [k for k, v in freq.items() if k != r]
                if len(other) == 2 and all(freq[k] == 2 for k in other):
                    return {'type': 'FOUR_TWO', 'main': r, 'len': 8}
    
    return None


def ai_add(out, seen, cards):
    """将候选牌组添加到候选列表（去重）"""
    if not cards:
        return
    # 用 card id 的 tuple 做去重 key
    key = tuple(sorted(c['id'] for c in cards))
    if key not in seen:
        seen.add(key)
        pattern = detect_pattern(cards)
        if pattern:
            out.append({'cards': cards, 'pattern': pattern})

def ai_candidates(hand):
    """候选出牌生成（从 JS 版翻译）"""
    out = []
    seen = set()
    freq = count_ranks(hand)
    ranks = sorted(freq.keys())
    
    def cards_of(r, n):
        """返回 hand 中 rank=r 的前 n 张牌"""
        result = []
        for c in hand:
            if c['rank'] == r and len(result) < n:
                result.append(c)
        return result
    
    def other_ranks(used):
        """返回 ranks 中不在 used 的 rank"""
        return [r for r in ranks if r not in used]
    
    # 单张、对子、三条、炸弹
    for r in ranks:
        ai_add(out, seen, cards_of(r, 1))
        if freq[r] >= 2:
            ai_add(out, seen, cards_of(r, 2))
        if freq[r] >= 3:
            ai_add(out, seen, cards_of(r, 3))
        if freq[r] == 4:
            ai_add(out, seen, cards_of(r, 4))
    
    # 火箭
    if freq.get(16, 0) and freq.get(17, 0):
        ai_add(out, seen, [c for c in hand if c['rank'] >= 16])
    
    # 顺子：5张及以上连续单牌
    for s in range(3, 15):
        for length in range(5, 15):
            if s + length - 1 > 14:
                break
            rs = list(range(s, s + length))
            if all(freq.get(r, 0) >= 1 for r in rs):
                cards = []
                for r in rs:
                    cards.extend(cards_of(r, 1))
                ai_add(out, seen, cards)
    
    # 连对：3对及以上连续对子
    for s in range(3, 15):
        for length in range(3, 15):
            if s + length - 1 > 14:
                break
            rs = list(range(s, s + length))
            if all(freq.get(r, 0) >= 2 for r in rs):
                cards = []
                for r in rs:
                    cards.extend(cards_of(r, 2))
                ai_add(out, seen, cards)
    
    # 三带一/三带二
    for r in ranks:
        if freq[r] < 3:
            continue
        for k in other_ranks([r]):
            # 三带一
            ai_add(out, seen, cards_of(r, 3) + cards_of(k, 1))
            # 三带二
            if freq[k] >= 2:
                ai_add(out, seen, cards_of(r, 3) + cards_of(k, 2))
    
    # 四带二（单/对）
    for r in ranks:
        if freq[r] != 4:
            continue
        others = other_ranks([r])
        # 四带二单
        for i in range(len(others)):
            for j in range(i+1, len(others)):
                cards1 = cards_of(others[i], 1)
                cards2 = cards_of(others[j], 1)
                if cards1 and cards2:
                    ai_add(out, seen, cards_of(r, 4) + cards1 + cards2)
        # 四带二对
        pairs = [x for x in others if freq[x] >= 2]
        for i in range(len(pairs)):
            for j in range(i+1, len(pairs)):
                ai_add(out, seen, cards_of(r, 4) + cards_of(pairs[i], 2) + cards_of(pairs[j], 2))
    
    # 飞机（连续三条 + 带单/带对）
    for s in range(3, 15):
        for length in range(2, 15):
            if s + length - 1 > 14:
                break
            rs = list(range(s, s + length))
            if all(freq.get(r, 0) >= 3 for r in rs):
                core = []
                for r in rs:
                    core.extend(cards_of(r, 3))
                others = other_ranks(rs)
                # 纯飞机
                ai_add(out, seen, core)
                # 飞机带单
                if len(others) >= length:
                    ai_add(out, seen, core + [cards_of(r, 1)[0] for r in others[:length]])
                # 飞机带对
                pairs = [r for r in others if freq[r] >= 2]
                if len(pairs) >= length:
                    cards = core[:]
                    for r in pairs[:length]:
                        cards.extend(cards_of(r, 2))
                    ai_add(out, seen, cards)
    
    return out


def ai_can_beat(x, last):
    """判断 x 能否压过 last（标准斗地主牌型比较）"""
    if not last:
        return True  # 没有上家牌，可以出
    
    pattern = x['pattern']
    if not pattern:
        return False
    
    # 火箭压一切
    if pattern['type'] == 'ROCKET':
        return True
    if last['type'] == 'ROCKET':
        return False
    
    # 炸弹压一切非火箭
    if pattern['type'] == 'BOMB':
        if last['type'] == 'BOMB':
            return pattern['main'] > last['main']
        return True
    if last['type'] == 'BOMB':
        return False
    
    # 同类型同长度比较
    if pattern['type'] == last['type'] and pattern['len'] == last['len']:
        return pattern['main'] > last['main']
    
    return False


# ==================== 辅助工具函数 ====================

def _last_player_for_ai(gs):
    """返回上一手出牌的玩家，无则 -1"""
    if gs.lastPlay and 'player' in gs.lastPlay:
        return gs.lastPlay['player']
    return -1


# ==================== 第一层：辅助/统计/评分函数 ====================

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


def estimate_count_in(gs, player, rank):
    """
    推算玩家 player 手里 rank 的期望张数。
    多因子加权：基础比例(0.4) + 出牌数量(0.3) + 出牌时机(0.2) + 牌型关联(0.1)
    """
    try:
        rem = remaining_map(gs)
        n = rem.get(rank, 0)
        if n <= 0:
            return 0

        # 找到另一个农民
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
        base_ratio = n * own / both

        played = gs.playedHands if gs.playedHands else [[], [], []]
        played_count = [0, 0, 0]
        for q in range(3):
            played_count[q] = sum(1 for c in (played[q] or []) if c['rank'] == rank)
        total_played = played_count[0] + played_count[1] + played_count[2] + 0.1
        play_factor = 1 - played_count[player] / total_played

        step = _learn.get('step', 0)
        if step <= 5:
            timing_factor = 0.8
        elif step <= 15:
            timing_factor = 0.9
        else:
            timing_factor = 0.95

        # 牌型关联因子
        combo_factor = 1
        landlord_played = played[gs.landlord] if gs.landlord >= 0 else []
        farmer_played = played[other_farmer] if other_farmer >= 0 else []
        land_triple = 0.7 if sum(1 for c in landlord_played if c['rank'] == rank) >= 3 else 1
        farm_triple = 0.7 if sum(1 for c in farmer_played if c['rank'] == rank) >= 3 else 1
        combo_factor = land_triple if player == gs.landlord else farm_triple

        est = n * (base_ratio * 0.4 + play_factor * 0.3 + timing_factor * 0.2 + combo_factor * 0.1)
        return max(0, min(4, est))
    except Exception:
        return 0


def probably_has(gs, player, rank, threshold=0.5):
    """推算玩家是否大概率持有某点数"""
    return estimate_count_in(gs, player, rank) >= threshold


def estimate_pair_in(gs, player, rank):
    """
    推算玩家 player 手里有对子的概率。
    返回 0~1 之间的浮点数。
    """
    try:
        rem = remaining_map(gs)
        n = rem.get(rank, 0)
        if n < 2:
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
        if own_count >= 2:
            return 1

        base_ratio = n / 2 * own / both

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


def evaluate_hand(cards):
    """
    手牌综合评分。
    返回 dict: {score: float, bombs: int, rocket: int, singles: int}
    """
    freq = count_ranks(cards)
    score = 0.0
    bombs = 0
    rocket = 0

    # 每张牌的基础分
    for c in cards:
        r = c['rank']
        if r == 17:
            score += 14
        elif r == 16:
            score += 10
        elif r == 15:
            score += 6
        elif r == 14:
            score += 4
        elif r == 13:
            score += 3
        elif r == 12:
            score += 2.5
        elif r == 11:
            score += 2
        elif r == 10:
            score += 1.8
        elif r == 9:
            score += 1.5
        elif r == 8:
            score += 1.2
        else:
            score += 1

    # 组合加分
    for r, cnt in freq.items():
        if cnt == 4:
            score += 12
            bombs += 1
        elif cnt == 3:
            score += 4
        elif cnt == 2:
            score += 2

    # 火箭加分
    if freq.get(16, 0) and freq.get(17, 0):
        score += 8
        rocket = 1

    # 顺子加分
    runs = consecutive_runs(list(freq.keys()), 5)
    for run in runs:
        if len(run) >= 5:
            score += 4 + min(len(run), 10) * 0.5

    # 连对加分
    pair_runs = consecutive_runs([r for r in freq if freq[r] >= 2], 3)
    for run in pair_runs:
        if len(run) >= 3:
            score += 4 + len(run)

    # 飞机加分
    triple_runs = consecutive_runs([r for r in freq if freq[r] >= 3], 2)
    for run in triple_runs:
        if len(run) >= 2:
            score += 6 + len(run) * 2

    # 张数惩罚
    score -= max(0, len(cards) - 17) * 1.5

    # 散牌过多惩罚
    singles = sum(1 for r in freq if freq[r] == 1)
    if singles >= 5:
        score -= (singles - 4) * 1.5

    return {
        'score': max(0, min(100, score)),
        'bombs': bombs,
        'rocket': rocket,
        'singles': singles,
    }


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


def split_penalty(cards, freq):
    """
    拆牌罚分（精确还原旧版JS aiSplitPenalty）。
    cards: 本次出的牌
    freq: 当前手牌的点数统计 {rank: count}
    返回罚分（整数）
    """
    # 统计本次用了多少张各点数
    used = {}
    for c in cards:
        r = c['rank']
        used[r] = used.get(r, 0) + 1

    p = 0
    for r, n_used in used.items():
        n = freq.get(r, 0)
        if n >= 4 and n_used < 4:
            p += 30
        if (r == 16 or r == 17) and n > n_used:
            p += 25
        if n == 3 and n_used < 3:
            p += 10
        if n == 2 and n_used < 2:
            p += 6

    return p


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
    mult = 0.5 if is_counter else 1.0

    def add(r, n):
        nonlocal waste
        if n <= 0:
            return
        if r == 17:
            waste += int(n * 35 * mult)
        elif r == 16:
            waste += int(n * 28 * mult)
        elif r == 15:
            waste += int(n * 22 * mult)
        elif r == 14:
            waste += int(n * 18 * mult)
        elif r == 13:
            waste += int(n * 12 * mult)
        elif r == 12:
            waste += int(n * 5 * mult)

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


def bomb_allowed(gs, who, last):
    """
    炸弹时机判断。
    gs: 游戏状态
    who: 当前玩家编号
    last: 上一手牌 pattern dict {type, main, len}
    返回 True 允许炸，False 不允许
    """
    role = gs.get_role(who)
    threat = gs.get_threat_count(who)
    hand = gs.hands[who]
    big = big_cards_status(gs)
    freq = count_ranks(hand)

    if last['type'] == 'ROCKET':
        return False
    if last['type'] == 'BOMB' and threat > 4:
        return False
    if big['smallJoker'] + big['bigJoker'] > 0 and threat > 5:
        return False

    # 炸完剩余牌 <=4 张视为能走完，允许炸
    bomb_ranks = [r for r in freq if freq[r] == 4]
    after_bomb = len(hand) - (4 if bomb_ranks else 0)
    can_finish_after_bomb = after_bomb <= 4

    if role == 'farmerNext' and gs.get_landlord_count() > 4 and not can_finish_after_bomb:
        return False
    if threat <= 3 or len(hand) <= 5 or can_finish_after_bomb:
        return True
    return threat <= 4


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

    role = gs.get_role(who)
    after = [c for c in hand if not any(y['id'] == c['id'] for y in x['cards'])]
    landlord_count = gs.get_landlord_count()
    partner = gs.get_partner(who)
    partner_count = gs.get_teammate_count(who) if partner >= 0 else 99
    last_player = _last_player_for_ai(gs)

    if not after:
        return 180

    # counter 模式：压地主的牌
    if mode == 'counter' and role != 'landlord' and last_player == gs.landlord:
        if landlord_count <= 3:
            return 150
        if landlord_count <= 6:
            return 80
        if last and last['type'] == 'BOMB' and x['pattern']['type'] == 'BOMB':
            return 100
        return -80

    # counter 模式：压队友的牌
    if mode == 'counter' and role != 'landlord' and last_player == partner:
        return -90 if partner_count <= 3 else -25

    # counter 模式：地主角色
    if mode == 'counter' and role == 'landlord':
        threat = gs.get_teammate_count(gs.current)
        if threat <= 3:
            return 120
        if last and last['type'] == 'BOMB':
            return 100
        return -80

    # 农民方且地主牌少
    if role != 'landlord' and landlord_count <= 3:
        return 120

    if len(hand) <= 6:
        return 70
    return -70


def route_value(gs, hand, candidate, who):
    """
    路线价值（拆牌/手数分析）。
    candidate: dict {cards: list, pattern: dict}
    返回整数评分
    """
    after = [c for c in hand if not any(x['id'] == c['id'] for x in candidate['cards'])]
    if not after:
        return 180

    next_cands = ai_candidates(after)
    if not next_cands:
        return -80

    shape = hand_shape(after)
    value = -shape['groups'] * 7 - shape['singles'] * 3

    if any(len(x['cards']) == len(after) for x in next_cands):
        value += 90

    value += max((len(x['cards']) for x in next_cands), default=0) * 4

    # 手数分析（旧版JS: (5-Math.min(5,hands))*5）
    hands = estimate_hands(after)
    value += (5 - min(5, hands)) * 5

    # 队友偏好加成
    partner = gs.get_partner(who)
    if partner >= 0 and partner < len(ai_mem.patterns):
        pref = ai_mem.patterns[partner]
        ptype = candidate['pattern']['type']
        if ptype in pref:
            value += min(18, pref[ptype] * 3)

    return value


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
    type_factor = 1.2 if last['type'] != 'SINGLE' else 1.0

    landlord_count = gs.get_landlord_count()
    has_pair_two = freq.get(15, 0) >= 2
    has_joker = freq.get(16, 0) > 0 or freq.get(17, 0) > 0

    if not has_pair_two or not has_joker:
        return 0

    main = x['pattern']['main']
    if main == 15:
        if landlord_count <= 5:
            return int(-18 * type_factor)
        elif landlord_count <= 8:
            return int(-8 * type_factor)
        else:
            return 0
    if main == 16 or main == 17:
        if landlord_count > 8:
            return int(-20 * type_factor)
        elif landlord_count <= 3:
            return int(8 * type_factor)
        else:
            return 0
    return 0


# ==================== 第三层：学习修正函数 ====================

def _learn_query(action_type, bucket):
    """查询学习桶数据"""
    if not _learn.get('loaded', True):
        return None
    key = action_type + '|' + bucket
    return ai_mem._learn.get('buckets', {}).get(key) or _learn.get('buckets', {}).get(key) or None


def _learn_adjust(action_type, bucket):
    """
    修正分 = (桶胜率 - 基准胜率) × 200，钳制 ±20，乘渐进系数 min(1, total/100)
    """
    b = _learn_query(action_type, bucket)
    if not b or b.get('total', 0) < 30:
        return 0
    base_wr = (ai_mem._learn.get('base', {}).get(action_type) or _learn.get('base', {}).get(action_type) or {}).get('win_rate')
    if base_wr is None:
        return 0
    raw = (b.get('win_rate', 0) - base_wr) * 200
    clamped = max(-20, min(20, raw))
    return clamped * min(1, b.get('total', 0) / 100)


def _learn_pass_bias(role, landlord_count):
    """
    PASS 专用：让牌 vs 压牌 双桶对照。正=更愿压，负=更愿让
    """
    band = 'lt3' if landlord_count <= 3 else ('lt8' if landlord_count <= 8 else 'gt8')
    beat = _learn_query('PASS', 'beat:' + role + ':' + band)
    pass_b = _learn_query('PASS', 'pass:' + role + ':' + band)
    if not beat and not pass_b:
        return 0
    base_wr = (ai_mem._learn.get('base', {}).get('PASS') or _learn.get('base', {}).get('PASS') or {}).get('win_rate')
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


def _ai_next(who):
    """返回下一个出牌玩家（JS 中 aiNext(who) = (who+2)%3）"""
    return (who + 2) % 3


# ==================== 第四层：核心评分函数 ====================

def candidate_score(gs, x, hand, who, mode, last):
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
        score = 0
    elif pattern['type'] == 'PAIR':
        score = 8
    else:
        score = 18

    if pattern['type'] in ('STRAIGHT', 'STRAIGHT_PAIR') or pattern['type'].startswith('AIRPLANE'):
        score += 12
    if pattern['type'] == 'FOUR_TWO':
        score += 10
    if pattern['type'] == 'FOUR_TWO' and freq.get(pattern['main'], 0) == 4 and len(after) > 0:
        score -= 30  # 整副炸弹不当四带二主牌（清空手牌除外）

    # === Core 2: structure value (route_value + split penalty) ===
    # route_value 只在主动出牌 lead 模式计算；跟牌 counter 跳过（否则"出大牌剩余结构好"
    # 会误导 AI 甩大牌压小牌，跟牌应优先出最小能压的牌）
    if mode != 'counter':
        score += route_value(gs, hand, x, who)
    _sp = split_penalty(x['cards'], freq)
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
        hand_band = 'h8' if len(hand) <= 8 else 'hm'
        score += _learn_adjust('SPLIT', pen_band + ':' + hand_band)
    score -= kicker_waste(x['cards'], pattern, mode == 'counter')

    # === Core 3: hand count delta（仅主动出牌 lead 模式计算；跟牌 counter 跳过，
    #      避免"甩大牌减手数"误导 AI 浪费控制牌） ===
    if mode != 'counter':
        hands_before = estimate_hands(hand)
        hands_after = estimate_hands(after)
        delta = hands_before - hands_after
        if delta >= 2:
            score += 15
        elif delta == 1:
            score += 8
        elif delta == 0:
            pass
        else:
            score -= 12

    # === Core 5: tracker integration ===
    if mode != 'counter' or not last:
        if big['bigJoker'] == 0 and big['smallJoker'] == 0:
            pass
        elif pattern['type'] == 'SINGLE' and pattern['main'] == 15:
            score -= 10
        if big['A'] == 0 and pattern['type'] == 'SINGLE' and pattern['main'] == 13:
            score += 5

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
                score += 120
            elif landlord_count <= 3:
                score += 95
            elif landlord_count <= 5:
                score += 65
            elif landlord_count <= 8:
                score += 30
            else:
                score += 8
            if role == 'farmerPrev':
                score += 30 if landlord_count <= 6 else 14
            if role == 'farmerPrev' and landlord_count <= 2:
                score += 60
            if pattern['type'] == 'SINGLE' and pattern['main'] <= 10:
                score += 8
        if partner_play:
            if partner_count <= 2:
                score -= 70
            elif partner_count <= 4:
                score -= 35
            else:
                score -= 8
            if landlord_count <= 3:
                score += 90
            elif landlord_count <= 6:
                score += 42
            if pattern['type'] not in ('BOMB', 'ROCKET'):
                max_rank = max(c['rank'] for c in x['cards'])
                if max_rank >= 13:
                    score -= 30
                if max_rank >= 15:
                    score -= 20
        if len(after) == 0:
            score += 140
    else:
        # === Lead mode ===
        score += big_value(gs, x, hand, who, last, mode)
        if pattern['type'] in ('BOMB', 'ROCKET'):
            _threat2 = gs.get_threat_count(who)
            threat_band2 = 't3' if _threat2 <= 3 else ('t4' if _threat2 <= 4 else 't5')
            hand_band2 = 'h5' if len(hand) <= 5 else ('h10' if len(hand) <= 10 else 'hm')
            score += _learn_adjust('BOMB', threat_band2 + ':' + hand_band2)
        if len(after) == 0:
            score += 120
        if len(hand) <= 6:
            if len(after) == 0:
                score += len(x['cards']) * 14
            elif pattern['main'] >= 14 and pattern['type'] not in ('BOMB', 'ROCKET'):
                score -= 25
            else:
                score += len(x['cards']) * 14
        # 控制牌保留
        if (len(after) > 0 and pattern['main'] >= 14 and
                pattern['type'] in ('SINGLE', 'PAIR') and
                pattern['type'] not in ('BOMB', 'ROCKET')):
            score -= 25
        # 带牌更优
        if pattern['type'] == 'TRIPLE_ONE':
            score += 8
        if pattern['type'] == 'TRIPLE_TWO':
            score += 12
        # 带牌不带大牌
        if (len(after) > 0 and pattern['type'] in ('TRIPLE_ONE', 'TRIPLE_TWO', 'AIRPLANE_SINGLE', 'AIRPLANE_PAIR')):
            main_cnt = sum(1 for c in x['cards'] if c['rank'] == pattern['main'])
            kicker_big = any(c['rank'] >= 15 and not (c['rank'] == pattern['main'] and main_cnt >= 3) for c in x['cards'])
            if kicker_big:
                score -= 40
        # 大牌型整合奖励
        if pattern['type'] == 'STRAIGHT_PAIR' and pattern['len'] >= 5 and pattern['main'] + pattern['len'] - 1 <= 11:
            score += 50
        elif pattern['type'] == 'STRAIGHT_PAIR' and pattern['len'] >= 3 and pattern['main'] + pattern['len'] - 1 <= 11:
            score += 25
        elif pattern['type'] == 'STRAIGHT_PAIR' and pattern['main'] + pattern['len'] - 1 >= 12:
            score -= 15
        if pattern['type'] == 'STRAIGHT' and pattern['len'] >= 5 and pattern['main'] + pattern['len'] - 1 <= 13:
            score += 40
        elif pattern['type'] == 'STRAIGHT' and pattern['main'] + pattern['len'] - 1 >= 14:
            score -= 10
        if pattern['type'] == 'AIRPLANE':
            score += 45
        if pattern['type'] == 'AIRPLANE_PAIR':
            score += 45
        elif pattern['type'] == 'AIRPLANE_SINGLE':
            score += 25
        # 回收能力
        if (len(after) > 0 and pattern['type'] not in ('BOMB', 'ROCKET')):
            next_cands = ai_candidates(after)
            recover = any(
                (c['pattern']['type'] == pattern['type'] and
                 c['pattern']['len'] == pattern['len'] and
                 c['pattern']['main'] > pattern['main']) or
                c['pattern']['type'] in ('BOMB', 'ROCKET')
                for c in next_cands
            )
            if recover:
                score += 8
            else:
                score -= 12
        # 送牌三原则
        if role != 'landlord' and partner >= 0 and partner_count <= 2 and partner == _ai_next(who):
            if (pattern['type'] in ('SINGLE', 'PAIR')) and pattern['main'] >= 15:
                score -= 70
            send_ok = ((partner_count == 1 and pattern['type'] == 'SINGLE') or
                       (partner_count == 2 and pattern['type'] in ('SINGLE', 'PAIR')))
            if send_ok:
                send_split = split_penalty(x['cards'], freq)
                max_send_rank = max(c['rank'] for c in x['cards'])
                send_good = send_split < 8 and max_send_rank < 14 and len(after) > 0
                if send_good and landlord_count <= 2 and pattern['type'] == 'SINGLE':
                    send_good = False
                if send_good:
                    if pattern['type'] == 'SINGLE':
                        score += 40
                    elif pattern['type'] == 'PAIR':
                        score += 30
        elif (role != 'landlord' and 3 <= partner_count <= 5 and partner_count < len(hand)):
            # 队友牌还多(3~5张)：温和倾向出小牌送（队友≤2张时走严格送牌，不在此）
            if pattern['type'] == 'SINGLE' and pattern['main'] <= 6:
                score += 34
            if pattern['type'] == 'PAIR' and pattern['main'] <= 8:
                score += 20
        if role != 'landlord' and landlord_count <= 5 and pattern['type'] in ('BOMB', 'ROCKET'):
            score += 24
        if role == 'landlord' and pattern['type'] != 'SINGLE':
            score += 10
        # 地主 AI 专属策略
        if role == 'landlord':
            if len(hand) > 8:
                if pattern['type'] == 'SINGLE' and pattern['main'] <= 7:
                    score += 24
                if pattern['type'] in ('SINGLE', 'PAIR') and pattern['main'] >= 14:
                    score -= 20
            if len(hand) > 10 and split_penalty(x['cards'], freq) > 0:
                score -= 10
            if len(hand) <= 5 and len(after) > 0:
                score += len(x['cards']) * 8
            if len(hand) == 2 and pattern['type'] == 'PAIR':
                min_farm = gs.get_teammate_count(gs.current)
                if min_farm <= 2:
                    score += 25
        # 基本排序
        if pattern['type'] not in ('BOMB', 'ROCKET'):
            score += (14 - pattern['main']) * 2
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
        # 策略适配
        strat = (mode or '').replace('lead-', '')
        if strat == 'aggressive':
            if len(after) <= 2:
                score += 18
            elif len(hand) <= 5:
                score += len(x['cards']) * 6
        elif strat == 'support':
            if partner_count <= 4:
                if pattern['type'] == 'SINGLE' and pattern['main'] <= 7:
                    score += 22
                if pattern['type'] == 'PAIR' and pattern['main'] <= 9:
                    score += 16
            if pattern['type'] in ('BOMB', 'ROCKET'):
                score -= 15
        elif strat == 'defensive':
            max_card_rank = max(c['rank'] for c in x['cards'])
            if len(after) > 2 and max_card_rank >= 14 and pattern['type'] not in ('BOMB', 'ROCKET'):
                score -= 12

    return score


# ==================== 第五层：让牌决策函数 ====================

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

    # 地主角色简化处理
    if role == 'landlord':
        freq = count_ranks(hand)
        normal = [x for x in candidates
                  if x['pattern']['type'] not in ('BOMB', 'ROCKET') and
                  x['pattern']['main'] <= 14 and
                  split_penalty(x['cards'], freq) < 25]
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
    if lp == gs.landlord and role != 'landlord' and landlord_count <= 2:
        return False

    # === 缺陷A/F修复：农民单张只剩大牌(2/王)顶地主单张 → 让牌 ===
    # 本工程 rank: 3~14=3~A, 15=2, 16=小王, 17=大王。
    # 农民(非地主)面对地主出的单张(main<=15,即2及以下，不含王对王)，若不拆对/三条时能压的单张
    # 全是2/王(main>=15)，则出大牌顶地主的大牌/小牌太浪费，应让牌(把2/王留到关键时刻)。
    # 必须放在 Lv4(位置压牌)之前，否则被抢先 return。Lv2 已处理"地主剩<=2必须压"。
    if (role != 'landlord' and lp == gs.landlord and last['type'] == 'SINGLE'
            and last['main'] <= 15 and landlord_count > 2):
        # 只考虑"不拆牌的单张"（该点数在手里只有1张），拆对/三条得来的单张不算
        free_singles = [x for x in candidates
                        if x['pattern']['type'] == 'SINGLE'
                        and x['pattern']['type'] not in ('BOMB', 'ROCKET')
                        and freq.get(x['pattern']['main'], 0) <= 1]
        # 手里是否有成对/三条等结构（拆了可惜）——若全散单张则不该让牌
        has_structure = any(cnt >= 2 for cnt in freq.values())
        # 不拆牌时能压的单张都是大牌(2/王, main>=15) + 有结构值得保护 → 让牌
        if free_singles and has_structure and all(x['pattern']['main'] >= 15 for x in free_singles):
            return True

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

    # Lv4: farmerNext and landlord <=8
    # farmerNext(下家)配合策略(动态看张数, 不写死):
    #   - 地主快走完(≤2, 已由Lv2处理)必须压
    #   - 地主出小牌单张, 下家有"能顺的小散单张"(main较小, 清自己小牌) → 出牌(顺小牌)
    #   - 下家只有大牌/成对、没小散单张可顺, 且地主非急(>3), 队友(上家)牌还多 → 让牌, 把顶牌留给上家
    #   - 地主出大牌(K/2) → 下家压(保护, Lv4.5)
    if lp == gs.landlord and role == 'farmerNext' and landlord_count <= 8 and landlord_count > 2:
        # 下家面对地主单张: 是否只有大牌可压(没小散单张可顺)
        if last['type'] == 'SINGLE' and last['main'] <= 10:
            # 下家手里不拆牌能压的最小单张
            cheap_free = [x for x in candidates
                          if x['pattern']['type'] == 'SINGLE'
                          and x['pattern']['type'] not in ('BOMB', 'ROCKET')
                          and freq.get(x['pattern']['main'], 0) <= 1
                          and x['pattern']['main'] <= 10]
            # 只有大牌(>10, 即J以上/2/王)能压、没小牌可顺 → 若队友(上家)还在且地主不急, 让牌给上家顶
            only_big = (not cheap_free) and any(x['pattern']['main'] > 10 for x in candidates)
            if only_big and partner_count >= 4 and landlord_count > 3:
                return True
        return False

    # Lv4.5: farmerNext raise price when landlord plays big cards
    if lp == gs.landlord and role == 'farmerNext':
        if last['main'] >= 13:
            has_counter = any(x['pattern']['type'] not in ('BOMB', 'ROCKET') and
                             x['pattern']['main'] > last['main']
                             for x in candidates)
            if has_counter:
                return False

    # Lv5: farmerPrev and landlord <=5
    if lp == gs.landlord and role == 'farmerPrev' and landlord_count <= 5:
        return False

    # Lv5.5: farmerPrev must block landlord
    if lp == gs.landlord and role == 'farmerPrev':
        my_hand_strength = evaluate_hand(hand)['score']
        threshold = 65 if landlord_count <= 8 else 55
        if my_hand_strength <= threshold:
            has_normal = any(x['pattern']['type'] not in ('BOMB', 'ROCKET') for x in candidates)
            if has_normal:
                return False

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

    # Lv8: card counter suggests cheap cards in partner
    if (lp == gs.landlord and not dangerous_landlord and landlord_count > 5 and
            other_farmer >= 0 and ai_mem.pass_streak[other_farmer] == 0):
        cheap = any(x['pattern']['type'] not in ('BOMB', 'ROCKET') and x['pattern']['main'] < 14
                    for x in candidates)
        if not cheap:
            partner_h = gs.get_teammate_count(who) if partner >= 0 else 0
            landlord_h = landlord_count
            if partner_h >= landlord_h:
                cheaper_in_partner = False
                if last['type'] == 'SINGLE':
                    for r in range(last['main'] + 1, 15):
                        if estimate_count_in(gs, partner, r) >= 0.8:
                            cheaper_in_partner = True
                            break
                elif last['type'] == 'PAIR':
                    for r in range(last['main'] + 1, 15):
                        if estimate_count_in(gs, partner, r) >= 1.5:
                            cheaper_in_partner = True
                            break
                elif last['type'] in ('TRIPLE', 'TRIPLE_ONE', 'TRIPLE_TWO'):
                    for r in range(last['main'] + 1, 15):
                        if estimate_count_in(gs, partner, r) >= 2.2:
                            cheaper_in_partner = True
                            break
                if cheaper_in_partner:
                    return True

    # Special: both partner and landlord close to finish
    if partner_play and partner_count <= 3 and landlord_count <= 3:
        return False

    # 下家面对地主出的牌
    if role == 'farmerNext' and lp == gs.landlord and landlord_count > 5 and other_farmer >= 0:
        # 若能用"同类型、点数更大"的牌型干净压过地主，则不应让牌（是合理压牌，非浪费大牌）
        clean_beat = any(
            x['pattern']['type'] == last['type'] and
            x['pattern']['type'] not in ('BOMB', 'ROCKET') and
            x['pattern']['main'] > last['main'] and
            x['pattern'].get('len') == last.get('len')
            for x in candidates)
        if clean_beat:
            return False
        cheap = any(x['pattern']['type'] not in ('BOMB', 'ROCKET') and x['pattern']['main'] < 10
                    for x in candidates)
        if not cheap:
            return True

    # farmerNext take back when partner led medium cards and landlord passed
    if role == 'farmerNext' and lp == partner and ai_mem.pass_streak[gs.landlord] > 0:
        if 7 <= last['main'] <= 11:
            has_mid = any(x['pattern']['type'] not in ('BOMB', 'ROCKET') and
                          7 <= x['pattern']['main'] <= 11
                          for x in candidates)
            if has_mid:
                return False

    # Default: play normally
    return False


# ==================== 第六层：最优出牌选择函数 ====================

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
            c2 = ai_candidates(after)
            if not c2:
                continue
            s2 = [{'x': cx, 'score': candidate_score(gs, cx, after, gs.current, 'lead-lookahead', None)} for cx in c2]
            s2.sort(key=lambda v: -v['score'])
            best2 = s2[0]
            if not best2:
                continue
            safe2 = all((rem.get(r, 0) <= 0 or
                         not any(c['rank'] == r for c in best2['x']['cards']))
                        for r in rem)
            after2 = [c for c in after if not any(y['id'] == c['id'] for y in best2['x']['cards'])]
            if not after2:
                bonus += 50 + (5 if safe2 else 0)
            else:
                bonus += 30
                # Step 3
                c3 = ai_candidates(after2)
                if c3:
                    s3 = [{'x': cx, 'score': candidate_score(gs, cx, after2, gs.current, 'lead-lookahead', None)} for cx in c3]
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


def ai_find_counter(gs, hand, last, who, strategy):
    """
    跟牌决策（有人出牌后，决定跟还是过）。
    返回 list[card] 或 None（表示不出）。
    """
    # 1. 调 ai_observe_play()（观测已出牌型）
    ai_observe_play(gs)
    
    # 2. 获取所有能压过的候选
    cands = [x for x in ai_candidates(hand) if ai_can_beat(x, last)]
    
    # 2.1 炸弹时机约束：不被 bomb_allowed 允许的炸弹/王炸剔除（防止"能炸就炸"）
    cands = [x for x in cands if not (x['pattern']['type'] in ('BOMB', 'ROCKET') and not bomb_allowed(gs, who, last))]
    
    # 3. 如果没有候选 → 记录 PASS → 返回 None
    if not cands:
        ai_record_step(gs, 'PASS', who)
        return None
    
    # 4. 如果 ai_should_pass_counter 返回 True → 记录 PASS → 返回 None
    if ai_should_pass_counter(gs, hand, last, who, cands):
        ai_record_step(gs, 'PASS', who)
        return None
    
    # 5. 优先找同类型同长度的最小能压的牌（过滤 sameType）
    same_type = [x for x in cands if x['pattern']['type'] == last['type'] and x['pattern']['len'] == last['len']]

    # 6. 调 ai_pick_scored 从候选中选最优
    if same_type:
        # 同类型存在：只保留最小能压的一张（旧版核心逻辑，避免甩大牌）
        min_main = min(x['pattern']['main'] for x in same_type)
        candidates = [x for x in same_type if x['pattern']['main'] == min_main]

        # 农民跟地主单张：按角色区别对待（配合策略，动态看张数，不写死）。
        # 上家 farmerPrev：负责顶牌，用中牌(8~11)压地主，制造压力。
        # 下家 farmerNext：负责"顺自己的小散单张"(出最小能压的)，清掉自己的小牌；
        #   若自己没有可顺的小散单张(全是成对/大牌)，是否出牌/让牌由 ai_should_pass_counter 依据张数决定，
        #   此处仍出最小能压的(避免甩大牌)。
        # 紧急(地主剩≤2)：无论上下家都必须压死，取不拆牌单张里最大的(有9出9,不拆555)。
        if (last['type'] == 'SINGLE' and gs.get_role(who) != 'landlord'
                and _last_player_for_ai(gs) == gs.landlord):
            my_role = gs.get_role(who)
            freq = count_ranks(hand)
            free = [x for x in same_type if freq.get(x['pattern']['main'], 0) <= 1]
            if gs.get_landlord_count() <= 2:
                # 紧急：必须压死，用不拆牌单张里最大的
                if free:
                    top_main = max(x['pattern']['main'] for x in free)
                    candidates = [x for x in free if x['pattern']['main'] == top_main]
                else:
                    top_main = max(x['pattern']['main'] for x in same_type)
                    candidates = [x for x in same_type if x['pattern']['main'] == top_main]
            elif my_role == 'farmerPrev':
                # 上家顶牌：优先中牌8~11，其次最小不拆牌单张，最后才允许拆
                mid = [x for x in free if 8 <= x['pattern']['main'] <= 11]
                if mid:
                    mid_main = min(x['pattern']['main'] for x in mid)
                    candidates = [x for x in mid if x['pattern']['main'] == mid_main]
                elif free:
                    free_main = min(x['pattern']['main'] for x in free)
                    candidates = [x for x in free if x['pattern']['main'] == free_main]
                else:
                    min_main = min(x['pattern']['main'] for x in same_type)
                    candidates = [x for x in same_type if x['pattern']['main'] == min_main]
            else:
                # 下家(farmerNext)：顺自己最小的散单张(清小牌)，不拆对/三条
                if free:
                    free_main = min(x['pattern']['main'] for x in free)
                    candidates = [x for x in free if x['pattern']['main'] == free_main]
                else:
                    min_main = min(x['pattern']['main'] for x in same_type)
                    candidates = [x for x in same_type if x['pattern']['main'] == min_main]
        scored = []
        for x in candidates:
            score = candidate_score(gs, x, hand, who, 'counter', last)
            scored.append({'x': x, 'score': score})
        best_cards = ai_pick_scored(gs, scored, who)
    else:
        # 没有同类型同长度，用所有候选（炸弹/跨类型兜底，经 bomb_allowed 过滤）
        scored = []
        for x in cands:
            score = candidate_score(gs, x, hand, who, 'counter', last)
            scored.append({'x': x, 'score': score})
        best_cards = ai_pick_scored(gs, scored, who)
    
    # 7. 记录学习数据
    if best_cards:
        pattern = detect_pattern(best_cards)
        if pattern:
            if pattern['type'] in ('BOMB', 'ROCKET'):
                ai_record_step(gs, 'BOMB', who)
            elif len(best_cards) != len(hand):
                ai_record_step(gs, 'SPLIT', who)
            else:
                # 正常跟牌（不拆牌、非炸弹）：出了牌就不能记成 PASS，
                # 否则 pass_streak 会被错误累加，污染后续让牌/接力判断
                ai_record_step(gs, 'NORMAL', who)
    
    # 8. 返回选出的牌
    return best_cards


def ai_lead(gs, hand, who, strategy):
    """
    主动出牌决策（没人要，该你出牌）。
    返回 list[card]。
    """
    # 1. ai_observe_play()
    ai_observe_play(gs)
    
    # 2. 候选列表
    cands = ai_candidates(hand)
    
    # 3. 如果没有候选 → 返回 hand[:1]（出最小单张兜底）
    if not cands:
        # 出最小的单张
        sorted_hand = sorted(hand, key=lambda c: c['rank'])
        return [sorted_hand[0]] if sorted_hand else []
    
    # 4. 调 ai_pick_scored 选最优（mode='lead-'+strategy）
    mode = 'lead-' + strategy if strategy else 'lead-balanced'
    scored = []
    for x in cands:
        score = candidate_score(gs, x, hand, who, mode, None)
        scored.append({'x': x, 'score': score})
    
    best_cards = ai_pick_scored(gs, scored, who)
    
    # 5. 记录学习数据
    if best_cards:
        pattern = detect_pattern(best_cards)
        if pattern:
            if pattern['type'] in ('BOMB', 'ROCKET'):
                ai_record_step(gs, 'BOMB', who)
            else:
                ai_record_step(gs, 'SPLIT', who)
    
    # 6. 返回选出的牌
    return best_cards


def ai_play(gs, hand, last_pattern):
    """
    统一出牌入口。
    返回 dict{'action': list[card], 'pattern': dict} or None。
    """
    # 0. 加载 AI 学习数据（60秒缓存，失败静默，不影响出牌）
    load_learn_from_db()

    # 1. 确定当前玩家角色、队友、地主张数
    who = gs.current
    role = gs.get_role(who)
    teammate = gs.get_partner(who)
    landlord_count = gs.get_landlord_count()
    
    # 2. 调 evaluate_hand 获取手牌评分
    hand_eval = evaluate_hand(hand)
    score = hand_eval['score']
    hand_len = len(hand)
    
    # 3. 根据评分+张数决定策略
    strategy = 'balanced'  # 默认策略
    
    # 策略选择逻辑（和 JS 完全一致）
    if hand_len <= 5:
        strategy = 'aggressive'
    elif score > 60 and hand_len <= 8:
        strategy = 'aggressive'
    elif role != 'landlord' and teammate >= 0:
        teammate_count = gs.teammate_count_override if gs.teammate_count_override >= 0 else (len(gs.hands[teammate]) if teammate < len(gs.hands) else 99)
        if teammate_count <= 4:
            strategy = 'support'
    elif score < 35 and hand_len > 8:
        strategy = 'defensive'
    elif landlord_count <= 4:
        if role == 'landlord':
            strategy = 'aggressive'
        else:
            strategy = 'defensive'
    elif score < 40 and hand_len > 10:
        strategy = 'defensive'
    else:
        strategy = 'balanced'
    
    # 4. 如果 last_pattern 为 None → 调 ai_lead
    if last_pattern is None:
        cards = ai_lead(gs, hand, who, strategy)
        pattern = detect_pattern(cards) if cards else None
        if cards and pattern:
            return {'action': cards, 'pattern': pattern}
        return None
    
    # 5. 否则 → 调 ai_find_counter
    cards = ai_find_counter(gs, hand, last_pattern, who, strategy)
    if cards:
        pattern = detect_pattern(cards)
        if pattern:
            return {'action': cards, 'pattern': pattern}
    return None
