"""
斗地主 - 候选出牌生成模块（锁死部分）
职责：生成所有合法的出牌组合

规则：
1. 自由出牌：生成所有可能的牌型
2. 跟牌：只生成能压过上家的牌型
"""

from ai.pattern import detect_pattern, can_beat


def generate_candidates(hand, last_pattern=None):
    """
    生成所有合法的出牌候选
    
    参数：
        hand: list[dict] - 当前手牌
        last_pattern: dict or None - 上家牌型，None表示自由出牌
    
    返回：
        list[dict] - [{'cards': [...], 'pattern': {...}}, ...]
    """
    candidates = []
    seen = set()
    
    # 统计每个点数的张数
    freq = {}
    for c in hand:
        r = c['rank']
        freq[r] = freq.get(r, 0) + 1
    
    ranks = sorted(freq.keys())
    
    def cards_of(rank, count):
        """返回指定点数的前count张牌"""
        result = []
        for c in hand:
            if c['rank'] == rank and len(result) < count:
                result.append(c)
        return result
    
    def add_candidate(cards):
        """添加候选（去重）"""
        if not cards:
            return
        key = tuple(sorted(c['id'] for c in cards))
        if key in seen:
            return
        seen.add(key)
        pattern = detect_pattern(cards)
        if pattern:
            if last_pattern is None or can_beat(pattern, last_pattern):
                candidates.append({'cards': cards, 'pattern': pattern})
    
    # ==================== 单张 ====================
    for r in ranks:
        add_candidate(cards_of(r, 1))
    
    # ==================== 对子 ====================
    for r in ranks:
        if freq[r] >= 2:
            add_candidate(cards_of(r, 2))
    
    # ==================== 三条 ====================
    for r in ranks:
        if freq[r] >= 3:
            add_candidate(cards_of(r, 3))
    
    # ==================== 三带一 ====================
    for r in ranks:
        if freq[r] >= 3:
            triple = cards_of(r, 3)
            # 优先选最小的非2/王单牌做kicker
            kickers = [kr for kr in ranks if kr != r and freq[kr] >= 1 and kr <= 14]
            if not kickers:
                kickers = [kr for kr in ranks if kr != r and freq[kr] >= 1]
            if kickers:
                add_candidate(triple + cards_of(kickers[0], 1))
    
    # ==================== 三带二 ====================
    for r in ranks:
        if freq[r] >= 3:
            triple = cards_of(r, 3)
            # 优先选最小的非2/王对子做kicker
            kickers = [kr for kr in ranks if kr != r and freq[kr] >= 2 and kr <= 14]
            if not kickers:
                kickers = [kr for kr in ranks if kr != r and freq[kr] >= 2]
            if kickers:
                add_candidate(triple + cards_of(kickers[0], 2))
    
    # ==================== 顺子 ====================
    for start in ranks:
        if start < 3 or start > 14:
            continue
        for length in range(5, 13):
            if start + length - 1 > 14:
                break
            straight = []
            valid = True
            for i in range(length):
                r = start + i
                if freq.get(r, 0) < 1:
                    valid = False
                    break
                straight.extend(cards_of(r, 1))
            if valid and len(straight) == length:
                add_candidate(straight)
    
    # ==================== 连对 ====================
    for start in ranks:
        if start < 3 or start > 14:
            continue
        for length in range(3, 11):
            if start + length - 1 > 14:
                break
            double_straight = []
            valid = True
            for i in range(length):
                r = start + i
                if freq.get(r, 0) < 2:
                    valid = False
                    break
                double_straight.extend(cards_of(r, 2))
            if valid and len(double_straight) == length * 2:
                add_candidate(double_straight)
    
    # ==================== 炸弹 ====================
    for r in ranks:
        if freq[r] == 4:
            add_candidate(cards_of(r, 4))
    
    # ==================== 火箭 ====================
    if freq.get(16, 0) >= 1 and freq.get(17, 0) >= 1:
        add_candidate(cards_of(16, 1) + cards_of(17, 1))
    
    # ==================== 飞机系列 ====================
    # 找出所有三条
    triples = sorted([r for r in ranks if freq[r] >= 3])
    
    # 尝试连续三条组合
    for i in range(len(triples)):
        for j in range(i + 2, len(triples) + 1):
            triple_group = triples[i:j]
            # 检查是否连续
            if triple_group != list(range(triple_group[0], triple_group[0] + len(triple_group))):
                continue
            # 检查是否在3-A范围内
            if not all(3 <= r <= 14 for r in triple_group):
                continue
            
            # 飞机（不带）
            airplane = []
            for r in triple_group:
                airplane.extend(cards_of(r, 3))
            add_candidate(airplane)
            
            # 飞机带单
            other_singles = [r for r in ranks if r not in triple_group]
            if len(other_singles) >= len(triple_group):
                wing = []
                for r in other_singles[:len(triple_group)]:
                    wing.extend(cards_of(r, 1))
                add_candidate(airplane + wing)
            
            # 飞机带对
            other_pairs = [r for r in ranks if r not in triple_group and freq[r] >= 2]
            if len(other_pairs) >= len(triple_group):
                wing = []
                for r in other_pairs[:len(triple_group)]:
                    wing.extend(cards_of(r, 2))
                add_candidate(airplane + wing)
    
    # ==================== 四带二 ====================
    fours = [r for r in ranks if freq[r] == 4]
    for r in fours:
        four = cards_of(r, 4)
        other = [x for x in ranks if x != r]
        
        # 四带二单：优先选最小的非2/王单牌
        low_other = sorted([x for x in other if x <= 14])
        if len(low_other) >= 2:
            wing = cards_of(low_other[0], 1) + cards_of(low_other[1], 1)
            add_candidate(four + wing)
        elif len(other) >= 2:
            wing = cards_of(other[0], 1) + cards_of(other[1], 1)
            add_candidate(four + wing)
        
        # 四带二对：优先选最小的非2/王对子
        low_pairs = sorted([x for x in other if freq[x] >= 2 and x <= 14])
        if len(low_pairs) >= 2:
            wing = cards_of(low_pairs[0], 2) + cards_of(low_pairs[1], 2)
            add_candidate(four + wing)
        elif len(other_pairs := [x for x in other if freq[x] >= 2]) >= 2:
            wing = cards_of(other_pairs[0], 2) + cards_of(other_pairs[1], 2)
            add_candidate(four + wing)
    
    return candidates
