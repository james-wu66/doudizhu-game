# -*- coding: utf-8 -*-
"""
斗地主 - AI引擎主入口
职责：整合所有模块，提供AI出牌决策

调用链：
1. ai_play() - 主入口（路由分流）
2. ai_landlord_decision() - 地主跟牌
3. ai_gate_decision() - 门板(farmerPrev)决策
4. ai_next_decision() - 下家(farmerNext)决策
5. ai_landlord_lead() - 地主自由出牌
6. candidates - 生成候选出牌
7. L0生存检查 - 过滤会送赢的候选
8. evaluation - 给候选出牌打分
9. strategy - 决定出不出、出什么
"""


import json
import os
from ai.state import GameState, PLAYER, LEFT, RIGHT
from ai.pattern import detect_pattern, can_beat
from ai.candidates import generate_candidates
from ai.strategy import remaining_map
from ai.evaluation import score_candidates



def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}



# ==================== 加载学习数据 ====================
def _ensure_learn_loaded():
    """每次 ai_play 进入时调用；load_learn_from_db 内部 60 秒缓存负责防抖。
    TASK-A 改动四：删除原"只加载一次"布尔锁，否则学习数据进程内永不刷新。"""
    try:
        from ai.learning import load_learn_from_db
        load_learn_from_db()
    except Exception as e:
        print(f"[AI学习] 加载失败: {e}", flush=True)



# ==================== L0 生存检查（硬约束，最高优先级） ====================

def l0_survival_filter(candidates, gs, who):
    """
    L0生存检查：过滤掉会让对手直接走完的候选出牌。
    
    核心判据（来自高手文档第11章）：
    > 出这一手之后，如果对手能在你下一次出牌之前走完，
    > 那么这一手必须是他压不了的（绝对大牌），否则就是送他走。
    
    参数:
        candidates: list[dict] - 候选出牌列表
        gs: GameState - 游戏状态
        who: int - 当前玩家
    
    返回:
        list[dict] - 过滤后的候选出牌（至少保留1个）
    """
    if not candidates:
        return candidates
    
    # P2修复：出牌顺序为逆时针 (who+2)%3 才是下家，原 (who+1)%3 查的是上家
    next_player = (who + 2) % 3
    next_count = len(gs.hands[next_player]) if gs.hands[next_player] else 0
    
    # 下家有3张以上，L0风险低，不过滤
    if next_count > 3:
        return candidates
    
    filtered = []
    
    for cand in candidates:
        cards = cand['cards']
        n_play = len(cards)
        pattern = cand['pattern']
        is_safe = True
        
        # === 检查下家（next_player）===
        if gs.hands[next_player]:
            opp_cards = gs.hands[next_player]
            opp_count = len(opp_cards)
            
            # Case 1: 下家剩1张，我出1张单牌，下家能压 → 他赢
            if opp_count == 1 and n_play == 1 and pattern['type'] == 'SINGLE':
                opp_card = opp_cards[0]
                if opp_card['rank'] > pattern['main']:
                    is_safe = False
            
            # Case 2: 下家剩2张，我出1张，下家有对子能压 → 他可能赢
            if opp_count == 2 and n_play == 1 and pattern['type'] == 'SINGLE':
                # 检查下家是否有对子（两张一样大且大于我的牌）
                rank_count = {}
                for c in opp_cards:
                    r = c['rank']
                    rank_count[r] = rank_count.get(r, 0) + 1
                for r, cnt in rank_count.items():
                    if cnt >= 2 and r > pattern['main']:
                        is_safe = False
                        break
            
            # Case 3: 下家剩2张，我出1张，下家两张单牌都比我大 → 他可能分两次出完
            # 这个太保守了，暂不检查（会过度过滤）
        
        # === 检查上家（prev_player）===
        # 上家在下家之后出牌，如果下家pass了，上家也能响应
        # 简化：只检查下家（最常见的L0场景）
        
        if is_safe:
            filtered.append(cand)
    
    # 安全阀：不能过滤掉所有候选，至少保留1个
    if not filtered:
        # 返回分数最高的那个（通过pattern大小简单排序）
        filtered = [max(candidates, key=lambda x: x['pattern'].get('main', 0))]


    # === TASK-G 小节3a（20260906）：地主剩1张=明牌威胁，禁喂单张 ===
    # 公平记牌下地主最后一张只能推定为"外部剩余集合"：
    #   54 - 全部已出 - 我的 hands（partner 暗张混在其中，宁可保守当可能）。
    # 领出单张只要外部存在更大点数就有被吃掉直接输的风险 → 硬过滤。
    # 对子/三带/顺子等地主1张接不了，不受限。安全阀：农民只剩单张可出时放行。
    # 自由领出判定用 gs.lastPlay is None（l0_survival_filter 无 last_pattern 入参）。
    role_now = gs.get_role(who)
    Lc = len(gs.hands[gs.landlord]) if gs.landlord >= 0 and gs.hands[gs.landlord] else \
        getattr(gs, 'landlord_count_override', 99)
    if role_now != 'landlord' and Lc == 1 and getattr(gs, 'lastPlay', None) is None \
            and len(candidates) > 1:
        rem = remaining_map(gs)
        ext_max = max((r for r, n in rem.items() if n > 0), default=18)
        safe = [c for c in filtered
                if c['pattern']['type'] != 'SINGLE' or c['pattern']['main'] >= ext_max]
        if safe:
            filtered = safe


    return filtered


