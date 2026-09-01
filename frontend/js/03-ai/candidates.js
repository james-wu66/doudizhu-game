// ============================================================
// 斗地主终极版 · AI 引擎 / 候选生成
// 职责：枚举所有可能出牌组合
// 来源：game.js 第 1417-1480 行（模块化拆分，代码未做改动）
// ============================================================
// ===== 候选生成 v3（S2：炸弹可拆，拆牌成本交给评分） =====
function aiAdd(out,seen,cards){
  if(!cards||!cards.length)return;
  const pattern=detectPattern(cards);if(!pattern)return;
  const key=cards.map(c=>c.id).sort((a,b)=>a-b).join(',');if(seen.has(key))return;
  seen.add(key);out.push({cards:[...cards],pattern});
}
function aiCandidates(hand){
  const out=[],seen=new Set(),freq=aiCountRanks(hand),ranks=Object.keys(freq).map(Number).sort((a,b)=>a-b);
  const cardsOf=(r,n)=>hand.filter(c=>c.rank===r).slice(0,n);
  const otherRanks=used=>ranks.filter(r=>!used.includes(r));
  ranks.forEach(r=>{
    aiAdd(out,seen,cardsOf(r,1));
    if(freq[r]>=2)aiAdd(out,seen,cardsOf(r,2));
    if(freq[r]>=3)aiAdd(out,seen,cardsOf(r,3));
    if(freq[r]===4)aiAdd(out,seen,cardsOf(r,4));
  });
  if(freq[16]&&freq[17])aiAdd(out,seen,hand.filter(c=>c.rank>=16));
  for(let s=3;s<=14;s++)for(let len=5;s+len-1<=14;len++){
    const rs=Array.from({length:len},(_,i)=>s+i);
    if(rs.every(r=>freq[r]>=1))aiAdd(out,seen,rs.flatMap(r=>cardsOf(r,1)));
  }
  for(let s=3;s<=14;s++)for(let len=3;s+len-1<=14;len++){
    const rs=Array.from({length:len},(_,i)=>s+i);
    if(rs.every(r=>freq[r]>=2))aiAdd(out,seen,rs.flatMap(r=>cardsOf(r,2)));
  }
  for(const r of ranks){
    if(freq[r]<3)continue;
    for(const k of otherRanks([r])){
      aiAdd(out,seen,[...cardsOf(r,3),...cardsOf(k,1)]);
      if(freq[k]>=2)aiAdd(out,seen,[...cardsOf(r,3),...cardsOf(k,2)]);
    }
  }
  for(const r of ranks){
    if(freq[r]!==4)continue;
    const others=otherRanks([r]);
    for(let i=0;i<others.length;i++)for(let j=i+1;j<others.length;j++)
      aiAdd(out,seen,[...cardsOf(r,4),cardsOf(others[i],1)[0],cardsOf(others[j],1)[0]]);
    const pairs=others.filter(x=>freq[x]>=2);
    for(let i=0;i<pairs.length;i++)for(let j=i+1;j<pairs.length;j++)
      aiAdd(out,seen,[...cardsOf(r,4),...cardsOf(pairs[i],2),...cardsOf(pairs[j],2)]);
  }
  for(let s=3;s<=14;s++)for(let len=2;s+len-1<=14;len++){
    const rs=Array.from({length:len},(_,i)=>s+i);
    if(!rs.every(r=>freq[r]>=3))continue;
    const core=rs.flatMap(r=>cardsOf(r,3)),others=otherRanks(rs);
    aiAdd(out,seen,core);
    if(others.length>=len)aiAdd(out,seen,[...core,...others.slice(0,len).map(r=>cardsOf(r,1)[0])]);
    const pairs=others.filter(r=>freq[r]>=2);
    if(pairs.length>=len)aiAdd(out,seen,[...core,...pairs.slice(0,len).flatMap(r=>cardsOf(r,2))]);
  }
  return out;
}

function aiCanBeat(x,last){return x&&x.pattern&&canBeat(x.pattern,last);}
function aiFindSameType(hand,last){
  return aiCandidates(hand).filter(x=>x.pattern.type===last.type&&x.pattern.len===last.len&&aiCanBeat(x,last)).sort((a,b)=>a.pattern.main-b.pattern.main||a.cards.length-b.cards.length);
}
function aiBombs(hand){return aiCandidates(hand).filter(x=>x.pattern.type==='BOMB'||x.pattern.type==='ROCKET').sort((a,b)=>a.pattern.main-b.pattern.main);}




// ===== 后端 API 调用辅助 =====
