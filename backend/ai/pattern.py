"""
斗地主 - 牌型检测模块（锁死部分）
职责：判断牌型，规则固定，不能出错

牌型定义：
- ROCKET: 火箭（大王+小王）
- BOMB: 炸弹（4张相同点数）
- SINGLE: 单张
- PAIR: 对子
- TRIPLE: 三条
- TRIPLE_ONE: 三带一
- TRIPLE_TWO: 三带二
- STRAIGHT: 顺子（5张及以上连续单牌，3-A，不含2和王）
- STRAIGHT_PAIR: 连对（3对及以上连续对子）
- AIRPLANE: 飞机（2组及以上连续三条）
- AIRPLANE_SINGLE: 飞机带单
- AIRPLANE_PAIR: 飞机带对
- FOUR_TWO: 四带二（单或对）
"""


def detect_pattern(cards):
    """
    检测牌型
    
    参数：
        cards: list[dict] - 手牌列表，每张牌格式 {'id': int, 'rank': int, 'suit': int}
    
    返回：
        dict - 牌型信息，格式 {'type': str, 'main': int, 'len': int}
        None - 无法识别的牌型
    
    rank编码：
        3-10: 对应点数
        11: J, 12: Q, 13: K, 14: A, 15: 2
        16: 小王, 17: 大王
    """
    if not cards:
        return None
    
    # 统计每个点数的张数
    freq = {}
    for c in cards:
        r = c['rank']
        freq[r] = freq.get(r, 0) + 1
    
    ranks = sorted(freq.keys())
    n = len(cards)
    
    # 特殊牌型：火箭和炸弹
    result = _check_special(freq, n)
    if result:
        return result
    
    # 基本牌型
    result = _check_basic(freq, n)
    if result:
        return result
    
    # 连续牌型：顺子和连对
    result = _check_straight(freq, ranks, n)
    if result:
        return result
    
    # 飞机系列
    result = _check_airplane(freq, ranks, n)
    if result:
        return result
    
    # 四带二
    result = _check_four_two(freq, n)
    if result:
        return result
    
    return None


def _check_special(freq, n):
    """检查火箭和炸弹"""
    # 火箭：大小王
    if n == 2 and 16 in freq and 17 in freq:
        return {'type': 'ROCKET', 'main': 17, 'len': 2}
    
    # 炸弹：四张同点
    if n == 4 and len(freq) == 1 and 4 in freq.values():
        return {'type': 'BOMB', 'main': list(freq.keys())[0], 'len': 4}
    
    return None


def _check_basic(freq, n):
    """检查单张、对子、三条、三带一、三带二"""
    # 用字典映射：{张数: 牌型}
    basic_map = {
        1: 'SINGLE',
        2: 'PAIR',
        3: 'TRIPLE'
    }
    
    # 单张、对子、三条（只有一种点数）
    if n in basic_map and len(freq) == 1:
        return {'type': basic_map[n], 'main': list(freq.keys())[0], 'len': n}
    
    # 三带一：4张，2种点数，其中一种有3张
    if n == 4 and len(freq) == 2:
        for r, cnt in freq.items():
            if cnt == 3:
                return {'type': 'TRIPLE_ONE', 'main': r, 'len': 4}
    
    # 三带二：5张，2种点数，其中一种有3张，另一种有2张
    if n == 5 and len(freq) == 2:
        for r, cnt in freq.items():
            if cnt == 3:
                other_r = [k for k in freq.keys() if k != r][0]
                if freq[other_r] == 2:
                    return {'type': 'TRIPLE_TWO', 'main': r, 'len': 5}
    
    return None


def _check_straight(freq, ranks, n):
    """检查顺子和连对"""
    # 顺子：5张以上连续单牌，3-A范围
    if n >= 5 and all(cnt == 1 for cnt in freq.values()):
        if _is_consecutive(ranks, 3, 14) and len(ranks) == n:
            return {'type': 'STRAIGHT', 'main': ranks[0], 'len': n}
    
    # 连对：3对以上连续对子，3-A范围
    if n >= 6 and n % 2 == 0 and all(cnt == 2 for cnt in freq.values()):
        if _is_consecutive(ranks, 3, 14):
            return {'type': 'STRAIGHT_PAIR', 'main': ranks[0], 'len': len(ranks)}
    
    return None


def _check_airplane(freq, ranks, n):
    """检查飞机系列"""
    # 找出所有三条
    triples = sorted([r for r, cnt in freq.items() if cnt >= 3])
    
    if len(triples) < 2:
        return None
    
    # 检查是否连续（3-A范围）
    if not _is_consecutive(triples, 3, 14):
        return None
    
    triple_count = len(triples)
    
    # 计算非三条部分的数量
    other_count = 0
    other_pairs = 0
    for r, cnt in freq.items():
        if r in triples:
            if cnt > 3:
                other_count += cnt - 3
        else:
            other_count += cnt
            if cnt == 2:
                other_pairs += 1
    
    # 飞机（不带）
    if n == 3 * triple_count:
        return {'type': 'AIRPLANE', 'main': triples[0], 'len': triple_count}
    
    # 飞机带单
    if n == 4 * triple_count and other_count == triple_count:
        return {'type': 'AIRPLANE_SINGLE', 'main': triples[0], 'len': triple_count}
    
    # 飞机带对
    if n == 5 * triple_count and other_count == triple_count * 2 and other_pairs == triple_count:
        return {'type': 'AIRPLANE_PAIR', 'main': triples[0], 'len': triple_count}
    
    return None


def _check_four_two(freq, n):
    """检查四带二"""
    fours = [r for r, cnt in freq.items() if cnt == 4]
    
    if len(fours) != 1:
        return None
    
    r = fours[0]
    other = {k: v for k, v in freq.items() if k != r}
    other_total = sum(other.values())
    
    # 四带二单：6张，四张+另外2张
    if n == 6 and other_total == 2:
        return {'type': 'FOUR_TWO', 'main': r, 'len': 6}
    
    # 四带二对：8张，四张+另外2对
    if n == 8 and other_total == 4 and all(v == 2 for v in other.values()):
        return {'type': 'FOUR_TWO', 'main': r, 'len': 8}
    
    return None


def _is_consecutive(ranks, min_val, max_val):
    """检查是否连续（在指定范围内）"""
    if not ranks:
        return False
    if ranks[0] < min_val or ranks[-1] > max_val:
        return False
    return ranks == list(range(ranks[0], ranks[0] + len(ranks)))


def can_beat(pattern, last_pattern):
    """
    判断能否压过上家
    
    参数：
        pattern: dict - 当前要出的牌型
        last_pattern: dict - 上家出的牌型
    
    返回：
        bool - 能否压过
    """
    if last_pattern is None:
        return True
    
    # 火箭最大
    if pattern['type'] == 'ROCKET':
        return True
    
    # 炸弹可以压非火箭
    if pattern['type'] == 'BOMB':
        if last_pattern['type'] == 'ROCKET':
            return False
        if last_pattern['type'] == 'BOMB':
            return pattern['main'] > last_pattern['main']
        return True
    
    # 同牌型比点数
    if pattern['type'] == last_pattern['type'] and pattern['len'] == last_pattern['len']:
        return pattern['main'] > last_pattern['main']
    
    return False