# ==================== 炸弹硬闸门（20260906 James Wu 拍板：炸弹是最大的牌=最后底牌） ====================

def bomb_discipline_filter(candidates, gs, who, last_pattern, hand, config=None):
    """有牌能压就绝不炸——全员硬纪律（地主/门板/下家通用，含压队友场景）。
    炸弹既然最大，就该在存在普通牌替代时直接剔除出候选（不是打分权衡，
    是资格剥夺），防止'该写死的被加分项翻盘'。例外放行（任一即放）：
      ① 对手进危险区：地主视角=农民最小张数<=bb_crisis_threat；
         农民视角=地主张数<=bb_crisis_threat（再不炸没机会了）
      ② 炸完剩余<=bb_finish_hands手能走完（炸完就是赢，含一手出完）
      ③ 上一手本来就是炸弹/王炸（炸弹对轰天经地义）
      ④ 除炸无别家能压（候选只剩炸弹=没得选，不算乱扔）
    阈值复用 config 现成参数（bb_crisis_threat/bb_finish_hands），
    不新设键；尺度以后由 BOMB 桶学习数据纠正。"""
    if not last_pattern or last_pattern.get('type') in ('BOMB', 'ROCKET'):
        return candidates                                    # ③
    bombs = [x for x in candidates if x['pattern']['type'] in ('BOMB', 'ROCKET')]
    others = [x for x in candidates if x['pattern']['type'] not in ('BOMB', 'ROCKET')]
    if not bombs or not others:
        return candidates                                    # ④（含"没炸弹"常态）
    P = (config or {}).get('params', {})
    crisis = P.get('bb_crisis_threat', 3)
    finish_h = P.get('bb_finish_hands', 2)
    role = gs.get_role(who)
    if role == 'landlord':
        danger = gs.get_teammate_count(who) <= crisis        # ① 地主：任一农民冲线
    else:
        danger = gs.get_landlord_count() <= crisis           # ① 农民：地主冲线
    if danger:
        return candidates
    from ai.evaluation import estimate_hands                 # 局部import防循环
    keep = []
    for b in bombs:                                          # 逐个炸弹查 ②
        after = [c for c in hand if not any(y['id'] == c['id'] for y in b['cards'])]
        if not after or estimate_hands(after) <= finish_h:   # 炸完直接出完=最强放行
            keep.append(b)
    return others + keep



# ==================== 三个角色决策函数（第1步：壳，逻辑从ai_play原样搬入） ====================

