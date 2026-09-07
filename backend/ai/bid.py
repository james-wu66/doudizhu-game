"""
斗地主 - 叫地主 / 抢地主模块

规则严格对照旧项目 frontend/js/02-game/bidding.js 的原版流程：
1. 阶段1【叫地主】：三人按逆时针 0 → 2 → 1 → 0 依次选"叫地主"或"不叫"
   - 第一个叫地主的人成为 caller，立刻进入阶段2
   - 三人都不叫 → 重新发牌
2. 阶段2【抢地主】：从 caller 的下家开始，两个非 caller 各问一次"抢地主"或"不抢"
   - 每抢一次 → 倍数 ×2
   - 一圈回到 caller：
     - 没人抢 → caller 当地主，结束
     - 有人抢 → caller 有最后一次"再抢 / 不抢"
3. 地主归属：最后抢地主的人（没人抢时就是 caller）
4. 倍数：叫地主 = 2倍，此后每抢一次 ×2（2 → 4 → 8 → 16）

重要说明：
旧后端 routes/ai.py 曾返回 bid = 1/2/3 的"叫分"，但旧前端 aiDecideBid
只做真假判断（if(call) / if(grab) / if(finalGrab)），那套叫分从未生效。
本模块一律返回 bool，不保留叫分制。
"""

import random

from ai.evaluation import evaluate_hand

# 阶段常量（对应旧前端的三处调用位置）
PHASE_CALL = 'call'    # 叫地主阶段（旧前端第 55 行）
PHASE_GRAB = 'grab'    # 抢地主：非 caller 的普通抢（旧前端第 88 行）
PHASE_FINAL = 'final'  # caller 被抢后的最后一次再抢（旧前端第 78 行）

# 基础阈值
# 校准依据（tests/calibrate_bid.py，10000 副真实发牌）：
#   evaluate_hand 分数实际分布：最低 17，最高 83，中位 38.5，平均 39.8
#   旧后端沿用的 58/60 阈值只让 6% / 4.5% 的手牌叫地主，
#   三人轮流叫时约 83% 的局无人叫地主 → 反复重新发牌，游戏卡死。
# 现按分布重新校准：叫地主取中位偏上（约 45% 的手牌会叫），
# 抢地主更严格（约 22% 会抢），保证绝大多数牌局能正常开始。
CALL_THRESHOLD = 36  # 叫地主
GRAB_THRESHOLD = 42  # 抢地主


def pick_first_caller(rng=None):
    """
    随机决定谁第一个叫地主

    每局开局前调用一次，三个座位各 1/3 概率。
    之后按逆时针顺序 0 → 2 → 1 → 0 依次询问。

    参数：
        rng: random.Random - 随机数发生器，仅测试时传入固定种子

    返回：
        int - 第一个叫地主的座位号（0/1/2）
    """
    if rng is None:
        rng = random
    return rng.randint(0, 2)


def get_bid_order(first_caller):
    """
    获取完整的叫地主顺序（逆时针 0 → 2 → 1 → 0）

    参数：
        first_caller: int - 第一个叫地主的座位号

    返回：
        list[int] - 三人的叫牌顺序，如 [0, 2, 1]
    """
    order = [first_caller]
    who = first_caller
    for _ in range(2):
        who = (who + 2) % 3   # 逆时针
        order.append(who)
    return order


def ai_bid(hand, config, phase=PHASE_CALL, grab_count=0, bid_mult=2, passed_count=0):
    """
    AI 叫地主 / 抢地主 决策

    参数：
        hand: list[dict] - 手牌
        config: dict - AI 配置
        phase: str - PHASE_CALL / PHASE_GRAB / PHASE_FINAL
        grab_count: int - 到目前为止有几个人抢过地主
        bid_mult: int - 当前倍数
        passed_count: int - 叫地主阶段，在我之前已经选择"不叫"的人数

    返回：
        dict - {'bid': bool, 'score': float, 'threshold': float}
               bid=True 表示叫地主 / 抢地主，False 表示不叫 / 不抢
    """
    report = evaluate_hand(hand, config)
    score = report['score']

    if phase == PHASE_CALL:
        threshold = _call_threshold(report, passed_count)
    else:
        threshold = _grab_threshold(report, phase, grab_count, bid_mult)

    return {
        'bid': score >= threshold,
        'score': score,
        'threshold': threshold
    }


def _call_threshold(report, passed_count):
    """
    计算叫地主阶段的阈值（数值越低越敢叫）

    参数：
        report: dict - evaluate_hand 的返回值
        passed_count: int - 前面已选择"不叫"的人数

    返回：
        float - 阈值
    """
    threshold = CALL_THRESHOLD

    # 有大牌支撑，降低叫牌门槛
    if report.get('rocket', 0):
        threshold -= 10
    if report.get('bombs', 0) >= 1:
        threshold -= 8

    # 散牌太多，抬高兴门槛
    if report.get('singles', 0) >= 6:
        threshold += 8

    # 前面不叫的人越多，说明大家牌都一般，自己中等偏上就可以叫
    threshold -= passed_count * 3

    return threshold


def _grab_threshold(report, phase, grab_count, bid_mult):
    """
    计算抢地主阶段的阈值（数值越低越敢抢）

    参数：
        report: dict - evaluate_hand 的返回值
        phase: str - PHASE_GRAB 或 PHASE_FINAL
        grab_count: int - 已经抢过的人数
        bid_mult: int - 当前倍数

    返回：
        float - 阈值
    """
    threshold = GRAB_THRESHOLD

    if report.get('rocket', 0):
        threshold -= 10
    if report.get('bombs', 0) >= 1:
        threshold -= 8
    if report.get('singles', 0) >= 6:
        threshold += 8

    # 已经有人抢过：说明有强敌，非顶级牌不跟抢
    # 注意：只统计"真的抢了"的人，选择不抢的人不算
    if phase == PHASE_GRAB:
        threshold += grab_count * 2

    # 倍数越高，输了赔得越多，越要保守
    if bid_mult >= 8:
        threshold += 8
    elif bid_mult >= 4:
        threshold += 4

    return threshold


def determine_landlord(caller, grabbers=None):
    """
    确定地主和最终倍数

    参数：
        caller: int - 叫地主的人；None 表示三人都不叫
        grabbers: list[int] - 按先后顺序抢地主的人（caller 最后再抢也要放进来）

    返回：
        dict - {'redeal': True} 没人叫地主，需要重新发牌
               {'redeal': False, 'landlord': int, 'bid_mult': int}
    """
    if caller is None:
        return {'redeal': True}

    if grabbers is None:
        grabbers = []

    # 叫地主 2 倍，此后每抢一次翻倍
    bid_mult = 2

    # 地主是最后抢地主的人，没人抢就是 caller
    landlord = caller
    for who in grabbers:
        bid_mult *= 2
        landlord = who

    return {
        'redeal': False,
        'landlord': landlord,
        'bid_mult': bid_mult
    }


def get_bid_threshold(hand, config, phase=PHASE_CALL, grab_count=0, bid_mult=2, passed_count=0):
    """
    获取叫牌阈值（供前端展示"为什么 AI 这么选"）

    参数同 ai_bid

    返回：
        dict - {'threshold': float, 'score': float, 'should_bid': bool}
    """
    result = ai_bid(hand, config, phase, grab_count, bid_mult, passed_count)
    return {
        'threshold': result['threshold'],
        'score': result['score'],
        'should_bid': result['bid']
    }
