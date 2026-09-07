"""
AI 接口路由：出牌决策、叫地主、提示、学习数据收集与查询
"""

import json
from flask import Blueprint, request, jsonify
from utils import get_db, beijing_now_str
from ai.state import GameState, PLAYER, LEFT, RIGHT
from ai.engine import ai_play as ai_play_engine
from ai.candidates import generate_candidates as ai_candidates
from ai.pattern import can_beat as ai_can_beat
from ai.evaluation import evaluate_hand

ai_bp = Blueprint("ai", __name__)


def _ai_learning_insert(conn, fields):
    """写入 ai_learning。
    CloudBase 为该表注入的 _openid 列是 NOT NULL 且无默认值，INSERT 不带该列会报 1364；
    而本地 SQLite 表没有该列，带上反而会报错。故优先带 _openid，失败则回退为不带。
    20260907 时区修复：显式写入北京时间 created_at。"""
    if "created_at" not in fields:
        fields = dict(fields)
        fields["created_at"] = beijing_now_str()
    try:
        cols = ",".join(fields.keys()) + ",_openid"
        ph = ",".join(["%s"] * (len(fields) + 1))
        conn.cursor().execute(
            "INSERT INTO ai_learning (%s) VALUES (%s)" % (cols, ph),
            list(fields.values()) + [""])
    except Exception:
        cols = ",".join(fields.keys())
        ph = ",".join(["%s"] * len(fields))
        conn.cursor().execute(
            "INSERT INTO ai_learning (%s) VALUES (%s)" % (cols, ph),
            list(fields.values()))


def _record_ai_step(round_id, step, hand_state, action, pattern, who,
                    sp=0, threat=0, seat_role="", is_lead=False):
    """记录 AI 学习数据到数据库（静默，失败不影响游戏）。
    action_type 优先级：BOMB > SPLIT > COUNTER > LEAD > NORMAL（20260905 加入 COUNTER）；
    bucket：BOMB=威胁档:手牌档，SPLIT=罚分档:手牌档，COUNTER=角色:威胁档，LEAD=角色名，NORMAL=空串。
    另有附加行（20260906 方案A 丁）：夺权/接风 lead（非地主、主行之外追加一行）
    action_type=LEADSEIZE，bucket=角色:struct（结构牌）或 角色:clean（干净小牌 sp==0）。"""
    try:
        conn = get_db()
        hand_count = (hand_state or {}).get("hand_count", 0)
        action_type = "NORMAL"
        bucket = ""
        ptype = pattern.get("type") if pattern else None
        if ptype in ("BOMB", "ROCKET"):
            action_type = "BOMB"
            t_band = 't3' if threat <= 3 else ('t4' if threat <= 4 else 't5')
            h_band = 'h5' if hand_count <= 5 else ('h10' if hand_count <= 10 else 'hm')
            bucket = t_band + ":" + h_band
        elif sp > 0:
            action_type = "SPLIT"
            p_band = 'p6' if sp <= 6 else ('p10' if sp <= 10 else ('p25' if sp <= 25 else 'p30'))
            h_band = 'h8' if hand_count <= 8 else 'hm'
            bucket = p_band + ":" + h_band
        elif not is_lead:
            # 任务D（20260905）：跟牌（counter）且非炸非拆 → 单独 COUNTER 桶，
            # 按 角色:对手剩余档 分桶（农民威胁档=地主张数，地主=自身手数，同 BOMB 口径）
            action_type = "COUNTER"
            t_band = 't3' if threat <= 3 else ('t4' if threat <= 4 else 't5')
            bucket = str(seat_role) + ":" + t_band
        elif is_lead:
            action_type = "LEAD"
            bucket = seat_role  # landlord / farmerPrev / farmerNext
        _act_json = json.dumps([{"r": card["rank"], "s": card["suit"]} for card in (action or [])], ensure_ascii=False)
        _ai_learning_insert(conn, {
            "round_id": round_id,
            "step_number": step,
            "hand_state": json.dumps(hand_state, ensure_ascii=False),
            "action_taken": _act_json,
            "action_type": action_type,
            "result": "",
            "score_change": 0,
            "who": str(who),
            "bucket": bucket,
        })
        # 方案A 丁（20260906）：夺权/接风 lead 追加 LEADSEIZE 桶行（主行照常，
        # 结局回填按 round_id+who 会一并覆盖）。与 evaluation 打分侧同口径：
        # last 为空 & 非地主 & 非炸弹；结构牌→角色:struct，干净小牌(sp==0)→角色:clean。
        if (is_lead and seat_role and seat_role != "landlord"
                and ptype not in ("BOMB", "ROCKET")):
            if ptype in ("STRAIGHT", "STRAIGHT_PAIR", "AIRPLANE",
                         "AIRPLANE_SINGLE", "AIRPLANE_PAIR"):
                _seize_bucket = str(seat_role) + ":struct"
            elif sp <= 0:
                _seize_bucket = str(seat_role) + ":clean"
            else:
                _seize_bucket = None  # 非结构且拆牌：打分侧无 LEADSEIZE 修正，不记
            if _seize_bucket:
                _ai_learning_insert(conn, {
                    "round_id": round_id,
                    "step_number": step,
                    "hand_state": json.dumps(hand_state, ensure_ascii=False),
                    "action_taken": _act_json,
                    "action_type": "LEADSEIZE",
                    "result": "",
                    "score_change": 0,
                    "who": str(who),
                    "bucket": _seize_bucket,
                })
        conn.commit()
        conn.close()
    except Exception:
        pass


