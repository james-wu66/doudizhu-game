# -*- coding: utf-8 -*-
"""
partner_model.py — Q4·S1 队友牌力推断（纯函数，不接线，零决策影响）

设计依据：设计_Q4_农民高级配合_20260906_v2.md §3
红线：只用已公开信息（自己手牌 + playedHands + 各家张数override +
      本轮passCount + lastPlay），绝不读对手暗牌。

轮转事实（代码核实）：地主L → farmerNext=(L+2)%3 → farmerPrev=(L+1)%3 → L
  · 下家领出→门板紧跟   = 安全送（地主插不了队）
  · 门板领出→下家接     = 隔地主（危险，S3 要地主压不过推算才放行）

S1 只产出结构化信号；消费方（C1/C2/C3）在 S2~S4 接线。
张数线 pm_send_max 等尺度参数 S1 先走函数默认值，config 键同步留到
S2 接线时按"三处同步163键"口径一起加，避免 S1 无谓漂移。
"""

# 大牌段位：A/2/王（顶/守的关键张）
_BIG_RANKS = range(14, 18)


def send_direction(gs, who):
    """按轮转方向判定"我领出送队友"是否安全。

    返回: 'safe' | 'blocked' | None(地主/未定)
      safe    : 我是下家(farmerNext)，队友门板紧跟在我后面，地主插不了队
      blocked : 我是门板(farmerPrev)，我领出后地主先过手，可能被截
    """
    if gs.landlord < 0:
        return None
    role = gs.get_role(who)
    if role == 'farmerNext':
        return 'safe'
    if role == 'farmerPrev':
        return 'blocked'
    return None


def partner_passed_last(gs, who):
    """本轮最后一个出牌者是地主，且按轮转推算队友在我之前已对该手PASS。

    pass_count = 自 lastPlay.player 起连续过牌数（不含我）。
    地主L出牌后顺序: L → (L+2)%3 next → (L+1)%3 prev。
    pass_count>=1 → next 已过；pass_count>=2 → next+prev 都过。
    队友过牌位置 = 轮转上排在我前面且已发生的那些。
    """
    if gs.landlord < 0 or not getattr(gs, 'lastPlay', None):
        return False
    lp = gs.lastPlay.get('player', -1)
    if lp != gs.landlord:
        return False  # 只裁"地主一手"的让牌信号（队友间PASS另有C3仲裁）
    partner = gs.get_partner(who)
    if partner < 0:
        return False
    # 地主出牌后轮转位置: 第k位应答者 = (lp + 2k) % 3（NEXT=+2，先(L+2)后(L+1)）
    # 反解: k = 2*(partner - lp) mod 3（2的逆元是2，因 2*2=4≡1 mod 3）
    pc = getattr(gs, 'passCount', 0)
    k_partner = (2 * (partner - lp)) % 3
    return 1 <= k_partner <= pc


def partner_single_weak(gs, who):
    """地主领出较大单张(>=10)而队友已PASS → 队友该段以上单张弱（公开信号）。

    配合 partner_passed_last 使用；小单(<=8)PASS不作强信号——
    vm跳档会主动放，PASS≠没有（惜牌歧义）。
    """
    if not partner_passed_last(gs, who):
        return False
    last = getattr(gs, 'lastPlay', None)
    if not last:
        return False
    pat = last.get('pattern') or {}
    return pat.get('type') == 'SINGLE' and pat.get('main', 0) >= 10


def partner_big_bounds(gs, who):
    """鸽笼界：队友手里 A/2/王 张数的上下界（纯公开牌张代数，最硬信号）。

    外部剩余大牌 N = 54张账 - 我已出 - 所有人已出 - 我手牌（remaining_map）。
    地主手里 L 张（get_landlord_count，真实值）。
      上界: min(N, partner_count)
      下界: max(0, N - L)   地主最多装L张，剩下的必在队友手里
    返回 (lo, hi)。拿不到账(未定地主等)返回 (0, 99) 表示"未知"。
    """
    if gs.landlord < 0:
        return (0, 99)
    from ai.strategy import remaining_map
    rem = remaining_map(gs)
    n_big = sum(rem.get(r, 0) for r in _BIG_RANKS)
    L = gs.get_landlord_count()
    partner = gs.get_partner(who)
    if partner < 0:
        return (0, 99)
    pc = gs.get_teammate_count(who)
    hi = min(n_big, pc)
    lo = max(0, n_big - L)
    return (lo, hi)