def ai_landlord_decision(gs, hand, last_pattern, candidates, config=None):
    """地主跟牌决策（独立版本）。
    核心改进：手牌分解——先评估最优出牌组合，再按组合顺序选择。
    地主的核心逻辑：尽快出完手牌，控制牌权。"""
    from ai.evaluation import estimate_hands
    from ai.strategy import count_ranks, split_penalty
    who = gs.current
    
    # 冲刺模式：手牌<=6张，优先一手出完
    if len(hand) <= 6:
        finish = [x for x in candidates if len(x['cards']) == len(hand)]
        if finish:
            return finish[0]
    
    # L0生存检查
    candidates = l0_survival_filter(candidates, gs, who)
    # 炸弹硬闸门：有牌能压就不许动底牌（20260906 James Wu 拍板）
    candidates = bomb_discipline_filter(candidates, gs, who, last_pattern, hand, config)
    if not candidates:
        return {'cards': [], 'pattern': None}
    
    # 残局：手牌<=4张
    if len(hand) <= 4:
        finish = [x for x in candidates if len(x['cards']) == len(hand)]
        if finish:
            return finish[0]
        if len(hand) <= 3 and last_pattern:
            return candidates[0]
    
    # 核心：手牌分解评分
    scored = score_candidates(candidates, gs, who, last_pattern, config)
    if not scored:
        return {'cards': [], 'pattern': None}
    # TASK-H3（20260906 James Wu 拍板）：地主跟牌平手"最小够用"——同分同牌型
    # 候选中取点数最小者（seed49实锤：8/9/10/J/2全5.0分，排序2nd键"拆罚小优先"
    # 反让2赢了8：拆4张迷你连被当高罚）。只裁决平手，不改任何分数，不动
    # 门板/下家链路。豁免：任一农民进危险区(<=3张,与炸弹闸门危机线同口径)
    # 不启用——该用大牌锁死牌权（如门板出3时下家只剩1张，地主必须顶大的场景）。
    if gs.get_teammate_count(who) > 3:
        top = scored[0]
        wtype = top['pattern']['type']
        wlen = len(top['cards'])
        tscore = top.get('score', 0)
        ties = [x for x in scored
                if x.get('score', 0) == tscore
                and x['pattern']['type'] == wtype
                and len(x['cards']) == wlen]
        if ties:
            top = min(ties, key=lambda x: x['pattern']['main'])
        return top
    return scored[0]


def ai_gate_decision(gs, hand, last_pattern, candidates, config=None):
    """门板(farmerPrev)决策。
    - 地主出牌：用 vm 价值匹配引擎裁决压/让
    - 队友出牌：走配合逻辑（不压队友，除非地主快走完）"""
    from ai.strategy import vm_counter_vs_landlord, _last_player_for_ai
    
    last_player = _last_player_for_ai(gs)
    is_landlord_play = (last_player == gs.landlord)
    
    if is_landlord_play:
        # 地主出牌：价值匹配裁决
        should_pass = vm_counter_vs_landlord(gs, hand, last_pattern, gs.current, candidates)
        if should_pass:
            # === Q4·S4.8 放出口升级（S4.5 继任，物理替代旧 vm 内嵌块）===
            # 深算区内=成本模型 auto 重判（单张行为覆盖旧S4.5 seal改判，
            # 对子域=新增）；区外=L>s48_deep_le 退回旧 seal 判据（G3逐字节）。
            import ai.strategy as _st
            P_48 = _st.P
            from ai.gate_cost import gate_top_cost as _g48
            _out = _g48(gs, gs.current, hand, last_pattern, candidates, mode='auto')
            if _out is not None:
                return _out['action'] or {'cards': [], 'pattern': None}
            if P_48['vm_card_counter'] and last_pattern.get('type') == 'SINGLE':
                from ai.partner_model import landlord_beat_prob
                from ai.candidates import generate_candidates as _gc
                _legal = [x for x in _gc(hand, last_pattern)
                          if x['pattern']['type'] not in ('BOMB', 'ROCKET')]
                if _legal:
                    _sm = min(x['pattern']['main'] for x in _legal)
                    if landlord_beat_prob(gs, gs.current, 'SINGLE',
                                          _sm) <= P_48['s4_seal_max_p']:
                        _c = sorted(_legal, key=lambda x: x['pattern']['main'])[0]
                        return _c
            return {'cards': [], 'pattern': None}
    else:
        # 队友出牌：默认不压，除非地主快走完
        landlord_count = gs.get_landlord_count()
        if landlord_count > 5:
            # === Q4·S4.8乙 接队友出口（20260907 James Wu 定稿：'压队友=浪费'
            # 只禁勾圈级抬价压；队友小牌牌权悬着要便宜接住保牌权）===
            # 触发线/成本全活参数；c48_partner=0 回滚=原样无条件PASS。
            # 地主<=5 的疯狂顶老窗口（下方+seal过滤）不碰。
            from ai.gate_cost import gate_partner_accept
            _ac = gate_partner_accept(gs, gs.current, hand, last_pattern, candidates)
            if _ac is not None:
                return _ac
            return {'cards': [], 'pattern': None}
        # 地主<=5张：可以压队友的牌抢回牌权（走评分，不用硬规则）
    
    # 炸弹硬闸门：有牌能压就不许动底牌——压地主/压队友同样管
    # （20260906 James Wu 拍板：炸弹=最大=最后底牌，全员纪律）
    candidates = bomb_discipline_filter(candidates, gs, gs.current, last_pattern, hand, config)
    if len(candidates) == 1:
        return candidates[0]
    candidates = l0_survival_filter(candidates, gs, gs.current)
    if len(hand) <= 4:
        finish = [x for x in candidates if len(x['cards']) == len(hand)]
        if finish:
            return finish[0]
        if len(hand) <= 3 and last_pattern:
            return candidates[0]
    scored = score_candidates(candidates, gs, gs.current, last_pattern, config)
    return scored[0] if scored else {'cards': [], 'pattern': None}