def _record_pass_step(round_id, step, hand, who, seat_role, landlord_count):
    """让牌 PASS 记录（bucket=pass:角色:地主剩牌档），静默不影响返回。"""
    try:
        conn = get_db()
        band = 'lt3' if landlord_count <= 3 else ('lt8' if landlord_count <= 8 else 'gt8')
        _ai_learning_insert(conn, {
            "round_id": round_id,
            "step_number": step,
            "hand_state": json.dumps({"hand_count": len(hand or []), "role": seat_role}, ensure_ascii=False),
            "action_taken": json.dumps([], ensure_ascii=False),
            "action_type": "PASS",
            "result": "",
            "score_change": 0,
            "who": str(who),
            "bucket": "pass:" + str(seat_role) + ":" + band,
        })
        conn.commit()
        conn.close()
    except Exception:
        pass


def _record_beat_step(round_id, step, hand, action, who, seat_role, landlord_count):
    """TASK-G 小节1（20260906）：农民压地主牌时记 beat 对照行，补 _learn_pass_bias
    双桶缺的那条腿（此前 beat: 桶 0 行，学习只能拿 pass 独腿算）。
    纯记录，零决策影响；bucket/action_type/hand_state 口径与 _record_pass_step 完全一致，
    仅前缀 beat: 区分（读取侧 learning._learn_pass_bias 现成按此查询，无需改）。
    地主自己压牌不记（beat 桶只服务农民让牌对照）。静默失败。"""
    try:
        if seat_role == "landlord":
            return
        conn = get_db()
        band = 'lt3' if landlord_count <= 3 else ('lt8' if landlord_count <= 8 else 'gt8')
        _ai_learning_insert(conn, {
            "round_id": round_id,
            "step_number": step,
            "hand_state": json.dumps({"hand_count": len(hand or []), "role": seat_role}, ensure_ascii=False),
            "action_taken": json.dumps([{"r": c["rank"], "s": c["suit"]} for c in (action or [])], ensure_ascii=False),
            "action_type": "PASS",
            "result": "",
            "score_change": 0,
            "who": str(who),
            "bucket": "beat:" + str(seat_role) + ":" + band,
        })
        conn.commit()
        conn.close()
    except Exception:
        pass


def _parse_hand(hand_raw):
    """前端牌格式 → 后端格式"""
    return [{"id": c.get("id", i), "rank": c.get("r", c.get("rank", 0)), "suit": c.get("s", c.get("suit", 0))} for i, c in enumerate(hand_raw)]


def _normalize_last(last):
    """前端牌型 len（段数）→ 后端牌型 len（张数）。

    根因修复：前端 pattern.js 的 len 是段数（PAIR/TRIPLE/三带/炸弹/王炸恒为1，
    连对为对数，飞机为段数），后端 pattern.py 的 len 是张数（PAIR=2、TRIPLE=3、
    三带一=4、三带二=5、BOMB=4、ROCKET=2、STRAIGHT=张数、连对/飞机=连段数、
    四带二=6/8）。can_beat 要求两侧 len 相等，前端字典直接传入会导致
    除单张/顺子外所有跟牌候选恒为空（对子/三带/炸弹全部被迫 PASS）。
    """
    if not isinstance(last, dict) or "len" not in last:
        return last
    t = last.get("type")
    mapped = {"SINGLE": 1, "PAIR": 2, "TRIPLE": 3, "TRIPLE_ONE": 4, "TRIPLE_TWO": 5,
              "BOMB": 4, "ROCKET": 2}
    if t in mapped:
        n = mapped[t]
    elif t in ("STRAIGHT", "STRAIGHT_PAIR", "AIRPLANE", "AIRPLANE_SINGLE", "AIRPLANE_PAIR"):
        n = last["len"]
    elif t == "FOUR_TWO":
        n = 8 if last["len"] == 2 else 6
    else:
        return last
    out = dict(last)
    out["len"] = n
    return out


