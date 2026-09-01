// ============================================================
// 斗地主终极版 · AI 引擎 / 手牌评估
// 职责：手牌打分与 AI 学习记录
// 来源：game.js 第 1327-1406 行（模块化拆分，代码未做改动）
// ============================================================
// ==================== AI ENGINE v3（完整替换） ====================
function aiCountRanks(cards){
  const f={};cards.forEach(c=>{f[c.rank]=(f[c.rank]||0)+1;});return f;
}

// ===== 牌力评估（修复 7/8/9/10 零分 + 张数修正 + 结构分细化） =====
function evaluateHand(cards){
  const freq=aiCountRanks(cards);
  let score=0, bombs=0, rocket=0;
  cards.forEach(c=>{
    if(c.rank===17)score+=14;
    else if(c.rank===16)score+=10;
    else if(c.rank===15)score+=6;
    else if(c.rank===14)score+=4;
    else if(c.rank===13)score+=3;
    else if(c.rank===12)score+=2.5;
    else if(c.rank===11)score+=2;
    else if(c.rank===10)score+=1.8;
    else if(c.rank===9)score+=1.5;
    else if(c.rank===8)score+=1.2;
    else score+=1;
  });
  Object.keys(freq).map(Number).forEach(r=>{
    if(freq[r]===4){score+=12;bombs++;}
    else if(freq[r]===3)score+=4;
    else if(freq[r]===2)score+=2;
  });
  if(freq[16]&&freq[17]){score+=8;rocket=1;}
  const runs=aiConsecutiveRuns(Object.keys(freq).map(Number),5);
  runs.forEach(run=>{if(run.length>=5)score+=4+Math.min(run.length,10)*0.5;});
  const pairRuns=aiConsecutiveRuns(Object.keys(freq).map(Number).filter(r=>freq[r]>=2),3);
  pairRuns.forEach(run=>{if(run.length>=3)score+=4+run.length;});
  const tripleRuns=aiConsecutiveRuns(Object.keys(freq).map(Number).filter(r=>freq[r]>=3),2);
  tripleRuns.forEach(run=>{if(run.length>=2)score+=6+run.length*2;});
  score-=Math.max(0,cards.length-17)*1.5;
  const singles=Object.keys(freq).map(Number).filter(r=>freq[r]===1).length;
  if(singles>=5)score-=(singles-4)*1.5;
  return {score:Math.max(0,Math.min(100,score)),bombs,rocket,singles};
}

// ===== AI 学习：修正参数加载与计算 =====
function learnLoad(){
  fetch(API_BASE + '/api/ai/learning')
    .then(r => r.json())
    .then(d => {
      if(d && d.base){
        LEARN.base = d.base || {};
        LEARN.buckets = {};
        (d.buckets || []).forEach(b => { LEARN.buckets[b.action_type + '|' + b.bucket] = b; });
      }
      LEARN.loaded = true;
    })
    .catch(() => { LEARN.loaded = true; }); // 加载失败不阻塞游戏，修正分为 0
}
function aiRecordStep(step, handState, action, actionType, bucket, who){
  if(!LEARN.roundId) return;
  const payload = {
    round_id: LEARN.roundId,
    step: step,
    hand_state: handState,
    action: action,
    action_type: actionType,
    who: who,
    bucket: bucket || '',
    result: '',
    score_change: 0
  };
  fetch(API_BASE + '/api/ai/record', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  }).catch(() => {}); // 记录失败静默，不影响游戏
}
function aiActionTypeOf(candidate, freq){
  if(candidate && (candidate.pattern.type === 'BOMB' || candidate.pattern.type === 'ROCKET')) return 'BOMB';
  if(candidate && aiSplitPenalty(candidate.cards, freq) > 0) return 'SPLIT';
  return 'NORMAL'; // NORMAL 不参与统计
}
function aiRoleNameFor(seat){ return seat === LEFT ? 'LEFT' : seat === RIGHT ? 'RIGHT' : 'PLAYER'; }