def ai_next_decision(gs, hand, last_pattern, candidates, config=None):
    """下家(farmerNext)决策。
    - 地主出牌：用 vm 价值匹配引擎裁决（下家门槛更窄）
    - 队友出牌：走配合逻辑（不压队友，除非地主快走完）"""
    from ai.strategy import vm_counter_vs_landlord, _last_player_for_ai
    
    last_player = _last_player_for_ai(gs)
    is_landlord_play = (last_player == gs.landlord)
    
    if is_landlord_play:
        # 地主出牌：价值匹配裁决
        should_pass = vm_counter_vs_landlord(gs, hand, last_pattern, gs.current, candidates)
        if should_pass:
            return {'cards': [], 'pattern': None}
    else:
        # 队友出牌：配合逻辑——默认不压，除非地主快走完
        landlord_count = gs.get_landlord_count()
        if landlord_count > 5:
            return {'cards': [], 'pattern': None}
    
    # 炸弹硬闸门：有牌能压就不许动底牌——压地主/压队友同样管
    # （20260906 James Wu 拍板：炸弹=最大=最后底牌，全员纪律）
    candidates = bomb_discipline_filter(candidates, gs, gs.current, last_pattern, hand, config)
    if len(candidates) == 1:
        return candidates[0]
    candidates = l0_survival_filter(candidates, gs, gs.current)
    if len(hand) <= 4:
        finish = [x for x in candidates if len(x['cards']) == len(hand)]
        if finish:
            return finish[0]
        if len(hand) <= 3 and last_pattern:
            return candidates[0]
    scored = score_candidates(candidates, gs, gs.current, last_pattern, config)
    return scored[0] if scored else {'cards': [], 'pattern': None}



# ==================== AI出牌主函数（路由分流） ====================

