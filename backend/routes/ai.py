"""
AI 接口路由：出牌决策、叫地主、提示、学习数据收集与查询
"""

import json
from flask import Blueprint, request, jsonify
from utils import get_db
from ai_state import GameState, PLAYER, LEFT, RIGHT
from ai_engine import ai_play as ai_play_engine, ai_candidates, ai_can_beat, evaluate_hand

ai_bp = Blueprint("ai", __name__)


def _ai_learning_insert(conn, fields):
    """写入 ai_learning。
    CloudBase 为该表注入的 _openid 列是 NOT NULL 且无默认值，INSERT 不带该列会报 1364；
    而本地 SQLite 表没有该列，带上反而会报错。故优先带 _openid，失败则回退为不带。"""
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


def _record_ai_step(round_id, step, hand_state, action, pattern, who):
    """记录 AI 学习数据到数据库（静默，失败不影响游戏）"""
    try:
        conn = get_db()
        action_type = "NORMAL"
        if pattern and pattern.get("type") in ("BOMB", "ROCKET"):
            action_type = "BOMB"
        _ai_learning_insert(conn, {
            "round_id": round_id,
            "step_number": step,
            "hand_state": json.dumps(hand_state, ensure_ascii=False),
            "action_taken": json.dumps([{"r": card["rank"], "s": card["suit"]} for card in (action or [])], ensure_ascii=False),
            "action_type": action_type,
            "result": "",
            "score_change": 0,
            "who": str(who),
            "bucket": "",
        })
        conn.commit()
        conn.close()
    except Exception:
        pass


def _parse_hand(hand_raw):
    """前端牌格式 → 后端格式"""
    return [{"id": c.get("id", i), "rank": c.get("r", c.get("rank", 0)), "suit": c.get("s", c.get("suit", 0))} for i, c in enumerate(hand_raw)]


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
    last = data.get("last")
    if last and not isinstance(last, dict): last = None
    who = data.get("who", PLAYER)
    role = data.get("role", "balanced")
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
            return jsonify({"ok": True, "action": None, "pattern": None, "passed": True})
        action = result["action"]
        pattern = result["pattern"]
        if round_id:
            _record_ai_step(round_id, step, {"hand_count": len(hand), "role": role}, action, pattern, who)
        return jsonify({"ok": True, "action": [{"r": c["rank"], "s": c["suit"]} for c in action], "pattern": pattern, "passed": False})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@ai_bp.route("/api/ai/hint", methods=["POST"])
def ai_hint():
    """AI 提示接口"""
    data = request.json or {}
    hand = _parse_hand(data.get("hand", []))
    last = data.get("last")
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
            cands = [c for c in cands if ai_can_beat(c, last)]
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
            best_key = sorted((c["rank"], c["suit"]) for c in best["action"])
            for i, cand in enumerate(cands):
                if sorted((c["rank"], c["suit"]) for c in cand["cards"]) == best_key:
                    cands.insert(0, cands.pop(i))
                    break
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
