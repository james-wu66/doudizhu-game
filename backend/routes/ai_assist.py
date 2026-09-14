# -*- coding: utf-8 -*-
"""
AI 复盘与问答助手 后端蓝图
路由前缀: /api/assist
红线: 不碰 routes/ai.py、backend/ai/；只新增 ai_usage 表；全量写审计。
20260908 R3: 问答=双模型(商汤主/小米备, 429自动跳+60s冷却)；复盘=本地模板引擎(零模型零token)。
"""

import os
import re
import json
import time as _time
import hashlib
import requests
from flask import Blueprint, request, jsonify
from utils import get_db, beijing_now_str

ai_assist_bp = Blueprint("ai_assist", __name__)

# === 死参数 ===
# ⚠️配额（jameswu 20260908 拍板）：20次/天(T1) + 100次/账户累计(T9)，费用锁取消。
# 单价常量仅后台展示口径（小米已核实截图价；商汤免费额度行也按此估算显示，用户拍板"都按小米记"）。
DAILY_QUOTA = 20          # 锁一：每天 review+ask 合计上限（次），超→T1
TOTAL_CAP_CALLS = 100     # 锁二：每账户累计真实调用上限（次），超→T9
LOW_BID_MULTIPLIER = 4    # 低倍叫地主阈值
ADMIN_USERS = {'本地1234', '线上1234'}   # 白名单不受两锁，仍全量写审计
PRICE_IN_PER_MTOK = 0.6   # 元/百万 input（小米价，展示用）
PRICE_OUT_PER_MTOK = 1.2  # 元/百万 output（小米价，展示用）
MODEL_TIMEOUT = (5, 30)   # 连接5秒/读取30秒（覆盖项 C9）
FAILOVER_COOLDOWN = 60    # 商汤限流后的冷却秒数，期内直接走小米

T = {
    'T1': '今天的AI次数用完啦，明天请早～',
    'T2': '这个问题小助手不会哦，咱们聊斗地主吧～',
    'T3': '我只懂斗地主相关的问题哦，其他的不太会～',
    'T4': '你还没有对局记录，先去打几把再来复盘～',
    'T6': '小助手说明书没带，稍后再试～',
    'T7': '不好意思，这个问题小助手还不明白呢',
    'T8': '登录之后才能看你的复盘哦～',
    'T9': '你的AI额度用完啦，小助手要休息一阵～',
    'T10_ASK': '哎呀，小助手刚才走神了，你稍等会儿再试试～',
}


def _review_str(n):
    return {1: '[复盘·上一局]', 3: '[复盘·三局]', 5: '[复盘·五局]'}[n]


# ============================================================
# 模型配置（13.3：config_local 优先、os.environ 兜底，绝不硬编码 key）
# 主 ASSIST_* = 商汤 token.sensenova.cn deepseek-v4-flash（2~3秒，免费额度但有TPM/RPM限流）
# 备 BACKUP_* = 小米 mm-api mimo-v2.5（6~15秒，预付按量计费）
# 主撞429→挂60秒冷却，冷却期内直接走备；到期自动回主试探。两家都挂→None→调用方降级。
# ============================================================
_fail_until = 0.0


def _cfg3(prefix):
    key = base = model = None
    try:
        import config_local  # noqa
        key = getattr(config_local, prefix + '_API_KEY', None)
        base = getattr(config_local, prefix + '_BASE_URL', None)
        model = getattr(config_local, prefix + '_MODEL', None)
    except ImportError:
        pass
    key = key or os.environ.get(prefix + '_API_KEY')
    base = base or os.environ.get(prefix + '_BASE_URL')
    model = model or os.environ.get(prefix + '_MODEL')
    return key, base, model


def _call_once(key, base, model, messages, max_tokens,
               temperature=0.7, timeout=None):
    """单次调用。返回 (content, usage)。429→(None, {'_rl':1})。
    TASK-012 模块2：加可选 temperature/timeout 参数（追问改写用 temp=0/5s），默认行为不变。"""
    try:
        resp = requests.post(
            base.rstrip('/') + '/chat/completions',
            headers={'Authorization': 'Bearer ' + key},
            json={'model': model, 'messages': messages,
                  'max_tokens': max_tokens, 'temperature': temperature, 'stream': False},
            timeout=timeout or MODEL_TIMEOUT)
        if resp.status_code == 429:
            return None, {'_rl': 1}
        if resp.status_code != 200:
            return None, None
        d = resp.json()
        content = (d['choices'][0]['message'].get('content') or '').strip()
        if not content:   # 推理模型预算烧尽返回空串 = 视为失败, 交给备胎/降级
            return None, None
        return content, (d.get('usage') or {})
    except Exception as e:
        print('[assist] _call_once 异常(%s): %s' % (type(e).__name__, str(e)[:150]), flush=True)
        return None, None


def _call_model(messages, max_tokens=300):
    """返回 (content, usage, model_used)；全挂 (None, None, None)。不重试轰炸。"""
    global _fail_until
    pkey, pbase, pmodel = _cfg3('ASSIST')
    if pkey and pbase and pmodel and _time.time() >= _fail_until:
        content, usage = _call_once(pkey, pbase, pmodel, messages, max_tokens)
        if content is not None:
            return content, usage, pmodel
        if usage and usage.get('_rl'):
            _fail_until = _time.time() + FAILOVER_COOLDOWN
    bkey, bbase, bmodel = _cfg3('BACKUP')
    if bkey and bbase and bmodel:
        content, usage = _call_once(bkey, bbase, bmodel, messages, max_tokens)
        if content is not None:
            return content, usage, bmodel
    return None, None, None


# === 知识库文件（红线 1：encoding='utf-8'；13.4：加载容错）===
_KNOWN = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge')


def _load_rules():
    try:
        with open(os.path.join(_KNOWN, 'rules.txt'), encoding='utf-8') as f:
            txt = f.read()
        return txt if txt.strip() else None
    except Exception:
        return None


def _load_blocked():
    try:
        path = os.path.join(_KNOWN, 'blocked_words.txt')
        with open(path, encoding='utf-8') as f:
            words = [w.strip() for w in f if len(w.strip()) >= 2]
        if not words:
            print('[assist] 警告: blocked_words.txt 为空，敏感词过滤降级为不拦截', flush=True)
            return None
        return set(words)
    except Exception:
        print('[assist] 警告: blocked_words.txt 读取失败，敏感词过滤降级为不拦截', flush=True)
        return None


_BLOCKED = _load_blocked()

# 斗地主术语白名单（4.2 新版全 37 词）
_GAME_WHITELIST = ['炸弹', '王炸', '炸', '四带二', '轰', '顺子', '连对', '飞机',
                   '春天', '地主', '农民', '对子', '三带一', '单张', '牌型', '加倍',
                   '明牌', '抢地主', '记牌', '算牌', '残局', '诱敌',
                   '叫地主', '底牌', '门板', '冲锋', '让牌', '压牌', '倍数', '反春',
                   '报单', '接风', '单牌', '拆牌', '控场', '首出', '顶牌']