def ai_play(gs, hand, last_pattern=None, config=None):
    """
    AI出牌主函数（路由分流入口）
    
    参数：
        gs: GameState - 游戏状态
        hand: list[dict] - 当前手牌
        last_pattern: dict or None - 上家牌型，None表示自由出牌
        config: dict or None - AI配置
    
    返回：
        dict - {'cards': [...], 'pattern': {...}} 或 {'cards': [], 'pattern': None}（过牌）
    """
    if config is None:
        config = load_config()
    
    _ensure_learn_loaded()
    
    who = gs.current
    role = gs.get_role(who)
    
    # 1. 生成所有合法的候选出牌
    candidates = generate_candidates(hand, last_pattern)
    
    # 2. 如果没有合法出牌，只能过
    if not candidates:
        return {'cards': [], 'pattern': None}

    # 2.5 赢牌出口（20260906 James Wu 拍板："赢才是最终目标"）：
    # 手里存在"一手出完"的合法候选（压住上家/领出后手牌清零）→ 无条件打，直接获胜。
    # 凌驾于一切角色分流之上：不受 vm 跳档门槛、不压队友纪律、打分权衡的拦截。
    # 病灶标本 game59[56]：下家农民剩最后一张♥2，压地主单J即获胜，
    # 却被 vm_counter_vs_landlord 跳档4>门槛3 裁成 PASS（finish 出口在放行之后，看不到）。
    # 一手出完=游戏立即结束，任何角色任何场景都是唯一正解，写死为最高纪律。
    if last_pattern is not None:
        _wf = [x for x in candidates if len(x['cards']) == len(hand)]
        if _wf:
            # 多个一手出完候选（同集合不同拆法极罕见）时取点数最小=残局最稳
            _wf.sort(key=lambda x: x['pattern']['main'])
            return _wf[0]

    # 2.6 火力纪律（Q4·S4 C3，20260906 James Wu 口径：门板主顶往死里顶/拆牌也顶；
    #     危险线内下家补位；压队友必须卡死，禁爬梯子。数字全活参数，学习校准；
    #     例外让路：赢牌出口(2.5)在前；炸弹/王炸不进本块=炸归炸弹闸门管）
    import ai.strategy as _st   # 模块级引用：读 _st.P 现值（from import 是启动快照，
                            # 测试/学习改参数会失灵——S5网格实验暴露的接线bug）
    from ai.strategy import _last_player_for_ai
    P_ = _st.P
    if P_['c3_enable'] and role != 'landlord' and last_pattern is not None:
        _lp = _last_player_for_ai(gs)
        _lt = last_pattern.get('type')
        _lm = last_pattern.get('main', 0)
        _nb = [x for x in candidates if x['pattern']['type'] not in ('BOMB', 'ROCKET')]
        _L = gs.get_landlord_count()
        if _lp == gs.landlord:
            # 守卫：本块只治"vm本来会PASS"的场景（全部跟牌候选都超档）；
            # 有门槛内便宜压牌→让路给vm/打分老链路（C3：别把4的顺手压劫持成J）
            _cap = P_['vm_jump_gate'] if role == 'farmerPrev' else P_['vm_jump_next']
            _all_over = bool(_nb) and all(
                x['pattern']['main'] - _lm > _cap for x in _nb)
            if _all_over and _lt == 'SINGLE' and role == 'farmerPrev':
                # === Q4·S4.8 成本模型接线（20260907 James Wu 定稿）===
                # 深算区内(地主<=s48_deep_le)：S4三条硬if+S4.5 整块退位，
                # 合成成本题一次裁决（纪律必顶精神不变，选牌走三本账）。
                # 区外：退回下方已bless的S4硬if（牌账不清不猜，G3锁逐字节）。
                from ai.gate_cost import gate_top_cost as _g48
                if _L <= P_['s48_deep_le']:
                    _out = _g48(gs, who, hand, last_pattern, candidates, mode='auto')
                    if _out is not None:
                        if _out['action'] is None:
                            return {'cards': [], 'pattern': None}
                        return _out['action']
                _g = [x for x in _nb if x['pattern']['type'] == 'SINGLE'
                      and x['pattern']['main'] >= P_['s4_gate_top_single']]
                if _g:   # 门板有底线牌必顶（跳档多超档都顶，最便宜的那张）
                    # 天花板(20260906甲案)：只剩A/2/王能压时，地主牌多(>5)
                    # 放——终结火力不烧在过牌上；地主<=5危机线才用A以上顶。
                    _gk = [x for x in _g if x['pattern']['main']
                           <= P_['s4_gate_top_ceiling']]
                    if not _gk:
                        if _L <= P_['s4_gate_big_le']:
                            _gk = _g        # 危机线内允许A以上顶
                        else:
                            return {'cards': [], 'pattern': None}
                    _gk.sort(key=lambda x: x['pattern']['main'])
                    return _gk[0]
            elif _all_over and _lt == 'SINGLE' and role == 'farmerNext':
                if _L <= P_['s4_next_cover_le']:
                    _n = [x for x in _nb if x['pattern']['type'] == 'SINGLE'
                          and x['pattern']['main'] >= P_['s4_next_cover_floor']]
                    if _n:   # 危险线内门板已放=下家补位（J级起，活参数）
                        _n.sort(key=lambda x: x['pattern']['main'])
                        return _n[0]
            elif _all_over and _lt == 'PAIR' and role == 'farmerPrev':
                # === Q4·S4.8 成本模型接线（对子域，同单张口径）===
                from ai.gate_cost import gate_top_cost as _g48
                if _L <= P_['s48_deep_le']:
                    _out = _g48(gs, who, hand, last_pattern, candidates, mode='auto')
                    if _out is not None:
                        if _out['action'] is None:
                            return {'cards': [], 'pattern': None}
                        return _out['action']
                _gp = [x for x in _nb if x['pattern']['type'] == 'PAIR'
                       and x['pattern']['main'] >= P_['s4_gate_top_pair']]
                if _gp:
                    # 天花板同单张：只剩对A/对2时地主牌多就放，<=5才顶
                    _gpk = [x for x in _gp if x['pattern']['main']
                            <= P_['s4_gate_top_ceiling']]
                    if not _gpk:
                        if _L <= P_['s4_gate_big_le']:
                            _gpk = _gp
                        else:
                            return {'cards': [], 'pattern': None}
                    _gpk.sort(key=lambda x: x['pattern']['main'])
                    return _gpk[0]
        else:
            # 队友一手，我是门板：默认纪律不动（地主>5直接PASS——首版把"禁非卡死
            # 压队友"写成了"卡死就主动抢权"，228次抢队友牌权、胜率61→69劣化，
            # 500局定罪回滚）。只在【地主<=5老抢权窗口】里加卡死过滤：
            # 抢权候选必须"地主压不回"(seal)且不含王炸级(16/17留给终结，#4c原意)。
            if role == 'farmerPrev' and _L <= 5 and _lt == 'SINGLE':
                from ai.partner_model import landlord_beat_prob
                _sl = [x for x in _nb
                       if x['pattern']['type'] == 'SINGLE'
                       and x['pattern']['main'] < 16
                       and landlord_beat_prob(gs, who, 'SINGLE',
                                              x['pattern']['main']) <= P_['s4_seal_max_p']]
                if _nb and not _sl:
                    return {'cards': [], 'pattern': None}   # 没一张卡得死=省火力不爬梯
                # 有卡死候选→交回老打分链路挑（不硬选，cp_partner罚分照旧生效）
                candidates = [x for x in candidates if x in _sl] + [
                    x for x in candidates if x['pattern']['type'] in ('BOMB', 'ROCKET')]
                if len(candidates) == 1:
                    return candidates[0]

    # 3. 路由分流：按角色+场景分发到对应决策函数
    if last_pattern is not None:
        # 跟牌场景
        if role == 'landlord':
            return ai_landlord_decision(gs, hand, last_pattern, candidates, config)
        elif role == 'farmerPrev':
            return ai_gate_decision(gs, hand, last_pattern, candidates, config)
        else:  # farmerNext
            return ai_next_decision(gs, hand, last_pattern, candidates, config)
    else:
        # 自由出牌场景
        if role == 'landlord':
            return ai_landlord_lead(gs, hand, config)
        else:
            # 农民自由出牌（不应到达，ai_lead已处理）——兜底用评分
            if len(candidates) == 1:
                return candidates[0]
            candidates = l0_survival_filter(candidates, gs, who)
            if len(hand) <= 4:
                finish = [x for x in candidates if len(x['cards']) == len(hand)]
                if finish:
                    return finish[0]
                # Q5（20260907 James Wu）：残局领出不再盲拿首候选——game63病根锁：
                # 门板[A,A,王] candidates[0]=单A，绕一步冤枉路。赢牌出口(finish)已
                # 在上一分支覆盖；这里改走打分链路（Q5相对账+既有账本共同裁决）。
                # 回滚锁：c5_q5_enable=0 → 逐字节退回老世界（盲拿首候选）。
                if len(hand) <= 3 and not P_['c5_q5_enable']:
                    return candidates[0]
            scored = score_candidates(candidates, gs, who, None, config)
            return scored[0] if scored else {'cards': [], 'pattern': None}



