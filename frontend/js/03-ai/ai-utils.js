// ============================================================
// 斗地主终极版 · AI 引擎 / 辅助判断
// 职责：角色、威胁度、找牌辅助
// 来源：game.js 第 1574-1594 行（模块化拆分，代码未做改动）
// ============================================================
// ===== 工具函数（hint 依赖，勿删） =====
function aiConsecutiveRuns(ranks,minLen){
  const out=[],a=[...new Set(ranks)].filter(r=>r<=14).sort((x,y)=>x-y);
  let run=[];
  for(const r of a){if(!run.length||r===run[run.length-1]+1)run.push(r);else{if(run.length>=minLen)out.push([...run]);run=[r];}}
  if(run.length>=minLen)out.push([...run]);
  return out;
}
function aiNext(who){return(who+2)%3;}
function aiRole(who){
  if(who===G.landlord)return'landlord';
  return who===aiNext(G.landlord)?'farmerNext':'farmerPrev';
}
function aiPartner(who){return aiRole(who)==='landlord'?-1:[PLAYER,LEFT,RIGHT].find(p=>p!==who&&p!==G.landlord);}
function aiLandlordCount(){return G.landlord>=0?(G.hands[G.landlord]||[]).length:99;}
function aiThreatCount(who){return aiRole(who)==='landlord'?Math.min(G.hands[LEFT].length,G.hands[RIGHT].length):aiLandlordCount();}
function findSmallestBeating(hand,last){return aiFindSameType(hand,last)[0]?.cards||null;}
function findBomb(hand){return aiBombs(hand)[0]?.cards||null;}
function findAllBeatingPlays(hand,last){return aiCandidates(hand).filter(x=>aiCanBeat(x,last)).map(x=>x.cards);}
function findAllLeadingPlays(hand){return aiCandidates(hand).map(x=>x.cards);}