def partner_finish_watch(gs, who, pm_send_max=4):
    """队友张数进入"可放跑"窗口（≤pm_send_max）且至今没亮过炸弹 → 残局协防优先级最高。"""
    partner = gs.get_partner(who)
    if partner < 0:
        return False
    pc = gs.get_teammate_count(who)
    if pc > pm_send_max or pc <= 0:
        return False
    played = gs.playedHands[partner] if 0 <= partner < len(gs.playedHands) else []
    # 已出牌里没有4张同点(炸)记录（王炸54张里没有同点，单张王<2也非炸，粗口径够用；
    # 精确炸弹识别归 pattern.py，S1 不引入决策依赖）
    from collections import Counter
    cnt = Counter(c['rank'] for c in (played or []))
    return not any(v >= 4 for v in cnt.values())


def build_partner_model(gs, who=None):
    """汇总入口：返回队友牌力推断结构化 dict（只含公开信息推出的信号）。

    {
      'partner_seat': int, 'role': str,
      'send_direction': 'safe'|'blocked'|None,
      'partner_count': int, 'landlord_count': int,
      'partner_passed_last': bool,
      'partner_single_weak': bool,
      'partner_big_lo': int, 'partner_big_hi': int,
      'partner_finish_watch': bool,
    }
    """
    who = gs.current if who is None else who
    partner = gs.get_partner(who)
    lo, hi = partner_big_bounds(gs, who)
    return {
        'partner_seat': partner,
        'role': gs.get_role(who),
        'send_direction': send_direction(gs, who),
        'partner_count': (gs.get_teammate_count(who) if partner >= 0 else 99),
        'landlord_count': gs.get_landlord_count(),
        'partner_passed_last': partner_passed_last(gs, who),
        'partner_single_weak': partner_single_weak(gs, who),
        'partner_big_lo': lo,
        'partner_big_hi': hi,
        'partner_finish_watch': partner_finish_watch(gs, who),
    }


# ==================== C1' 跑动推断（Q4·S2 核心纯函数） ====================
# 设计：设计_Q4 v2 §4-C1'。三路信息合并推算"队友还剩≤pm_send_max张时，
# 我领什么牌他能接、他能不能自己走完"：
#   ① 记牌器硬账：外部未知牌池（地主+队友的手牌），按点数聚合；
#   ② 组合枚举+超几何权重：rank层分配组合（花色无关牌型），每组合权重
#      = ∏C(池内该点剩余, 取用数)——未知牌随机分给两家的自然概率；
#   ③ 行为软折扣：队友PASS掉地主≥10的单张 → 含A/2/王候选权重×0.4
#      （PASS≠必无——vm会主动放超档牌，只降不杀）。
# 张数多/牌池大时不枚举直接 unknown（早期猜不准，也不许瞎指挥）。

from math import comb as _pm_comb


def _pm_rank_vectors(ranks, caps, n):
    """生成 rank 层取牌向量 {rank:count}：sum=n, 0≤count≤caps[rank]。"""
    if not ranks:
        if n == 0:
            yield {}
        return
    r = ranks[0]
    for take in range(0, min(caps[r], n) + 1):
        for rest in _pm_rank_vectors(ranks[1:], caps, n - take):
            if take:
                rest[r] = take
            yield rest


def _pm_beat_caps(counts):
    """该候选手牌各牌型的最大点数=能压过的领出上限（有比领出大的就能接管，
    判'接得动'用 max 不是 min——单张含王，对/三不含王）。"""
    cap = {}
    if counts:
        cap['SINGLE'] = max(counts)
    for ty, need in (('PAIR', 2), ('TRIPLE', 3)):
        r_max = max((r for r, v in counts.items() if v >= need and r < 16), default=0)
        if r_max:
            cap[ty] = r_max
    return cap