def _blocked_hit(question):
    """整句包含即拦，只拦 ≥2 字词；白名单命中则豁免。"""
    if not _BLOCKED:
        return False
    if any(w in question for w in _GAME_WHITELIST):
        return False
    return any(w in question for w in _BLOCKED)


# === T3 领域前置过滤关键词（4.5 + V16/R2 补词）===
_DOMAIN_WORDS = [
    '牌', '地主', '农民', '王', '炸弹', '王炸', '顺子', '连对', '飞机', '三带',
    '四带', '单张', '对子', '对', '勾', '圈', '尖', '倍数', '叫', '抢', '底牌',
    '门板', '冲锋', '让牌', '压牌', '接风', '报单', '春天', '反春', '计分', '得分',
    '胜率', '复盘', '首出', '控场', '顶牌', '拆', '记牌', '算牌', '残局', '诱敌',
    '配合', '队友', '输', '赢', '斗', '会会', '加倍', '明牌', '轰', '出',
    '手', '张', '大小', '小王', '大王', 'A', 'K', 'Q', 'J', '10', '9', '8', '7',
    '6', '5', '4', '3', '2',
    # V16评测补词(20260908): 章八界面/强度类题被误拦的教训。
    # 只补精确词——"电脑/AI"这类泛词实测会放行「电脑蓝屏怎么修」破坏无关题16/16，严禁回加。
    '按钮', '提示', '越打越强', '变强', '机器人', '人工智能', '出不起', '炸',
    '底分', '总分', '局数',
]


def _domain_hit(question):
    q = question.upper()
    return any(w.upper() in q for w in _DOMAIN_WORDS)


# === 手册切片（覆盖项 C2 + 4.1 关键词表，20260908 三轮修订版）===
_CHAPTER_KEYWORDS = {
    '一': ['牌型', '单张', '对子', '三带一', '顺子', '连对', '飞机', '炸弹', '王炸', '四带二', '几副'],
    '二': ['叫地主', '抢地主', '倍数'],
    '三': ['计分', '得分', '倍数', '春天', '反春', '结算', '怎么分', '底分'],  # 结算/怎么分/底分=V16#33补路由
    '四': ['农民', '配合', '压牌', '让牌', '送牌', '队友'],
    '五': ['地主', '首出', '控场'],
    '六': ['残局', '诱敌', '拆牌', '拆'],
    '七': ['误区', '错误', '新手', '常见'],
    '八': ['AI', '电脑', '机器人', '难度', '明牌', '加倍'],
    '九': ['记牌', '算牌', '概率', '剩余牌'],
    '十': ['术语', '规则说明', '勾', '圈', '尖'],
}


def _split_chapters(rules_text):
    """返回 [(章号, 章全文)]，按 '## 一、' 级标题切（草稿章标题是两级 #）。"""
    parts = re.split(r'(?m)^#{1,2} ', rules_text)
    chapters = []
    for p in parts[1:]:
        head = p.split('\n', 1)[0].rstrip('\r')
        m = re.match(r'([一二三四五六七八九十]+)、', head)
        if m:
            chapters.append((m.group(1), '## ' + p.rstrip()))
    return chapters


def _slice_rules(question):
    """返回 (切片文本, 命中章列表, note)。无命中→全文兜底 note='full_fallback'。"""
    rules = _load_rules()
    if not rules:
        return None, [], ''
    chapters = _split_chapters(rules)
    hit = [num for num, _ in chapters
           if any(kw in question for kw in _CHAPTER_KEYWORDS.get(num, []))]
    if hit:
        text = '\n\n'.join(body for num, body in chapters if num in hit)
        return text, hit, ''
    return rules, [], 'full_fallback'


# === TASK-012 模块2：多轮追问改写（只调小米备胎，temp 0 / max_tokens 60 / 超时5秒）===
# 指示词表（12 词 ≤ 20 上限）；触发条件=命中任一词 且 history 非空。
# 改写结果只用于检索与缓存 key，送回答模型的仍是原始问题；失败静默走原问题不重试。
_QR_WORDS = ['它', '他', '这', '这个', '这些', '那', '那个', '那样',
             '上面', '刚才', '再来', '还有']


def _rewrite_question(q, hist):
    """返回 (用于检索的问题, qr标记)。未触发返回 (q, '')；失败返回 (q, 'qr_fail')。"""
    try:
        if not any(w in q for w in _QR_WORDS) or not hist:
            return q, ''
        ctx = '\n'.join('- ' + str(h.get('q', ''))[:80]
                        for h in hist[-2:]
                        if isinstance(h, dict) and h.get('q'))
        if not ctx:
            return q, ''
        prompt = ('根据对话历史，把最后的问题改写成一个不依赖上下文、可独立检索的完整问题'
                  '（保持斗地主领域用词）。只输出改写后的问题，不要任何解释。\n'
                  '历史提问：\n%s\n最后的问题：%s' % (ctx, q))
        # 通道选择：优先主模型（qwen，快且稳），失败回退备胎（商汤429频发）。
        # 偏离任务书"调小米备胎"的原因：小米中转 500 全灭、商汤限流频发，主通道反而最稳。
        for prefix in ('ASSIST', 'BACKUP'):
            k, b, m = _cfg3(prefix)
            if not (k and b and m):
                continue
            content, _u = _call_once(k, b, m,
                                     [{'role': 'user', 'content': prompt}],
                                     max_tokens=1024, temperature=0, timeout=(5, 15))
                                    # max_tokens 1024：qwen3.8-flash 为思考型模型，60 会秒回400/思考烧尽返空；输出校验仍限40字
            if content:
                break
        else:
            return q, 'qr_fail'
        content = (content or '').strip().strip('"“”')
        if not content or len(content) > 40 or '\n' in content:
            return q, 'qr_fail'
        return content, 'qr_ok'
    except Exception:
        return q, 'qr_fail'


# === TASK-012 模块3：引用出处服务端校验（防幻觉核心）===
# 章号必须属于本次检索实际命中的章号集合；不在集合→剥掉后缀+cite_none，在→cite:章号。
# 任何异常→原样返回（降级不 500）。
_CITE_RE = re.compile(r'（依据[:：]\s*([^）]{1,80})）\s*$')


def _validate_citation(answer, hit_chapters):
    """返回 (answer, cite标记)。cite标记∈{'', 'cite:章号', 'cite_none'}。"""
    try:
        m = _CITE_RE.search(answer)
        if not m:
            return answer, ''
        inner = m.group(1)
        cands = set(re.findall(r'[一二三四五六七八九十]+|\d+', inner))
        ok = cands & set(hit_chapters or ())
        if ok:
            return answer, 'cite:' + sorted(ok, key=lambda x: -len(x))[0]
        return answer[:m.start()].rstrip(), 'cite_none'
    except Exception:
        return answer, ''


# === 数据库通用（红线 2：_openid 双保险；本地 sqlite 走 ? 占位）===
def _is_sqlite():
    try:
        import pymysql  # noqa
    except ImportError:
        return True
    from utils import USE_MYSQL
    return not USE_MYSQL