def _build_game_state(hand, who, landlord, last, landlord_count, teammate_count,
                      last_player=-1, pass_count=0, played_hands=None):
    """构建 GameState 对象"""
    gs = GameState()
    gs.hands = [hand if i == who else [] for i in range(3)]
    gs.current = who
    gs.landlord = landlord
    gs.lastPlay = {"cards": [], "pattern": last, "player": last_player} if last else None
    gs.passCount = pass_count
    gs.landlord_count_override = landlord_count
    gs.teammate_count_override = teammate_count
    if played_hands:
        gs.playedHands = played_hands
    return gs


@ai_bp.route("/api/ai/decide", methods=["POST"])
def ai_decide():
    """AI 出牌决策接口"""
    data = request.json or {}
    hand = _parse_hand(data.get("hand", []))
    last = _normalize_last(data.get("last"))
    if last and not isinstance(last, dict): last = None
    who = data.get("who", PLAYER)
    landlord = data.get("landlord", -1)
    landlord_count = data.get("landlord_count", 99)
    teammate_count = data.get("teammate_count", 99)
    last_player = data.get("last_player", -1)
    pass_count = data.get("pass_count", 0)
    played_hands = data.get("played_hands", None)
    if played_hands:
        played_hands = [[{"rank": c["r"], "suit": c["s"]} for c in arr] for arr in played_hands]
    gs = _build_game_state(hand, who, landlord, last, landlord_count, teammate_count,
                           last_player, pass_count, played_hands)
    round_id = data.get("round_id", "")
    step = data.get("step", 0)
    try:
        result = ai_play_engine(gs, hand, last)
        if result is None:
            if round_id:
                _record_pass_step(round_id, step, hand, who, gs.get_role(who), landlord_count)
            return jsonify({"ok": True, "action": None, "pattern": None, "passed": True})
        # 新版AI引擎返回 {'cards': [...], 'pattern': {...}}，适配为旧版格式
        if 'cards' in result:
            action = result["cards"]
            pattern = result["pattern"]
        else:
            action = result.get("action")
            pattern = result.get("pattern")
        if not action:
            if round_id:
                _record_pass_step(round_id, step, hand, who, gs.get_role(who), landlord_count)
            return jsonify({"ok": True, "action": None, "pattern": None, "passed": True})
        if round_id:
            # 记录用旁路计算（只 import 不修改决策模块；整体 try/except，失败不影响返回）
            sp_val, threat_val, seat_role = 0, 0, gs.get_role(who)
            try:
                from ai.strategy import split_penalty, count_ranks
                sp_val = split_penalty(action, count_ranks(hand), len(hand))
                threat_val = gs.get_threat_count(who)
            except Exception:
                pass
            _record_ai_step(round_id, step, {"hand_count": len(hand), "role": seat_role}, action, pattern, who,
                            sp=sp_val, threat=threat_val, seat_role=seat_role, is_lead=(last is None))
            # TASK-G 小节1：农民压地主（last 是地主出的跟牌）→ 追加 beat 对照行
            if last is not None and seat_role != "landlord" and last_player == landlord:
                _record_beat_step(round_id, step, hand, action, who, seat_role, landlord_count)
        return jsonify({"ok": True, "action": [{"r": c["rank"], "s": c["suit"]} for c in action], "pattern": pattern, "passed": False})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@ai_bp.route("/api/ai/hint", methods=["POST"])