def partner_runnable(gs, who, pm_send_max=4, pm_run_th=0.55, pm_stuck_th=0.5):
    """C1' 三态：runnable(送得动) / stuck(跑不动，自己打) / unknown(算不清别指挥)。

    状态 = 枚举队友可能手牌，按 estimate_hands(几手走完) 加权：
      P(≤2手)≥pm_run_th → runnable；P(≥3手)≥pm_stuck_th → stuck；其余 unknown。
    返回 {'state','send':(type,main)|None,'p_run','win_in_one'}
      send = runnable 时"他接得住"概率最大的中小领出（平局取更小main）。
    """
    unk = {'state': 'unknown', 'send': None, 'p_run': 0.0, 'win_in_one': False}
    partner = gs.get_partner(who)
    if partner < 0 or gs.landlord < 0:
        return unk
    pc = gs.get_teammate_count(who)
    if pc <= 0 or pc > pm_send_max:
        return unk
    from ai.strategy import remaining_map
    from ai.evaluation import estimate_hands
    rem = remaining_map(gs)
    caps = {r: k for r, k in rem.items() if k > 0}
    pool_n = sum(caps.values())          # = 地主L + 队友pc 的未知总张数
    L = gs.get_landlord_count()
    if L <= 0 or pool_n < pc + L or pool_n > 26:   # 账不合/池太大→不枚举
        return unk
    ranks = sorted(caps)
    weak_single = partner_single_weak(gs, who)     # 行为信号③

    W = 0.0
    le2 = 0.0
    win1 = 0.0
    per = {}           # type -> {m: 接得住质量}
    for counts in _pm_rank_vectors(ranks, caps, pc):
        w = 1
        for r, t in counts.items():
            w *= _pm_comb(caps[r], t)   # 超几何：池内该点选t张的方式数
        if weak_single and any(r >= 14 for r in counts):
            w *= 0.4                    # PASS≥10单 → 含大牌候选软折扣
        W += w
        h = estimate_hands([{'rank': r} for r, t in counts.items() for _ in range(t)])
        if h <= 2:
            le2 += w
        if h <= 1:
            win1 += w
        cap = _pm_beat_caps(counts)
        for ty, cm in cap.items():
            d = per.setdefault(ty, {})
            for m in range(3, 12):      # 送牌只考虑中小牌 main≤11
                if cm > m:              # 该型最大 > 领出 → 他接得动
                    d[m] = d.get(m, 0.0) + w
    if W <= 0:
        return unk
    p_run = le2 / W
    state = 'runnable' if p_run >= pm_run_th else (
        'stuck' if (1 - p_run) >= pm_stuck_th else 'unknown')
    send = None
    if state == 'runnable':
        best = None
        for ty in per:
            for m, q in per[ty].items():
                p = q / W
                if best is None or (p, -m) > (best[2], -best[1]):
                    best = (ty, m, p)
        send = (best[0], best[1]) if best else None
    return {
        'state': state,
        'send': send,
        'p_run': round(p_run, 3),
        'win_in_one': (win1 / W) >= 0.5,
    }


def _pm_comb(n, k):
    from math import comb
    return comb(n, k)


def landlord_beat_prob(gs, who, ptype, main):
    """C2 方向闸门推算：我领出 (ptype, main) 后，地主"插队压过"的概率。

    轮转事实（§2）：门板领出→地主先动→才轮到下家；地主压不过才敢送。
    口径：池=remaining_map（地主+队友未知牌，pool_n=L+pc 账合时）。
      SINGLE: 池内点数>main 的张数 higher，地主 L 张随机取自池：
              P = 1 - C(pool_n-higher, L)/C(pool_n, L)
        鸽笼特例：higher > pool_n-L(=pc) → 地主必含超main牌 → P=1
        higher=0 → P=0（地主铁定压不过，硬保证放行）
      PAIR/TRIPLE/结构型: 组合分布算不精 → 保守返回 1.0（S3不放行，只放单张）。
    返回 float [0,1]。账不合/未定地主 → 1.0（保守=禁送）。
    """
    if gs.landlord < 0:
        return 1.0
    if ptype != 'SINGLE':
        return 1.0
    partner = gs.get_partner(who)
    if partner < 0:
        return 1.0
    pc = gs.get_teammate_count(who)
    L = gs.get_landlord_count()
    if L <= 0 or pc <= 0:
        return 1.0
    from ai.strategy import remaining_map
    rem = remaining_map(gs)
    pool_n = sum(rem.values())
    if pool_n != L + pc:
        return 1.0            # 账不合不猜
    higher = sum(v for r, v in rem.items() if r > main)
    if higher <= 0:
        return 0.0
    if higher > pool_n - L:
        return 1.0            # 鸽笼：队友装不完，地主必有
    return 1.0 - _pm_comb(pool_n - higher, L) / _pm_comb(pool_n, L)


