# -*- coding: utf-8 -*-
"""
共享测试辅助工具 — 牌构造器 + GameState 工厂。
rank 映射：3-10=面值, J=11, Q=12, K=13, A=14, 2=15, 小王=16, 大王=17。
suit：0=♠ 1=♥ 2=♦ 3=♣（测试中 suit 无关紧要，用 0 即可）
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ai_state import GameState, PLAYER, LEFT, RIGHT

_next_id = 1000  # 全局递增 id，避免测试间冲突

def card(rank, suit=0):
    """构造单张牌。"""
    global _next_id
    _next_id += 1
    return {'id': _next_id, 'rank': rank, 'suit': suit}

def hand(*ranks):
    """快速构造手牌列表。例：hand(3,3,4,4,5,5) → 6张牌。"""
    return [card(r) for r in ranks]

def make_gs(landlord=0):
    """构造最小可测 GameState，含三个空手。"""
    gs = GameState()
    gs.landlord = landlord
    gs.current = PLAYER
    gs.lastPlay = None
    gs.passCount = 0
    return gs