def ai_hint():
    """AI 提示接口"""
    data = request.json or {}
    hand = _parse_hand(data.get("hand", []))
    last = _normalize_last(data.get("last"))
    if last and not isinstance(last, dict): last = None
    who = data.get("who", PLAYER)
    landlord = data.get("landlord", -1)
    landlord_count = data.get("landlord_count", 99)
    teammate_count = data.get("teammate_count", 99)
    last_player = data.get("last_player", -1)
    pass_count = data.get("pass_count", 0)
    played_hands = data.get("played_hands", None)
    if played_hands:
        played_hands = [[{"rank": c["r"], "suit": c["s"]} for c in arr] for arr in played_hands]
    gs = _build_game_state(hand, who, landlord, last, landlord_count, teammate_count,
                           last_player, pass_count, played_hands)
    try:
        cands = ai_candidates(hand)
        if last:
            cands = [c for c in cands if ai_can_beat(c["pattern"], last)]
        if not cands:
            return jsonify({"ok": True, "plays": [], "passed": True})
        # 候选排序：非炸弹优先于炸弹（炸弹稀缺，不优先提示），同类型按点数升序
        _type_prio = {'SINGLE':0,'PAIR':1,'TRIPLE':2,'TRIPLE_ONE':3,'TRIPLE_TWO':4,
                      'STRAIGHT':5,'STRAIGHT_PAIR':6,'AIRPLANE':7,'AIRPLANE_SINGLE':8,
                      'AIRPLANE_PAIR':9,'FOUR_TWO':10,'BOMB':11,'ROCKET':12}
        cands.sort(key=lambda c: (_type_prio.get(c['pattern']['type'], 99),
                                  c['pattern']['main'],
                                  c['pattern'].get('len', 0)))
        # 把 AI 决策引擎的最优解置顶：玩家点"提示"想看的是"这手该怎么打"，
        # 而不是"最小能打什么"——否则有顺子/连对时会被拆成单张提示
        try:
            best = ai_play_engine(gs, hand, last)
        except Exception:
            best = None
        if best is not None:
            best_cards = best.get("cards") or best.get("action") or []
            best_pat = best.get("pattern")
            if best_cards:
                best_key = sorted((c["rank"], c["suit"]) for c in best_cards)
                found = False
                for i, cand in enumerate(cands):
                    if sorted((c["rank"], c["suit"]) for c in cand["cards"]) == best_key:
                        cands.insert(0, cands.pop(i))
                        found = True
                        break
                if not found and best_cards:
                    ok = best_pat is not None and best_pat.get("type")
                    if ok and last:
                        ok = ai_can_beat(best_pat, last)
                    if ok:
                        cands.insert(0, {"cards": best_cards, "pattern": best_pat})
        plays = [{"cards": [{"r": c["rank"], "s": c["suit"]} for c in cand["cards"]], "pattern": cand["pattern"]} for cand in cands]
        return jsonify({"ok": True, "plays": plays, "passed": False})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@ai_bp.route("/api/ai/bid", methods=["POST"])
def ai_bid():
    """AI 叫地主决策接口（恢复旧版8-18叫分逻辑：含位置/倍率/散牌调整）"""
    data = request.json or {}
    hand = _parse_hand(data.get("hand", []))
    is_call_phase = data.get("isCallPhase", True)
    report = evaluate_hand(hand)
    threshold = 58 if is_call_phase else 60
    if report.get("bombs", 0) >= 1: threshold -= 8
    if report.get("rocket", 0): threshold -= 10  # 王炸加分叫
    if report.get("singles", 0) >= 6: threshold += 8  # 散牌多减分
    if is_call_phase:
        # 首叫阶段：前面"不叫"的人越多，说明大家牌一般，自己中等偏上就可以叫（位置优势）
        passed_before = sum(1 for v in data.get("call_acted", []) if v)
        threshold -= passed_before * 3
    else:
        # 抢地主阶段：倍数越高，抢的代价越大（输了赔更多），越要保守
        mult = data.get("bid_mult", 2) or 2
        if mult >= 8: threshold += 8
        elif mult >= 4: threshold += 4
        # 已经有人抢过：说明有强敌，非顶级牌不跟抢
        grabbed_before = sum(1 for v in data.get("grab_acted", []) if v)
        threshold += grabbed_before * 2
    bid = 0
    if report["score"] >= threshold: bid = 1
    if report["score"] >= threshold + 10: bid = 2
    if report["score"] >= threshold + 20: bid = 3
    # BID 学习记录（静默，不改叫分逻辑）。请求体无 round_id 则跳过该行（保持静默）。
    try:
        round_id = data.get("round_id", "")
        who = data.get("who", "")
        if round_id:
            score_val = report["score"]
            power_band = 'lt55' if score_val < 55 else ('gt70' if score_val > 70 else 'mid')
            phase = 'call' if is_call_phase else 'grab'
            conn = get_db()
            _ai_learning_insert(conn, {
                "round_id": round_id,
                "step_number": 0,
                "hand_state": json.dumps({"hand_count": len(hand), "score": score_val}, ensure_ascii=False),
                "action_taken": json.dumps([{"bid": bid}], ensure_ascii=False),
                "action_type": "BID",
                "result": "",
                "score_change": 0,
                "who": str(who),
                "bucket": phase + ":" + power_band,
            })
            conn.commit()
            conn.close()
    except Exception:
        pass
    return jsonify({"ok": True, "bid": bid, "score": report["score"]})


