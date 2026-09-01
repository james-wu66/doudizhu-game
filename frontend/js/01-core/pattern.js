// ============================================================
// 斗地主终极版 · 核心基础 / 牌型识别
// 职责：识别单张/对子/顺子/炸弹，判断能否压过
// 来源：game.js 第 121-212 行（模块化拆分，代码未做改动）
// ============================================================
// ==================== PATTERN DETECTION ====================
function detectPattern(cards){
  const n=cards.length;if(n===0)return null;
  const ranks=cards.map(c=>c.rank).sort((a,b)=>a-b);
  const freq=getFrequency(cards);
  const uRanks=Object.keys(freq).map(Number).sort((a,b)=>a-b);
  const fVals=Object.values(freq);
  if(n===2&&ranks[0]===16&&ranks[1]===17)return{type:'ROCKET',main:17,len:1};
  if(n===4&&fVals.length===1&&fVals[0]===4)return{type:'BOMB',main:ranks[0],len:1};
  if(n===1)return{type:'SINGLE',main:ranks[0],len:1};
  if(n===2&&fVals.length===1&&fVals[0]===2)return{type:'PAIR',main:ranks[0],len:1};
  if(n===3&&fVals.length===1&&fVals[0]===3)return{type:'TRIPLE',main:ranks[0],len:1};
  if(n===4){
    const tr=uRanks.find(r=>freq[r]===3),sr=uRanks.find(r=>freq[r]===1);
    if(tr!==undefined&&sr!==undefined)return{type:'TRIPLE_ONE',main:tr,len:1};
  }
  if(n===5){
    const tr=uRanks.find(r=>freq[r]===3),pr=uRanks.find(r=>freq[r]===2);
    if(tr!==undefined&&pr!==undefined)return{type:'TRIPLE_TWO',main:tr,len:1};
  }
  if(n===6||n===8){
    const quad=uRanks.find(r=>freq[r]===4);
    const kickers=uRanks.filter(r=>r!==quad);
    const needPairs=n===8;
    if(quad!==undefined&&kickers.length===(needPairs?2:2)&&kickers.every(r=>freq[r]===(needPairs?2:1)))
      return{type:'FOUR_TWO',main:quad,len:needPairs?2:1};
  }
  if(n>=5&&fVals.every(v=>v===1)){
    if(uRanks[uRanks.length-1]<=14){
      let ok=true;
      for(let i=1;i<uRanks.length;i++)if(uRanks[i]!==uRanks[i-1]+1){ok=false;break;}
      if(ok)return{type:'STRAIGHT',main:uRanks[0],len:n};
    }
  }
  if(n>=6&&n%2===0&&fVals.every(v=>v===2)){
    if(uRanks[uRanks.length-1]<=14){
      let ok=true;
      for(let i=1;i<uRanks.length;i++)if(uRanks[i]!==uRanks[i-1]+1){ok=false;break;}
      if(ok)return{type:'STRAIGHT_PAIR',main:uRanks[0],len:n/2};
    }
  }
  const ap=detectAirplane(freq,uRanks,n);if(ap)return ap;
  return null;
}

function detectAirplane(freq,uRanks,n){
  const tripleRanks=uRanks.filter(r=>freq[r]>=3&&r<=14).sort((a,b)=>a-b);
  for(let len=tripleRanks.length;len>=2;len--){
    for(let start=0;start<=tripleRanks.length-len;start++){
      const seq=tripleRanks.slice(start,start+len);
      let ok=true;
      for(let i=1;i<seq.length;i++)if(seq[i]!==seq[i-1]+1){ok=false;break;}
      if(!ok)continue;
      const tc=len*3,rem=n-tc;
      if(rem===0)return{type:'AIRPLANE',main:seq[0],len};
      if(rem===len){
        // S3 fix: wings must be len distinct singles, not pairs
        const rf={...freq};seq.forEach(r=>rf[r]-=3);
        const rv=Object.values(rf).filter(v=>v>0);
        if(rv.length===len&&rv.every(v=>v===1))return{type:'AIRPLANE_SINGLE',main:seq[0],len};
      }
      if(rem===len*2){
        const rf={...freq};seq.forEach(r=>rf[r]-=3);
        const wingRanks=Object.keys(rf).filter(r=>rf[r]>0);
        const rv=wingRanks.map(r=>rf[r]);
        if(wingRanks.length===len&&rv.every(v=>v===2))return{type:'AIRPLANE_PAIR',main:seq[0],len};
      }
    }
  }
  return null;
}

function canBeat(np,lp){
  if(!lp)return true;
  if(np.type==='ROCKET')return true;
  if(np.type==='BOMB'){
    if(lp.type==='ROCKET')return false;
    if(lp.type==='BOMB')return np.main>lp.main;
    return true;
  }
  if(np.type!==lp.type)return false;
  if(np.len!==lp.len)return false;
  return np.main>lp.main;
}

function patternName(t){
  const m={SINGLE:'单张',PAIR:'对子',TRIPLE:'三条',TRIPLE_ONE:'三带一',TRIPLE_TWO:'三带二',
    STRAIGHT:'顺子',STRAIGHT_PAIR:'连对',FOUR_TWO:'四带二',AIRPLANE:'飞机',AIRPLANE_SINGLE:'飞机带翅膀',AIRPLANE_PAIR:'飞机带翅膀',
    BOMB:'炸弹💣',ROCKET:'王炸🚀'};
  return m[t]||t;
}