def landlord_pair_beat_prob(gs, who, main):
    """Q4·S4.8 账本③对子版：门板顶地主 PAIR(main) 后，地主"收得回"的概率。

    口径与单张版 landlord_beat_prob 同池同账（池=remaining_map，L+pc 账合才敢算），
    唯一差异=事件从"地主有>main的单张"变"地主有>main某点数的对子（或4张含对）"。
    鸽笼两硬出口 + 超几何精确账（无对概率用初等对称函数 e_k 枚举 >main 各点数）：
      P(无对) = Σ_k e_k(rem_hi各点数) × C(pool_lo, L-k) / C(pool_n, L)
    （第3点：bomb不进本账——炸归炸弹闸门，同单张版口径。）
    账不合/未定地主/参数异常 → 1.0（保守：收得回，成本模型会因此收手不顶）。
    """
    if gs.landlord < 0:
        return 1.0
    partner = gs.get_partner(who)
    if partner < 0:
        return 1.0
    pc = gs.get_teammate_count(who)
    L = gs.get_landlord_count()
    if L <= 0 or pc <= 0:
        return 1.0
    from ai.strategy import remaining_map
    rem = remaining_map(gs)
    pool_n = sum(rem.values())
    if pool_n != L + pc:
        return 1.0            # 账不合不猜
    hi = {r: v for r, v in rem.items() if r > main and v >= 2}
    if not hi:
        return 0.0            # 硬出口：池内凑不出任何>main的对子，必收不回
    # 鸽笼硬出口：队友即使"containment"——每点数只留1张给地主装不完他的L张
    # （=地主必在某个点数上拿到≥2张）→ 必收得回
    cap_single = sum(rem.values()) - sum(max(0, v - 1) for v in hi.values())
    # cap_single = 地主最多能拿而不配对的上限：其余点数全拿 + hi各点数拿1张
    if L > cap_single:
        return 1.0
    pool_lo = pool_n - sum(hi.values())
    # 精确无对概率：地主k张来自hi(每点数≤1)，L-k张来自其余
    # e_k = 从hi各点数(每点数取0或1张，取v种花色选法)选k张的方案数
    ranks = sorted(hi)
    e = [0.0] * (min(len(ranks), L) + 1)
    e[0] = 1.0
    for r in ranks:
        for k in range(len(e) - 1, 0, -1):
            e[k] += e[k - 1] * hi[r]
    no_pair = 0.0
    for k in range(0, min(len(ranks), L) + 1):
        if L - k > pool_lo:
            continue
        no_pair += e[k] * _pm_comb(pool_lo, L - k)
    p = 1.0 - no_pair / _pm_comb(pool_n, L)
    return max(0.0, min(1.0, p))


def farmer_beat_prob(gs, who, ptype, main):
    """S4.6 镜像：地主视角——我领出 (ptype,main)，两农民【合计】压得回的概率。

    池 = 54 − 全部已出 − 我(地主)手 = 农手+地未出 = 真实"地主未知牌"。
    （注意：不能用 sum(remaining_map) 当池——它含我手，账永远差 len(hand)）
    农民各自张数=17−已出（标准17张/人，底牌归地主不影响农民基线）。
    超几何：P(压得回) = 1 − C(pool_n − higher, L1+L2)/C(pool_n, L1+L2)
    非单张/账不合/张数异常 → 保守 1.0（=有压得住的，地主按老逻辑打分）。
    """
    if gs.landlord < 0 or who != gs.landlord:
        return 1.0
    if ptype != 'SINGLE':
        return 1.0
    from ai.strategy import remaining_map
    played = gs.playedHands if gs.playedHands else [[], [], []]
    rem = remaining_map(gs)
    pool_n = 54 - sum(len(played[p]) if p < len(played) else 0 for p in range(3)) \
               - len(gs.hands[who])
    Lsum = 0
    for p in range(3):
        if p == gs.landlord:
            continue
        n_played = len(played[p]) if p < len(played) else 0
        li = 17 - n_played
        if li < 0:
            return 1.0        # 账异常（含王/怪数据）→ 保守
        Lsum += li
    if Lsum <= 0 or pool_n != Lsum:
        return 1.0            # 账不合不猜（开局后端无全账=返1.0退回老逻辑）
    higher = sum(v for r, v in rem.items() if r > main)
    if higher <= 0:
        return 0.0            # 硬保证：农民压不动
    if higher > pool_n - Lsum:
        return 1.0            # 鸽笼：大牌全装进农民手
    return 1.0 - _pm_comb(pool_n - higher, Lsum) / _pm_comb(pool_n, Lsum)