def _exec(conn, sql, params=None):
    cur = conn.cursor()
    if _is_sqlite():
        cur.execute(sql.replace('%s', '?'), params)
    else:
        cur.execute(sql, params)
    return cur


def _fetchall(conn, sql, params=None):
    cur = _exec(conn, sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def _insert_usage(user_name, kind, session_id, question, answer, tokens_in,
                  tokens_out, cached, feedback='', blocked=0, cache_key=None,
                  note='', cost=0.0):
    """写 ai_usage 一行。MySQL 先带 _openid、失败(1364)回退不带。返回行 id。"""
    fields = {
        'user_name': user_name, 'kind': kind, 'session_id': session_id,
        'question': question, 'answer': answer,
        'tokens': int(tokens_in or 0) + int(tokens_out or 0),  # 任务书4.4: 真实total_tokens
        'cached': cached, 'feedback': feedback, 'blocked': blocked,
        'cache_key': cache_key, 'note': note, 'cost': cost,
        'created_at': beijing_now_str(),
    }
    cols = list(fields.keys())
    vals = [fields[c] for c in cols]
    conn = get_db()
    try:
        if _is_sqlite():
            sql = "INSERT INTO ai_usage (%s) VALUES (%s)" % (
                ','.join(cols), ','.join('?' * len(cols)))
            cur = conn.cursor().execute(sql, vals)
            rid = cur.lastrowid
        else:
            # 注意：pymysql 的 execute() 返回 int(rowcount) 而非 cursor，
            # 不能链式取 .lastrowid（会 AttributeError → 审计行 id 丢失返回 0）。
            # 必须先拿 cursor 对象再单独 execute。
            cur = conn.cursor()
            try:
                sql = "INSERT INTO ai_usage (%s,_openid) VALUES (%s)" % (
                    ','.join(cols), ','.join(['%s'] * (len(cols) + 1)))
                cur.execute(sql, vals + [''])
            except Exception:
                sql = "INSERT INTO ai_usage (%s) VALUES (%s)" % (
                    ','.join(cols), ','.join(['%s'] * len(cols)))
                cur = conn.cursor()
                cur.execute(sql, vals)
            rid = cur.lastrowid
        try:
            conn.commit()  # sqlite 非 autocommit；mysql 分支 autocommit=True 重复 commit 无害
        except Exception:
            pass
        return rid
    except Exception as e:
        print('[assist] 审计写入失败:', e, flush=True)
        return 0


# === 身份：token 反查（第六节终审：绝不信任前端自报 user_name）===
def _lookup_user(token):
    if not token:
        return None
    conn = get_db()
    rows = _fetchall(conn, "SELECT name FROM users WHERE token = %s", (token,))
    return rows[0]['name'] if rows else None


def _identify(data):
    token = data.get('token') or ''
    claimed = (data.get('user_name') or '').strip()
    real = _lookup_user(token)
    if real is None:
        return None, None
    if claimed and claimed != real:
        _insert_usage(real, 'ask', '', '[冒名:' + claimed[:20] + ']',
                      'forbidden', 0, 0, 2, blocked=1, note='impersonation')
        return None, (jsonify({'ok': False, 'error': 'forbidden'}), 403)
    return real, None


# === 查询限流（TASK-010 包B 第六节1：同一账户+同IP 双维度，ask 每分钟 ≤6 次）===
# 滑动窗口计数存内存 dict，进程重启清零可接受。超限返回 T1 同款话术的 200 响应，
# 不泄露"你在被限流"，并审计一行 note=rate_limited。
_RL_WINDOW = 60.0
_RL_LIMIT = 6
_rl_by_user = {}
_rl_by_ip = {}


def _rate_limited(user_name):
    """True=已超限。仅统计 ask，超限不追加计数（避免长挂时越限越久）。"""
    now = _time.time()
    ip = request.remote_addr or 'unknown'

    def prune(d, key):
        lst = [t for t in d.get(key, []) if now - t < _RL_WINDOW]
        d[key] = lst
        return lst

    if len(prune(_rl_by_user, user_name)) >= _RL_LIMIT or \
       len(prune(_rl_by_ip, ip)) >= _RL_LIMIT:
        return True
    _rl_by_user.setdefault(user_name, []).append(now)
    _rl_by_ip.setdefault(ip, []).append(now)
    return False


# === 配额双封顶（第七节 + 20260908 新规）===
def _today_calls(user_name):
    conn = get_db()
    # R3: 复盘已模板化(零模型零token)不再计配额, 只有真调模型的问答计数
    rows = _fetchall(conn,
        "SELECT COUNT(*) c FROM ai_usage WHERE user_name=%s AND kind='ask' AND cached=0 "
        "AND blocked=0 AND substr(created_at,1,10)=substr(%s,1,10)",
        (user_name, beijing_now_str()))
    return rows[0]['c'] if rows else 0


def _total_paid_calls(user_name):
    """账户全历史真实调用模型的次数（只有 ask 计入; review=引擎零成本）。"""
    conn = get_db()
    rows = _fetchall(conn,
        "SELECT COUNT(*) c FROM ai_usage WHERE user_name=%s AND kind='ask' AND cached=0 AND blocked=0",
        (user_name,))
    return int(rows[0]['c'] or 0) if rows else 0


def _quota_check(user_name):
    """返回 (ok, 降级话术 or None)。"""
    if user_name in ADMIN_USERS:
        return True, None
    if _total_paid_calls(user_name) >= TOTAL_CAP_CALLS:
        return False, 'T9'
    if _today_calls(user_name) >= DAILY_QUOTA:
        return False, 'T1'
    return True, None


def _cost_of(usage):
    if not usage:
        return 0.0, 0, 0
    ti = int(usage.get('prompt_tokens') or 0)
    to = int(usage.get('completion_tokens') or 0)
    tot = int(usage.get('total_tokens') or 0) or (ti + to)
    if ti or to:
        cost = ti / 1e6 * PRICE_IN_PER_MTOK + to / 1e6 * PRICE_OUT_PER_MTOK
    else:
        cost = tot / 1e6 * PRICE_IN_PER_MTOK
    return cost, tot, ti + to


# === 对局数据（施工图 §6 口径）===
def _fetch_games(user_name, limit=None):
    conn = get_db()
    sql = ("SELECT id, result, role, bid_score, score_change, ai_decisions, created_at "
           "FROM game_records WHERE user_name=%s ORDER BY created_at DESC, id DESC")
    if limit:
        sql += " LIMIT " + str(int(limit))
    return _fetchall(conn, sql, (user_name,))


def _calc_rounds(arr):
    rounds, my_plays, last = 0, 0, None
    for m in arr:
        t = m.get('type')
        if t == 'play':
            if m.get('player') == 0:
                my_plays += 1
            if last != 'play':
                rounds += 1
            last = 'play'
        elif t == 'pass':
            last = 'pass'
    return rounds, my_plays


# ============================================================
# 复盘模板引擎（20260908 R3 jameswu 拍板：不调模型、数字全真、句式人写）
# 句库 review_lines.json；所有占位符缺数=整句弃用（宁缺不假）。
# ============================================================
_RL = None


def _review_lines():
    global _RL
    if _RL is not None:
        return _RL or None
    try:
        with open(os.path.join(_KNOWN, 'review_lines.json'), encoding='utf-8') as f:
            _RL = json.load(f)
    except Exception:
        print('[assist] 警告: review_lines.json 读取失败, 复盘走直出兜底', flush=True)
        _RL = False
    return _RL or None


def _fill(s, f):
    out = s
    for ph in set(re.findall(r'\{([^}]+)\}', s)):
        v = f.get(ph)
        if v is None or v == '':
            return None
        out = out.replace('{' + ph + '}', str(v))
    return out


def _pick(user_name, n, total, sid, f):
    """先筛出当前数据可完整填充的句池, 再按 用户+局数+场景+当天 哈希从池中取——
    均匀不塌缩；同一天内稳定(保缓存语义), 隔天自动换变体。"""
    rl = _review_lines()
    if not rl or sid not in rl['scenes']:
        return None
    pool = [s for s in rl['scenes'][sid]['variants'] if _fill(s, f)]
    if not pool:
        return None
    day = beijing_now_str()[:10]
    idx = int(hashlib.md5(('%s|%s|%d|%d|%s' % (user_name, sid, n, total, day)).encode('utf-8')).hexdigest()[:6], 16) % len(pool)
    return _fill(pool[idx], f)


def _game_scan(g):
    """逐局扫描，全部数字来自 ai_decisions 真实回放。"""
    try:
        arr = json.loads(g['ai_decisions']) if g['ai_decisions'] else []
    except Exception:
        arr = []
    ll = next((m.get('player') for m in arr if m.get('type') == 'landlord'), None)
    rounds, my_plays = _calc_rounds(arr)
    out = dict(ll=ll, rounds=rounds, plays=my_plays,
               landlord_opens=0, top_cnt=0, first_top=None,
               early_big=None, press_mate=None, opp_play=False, ll_play=False)
    last_was_play = True
    prev_play = None
    rnd = 0
    third = max(1, rounds // 3) if rounds else 0
    for m2 in arr:
        t = m2.get('type')
        if t not in ('play', 'pass'):
            continue
        if t == 'play':
            if last_was_play:
                rnd += 1
                prev_play = None
            last_was_play = True
            p, pat, cards = m2.get('player'), m2.get('pattern') or '', m2.get('cards') or ''
            if p == ll:
                out['landlord_opens'] += 1
                out['ll_play'] = True
            elif p == 0:
                pass
            else:
                out['opp_play'] = True
            if p == 0 and ll is not None and prev_play and prev_play[0] == ll:
                out['top_cnt'] += 1
                if out['first_top'] is None:
                    out['first_top'] = (rnd, cards or pat)
            if (p == 0 and prev_play and ll is not None
                    and prev_play[0] not in (0, ll) and out['press_mate'] is None):
                out['press_mate'] = (rnd, prev_play[2] or prev_play[1], prev_play[1],
                                     cards, pat)
            is_bomb_early = pat in ('炸弹', '王炸') and third and rnd <= third
            is_big_single = pat == '单张' and ('2' in cards or '王' in cards) and third and rnd <= third
            if p == 0 and out['early_big'] is None and (is_bomb_early or is_big_single):
                out['early_big'] = (rnd, cards or pat, pat)
            prev_play = (p, pat, cards)
        else:
            last_was_play = False
    return out


def _seat_cn(g, ll):
    if g['role'] in ('landlord', '地主'):
        return '地主'
    return '门板（地主上家）' if ll == 2 else '冲锋（地主下家）'


def _scene_single(user_name, g, total):
    """上一局场景路由（只走人工可核对的高置信规则；没把握的局走中性套）。"""
    sc = _game_scan(g)
    my_landlord = g['role'] in ('landlord', '地主')
    won = g['result'] == 'win'
    bid, score = g['bid_score'] or 0, abs(g['score_change'] or 0)
    f = {'B': bid or None, 'S': score or None, 'R': sc['rounds'] or None,
         'H': sc['plays'] or None, 'SEAT': _seat_cn(g, sc['ll'])}
    if my_landlord:
        if won and not sc['opp_play']:
            return 'S5', f
        if (not won) and not sc['ll_play']:
            return 'S6', f
        if won:
            return ('S1' if sc['rounds'] <= 8 else 'S2'), f
        if 0 < bid <= LOW_BID_MULTIPLIER:
            return 'S3', f
        if sc['early_big']:
            f['X'], f['C'] = sc['early_big'][0], sc['early_big'][1]
            f['P'] = sc['early_big'][2]
            f['REM'] = max(1, sc['rounds'] - sc['early_big'][0])
            return 'S4', f
        return 'S13', f
    if won:
        if sc['ll'] == 2 and sc['first_top']:
            f['X'], f['C'] = sc['first_top']
            f['T'], f['K'] = sc['top_cnt'], sc['landlord_opens']
            return 'S7', f
        if sc['ll'] == 1 and sc['first_top']:
            f['X'], f['C'] = sc['first_top']
            return 'S10', f
        return 'S23', f
    if sc['press_mate']:
        f['X'], f['MC'], f['MP'], f['C'], f['P'] = sc['press_mate']
        f['REM'] = max(1, sc['rounds'] - sc['press_mate'][0])
        return 'S11', f
    return 'S24', f


def _scene_multi(user_name, subset, n, total):
    """近N局场景路由。低置信槽位一律留 None 由 _fill 弃句兜底。"""
    scans = [(_game_scan(g), g) for g in subset]
    wins = sum(1 for _, g in scans if g['result'] == 'win')
    losses = len(subset) - wins
    net = sum((g['score_change'] or 0) for _, g in scans)
    smin = min([(g['score_change'] or 0) for _, g in scans] + [0])
    smax = max([(g['score_change'] or 0) for _, g in scans] + [0])
    fw = sum(1 for sc, g in scans if g['result'] == 'win' and g['role'] not in ('landlord', '地主'))
    lw = sum(1 for sc, g in scans if g['result'] == 'win' and g['role'] in ('landlord', '地主'))
    fl = sum(1 for sc, g in scans if g['result'] == 'lose' and g['role'] in ('landlord', '地主'))
    greedy = sum(1 for sc, g in scans if g['result'] == 'lose' and g['role'] in ('landlord', '地主')
                 and 0 < (g['bid_score'] or 0) <= LOW_BID_MULTIPLIER)
    press_n = sum(1 for sc, g in scans if g['result'] == 'lose' and sc['press_mate'])
    early_n = sum(1 for sc, g in scans if g['result'] == 'lose'
                  and sc['early_big'] and g['role'] in ('landlord', '地主'))
    err_name, err_cnt = '', 0
    for nm, cnt in (('贪叫', greedy), ('压队友', press_n), ('大牌早放', early_n)):
        if cnt > err_cnt:
            err_name, err_cnt = nm, cnt
    rl = _review_lines() or {}
    tips = rl.get('tips', {})
    tip_key = {'贪叫': 'R2', '压队友': 'R1', '大牌早放': 'R4'}.get(err_name)
    fastest = [sc['rounds'] for sc, g in scans if g['result'] == 'win' and sc['rounds']]
    avg = round(sum(sc['rounds'] for sc, _ in scans) / max(1, len(scans)), 1)
    f = {'label': ('近3局' if n == 3 else '近5局'), '胜': wins, '负': losses,
         'S': net if net > 0 else abs(net), 'W': round(wins / max(1, len(subset)) * 100, 1),
         'FW': fw or None, 'LW': lw or None, 'FL': fl or None,
         'K': greedy or None, 'X': (min(fastest) if fastest else None),
         'Smax': smax if smax > 0 else None, 'Smin': abs(smin) if smin < 0 else None,
         'SL': abs(sum(min(0, (g['score_change'] or 0)) for _, g in scans)) or None,
         'R': avg, 'E': err_cnt if err_cnt >= 2 else None,
         '错误类型': err_name if err_cnt >= 2 else None,
         '配对建议': tips.get(tip_key) if err_cnt >= 2 else None}
    if losses == len(subset):
        return 'S20', f
    if wins == len(subset):
        return ('S14' if n == 3 else 'S18'), f
    if greedy >= 2:
        return 'S19', f
    if err_cnt >= 2:
        return 'S15', f
    if fl >= 2 and fw >= 1:
        return 'S16', f
    if wins > losses and smin <= -48:
        return 'S17', f
    return ('S14' if n == 3 else 'S18'), f


def _engine_fallback(user_name, n, games):
    """句库不可用/全缺数时的纯事实安全句（所有数字必有）。"""
    subset = games[:n]
    wins = sum(1 for g in subset if g['result'] == 'win')
    net = sum((g['score_change'] or 0) for g in subset)
    if n == 1:
        g = subset[0]
        sc = _game_scan(g)
        res = '赢了%d分' % g['score_change'] if (g['score_change'] or 0) > 0 else '输了%d分' % abs(g['score_change'] or 0)
        return '上一局你坐%s，%s，全局%d轮你出手%d手。我逐轮数过没抓到明显失误，保持这个状态。' % (
            _seat_cn(g, sc['ll']), res, sc['rounds'], sc['plays'])
    return '近%d局%d胜%d负，净%s%d分。逐局数过没有同类失误扎堆，按自己的节奏继续打。' % (
        n, wins, n - wins, '-' if net < 0 else '+', abs(net))


def _gen_review(user_name, n):
    """复盘模板引擎。返回 (answer, usage=None, note='engine:Sx')。"""
    games = _fetch_games(user_name)
    if not games:
        return T['T4'], None, ''
    total = len(games)
    try:
        if n == 1:
            sid, f = _scene_single(user_name, games[0], total)
        else:
            sid, f = _scene_multi(user_name, games[:n], n, total)
        ans = _pick(user_name, n, total, sid, f)
        if ans:
            return ans, None, 'engine:' + sid
    except Exception as e:
        print('[assist] 复盘引擎异常(走兜底):', e, flush=True)
    return _engine_fallback(user_name, n, games), None, 'engine:fallback'


def _cache_get(key):
    conn = get_db()
    rows = _fetchall(conn,
        "SELECT id, answer FROM ai_usage WHERE cache_key=%s AND cached=0 AND blocked=0 "
        "ORDER BY id DESC LIMIT 1", (key,))
    return rows[0] if rows else None


def _today_games_count(user_name):
    conn = get_db()
    rows = _fetchall(conn,
        "SELECT COUNT(*) c FROM game_records WHERE user_name=%s "
        "AND substr(created_at,1,10)=substr(%s,1,10)",
        (user_name, beijing_now_str()))
    return rows[0]['c'] if rows else 0


# ============================================================
# A1 复盘（模板引擎版：零模型、零 token、秒出）
# ============================================================
@ai_assist_bp.route('/api/assist/review', methods=['POST'])
def review():
    data = request.get_json(silent=True) or {}
    real, resp = _identify(data)
    if resp:
        return resp
    n = data.get('n', 1)
    if n not in (1, 3, 5):
        n = 1
    question = _review_str(n)
    if real is None:
        rid = _insert_usage('游客', 'review', '', question, T['T8'], 0, 0, 2, note='guest')
        return jsonify({'ok': True, 'degraded': True, 'type': 'no_record',
                        'answer': T['T8'], 'usage_id': rid})
    okq, tcode = _quota_check(real)
    if not okq:
        rid = _insert_usage(real, 'review', '', question, T[tcode], 0, 0, 2)
        return jsonify({'ok': True, 'degraded': True, 'type': 'no_model',
                        'answer': T[tcode], 'usage_id': rid})
    key = 'rv4|%s|%s|%d|%d' % (real, beijing_now_str()[:10], _today_games_count(real), n)
    hit = _cache_get(key)
    if hit:
        all_g = _fetch_games(real)
        m = len(all_g)
        hint = '你目前只有 %d 局，已为你复盘全部 %d 局' % (m, min(n, m)) if 0 < m < n else ''
        rid = _insert_usage(real, 'review', '', question, hit['answer'],
                            0, 0, 1, cache_key=key, note='cache_hit')
        return jsonify({'ok': True, 'answer': hit['answer'], 'tokens': 0,
                        'cached': True, 'usage_id': rid, 'hint': hint})
    games = _fetch_games(real)
    if not games:
        rid = _insert_usage(real, 'review', '', question, T['T4'], 0, 0, 2, note='no_record')
        return jsonify({'ok': True, 'degraded': True, 'type': 'no_record',
                        'answer': T['T4'], 'usage_id': rid})
    m = len(games)
    hint = '你目前只有 %d 局，已为你复盘全部 %d 局' % (m, min(n, m)) if m < n else ''
    answer, usage, note = _gen_review(real, n)
    rid = _insert_usage(real, 'review', data.get('session_id', ''), question,
                        answer, 0, 0, 0, cache_key=key, note=note, cost=0.0)
    return jsonify({'ok': True, 'answer': answer, 'tokens': 0,
                    'cached': False, 'usage_id': rid, 'hint': hint})


# ============================================================
# A2 问答（双模型：商汤主 / 小米备）
# ============================================================
def _ask_sys():
    # TASK-012 模块3（三期唯一授权改动系统提示词）：手册口径的回答末尾带出处后缀，
    # 服务端会校验章号（_validate_citation），编造的引用会被剥掉，模型不敢乱写。
    return (
        '你是"会会斗地主"游戏里的斗地主小助手。只回答斗地主规则、打法、配合、计分、'
        '本项目玩法相关的问题，其他话题一律拒答。回答必须以下面的《官方规则与战术手册》'
        '（节选或全文）为准：手册有口径的按手册答；手册没有而属通用斗地主常识的可答；'
        '既没口径又没常识的回答「不好意思，这个问题小助手还不明白呢」。'
        '若回答内容出自手册，在回答最末尾追加一条出处后缀，格式：（依据：官方手册、章名 · x.y节），'
        '最多一条，章名用手册里的实际章名，节号按手册实际编号；手册没有明确口径的'
        '通用常识回答不加出处；不确定就不要加，严禁编造出处。'
        '正文不超过120字（出处后缀不计入），口语化，一句一个意思，不用列表，不反问；'
        '除这条出处后缀外，回答里禁止出现"依据""手册"等引用字样，禁止提"通用规则"这类标签。')


@ai_assist_bp.route('/api/assist/ask', methods=['POST'])
def ask():
    data = request.get_json(silent=True) or {}
    q = (data.get('question') or '').strip()[:200]
    if not q:
        return jsonify({'ok': False, 'error': 'empty question'})
    real, resp = _identify(data)
    if resp:
        return resp
    if real is None:
        real = '游客'  # A2 唯一游客例外（第六节）
    session_id = data.get('session_id', '')

    def audit(cached, blocked=0, answer='', tokens_in=0, tokens_out=0,
              cache_key=None, note='', cost=0.0):
        return _insert_usage(real, 'ask', session_id, q, answer, tokens_in,
                             tokens_out, cached, blocked=blocked,
                             cache_key=cache_key, note=note, cost=cost)

    # 0) 查询限流（TASK-010 包B 第六节1：第7次/分钟命中 rate_limited，T1 同款话术不泄露限流细节）
    if _rate_limited(real):
        rid = audit(2, answer=T['T1'], note='rate_limited')
        return jsonify({'ok': True, 'degraded': True, 'type': 'no_model',
                        'answer': T['T1'], 'tokens': 0, 'usage_id': rid})
    # 0.5) 追问改写（TASK-012 模块2：指示词+history 非空才触发，只调小米备胎 temp0/60tok/5s。
    #      必须在领域门之前算好 q_search——任务书硬题第2轮"它是怎么触发的"原问题不含领域词，
    #      领域门若只看原问题则永远 T3 拦死、改写无从生效；故领域门对原问题或改写问题任一放行。
    #      _domain_hit 函数与词表零改动；敏感词仍只看原始问题；改写失败静默走原问题不重试；
    #      改写调用费并入本次 ask 同行 ai_usage 的 cost，配额仍按 1 次计。）
    hist = (data.get('history') or [])[-2:]
    q_search, qr_note = _rewrite_question(q, hist)
    # 1) T3 领域前置过滤（原问题或改写问题任一命中领域即放行；记 cached=2 审计）
    if not (_domain_hit(q) or _domain_hit(q_search)):
        rid = audit(2, answer=T['T3'],
                    note=';'.join([x for x in ('out_of_domain', qr_note) if x]))
        return jsonify({'ok': True, 'degraded': True, 'type': 'blocked',
                        'answer': T['T3'], 'tokens': 0, 'usage_id': rid})
    # 2) 敏感词（红线 9，T2）
    if _blocked_hit(q):
        rid = audit(2, blocked=1, answer=T['T2'])
        return jsonify({'ok': True, 'blocked': True, 'answer': T['T2'],
                        'tokens': 0, 'usage_id': rid})
    # 3) 配额/费用
    okq, tcode = _quota_check(real)
    if not okq:
        rid = audit(2, answer=T[tcode])  # T1/T9 均记一行 cached=2（第七节）
        return jsonify({'ok': True, 'degraded': True, 'type': 'no_model',
                        'answer': T[tcode], 'tokens': 0, 'usage_id': rid})
    # 4) 缓存（4.9: ak|user|date|today_games|md5(q)[:12]；TASK-009 升 ak2|；
    #    TASK-012 模块2 升 ak3|——缓存 key 改为基于改写后问题计算，防新旧语义互相污染）
    md5 = hashlib.md5(q_search.encode('utf-8')).hexdigest()[:12]
    key = 'ak3|%s|%s|%d|%s' % (real, beijing_now_str()[:10],
                               _today_games_count(real) if real != '游客' else 0, md5)
    hit = _cache_get(key)
    if hit:
        rid = audit(1, answer=hit['answer'], cache_key=key, note='cache_hit')
        return jsonify({'ok': True, 'answer': hit['answer'], 'tokens': 0,
                        'cached': True, 'usage_id': rid})
    # 5) 手册切片（TASK-009 包A：向量+BM25 混合检索优先；任何异常回退旧 _slice_rules，链路不报错）
    rules = _load_rules()
    if not rules:
        rid = audit(2, answer=T['T6'], cache_key=key, note='no_rules')
        return jsonify({'ok': True, 'degraded': True, 'type': 'no_model',
                        'answer': T['T6'], 'tokens': 0, 'usage_id': rid})
    rag_hits = None
    kw_note = ''
    try:
        from ai_kb import retriever
        sliced, rag_hits = retriever.hybrid_search(q_search)
    except Exception as e:
        print('[assist] rag 检索失败, 回退关键词路由:', type(e).__name__, e, flush=True)
        sliced, rag_hits = None, None
    hit_chapters = set()
    if rag_hits is not None:
        hits = []
        hit_chapters = {h.split('#')[1] for h in rag_hits if '#' in h}
    else:
        sliced, hits, kw_note = _slice_rules(q_search)
        hit_chapters = set(hits)
    # 6) 模型（多轮：只带最近 2 轮用户问题，V7；送回答模型的仍是原始问题+原始历史）
    ctx = ''
    for h in hist:
        if isinstance(h, dict) and h.get('q'):
            ctx += '历史提问: %s\n' % str(h['q'])[:80]
    msg = [{'role': 'system', 'content': _ask_sys() + '\n《手册》节选开始——\n'
            + (sliced or rules)[:16000] + '\n——手册结束。'}]
    if ctx:
        msg.append({'role': 'user', 'content': ctx + '本次提问：' + q})
    else:
        msg.append({'role': 'user', 'content': q})
    content, usage, used = _call_model(msg)
    if content is None:
        rid = audit(2, answer=T['T10_ASK'], cache_key=key,
                    note=';'.join([x for x in ('model_fail', qr_note) if x]))
        return jsonify({'ok': True, 'degraded': True, 'type': 'no_model',
                        'answer': T['T10_ASK'], 'tokens': 0, 'usage_id': rid})
    answer = content.strip()
    # 6.5) 引用出处服务端校验（TASK-012 模块3：章号不在命中集合→剥掉后缀，用户永远看不到编造引用）
    answer, cite_note = _validate_citation(answer, hit_chapters)
    cost, tot, _ = _cost_of(usage)
    # note 预算重排（模块3：模型归属 > qr/cite 标记 > rag 命中列表截 2 个），总长截 255
    flags = [x for x in (qr_note, cite_note) if x]
    note = (used or '?') + (';' + ';'.join(flags) if flags else '')
    if rag_hits is not None:
        note += ';rag:' + ','.join(rag_hits[:2])[:60]
    else:
        note += ';' + (kw_note or 'rag_fallback')
    note = note[:255]
    rid = audit(0, answer=answer, cache_key=key, note=note, cost=cost,
                tokens_in=(usage or {}).get('prompt_tokens', 0),
                tokens_out=(usage or {}).get('completion_tokens', 0))
    return jsonify({'ok': True, 'answer': answer, 'tokens': tot,
                    'cached': False, 'usage_id': rid, 'blocked': False})


# ============================================================
# A3 反馈
# ============================================================
@ai_assist_bp.route('/api/assist/feedback', methods=['POST'])
def feedback():
    data = request.get_json(silent=True) or {}
    real, resp = _identify(data)
    if resp:
        return resp
    if real is None:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    vote = data.get('vote')
    uid = data.get('usage_id')
    if vote not in ('up', 'down') or not uid:
        return jsonify({'ok': False, 'error': 'bad params'})
    conn = get_db()
    rows = _fetchall(conn, "SELECT id, feedback, user_name FROM ai_usage WHERE id=%s", (uid,))
    if not rows:
        return jsonify({'ok': False, 'error': 'not_found'})
    if rows[0]['user_name'] != real:
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    if (rows[0]['feedback'] or '') != '':
        return jsonify({'ok': False, 'error': 'already_voted'})
    _exec(conn, "UPDATE ai_usage SET feedback=%s WHERE id=%s AND feedback=''", (vote, uid))
    try:
        conn.commit()
    except Exception:
        pass
    return jsonify({'ok': True})


# ============================================================
# A4/A5/A6 管理后台（全部 POST，token 进 body；非白名单 403）
# ============================================================
def _require_admin(data):
    real, resp = _identify(data)
    if resp:
        return None, resp
    if real is None:
        return None, (jsonify({'ok': False, 'error': 'unauthorized'}), 401)
    if real not in ADMIN_USERS:
        return None, (jsonify({'ok': False, 'error': 'forbidden'}), 403)
    return real, None


_STATUS_MAP = {'paid': 'cached=0', 'cache': 'cached=1', 'degraded': 'cached=2',
               'blocked': 'blocked=1', 'whitelist': "user_name IN (%s)" %
               ','.join("'" + u + "'" for u in sorted(ADMIN_USERS))}


@ai_assist_bp.route('/api/assist/admin/summary', methods=['POST'])
def admin_summary():
    data = request.get_json(silent=True) or {}
    _, resp = _require_admin(data)
    if resp:
        return resp
    today = beijing_now_str()[:10]
    conn = get_db()

    def one(sql, params=()):
        rows = _fetchall(conn, sql, params)
        return rows[0] if rows else {}
    total = one("SELECT COUNT(*) c FROM ai_usage WHERE substr(created_at,1,10)=%s", (today,))
    paid = one("SELECT COUNT(*) c FROM ai_usage WHERE substr(created_at,1,10)=%s AND cached=0 AND blocked=0", (today,))
    toks = one("SELECT COALESCE(SUM(tokens),0) s FROM ai_usage WHERE substr(created_at,1,10)=%s AND cached=0 AND blocked=0", (today,))
    down = one("SELECT COUNT(*) c FROM ai_usage WHERE substr(created_at,1,10)=%s AND feedback='down'", (today,))
    blocked = one("SELECT COUNT(*) c FROM ai_usage WHERE substr(created_at,1,10)=%s AND blocked=1", (today,))
    cost = one("SELECT COALESCE(SUM(cost),0) s FROM ai_usage WHERE substr(created_at,1,10)=%s", (today,))
    return jsonify({'ok': True,
                    'today_calls': total.get('c', 0),
                    'today_paid': paid.get('c', 0),
                    'today_tokens': toks.get('s', 0),
                    'today_down': down.get('c', 0),
                    'today_blocked': blocked.get('c', 0),
                    'cost_estimate': '¥%.4f（按官方价估算，实际以中转站为准）' % (cost.get('s', 0) or 0)})


@ai_assist_bp.route('/api/assist/admin/sessions', methods=['POST'])
def admin_sessions():
    data = request.get_json(silent=True) or {}
    _, resp = _require_admin(data)
    if resp:
        return resp
    where, params = ['1=1'], []
    if data.get('user'):
        where.append('user_name LIKE %s'); params.append('%' + str(data['user']) + '%')
    if data.get('kind') in ('ask', 'review'):
        where.append('kind=%s'); params.append(data['kind'])
    if data.get('date_from'):
        where.append('substr(created_at,1,10)>=%s'); params.append(str(data['date_from']))
    if data.get('date_to'):
        where.append('substr(created_at,1,10)<=%s'); params.append(str(data['date_to']))
    if data.get('status') in _STATUS_MAP:
        where.append(_STATUS_MAP[data['status']])
    sql = ("SELECT id, user_name, kind, session_id, question, answer, tokens, cached, "
           "feedback, blocked, cost, note, created_at FROM ai_usage WHERE "
           + ' AND '.join(where) + " ORDER BY id DESC LIMIT 5000")
    conn = get_db()
    rows = _fetchall(conn, sql, tuple(params))
    truncated = len(rows) >= 5000
    return jsonify({'ok': True, 'sessions': rows, 'truncated': truncated})


@ai_assist_bp.route('/api/assist/admin/topusers', methods=['POST'])
def admin_topusers():
    data = request.get_json(silent=True) or {}
    _, resp = _require_admin(data)
    if resp:
        return resp
    conn = get_db()
    rows = _fetchall(conn,
        "SELECT user_name, COUNT(*) calls FROM ai_usage "
        "WHERE substr(created_at,1,10)=%s GROUP BY user_name ORDER BY calls DESC LIMIT 10",
        (beijing_now_str()[:10],))
    return jsonify({'ok': True, 'top': rows})


# ============================================================
# TASK-013 差评回流与知识改进队列
# 红线：只读消费 ai_usage（feedback 列既有写入逻辑不动，禁止 UPDATE/DELETE 历史行）；
# 状态存 kb_badcase 新表（懒插入）；聚合实时算（差评量级<1000 无需定时任务）。
# 管理接口走 auth_utils.require_admin（token 反查 + role=admin 双重校验，包B role 列已上线）。
# ============================================================
_BADCASE_STATUSES = ('open', 'in_progress', 'resolved', 'wontfix')


def _norm_question(q):
    """归并键（任务书数值规格2）：首尾空白 + 全半角问号差异视为同题。
    任务书硬例"接风是什么？"与"接风是什么 ？"必须同组——问号前的空格不在首尾，
    故末尾"空白/问号"连续串整体剥掉（'接风是什么？'/'接风是什么 ？'/'接风是什么' 同键）。"""
    s = str(q or '').strip().replace('？', '?')
    return re.sub(r'[\s?]+$', '', s)


def _ensure_badcase_table():
    """kb_badcase 幂等建表（SQLite/MySQL 双方言）。返回连接。"""
    conn = get_db()
    if _is_sqlite():
        conn.execute(
            "CREATE TABLE IF NOT EXISTS kb_badcase ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " question_norm VARCHAR(200) NOT NULL,"
            " question_samples TEXT NOT NULL,"
            " down_count INTEGER DEFAULT 0,"
            " last_rag_note VARCHAR(255) DEFAULT '',"
            " status VARCHAR(16) DEFAULT 'open',"
            " updated_by VARCHAR(64) DEFAULT '',"
            " updated_at TEXT,"
            " resolution_note TEXT DEFAULT '')")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_badcase_norm ON kb_badcase(question_norm)")
        conn.commit()
    else:
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS kb_badcase ("
            " id INT AUTO_INCREMENT PRIMARY KEY,"
            " question_norm VARCHAR(200) NOT NULL,"
            " question_samples MEDIUMTEXT NOT NULL,"
            " down_count INT DEFAULT 0,"
            " last_rag_note VARCHAR(255) DEFAULT '',"
            " status VARCHAR(16) DEFAULT 'open',"
            " updated_by VARCHAR(64) DEFAULT '',"
            " updated_at DATETIME,"
            " resolution_note MEDIUMTEXT,"
            " KEY idx_kb_badcase_norm (question_norm)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
    return conn


def _eval_question_norms():
    """金样集全部问题（归并键口径），用于 resolved 挂钩提示。异常→空集（不提示）。"""
    try:
        with open(os.path.join(_KNOWN, 'eval_queries.json'), encoding='utf-8') as f:
            d = json.load(f)
        out = set()
        for key in ('domain_queries', 'out_of_domain'):
            for it in d.get(key, []):
                if isinstance(it, dict) and it.get('question'):
                    out.add(_norm_question(it['question']))
        return out
    except Exception:
        return set()


@ai_assist_bp.route('/api/assist/admin/badcases', methods=['POST'])
def admin_badcases():
    from auth_utils import require_admin
    real, err = require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    where = ["kind='ask'", "feedback='down'"]
    params = []
    if data.get('date_from'):
        where.append("substr(created_at,1,10)>=%s")
        params.append(str(data['date_from']))
    if data.get('date_to'):
        where.append("substr(created_at,1,10)<=%s")
        params.append(str(data['date_to']))
    conn = get_db()
    rows = _fetchall(conn,
        "SELECT id, question, answer, note, created_at FROM ai_usage WHERE "
        + ' AND '.join(where) + " ORDER BY id ASC", tuple(params))
    # 实时聚合：同问题归并（次数/最近时间/最近rag命中/答案样本1条）
    groups = {}
    order = []
    for r in rows:
        norm = _norm_question(r['question'])
        g = groups.get(norm)
        if g is None:
            g = groups[norm] = {'question_norm': norm, 'question_sample': r['question'],
                                'samples': [], 'down_count': 0, 'last_time': '',
                                'last_rag_note': '', 'answer_sample': ''}
            order.append(norm)
        g['down_count'] += 1
        if len(g['samples']) < 10 and r['question'] not in g['samples']:
            g['samples'].append(r['question'])
        if r['created_at'] >= g['last_time']:
            g['last_time'] = r['created_at']
            g['last_rag_note'] = (r['note'] or '')[:255]
            g['answer_sample'] = (r['answer'] or '')[:200]
    # 懒插入 + 计数回写（kb_badcase 是本模块自己的状态表，ai_usage 只读）
    conn = _ensure_badcase_table()
    eval_norms = _eval_question_norms()
    try:
        existing = {r['question_norm']: r for r in _fetchall(conn, "SELECT * FROM kb_badcase")}
        for norm in order:
            g = groups[norm]
            ex = existing.get(norm)
            if ex is None:
                _exec(conn,
                      "INSERT INTO kb_badcase (question_norm, question_samples, down_count, "
                      "last_rag_note, status, updated_by, updated_at, resolution_note) "
                      "VALUES (%s,%s,%s,%s,'open',%s,%s,'')",
                      (norm[:200], json.dumps(g['samples'], ensure_ascii=False),
                       g['down_count'], g['last_rag_note'], real, beijing_now_str()))
            else:
                _exec(conn,
                      "UPDATE kb_badcase SET down_count=%s, last_rag_note=%s WHERE id=%s",
                      (g['down_count'], g['last_rag_note'], ex['id']))
                g['id'] = ex['id']
        try:
            conn.commit()
        except Exception:
            pass
        # 带上表内状态输出
        rows2 = {r['question_norm']: r for r in _fetchall(conn, "SELECT * FROM kb_badcase")}
    finally:
        try:
            conn.close()
        except Exception:
            pass
    status_filter = data.get('status')
    items = []
    for norm in order:
        g = groups[norm]
        b = rows2.get(norm) or {}
        item = {'id': b.get('id'), 'question': g['question_sample'],
                'question_norm': norm, 'down_count': g['down_count'],
                'last_time': g['last_time'], 'last_rag_note': g['last_rag_note'],
                'answer_sample': g['answer_sample'],
                'samples': json.loads(b['question_samples']) if b.get('question_samples') else g['samples'],
                'status': b.get('status') or 'open',
                'resolution_note': b.get('resolution_note') or '',
                'updated_by': b.get('updated_by') or '', 'updated_at': b.get('updated_at') or ''}
        if item['status'] == 'resolved' and item['question_norm'] not in eval_norms:
            item['hint'] = '建议将该题追加进金样集（eval_queries.json）'
        if status_filter and item['status'] != status_filter:
            continue
        items.append(item)
    return jsonify({'ok': True, 'badcases': items, 'total_groups': len(items)})


@ai_assist_bp.route('/api/assist/admin/badcase/status', methods=['POST'])
def admin_badcase_status():
    from auth_utils import require_admin
    real, err = require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    bid = data.get('badcase_id')
    status = data.get('status')
    note = str(data.get('resolution_note') or '')[:500]
    if not bid or status not in _BADCASE_STATUSES:
        return jsonify({'ok': False, 'error': 'bad params'})
    conn = _ensure_badcase_table()
    try:
        rows = _fetchall(conn, "SELECT * FROM kb_badcase WHERE id=%s", (bid,))
        if not rows:
            return jsonify({'ok': False, 'error': 'not_found'})
        _exec(conn,
              "UPDATE kb_badcase SET status=%s, updated_by=%s, updated_at=%s, "
              "resolution_note=CASE WHEN %s='' THEN resolution_note ELSE %s END WHERE id=%s",
              (status, real, beijing_now_str(), note, note, bid))
        try:
            conn.commit()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    # 审计一行 kind=kb_debug（本任务唯一允许的 ai_usage 新增路径）
    _insert_usage(real, 'kb_debug', '', 'badcase:%s→%s' % (bid, status), note,
                  0, 0, 0, note='badcase_status')
    out = {'ok': True}
    if status == 'resolved' and not note:
        out['warning'] = 'resolved 但 resolution_note 为空：建议写明对应的 rules.txt 修改点'
    if status == 'resolved':
        samples = []
        try:
            samples = json.loads(rows[0]['question_samples'] or '[]')
        except Exception:
            samples = []
        eval_norms = _eval_question_norms()
        if samples and any(_norm_question(s) not in eval_norms for s in samples):
            out['hint'] = '建议将该题追加进金样集（eval_queries.json）'
    return jsonify(out)