@ai_bp.route("/api/ai/record", methods=["POST"])
def record_ai_step():
    data = request.json
    conn = get_db()
    _ai_learning_insert(conn, {
        "game_id": data.get("game_id"),
        "step_number": data.get("step"),
        "hand_state": json.dumps(data.get("hand_state", []), ensure_ascii=False),
        "action_taken": json.dumps(data.get("action", {}), ensure_ascii=False),
        "action_type": data.get("action_type", ""),
        "who": data.get("who", ""),
        "bucket": data.get("bucket", ""),
        "result": data.get("result", ""),
        "score_change": data.get("score_change", 0),
        "round_id": data.get("round_id", ""),
    })
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@ai_bp.route("/api/ai/insights")
def ai_insights():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT action_type, COUNT(*) as total,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
               AVG(score_change) as avg_score
        FROM ai_learning WHERE action_type != ''
        GROUP BY action_type HAVING total >= 3 ORDER BY avg_score DESC
    """)
    rows = c.fetchall()
    conn.close()
    result = [{"action_type": r["action_type"], "total": r["total"], "wins": r["wins"],
               "win_rate": round(r["wins"] / r["total"] * 100, 1) if r["total"] > 0 else 0,
               "avg_score": round(r["avg_score"], 2)} for r in rows]
    return jsonify(result)


@ai_bp.route("/api/ai/backfill", methods=["POST"])
def backfill_ai_results():
    """局终回填：按 round_id + who 把该局所有 AI 步骤的胜负结果补上"""
    data = request.json
    conn = get_db()
    c = conn.cursor()
    for item in data.get("results", []):
        c.execute("""
            UPDATE ai_learning SET result = %s, game_id = COALESCE(%s, game_id)
            WHERE round_id = %s AND who = %s AND (result = '' OR result = 'pending')
        """, (item.get("result", ""), data.get("game_id"), data.get("round_id", ""), item.get("who", "")))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@ai_bp.route("/api/ai/learning")
def ai_learning():
    """返回各策略基准胜率 + 桶级胜率"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT action_type,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate,
               COUNT(*) as total
        FROM ai_learning WHERE result IN ('win','lose') AND action_type != '' AND action_type != 'NORMAL'
        GROUP BY action_type
    """)
    base = {r["action_type"]: {"win_rate": round(r["win_rate"], 4), "total": r["total"]} for r in c.fetchall()}
    c.execute("""
        SELECT action_type, bucket,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate,
               COUNT(*) as total
        FROM ai_learning WHERE result IN ('win','lose') AND action_type != '' AND bucket != ''
        GROUP BY action_type, bucket HAVING COUNT(*) >= 30
    """)
    buckets = [{"action_type": r["action_type"], "bucket": r["bucket"],
                "win_rate": round(r["win_rate"], 4), "total": r["total"]} for r in c.fetchall()]
    conn.close()
    return jsonify({"base": base, "buckets": buckets})


@ai_bp.route("/api/ai/learning/progress")
def ai_learning_progress():
    """学习进度看板"""
    THRESHOLD = 30
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total FROM ai_learning")
    total = c.fetchone()["total"]
    c.execute("""
        SELECT action_type, COUNT(*) as total,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN result = 'lose' THEN 1 ELSE 0 END) as losses
        FROM ai_learning WHERE action_type != '' AND action_type != 'NORMAL'
        GROUP BY action_type ORDER BY total DESC
    """)
    strategies = [{"action_type": r["action_type"], "total": r["total"], "wins": r["wins"],
                   "losses": r["losses"], "win_rate": round(r["wins"] / r["total"], 4) if r["total"] > 0 else 0,
                   "threshold_met": r["total"] >= THRESHOLD} for r in c.fetchall()]
    c.execute("""
        SELECT action_type, bucket, COUNT(*) as total,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins
        FROM ai_learning WHERE bucket != '' AND result IN ('win','lose')
        GROUP BY action_type, bucket ORDER BY action_type, total DESC
    """)
    buckets = [{"action_type": r["action_type"], "bucket": r["bucket"], "total": r["total"],
                "wins": r["wins"], "win_rate": round(r["wins"] / r["total"], 4) if r["total"] > 0 else 0,
                "threshold_met": r["total"] >= THRESHOLD} for r in c.fetchall()]
    conn.close()
    return jsonify({"total": total, "threshold": THRESHOLD, "strategies": strategies, "buckets": buckets})
