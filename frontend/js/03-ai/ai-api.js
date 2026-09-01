// ============================================================
// 斗地主终极版 · AI 引擎 / 后端调用
// 职责：调用后端 AI 接口与本地兜底
// 来源：game.js 第 1407-1416 + 1481-1573 行（模块化拆分，代码未做改动）
// ============================================================
// ===== 叫地主 v4（改为后端 API 调用 + 简化 fallback） =====
async function aiDecideBid(hand, isCallPhase) {
  // 尝试后端 API
  const apiBid = await aiBidViaAPI(hand, isCallPhase);
  if (apiBid >= 0) return apiBid;

  // 降级：简化判断
  return fallbackBidSimple(hand);
}

const AI_API = window.location.origin + '/api/ai';

async function aiDecideViaAPI(hand, last, who, role, strategy, roundId, step) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 3000);
  try {
    const res = await fetch(AI_API + '/decide', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: ctrl.signal,
      body: JSON.stringify({
        hand: hand.map(c => ({ id: c.id, r: c.rank, s: c.suit })),
        last: last ? { type: last.type, main: last.main, len: last.len } : null,
        who, role, strategy,
        round_id: roundId || '',
        step: step || 0,
        landlord: G.landlord,
        landlord_count: aiLandlordCount(),
        teammate_count: (function(){const p=aiPartner(who); return p>=0?(G.hands[p]||[]).length:99;})(),
        last_player: G.lastPlay ? G.lastPlay.player : -1,
        pass_count: G.passCount || 0,
        played_hands: (G.playedHands || [[], [], []]).map(arr => arr.map(c => ({r: c.rank, s: c.suit})))
      })
    });
    clearTimeout(timer);
    const data = await res.json();
    if (data.ok && data.action) {
      return apiCardsToHand(data.action, hand);
    }
    return null;
  } catch(e) {
    clearTimeout(timer);
    return null; // 超时/网络错误 → 用 fallback
  }
}

async function aiBidViaAPI(hand, isCallPhase) {
  try {
    const res = await fetch(AI_API + '/bid', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hand: hand.map(c => ({ id: c.id, r: c.rank, s: c.suit })),
        isCallPhase,
        call_acted: (G.callActed || []),
        bid_mult: (G.bidMult || 2),
        grab_acted: (G.grabActed || [])
      })
    });
    const data = await res.json();
    return data.ok ? data.bid : -1;
  } catch(e) {
    return -1;
  }
}

// 简化 fallback：出最小能压的牌（不依赖复杂评分，不出错即可）
function fallbackSimple(hand, last) {
  const cands = aiCandidates(hand).filter(x => last ? aiCanBeat(x, last) : true);
  if (!cands.length) return null;
  if (!last) return cands[0].cards; // 主动出最小
  const sorted = cands.sort((a,b) => (a.pattern.main||0) - (b.pattern.main||0));
  return sorted[0].cards;
}

function fallbackBidSimple(hand) {
  const eh = evaluateHand(hand);
  let threshold = 58;
  if (eh.bombs >= 1) threshold -= 8;
  return eh.score >= threshold ? 1 : 0;
}

// 后端格式转前端 card 对象（从手牌中匹配）
function apiCardsToHand(apiCards, hand) {
  const used = new Set();
  return apiCards.map(a => {
    const match = hand.find(c => c.rank === a.r && c.suit === a.s && !used.has(c.id));
    if (match) { used.add(match.id); return match; }
    return { id: -1, rank: a.r, suit: a.s };
  });
}

// ===== 出牌入口（改为后端 API 调用 + 简化 fallback） =====
async function aiPlay(hand, lastPattern) {
  const who = G.current, role = aiRole(who), teammate = aiPartner(who);
  const teammateCount = teammate >= 0 ? (G.hands[teammate] || []).length : 99;
  const landlordCount = aiLandlordCount();
  const _ehScore = evaluateHand(hand).score;
  const strategy = hand.length <= 5 ? 'aggressive' : (_ehScore > 60 && hand.length <= 8 ? 'aggressive' : (role !== 'landlord' && teammateCount <= 4 ? 'support' : (_ehScore < 35 && hand.length > 8 ? 'defensive' : (landlordCount <= 4 ? (role === 'landlord' ? 'aggressive' : 'defensive') : (_ehScore < 40 && hand.length > 10 ? 'defensive' : 'balanced')))));

  // 尝试后端 API
  const apiResult = await aiDecideViaAPI(hand, lastPattern, who, role, strategy, LEARN.roundId, LEARN.step);
  if (apiResult) {
    LEARN.step++;
    return apiResult;
  }

  // 降级：后端挂了用简化 fallback
  console.warn('AI API failed, using fallback');
  return fallbackSimple(hand, lastPattern);
}