# ==================== 地主专属出牌（自由出牌时） ====================

def ai_landlord_lead(gs, hand, config=None):
    """
    地主主动出牌（专属策略）：
    核心循环：抢权 → 出废牌 → 牌权丢失 → 用控制牌抢回 → 再走废牌
    
    参数:
        gs: GameState - 游戏状态
        hand: list[dict] - 当前手牌
        config: dict or None - AI配置
    
    返回:
        dict - {'cards': [...], 'pattern': {...}}
    """
    if config is None:
        config = load_config()
    
    who = gs.current
    candidates = generate_candidates(hand, None)
    
    if not candidates:
        return {'cards': [], 'pattern': None}
    
    # 冲刺模式：手牌少于6张，全力出完（一手出完的 finish 候选恒为最小步数，Q5天然豁免；
    # Q5（20260907）：finish 为空时不再盲拿首候选，落入下方打分链路算步数账）
    if len(hand) <= 6:
        finish = [x for x in candidates if len(x['cards']) == len(hand)]
        if finish:
            return finish[0]
    
    # L0生存检查
    candidates = l0_survival_filter(candidates, gs, who)
    
    # 用评分系统选择最优出牌
    scored = score_candidates(candidates, gs, who, None, config)
    if scored:
        return scored[0]
    
    return candidates[0] if candidates else {'cards': [], 'pattern': None}



# ==================== AI出牌入口（通用） ====================

def ai_lead(gs, hand, config=None):
    """
    AI主动出牌（自由出牌）
    如果是地主，调用地主专属策略
    """
    role = gs.get_role(gs.current)
    if role == 'landlord':
        return ai_landlord_lead(gs, hand, config)
    return ai_play(gs, hand, last_pattern=None, config=config)



def ai_counter(gs, hand, last_pattern, config=None):
    """
    AI跟牌（压牌）
    """
    return ai_play(gs, hand, last_pattern=last_pattern, config=config)
