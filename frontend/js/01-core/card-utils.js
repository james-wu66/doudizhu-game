// ============================================================
// 斗地主终极版 · 核心基础 / 牌工具
// 职责：造牌、洗牌、排序、取牌名
// 来源：game.js 第 105-119 行（模块化拆分，代码未做改动）
// ============================================================
// ==================== CARD UTILS ====================
// cardIdCounter 已提前到 <script> 开头声明
function makeCard(suit,rank){return{id:cardIdCounter++,suit,rank};}
function createDeck(){
  cardIdCounter=0;const d=[];
  for(let s=0;s<4;s++)for(let r=3;r<=15;r++)d.push(makeCard(s,r));
  d.push(makeCard(-1,16));d.push(makeCard(-2,17));return d;
}
function shuffle(a){for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
function sortCards(c){return c.sort((a,b)=>a.rank!==b.rank?b.rank-a.rank:b.suit-a.suit);}
function getRankName(r){return RANK_NAMES[r]||'?';}
function getSuitSymbol(s){return s>=0?SUITS[s]:'';}
function getSuitColor(s){return s>=0?SUIT_COLORS[s]:(s===-1?'black':'red');}
function getFrequency(cards){const f={};cards.forEach(c=>f[c.rank]=(f[c.rank]||0)+1);return f;}
function getCardsOfRank(hand,rank,count){return hand.filter(c=>c.rank===rank).slice(0,count);}
