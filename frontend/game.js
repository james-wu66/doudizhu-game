// ==================== GLOBAL STATE (提前声明，避免 updateStartModal/saveGameState 等在 INIT 阶段触发 TDZ) ====================
let currentUser = null;
let currentTab = 'login';
let sessionScores = [0, 0, 0];
let currentRound = 0;
let roundScore = 0;
let cardIdCounter = 0;
let bgmMuted = false;
let sfxMuted = false;
// ===== AI 学习（LEARN）模块状态 =====
const LEARN = {loaded: false, base: {}, buckets: {}, roundId: '', step: 0};

// ==================== CONSTANTS ====================
const SUITS=['♠','♥','♦','♣'];
const SUIT_COLORS=['black','red','red','black'];
const RANK_NAMES={3:'3',4:'4',5:'5',6:'6',7:'7',8:'8',9:'9',10:'10',11:'J',12:'Q',13:'K',14:'A',15:'2',16:'小',17:'大'};
const PLAYER=0,LEFT=1,RIGHT=2;
const PLAYER_NAMES=['你','电脑A','电脑B'];
const TOTAL_ROUNDS=10;
const BASE_SCORE=3;

// ==================== SESSION STATE ====================
// sessionScores / currentRound / roundScore / cardIdCounter 已提前到 <script> 开头声明
const SAVE_KEY='doudizhu_ultimate_saved_game_v1';
function serializeCard(c){return{id:c.id,suit:c.suit,rank:c.rank};}
function saveGameState(){
  // 游客不保存存档：游客永远是新牌局
  if(currentUser && currentUser.name === '游客')return;
  if(!G||!G.phase||G.phase==='idle'||G.phase==='ended')return;
  try{
    const data={version:2,currentRound,sessionScores:[...sessionScores],roundScore,cardIdCounter,phaseStep:G.phaseStep,
      G:{...G,hands:(G.hands||[]).map(h=>h.map(serializeCard)),deck:(G.deck||[]).map(serializeCard),
        landlordCards:(G.landlordCards||[]).map(serializeCard),playedHands:(G.playedHands||[[],[],[]]).map(h=>h.map(serializeCard)),
        selectedIds:[],hintPlays:[],hintIdx:0}};
    localStorage.setItem(SAVE_KEY,JSON.stringify(data));
  }catch(err){console.warn('Save game failed',err);}
}
function clearSavedGame(){try{localStorage.removeItem(SAVE_KEY);}catch(err){console.warn('Clear saved game failed',err);}}
function readSavedGame(){
  try{const raw=localStorage.getItem(SAVE_KEY);if(!raw)return null;const data=JSON.parse(raw);return data&&(data.version===1||data.version===2)&&data.G?data:null;}
  catch(err){console.warn('Read saved game failed',err);return null;}
}
function updateStartModal(){
  const status=document.getElementById('start-status'),basic=document.getElementById('start-actions-basic'),choice=document.getElementById('start-actions-choice');
  if(!status)return;
  const isGuest=currentUser && currentUser.name==='游客';
  const saved=isGuest?null:readSavedGame();
  if(saved){
    // 有存档：进入游戏页直接显示"继续游戏/重新开始"两个按钮，不用先点"开始游戏"
    status.textContent='检测到未完成牌局，可以继续上次游戏';
    if(basic)basic.style.display='none';
    if(choice)choice.style.display='flex';
  }else{
    // 无存档/游客：只显示"开始游戏"按钮，点击直接开局
    status.textContent='';
    if(basic)basic.style.display='flex';
    if(choice)choice.style.display='none';
  }
}
function restoreGameState(data){
  currentRound=data.currentRound||1;sessionScores=Array.isArray(data.sessionScores)?data.sessionScores:[0,0,0];roundScore=data.roundScore||BASE_SCORE;cardIdCounter=data.cardIdCounter||0;
  const saved=data.G;
  G={...saved,hands:(saved.hands||[[],[],[]]).map(h=>h.map(c=>({...c}))),deck:(saved.deck||[]).map(c=>({...c})),landlordCards:(saved.landlordCards||[]).map(c=>({...c})),playedHands:(saved.playedHands||[[],[],[]]).map(h=>h.map(c=>({...c}))),selectedIds:new Set(),hintPlays:[],hintIdx:0};
  document.getElementById('start-modal').classList.add('hidden');document.getElementById('result-modal').classList.remove('show');
  clearAllPlayed();renderLandlordCards(G.phase==='playing'&&G.landlord>=0);renderOpponentCards(LEFT,G.hands[LEFT].length);renderOpponentCards(RIGHT,G.hands[RIGHT].length);renderPlayerHand();updateBadges();updateMultiplierDisplay();renderScoreTags();renderRoundDisplay();
  document.getElementById('actions').style.display='none';document.getElementById('bid-actions').style.display='none';
  if(data.phaseStep)G.phaseStep=data.phaseStep;
  if(G.phase==='playing'){G.playedHands.forEach((cards,who)=>{if(cards.length)renderPlayedCards(who,cards);});doPlayTurn();}
  else if(G.phase==='bidding'){renderLandlordCards(false);doBidTurn();}
  else{dealRound();}
}
function startFromMenu(){
  // 开始游戏：用户手势后主动播放背景音乐（浏览器放行自动播放策略）
  var _bgm=document.getElementById('bgm-audio');
  if(_bgm&&!_bgm.muted){_bgm.volume=(localStorage.getItem('doudizhu_bgm_vol')||80)/100;_bgm.play().catch(function(){});}
  // 游客：直接开始新游戏，不弹窗
  if(currentUser && currentUser.name === '游客'){
    document.getElementById('start-modal').classList.add('hidden');
    startNewGame();
    return;
  }
  // 无存档：直接开始新游戏
  if(!readSavedGame()){
    document.getElementById('start-modal').classList.add('hidden');
    startNewGame();
    return;
  }
  // 有存档兜底：切换为"继续游戏/重新开始"选择（正常进入页面时已直接显示）
  document.getElementById('start-status').textContent='检测到未完成牌局，可以继续上次游戏';
  const basic=document.getElementById('start-actions-basic'),choice=document.getElementById('start-actions-choice');
  if(basic)basic.style.display='none';
  if(choice)choice.style.display='flex';
}
function continueFromMenu(){
  // 点"继续游戏"：恢复上次存档
  var _bgm2=document.getElementById('bgm-audio');
  if(_bgm2&&!_bgm2.muted){_bgm2.volume=(localStorage.getItem('doudizhu_bgm_vol')||80)/100;_bgm2.play().catch(function(){});}
  const saved=readSavedGame();
  document.getElementById('start-modal').classList.add('hidden');
  if(saved)restoreGameState(saved);
  else startNewGame();
}
function restartFromMenu(){clearSavedGame();document.getElementById('start-modal').classList.add('hidden');startNewGame();}

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

// ==================== GAME STATE ====================
let G={};

// ==================== 回放模式 ====================
let isReplayMode=false;
let replayData=[];
let replayIndex=0;
let replaySpeed=1;
let replayTimer=null;

// 回放模式初始化
async function initReplayMode(gameId){
  isReplayMode=true;
  document.body.classList.add('replay-mode');
  // 修复4：注入回放专用CSS——解除出牌区容器高度限制（媒体查询把 played-left/right 高度锁在 8vh/10vh，导致牌被压瘪成扁牌）
  if(!document.getElementById('replay-style-fix')){
    var rs=document.createElement('style');
    rs.id='replay-style-fix';
    rs.textContent=''
      +'body.replay-mode #played-left,body.replay-mode #played-right{height:auto!important;min-height:60px!important;width:auto!important;max-width:42vw!important;display:flex!important;align-items:center!important;justify-content:center!important;overflow:visible!important;z-index:50!important;}'
      +'body.replay-mode #played-player{height:auto!important;min-height:60px!important;width:auto!important;max-width:50vw!important;display:flex!important;align-items:center!important;justify-content:center!important;overflow:visible!important;z-index:50!important;}'
      +'body.replay-mode #opp-left,body.replay-mode #opp-right{width:auto!important;height:auto!important;min-height:0!important;display:grid!important;align-items:center!important;justify-content:flex-start!important;overflow:visible!important;z-index:60!important;top:12vh!important;grid-template-columns:auto auto!important;grid-template-rows:auto auto auto!important;gap:2px 10px!important;}'
      +'body.replay-mode #opp-left .opp-label{grid-column:1;grid-row:1;justify-content:center!important;}'
      +'body.replay-mode #opp-left .opp-avatar{grid-column:1;grid-row:2;margin:0 auto!important;}'
      +'body.replay-mode #opp-left .opp-badge{grid-column:1;grid-row:3;justify-content:center!important;margin:0!important;}'
      +'body.replay-mode #opp-left .opp-info{grid-column:2;grid-row:1/4;align-items:center!important;margin-left:8px!important;}'
      +'body.replay-mode #opp-right .opp-label{grid-column:2;grid-row:1;justify-content:center!important;}'
      +'body.replay-mode #opp-right .opp-avatar{grid-column:2;grid-row:2;margin:0 auto!important;}'
      +'body.replay-mode #opp-right .opp-badge{grid-column:2;grid-row:3;justify-content:center!important;margin:0!important;}'
      +'body.replay-mode #opp-right .opp-info{grid-column:1;grid-row:1/4;align-items:center!important;margin-right:8px!important;}'
      +'body.replay-mode .opp-cards{display:block!important;position:relative!important;margin:0!important;max-width:none!important;overflow:visible!important;width:auto!important;height:auto!important;}'
      +'body.replay-mode .opp-cards .card{width:auto!important;height:auto!important;margin:0!important;flex:none!important;flex-basis:auto!important;max-width:none!important;max-height:none!important;}'
      +'body.replay-mode .played-cards{display:flex!important;flex-wrap:nowrap!important;gap:0!important;align-items:center!important;justify-content:center!important;overflow:visible!important;width:max-content!important;max-width:none!important;}'
      +'body.replay-mode .played-cards .card{margin:0!important;flex:none!important;flex-basis:auto!important;width:auto!important;height:auto!important;max-width:none!important;max-height:none!important;}';
    document.head.appendChild(rs);
  }
  try{
    const resp=await fetch(API_BASE+'/api/games/'+gameId+'/replay');
    const data=await resp.json();
    if(!data.success||!data.moves||data.moves.length===0){
      alert('该局没有回放数据');
      var _urlName = new URLSearchParams(window.location.search).get('name');
      window.location.href='/lobby'+(_urlName?'?name='+encodeURIComponent(_urlName):'');
      return;
    }
    replayData=data.moves;
    // 待办2：设置局数并刷新显示
    if(data.rounds&&data.rounds>0){
      currentRound=data.rounds;
      if(typeof renderRoundDisplay==='function')renderRoundDisplay();
    }
    // 新问题4：保存发牌数据用于窗口变化重绘
    window._replayDealMove=replayData.find(function(m){return m.type==='deal';});
    // 回放模式窗口变化重绘（避免横竖屏切换手牌错位）
    window._replayResizeHandler=function(){
      if(typeof isReplayMode!=='undefined'&&isReplayMode&&window._replayDealMove){
        if(typeof renderReplayHands==='function')renderReplayHands(window._replayDealMove);
      }
    };
    if(window._replayResizeBound)window.removeEventListener('resize',window._replayResizeBound);
    window.addEventListener('resize',window._replayResizeHandler);
    window._replayResizeBound=window._replayResizeHandler;
    // 隐藏开始弹窗和操作按钮
    var sm=document.getElementById('start-modal');
    if(sm)sm.classList.add('hidden');
    // 调用布局计算，确保CSS变量生效
    if(typeof resizeResponsiveLayout==='function')resizeResponsiveLayout();
    var acts=document.getElementById('actions');
    if(acts)acts.style.display='none';
    var bids=document.getElementById('bid-actions');
    if(bids)bids.style.display='none';
    var hand=document.getElementById('player-hand');
    if(hand)hand.style.pointerEvents='none';
    // 显示回放控制条
    showReplayBar();
    // 解析初始牌局
    var dealMove=replayData.find(m=>m.type==='deal');
    if(dealMove){
      renderReplayHands(dealMove);
      var lc=document.getElementById('landlord-area');
      if(lc&&dealMove.landlordCards){
        lc.innerHTML='';
        dealMove.landlordCards.forEach(function(rc){
          // 解析底牌（兼容对象和旧数字格式）
          var rk=(typeof rc==='object'&&rc!==null)?rc.rank:rc;
          var st=(typeof rc==='object'&&rc!==null)?rc.suit:0;
          var el=renderCardEl({id:Math.random(),suit:st,rank:rk});
          el.style.width='45px';el.style.height='63px';
          el.style.flexShrink='0';
          lc.appendChild(el);
        });
      }
    }
    // 开始自动回放
    replayIndex=1;
    startReplayPlayback();
  }catch(e){
    console.warn('回放加载失败',e);
    alert('回放加载失败');
    var _urlName2 = new URLSearchParams(window.location.search).get('name');
    window.location.href='/lobby'+(_urlName2?'?name='+encodeURIComponent(_urlName2):'');
  }
}

// 渲染三个人的牌（透视模式）
function renderReplayHands(dealMove){
  // 调用布局计算，确保CSS变量生效
  if(typeof resizeResponsiveLayout==='function')resizeResponsiveLayout();
  // 解析牌数据（兼容新格式{rank,suit}和旧格式纯数字）
  function parseCard(c){
    // 字符串rank映射
    var rankMap={'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15,'小王':16,'大王':17};
    if(typeof c==='object'&&c!==null){
      var r=c.rank;
      if(typeof r==='string')r=rankMap[r]!==undefined?rankMap[r]:parseInt(r)||0;
      return{rank:r,suit:c.suit||0};
    }
    if(typeof c==='string')return{rank:rankMap[c]!==undefined?rankMap[c]:parseInt(c)||0,suit:0};
    return{rank:c,suit:0};
  }
  // 修复5（核心）：维护"当前手牌状态"，出牌时从这里真实移除，渲染用状态而不是发牌原始数据
  if(!window._replayHands||window._replayHands._init!==true){
    window._replayHands=[
      (dealMove.myHand||[]).map(parseCard),
      (dealMove.leftHand||[]).map(parseCard),
      (dealMove.rightHand||[]).map(parseCard)
    ];
    window._replayHands._init=true;
  }
  // 渲染你的牌（底部，正常大小）——从状态读，排序后渲染
  var myHand=window._replayHands[0].slice();
  // 第2项：按斗地主大小降序（大王17>小王16>2> A>K>Q>J>10...>3）
  myHand.sort(function(a,b){return b.rank-a.rank;});
  var myContainer=document.getElementById('player-hand-inner');
  if(myContainer){
    myContainer.innerHTML='';
    var styles=getComputedStyle(document.documentElement);
    var cardW=parseFloat(styles.getPropertyValue('--legacy-card-w'))||window.innerHeight*.065;
    var cardH=parseFloat(styles.getPropertyValue('--legacy-card-h'))||cardW*1.4;
    myContainer.style.width=(cardW+(myHand.length-1)*cardW*.55)+'px';
    myHand.forEach(function(c,i){
      var el=renderCardEl({id:Math.random(),suit:c.suit,rank:c.rank});
      el.style.width=cardW+'px';el.style.height=cardH+'px';
      el.style.flex='0 0 '+cardW+'px';
      el.style.margin=(i===0?'0':'0 0 0 '+(-cardW*.45)+'px');
      // 待办2：角标和中央花色单独设置字号（防堆叠）
      var rF=cardH*0.30,sF=cardH*0.234,cF=cardH*0.495;
      var corners=el.querySelectorAll('.corner');
      corners.forEach(function(corner){
        corner.style.fontSize=sF+'px';
        var rn=corner.querySelector('.rank');if(rn)rn.style.fontSize=rF+'px';
        var su=corner.querySelector('.suit');if(su)su.style.fontSize=sF+'px';
      });
      var cs=el.querySelector('.center-suit');if(cs)cs.style.fontSize=cF+'px';
      myContainer.appendChild(el);
    });
  }
  // 渲染电脑A的牌（左上，正面透视）——从状态读
  renderReplayOpponent('opp-left',window._replayHands[1],'电脑A');
  // 渲染电脑B的牌（右上，正面透视）——从状态读
  renderReplayOpponent('opp-right',window._replayHands[2],'电脑B');
}

// 渲染对手的牌（正面透视+整齐两行，尺寸与玩家手牌一致）
function renderReplayOpponent(containerId,cards,label){
  var container=document.getElementById(containerId);
  if(!container)return;
  var cardsDiv=container.querySelector('.opp-cards')||container;
  cardsDiv.innerHTML='';
  cardsDiv.style.display='flex';
  cardsDiv.style.flexWrap='wrap';
  cardsDiv.style.gap='0';
  cardsDiv.style.justifyContent='flex-start';
  // 修复1：按斗地主大小降序（大王17>小王16>2>A>K>Q>J>10...>3），修乱码/排序错乱
  var sorted=cards.slice().sort(function(a,b){
    var ra=(typeof a==='object'&&a!==null)?a.rank:a;
    var rb=(typeof b==='object'&&b!==null)?b.rank:b;
    return rb-ra;
  });
  // 与玩家手牌同尺寸基础上整体缩小20%（等比例：花纹/数字字号随牌高自动缩）
  var styles=getComputedStyle(document.documentElement);
  function r2(n){return Math.round(n*100)/100;}
  var replayScale=(window.innerWidth<1100)?0.72:0.8;
  var cw=r2((parseFloat(styles.getPropertyValue('--legacy-card-w'))||window.innerHeight*.065)*replayScale);
  var ch=r2((parseFloat(styles.getPropertyValue('--legacy-card-h'))||cw*1.4)*replayScale);
  // 两行排布：第一行固定10张（17张=10+7，20张=10+10），重叠比例同玩家手牌（45%）
  var rowCount=10;
  var overlap=r2(cw*.45);
  var step=r2(cw-overlap); // 每张牌占位宽度
  var rowW=r2(cw+(rowCount-1)*step); // 第一行10张总宽
  var rowH=r2(ch+6); // 每行高度（牌高+行距）
  // 绝对定位钉死每张牌的位置：第1~10张第1行，第11张起第2行（永不裂开）
  cardsDiv.style.setProperty('max-width',rowW+'px','important');
  cardsDiv.style.setProperty('width',rowW+'px','important');
  cardsDiv.style.setProperty('height','auto','important');
  cardsDiv.style.setProperty('min-width','0','important');
  sorted.forEach(function(c,idx){
    var suit=(typeof c==='object'&&c!==null)?c.suit:0;
    var rank=(typeof c==='object'&&c!==null)?c.rank:c;
    var el=renderCardEl({id:Math.random(),suit:suit,rank:rank});
    // 全部用 setProperty 带 important，避免被全局 .opp-cards .card !important 覆盖
    el.style.setProperty('width',cw+'px','important');
    el.style.setProperty('height',ch+'px','important');
    el.style.setProperty('flex','0 0 '+cw+'px','important');
    el.style.setProperty('flex-shrink','0','important');
    el.style.setProperty('position','absolute','important');
    el.style.setProperty('box-sizing','border-box','important');
    // 钉死位置：left = 行内序号×step，top = 行号×rowH
    var row=Math.floor(idx/rowCount),col=idx%rowCount;
    el.style.setProperty('left',r2(col*step)+'px','important');
    el.style.setProperty('top',r2(row*rowH)+'px','important');
    el.style.setProperty('margin','0','important');
    // 花纹与牌等比缩放：点数=牌高*30%，花色=牌高*26%，中央=牌高*55%
    var rFont=ch*0.30;
    var sFont=ch*0.186;
    var cFont=ch*0.314;
    var corners=el.querySelectorAll('.corner');
    corners.forEach(function(corner){
      corner.style.setProperty('font-size',sFont+'px','important');
      var rn=corner.querySelector('.rank');if(rn)rn.style.setProperty('font-size',rFont+'px','important');
      var su=corner.querySelector('.suit');if(su)su.style.setProperty('font-size',sFont+'px','important');
    });
    var cs=el.querySelector('.center-suit');if(cs)cs.style.setProperty('font-size',cFont+'px','important');
    cardsDiv.appendChild(el);
  });
  // 容器高度按实际行数撑开（1行=rowH，2行=2*rowH）
  var rows=Math.ceil(sorted.length/rowCount);
  cardsDiv.style.setProperty('height',r2(rows*rowH)+'px','important');
  // 名字放到头像上面、张数标签放到头像下面（用户明确要求）
  var labelEl=container.querySelector('.opp-label');
  var avatar=container.querySelector('.opp-avatar');
  if(labelEl&&avatar&&labelEl.parentNode!==container){
    container.insertBefore(labelEl,avatar);
  }
  var countId=containerId==='opp-left'?'opp-left-count':'opp-right-count';
  var countEl=document.getElementById(countId);
  if(countEl){
    countEl.textContent=sorted.length+'张';
    if(avatar&&countEl.parentNode!==container){
      // 插到头像后面（下一个兄弟节点前）；没有兄弟则追加到末尾
      var next=avatar.nextSibling;
      if(next)container.insertBefore(countEl,next);
      else container.appendChild(countEl);
    }
    countEl.style.position='relative';
    countEl.style.zIndex='70';
  }
}

// 回放专用出牌渲染（45px基准，叠法同手牌，≥16张自动缩小）
function renderReplayPlayedCards(who,cards){
  var containerId=who===0?'played-player':who===1?'played-left':'played-right';
  var container=document.getElementById(containerId);
  if(!container)return;
  container.innerHTML='';
  container.classList.add('played-cards');
  var n=cards.length;
  var baseW=(window.innerWidth<1100)?34:55;
  // 玩家自己的出牌区较宽，1~20张保持45px
  var autoShrink=(who!==0&&n>=16);
  var cardW=baseW;
  if(autoShrink){
    var cw=container.clientWidth||410;
    cardW=cw/(1+0.55*(n-1));
    if(cardW<28)cardW=28;
  }
  var cardH=cardW*1.4;
  // 出牌区牌垂直居中（与回放CSS保持一致，不顶到顶部，避免"不平"）
  container.style.alignItems='center';
  cards.forEach(function(c,i){
    var el=renderCardEl({id:Math.random(),suit:c.suit,rank:c.rank});
    el.style.setProperty('width',cardW+'px','important');
    el.style.setProperty('height',cardH+'px','important');
    el.style.setProperty('flex','0 0 '+cardW+'px','important');
    el.style.setProperty('flex-shrink','0','important');
    el.style.setProperty('margin',(i===0?'0':'0 0 0 '+(-cardW*0.45)+'px'),'important');
    // 待办1：角标和中央花色按牌面比例设置字号
    var rF=cardH*0.30,sF=cardH*0.186,cF=cardH*0.314;
    var corners=el.querySelectorAll('.corner');
    corners.forEach(function(corner){
      corner.style.setProperty('font-size',sF+'px','important');
      var rn=corner.querySelector('.rank');if(rn)rn.style.setProperty('font-size',rF+'px','important');
      var su=corner.querySelector('.suit');if(su)su.style.setProperty('font-size',sF+'px','important');
    });
    var cs=el.querySelector('.center-suit');if(cs)cs.style.setProperty('font-size',cF+'px','important');
    container.appendChild(el);
  });
}


// 显示回放控制条
function showReplayBar(){
  var bar=document.createElement('div');
  bar.id='replay-bar';
  bar.style.cssText='position:fixed;bottom:0;left:0;right:0;background:rgba(0,0,0,0.85);padding:12px 20px;display:flex;align-items:center;justify-content:center;gap:16px;z-index:9999;';
  bar.innerHTML='<span style="color:#94a3b8;font-size:13px">回放速度：</span>'
    +'<button onclick="setReplaySpeed(1)" class="replay-speed-btn active" data-speed="1">1x</button>'
    +'<button onclick="setReplaySpeed(2)" class="replay-speed-btn" data-speed="2">2x</button>'
    +'<button onclick="setReplaySpeed(4)" class="replay-speed-btn" data-speed="4">4x</button>'
    +'<button onclick="setReplaySpeed(8)" class="replay-speed-btn" data-speed="8">8x</button>'
    +'<span style="color:#64748b;font-size:12px" id="replay-progress">0/'+replayData.length+'</span>'
    +'<button onclick="toggleReplayPause()" id="replay-pause-btn" style="padding:6px 16px;border-radius:6px;border:1px solid rgba(96,165,250,0.4);background:rgba(96,165,250,0.15);color:#60a5fa;font-size:13px;cursor:pointer">暂停</button>'
    +'<button onclick="replaySkip(-10)" title="后退10秒" style="padding:6px 14px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:transparent;color:#e2e8f0;font-size:13px;cursor:pointer">⏪ 10秒</button>'
    +'<button onclick="replaySkip(10)" title="前进10秒" style="padding:6px 14px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:transparent;color:#e2e8f0;font-size:13px;cursor:pointer">⏩ 10秒</button>'
    +'<button onclick="exitReplay()" style="padding:6px 16px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:transparent;color:#ef4444;font-size:13px;cursor:pointer;margin-left:24px">退出回放</button>';
  document.body.appendChild(bar);
  var style=document.createElement('style');
  style.textContent='.replay-speed-btn{padding:4px 12px;border-radius:6px;border:1px solid rgba(255,255,255,0.15);background:transparent;color:#94a3b8;font-size:13px;cursor:pointer;}.replay-speed-btn.active{background:rgba(96,165,250,0.2);color:#60a5fa;border-color:#60a5fa;}';
  document.head.appendChild(style);
}

function setReplaySpeed(speed){
  replaySpeed=speed;
  document.querySelectorAll('.replay-speed-btn').forEach(btn=>{
    btn.classList.toggle('active',parseInt(btn.dataset.speed)===speed);
  });
  if(replayTimer){clearInterval(replayTimer);startReplayPlayback();}
}

// 第8项：回放暂停/继续
var replayPaused=false;
function toggleReplayPause(){
  if(!replayTimer&&replayIndex>=replayData.length)return;
  replayPaused=!replayPaused;
  var btn=document.getElementById('replay-pause-btn');
  if(replayPaused){
    // 暂停：清除定时器
    if(replayTimer){clearInterval(replayTimer);replayTimer=null;}
    if(btn)btn.textContent='继续';
  }else{
    // 继续：从当前位置重启定时器
    if(btn)btn.textContent='暂停';
    startReplayPlayback();
  }
}

// 待办3：前进/后退10秒（真实跳转）
function replaySkip(seconds){
  if(!replayData||replayData.length===0)return;
  // 步间隔：1500ms / 倍速 → 10秒对应的步数
  var intervalMs=1500/replaySpeed;
  var steps=Math.max(1,Math.round(10000/intervalMs));
  var target;
  if(seconds<0){
    target=replayIndex-steps;
    if(target<1)target=1;
  }else{
    target=replayIndex+steps;
    if(target>replayData.length)target=replayData.length;
  }
  if(target===replayIndex)return;
  // 清除定时器
  if(replayTimer){clearInterval(replayTimer);replayTimer=null;}
  // 待办5：前进和后退都重绘画面（先恢复初始，再快进到目标步）
  // 修复5：重置手牌状态为发牌初始（_init置false触发重新初始化），再逐步执行到目标步
  if(window._replayDealMove&&typeof renderReplayHands==='function'){
    if(window._replayHands)window._replayHands._init=false;
    renderReplayHands(window._replayDealMove);
  }
  ['played-player','played-left','played-right'].forEach(function(id){
    var el=document.getElementById(id);
    if(el)el.innerHTML='';
  });
  replayIndex=1;
  while(replayIndex<target){
    executeReplayStep(replayData[replayIndex]);
    replayIndex++;
  }
  var prog=document.getElementById('replay-progress');
  if(prog)prog.textContent=replayIndex+'/'+replayData.length;
  // 从新位置继续播放
  startReplayPlayback();
}


function exitReplay(){
  if(replayTimer)clearInterval(replayTimer);
  if(currentUser&&currentUser.name){
    window.location.href='/lobby?name='+encodeURIComponent(currentUser.name);
  }else{
    window.location.href='/lobby';
  }
}

// 自动回放播放
function startReplayPlayback(){
  var interval=1500/replaySpeed;
  replayTimer=setInterval(function(){
    if(replayIndex>=replayData.length){
      clearInterval(replayTimer);replayTimer=null;
      showMsg('游戏结束',3000);
      return;
    }
    executeReplayStep(replayData[replayIndex]);
    replayIndex++;
    var prog=document.getElementById('replay-progress');
    if(prog)prog.textContent=replayIndex+'/'+replayData.length;
  },interval);
}

// 执行单步回放
function executeReplayStep(move){
  if(move.type==='deal')return;
  // 旧数据兼容：没有type但有cards的，当作出牌（player可能是字符串）
  if(!move.type&&move.cards){
    move.type='play';
  }
  var who=move.player;
  // 旧数据兼容：player 可能是名字字符串（'你'/'电脑A'/'电脑B'），映射回数字
  if(typeof who==='string'){
    var pm={'你':0,'电脑A':1,'电脑B':2};
    if(pm[who]!==undefined)who=pm[who];
    else who=0;
  }
  var name=PLAYER_NAMES[who]||'玩家';
  if(move.type==='landlord'){
    showMsg(name+'成为地主！');
    // 新问题2：定地主后，地主手牌+3张底牌（同步到手牌状态，保证重画不丢）
    var dealMove=replayData[0];
    if(dealMove&&dealMove.landlordCards){
      if(!window._replayHands||window._replayHands._init!==true){
        window._replayHands=[[],[],[]];
      }
      var handsArr=window._replayHands[who]||(window._replayHands[who]=[]);
      var rankMapL={'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15,'小王':16,'大王':17};
      dealMove.landlordCards.forEach(function(rc){
        var rk=(typeof rc==='object'&&rc!==null)?rc.rank:rc;
        var st=(typeof rc==='object'&&rc!==null)?rc.suit:0;
        if(typeof rk==='string')rk=rankMapL[rk]!==undefined?rankMapL[rk]:parseInt(rk)||0;
        handsArr.push({rank:rk,suit:st});
      });
      // 重画三份手牌（实时同步，张数+3）
      if(window._replayDealMove&&typeof renderReplayHands==='function')renderReplayHands(window._replayDealMove);
    }
    return;
  }
  if(move.type==='bid'){
    showMsg(name+'：'+(move.action||'叫地主')+'（'+(move.mult||1)+'倍）');
    // 在出牌区显示叫牌状态
    var playedId=who===0?'played-player':who===1?'played-left':'played-right';
    var played=document.getElementById(playedId);
    if(played){
      played.innerHTML='<div class="bid-status">'+name+'：'+(move.action||'叫地主')+'</div>';
    }
    // 第9项：刷新倍数显示（位置与正常游戏一致）
    var mult=move.mult||1;
    var multText=mult>1?('x'+mult):'';
    ['opp-left-mult','opp-right-mult','player-mult'].forEach(function(id){
      var el=document.getElementById(id);
      if(el)el.textContent=multText;
    });
    var sd=document.getElementById('score-display');
    if(sd)sd.textContent='倍数'+multText+' | 底分'+BASE_SCORE;
    return;
  }
  if(move.type==='pass'){
    showMsg(name+'：不出');
    // 在出牌区显示"不出"
    var playedId=who===0?'played-player':who===1?'played-left':'played-right';
    var played=document.getElementById(playedId);
    if(played){
      played.innerHTML='<div class="pass-text">不出</div>';
    }
    return;
  }
  if(move.type==='play'){
    // 第6项：提示文字用牌面名称，不显示数字
    var patName=move.pattern||'';
    var cardNames=(move.cards||'').split(',').map(function(cs){
      cs=cs.trim();
      if(cs==='小王')return '小王';
      if(cs==='大王')return '大王';
      var nm=cs.slice(0,-1);
      var nmMap={'J':'勾','Q':'圈','K':'K','A':'尖','2':'2'};
      var disp=nmMap[nm]!==undefined?nmMap[nm]:nm;
      return patName==='单张'||patName==='单'?('单'+disp):disp;
    }).join(' ');
    showMsg(name+'出了 '+patName+(cardNames?'：'+cardNames:''));
    // 解析牌面（兼容旧数据：没有type字段但有player和cards的也按出牌处理）
    var cardStrs=(move.cards||'').split(',');
    var cards=cardStrs.map(function(s){
      if(!s)return null;
      s=s.trim();
      // 大小王完整匹配
      if(s==='小王')return{id:Math.random(),suit:-1,rank:16};
      if(s==='大王')return{id:Math.random(),suit:-2,rank:17};
      // 兼容旧格式：数字点数+花色（如 14♠、16、17）
      var suitMap={'♠':0,'♥':1,'♦':2,'♣':3};
      var rankMap={'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15};
      if(s==='16')return{id:Math.random(),suit:-1,rank:16};
      if(s==='17')return{id:Math.random(),suit:-2,rank:17};
      var suitChar=s.slice(-1);
      var rankStr=s.slice(0,-1);
      var suit=suitMap[suitChar]!==undefined?suitMap[suitChar]:0;
      var rank=rankMap[rankStr]!==undefined?rankMap[rankStr]:(parseInt(rankStr)||0);
      return{id:Math.random(),suit:suit,rank:rank};
    }).filter(function(c){return c!==null;});
    // 渲染到出牌区（回放专用45px渲染）
    renderReplayPlayedCards(who,cards);
    // 修复5（核心）：从"当前手牌状态"中按点数+花色真实移除，再重画三份手牌（实时同步，出多少减多少）
    if(window._replayHands&&window._replayHands._init===true){
      var handsArr=window._replayHands[who]||[];
      cards.forEach(function(c){
        for(var j=0;j<handsArr.length;j++){
          if(handsArr[j].rank===c.rank&&handsArr[j].suit===c.suit){
            handsArr.splice(j,1);break;
          }
        }
      });
      if(window._replayDealMove&&typeof renderReplayHands==='function')renderReplayHands(window._replayDealMove);
    }
    return;
  }
}

// 从手牌中移除已出的牌
function removeCardsFromHand(containerId,cardsStr){
  var container=document.getElementById(containerId);
  if(!container)return;
  var cards=cardsStr.split(',');
  // 牌面名称 → 内部rank数字
  var rankToNum={'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15,'小王':16,'大王':17};
  // 旧格式数字点数 → 内部rank（兼容老数据）
  var numMap={'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'11':11,'12':12,'13':13,'14':14,'15':15,'16':16,'17':17};
  cards.forEach(function(cardStr){
    cardStr=cardStr.trim();
    if(!cardStr)return;
    var targetRank;
    if(cardStr==='小王')targetRank=16;
    else if(cardStr==='大王')targetRank=17;
    else{
      // 可能是"牌面+花色"(A♠) 或 旧格式"数字+花色"(14♠) 或 纯数字
      var rankStr;
      if(cardStr.length===1){rankStr=cardStr;}
      else{
        var lastCh=cardStr.slice(-1);
        if(lastCh==='♠'||lastCh==='♥'||lastCh==='♦'||lastCh==='♣')rankStr=cardStr.slice(0,-1);
        else rankStr=cardStr;
      }
      targetRank=rankToNum[rankStr]!==undefined?rankToNum[rankStr]:(numMap[rankStr]!==undefined?numMap[rankStr]:null);
    }
    if(targetRank===null)return;
    // 用 dataset.rank 匹配（renderCardEl 设置了 dataset.rank）
    var els=container.querySelectorAll('.card');
    for(var i=0;i<els.length;i++){
      var el=els[i];
      if(el.dataset.rank!==undefined&&Number(el.dataset.rank)===targetRank){
        el.remove();
        break;
      }
    }
  });
}


// 回放记录辅助函数
function recordBid(who,action){if(G.gameMoves)G.gameMoves.push({type:'bid',player:who,action:action,mult:G.bidMult||1});}

function initGame(){G={phase:'idle',deck:[],hands:[[],[],[]],landlordCards:[],landlord:-1,
    current:0,lastPlay:null,passCount:0,multiplier:1,
    selectedIds:new Set(),hintPlays:[],hintIdx:0,
    bidStarter:0,bidCurrent:0,bidCount:0,lastGrabber:-1,
    bidPhase:'call',caller:-1,callActed:[false,false,false],grabActed:[false,false,false],
    farmerPlayCount:0,landlordPlayCount:0,bidMult:1,bombMult:1,
    playedHands:[[],[],[]],phaseStep:'round_resolved',gameMoves:[]};
}


// 分数标签渲染（restoreGameState/dealRound/endGame 都会调用，不能删）
function renderScoreTags(){
  if(!sessionScores)return;
  var tags=['player-scores','opp-left-scores','opp-right-scores'];
  for(var i=0;i<3;i++){
    var el=document.getElementById(tags[i]);
    if(!el)continue;
    var s=sessionScores[i]||0;
    var cls=s>=0?'score-positive':'score-negative';
    el.innerHTML='<span class="score-tag '+cls+'">'+(s>=0?'+':'')+s+'</span>';
  }
}
// 回合显示渲染（restoreGameState/dealRound 都会调用，不能删）
function renderRoundDisplay(){
  var el=document.getElementById('round-display');
  if(el)el.textContent='第'+(currentRound||1)+'局 / 共'+TOTAL_ROUNDS+'局';
}
// ==================== GAME FLOW ====================



async function startNewGame(){
  clearSavedGame();
  currentRound++;
  playGameSound('voice_开始游戏');
  if(currentRound>TOTAL_ROUNDS){
    // Reset session
    currentRound=1;sessionScores=[0,0,0];
  }
  // 重新开始后重算一次布局（防止旋转/缓存导致的错位残留）
  if(typeof resizeResponsiveLayout==='function')resizeResponsiveLayout();
  await dealRound();
}

// 只负责发牌开局，不改局数（供"无人叫地主重新发牌"复用）
async function dealRound(){
  LEARN.roundId = Date.now() + '_' + Math.floor(Math.random() * 1000000);
  LEARN.step = 0;
  learnLoad();
  document.getElementById('result-modal').classList.remove('show');
  initGame();
  G.roundScores=[0,0,0]; // per-player score this round
  roundScore=BASE_SCORE;
  clearAllPlayed();clearLandlordCards();
  renderOpponentCards(LEFT,0);renderOpponentCards(RIGHT,0);
  renderPlayerHand();updateBadges();updateMultiplierDisplay();
  renderScoreTags();renderRoundDisplay();
  document.getElementById('actions').style.display='none';
  document.getElementById('bid-actions').style.display='none';
  const bidHistory=document.getElementById('bid-history');if(bidHistory)bidHistory.innerHTML='';
  showMsg('');

  G.deck=shuffle(createDeck());
  G.hands=[[],[],[]];
  for(let i=0;i<51;i++)G.hands[i%3].push(G.deck[i]);
  G.landlordCards=[G.deck[51],G.deck[52],G.deck[53]];
  G.hands.forEach(h=>sortCards(h));
  // 记录初始发牌（用于回放）
  G.gameMoves=[{type:'deal',myHand:G.hands[PLAYER].map(c=>({rank:c.rank,suit:c.suit})),leftHand:G.hands[LEFT].map(c=>({rank:c.rank,suit:c.suit})),rightHand:G.hands[RIGHT].map(c=>({rank:c.rank,suit:c.suit})),landlordCards:G.landlordCards.map(c=>({rank:c.rank,suit:c.suit}))}];
  G.phase='dealing';
  renderPlayerHand();
  const cards=document.querySelectorAll('#player-hand .card');
  cards.forEach((c,i)=>{c.style.opacity='0';c.style.animation='dealIn 0.25s '+(i*0.03)+'s ease-out forwards';});
  await sleep(300+cards.length*30);
  renderLandlordCards(false);
  renderOpponentCards(LEFT,17);renderOpponentCards(RIGHT,17);
  renderPlayerHand();updateBadges();

  G.bidStarter=Math.floor(Math.random()*3);
  G.bidCurrent=G.bidStarter;G.bidCount=0;
  G.phase='bidding';
  saveGameState();
  await sleep(500);
  doBidTurn();
}

function bidStatusContainer(who){
  return document.getElementById(who===LEFT?'played-left':(who===RIGHT?'played-right':'played-player'));
}
function renderBidStatus(who,text){
  const el=bidStatusContainer(who);if(!el)return;
  const old=el.querySelector('.bid-status');if(old&&old.textContent===text)return;
  el.innerHTML='<span class=\"bid-status\">'+text+'</span>';
}
function bidAreaFor(who){
  return who===PLAYER?document.getElementById('player-area'):
    document.getElementById(who===LEFT?'opp-left':'opp-right');
}
function clearBidHighlight(){
  document.querySelectorAll('.bid-active').forEach(el=>el.classList.remove('bid-active'));
}
function showBidStep(who,text){
  clearBidHighlight();
  const area=bidAreaFor(who);if(area)area.classList.add('bid-active');
  if(who===PLAYER)showMsg(text,1500);
  else renderBidStatus(who,text);
}
function bidResult(who,text){
  clearBidHighlight();renderBidStatus(who,text);
}
function nextPlayer(who){return(who+2)%3;}
function hideBidControls(){
  const el=document.getElementById('bid-actions');
  el.classList.remove('bid-pop');el.style.setProperty('display','none','important');
}
function showBidControls(mode){
  document.getElementById('actions').style.setProperty('display','none','important');
  const el=document.getElementById('bid-actions');
  const callMode=mode==='call',finalMode=mode==='final';
  document.getElementById('bid-yes').textContent=callMode?'叫地主':(finalMode?'再抢':'抢地主');
  document.getElementById('bid-no').textContent=callMode?'不叫':'不抢';
  el.style.setProperty('display','flex','important');void el.offsetWidth;el.classList.add('bid-pop');
}

async function doBidTurn(){
  if(G.phase!=='bidding')return;

  // Stage 1: P1 -> P2 -> P3. The first call immediately starts stage 2.
  if(G.bidPhase==='call'){
    const who=G.bidCurrent,label=PLAYER_NAMES[who];
    if(G.callActed[who]){G.bidCurrent=nextPlayer(who);doBidTurn();return;}
    if(who===PLAYER){
      showBidStep(who,'轮到你，请选择叫地主或不叫');showBidControls('call');return;
    }
    hideBidControls();showBidStep(who,label+'正在思考...');await sleep(1500);
    const call=await aiDecideBid(G.hands[who],true);G.callActed[who]=true;
    if(call){
      G.caller=who;G.lastGrabber=who;G.bidMult=2;updateMultiplierDisplay();
      playGameSound('voice_叫地主');recordBid(who,'叫地主');bidResult(who,label+'：叫地主（2倍）');await sleep(1500);
      G.bidPhase='grab';G.grabActed=[false,false,false];G.bidCurrent=nextPlayer(who);
    }else{
      playGameSound('voice_不抢');recordBid(who,'不叫');bidResult(who,label+'：不叫');await sleep(1500);
      if(G.callActed.every(Boolean)){await finishBidding();return;}
      G.bidCurrent=nextPlayer(who);
    }
    doBidTurn();return;
  }

  // Stage 2: ask the two players after caller exactly once.
  // If neither grabs, caller wins automatically without another prompt.
  const who=G.bidCurrent,label=PLAYER_NAMES[who];
  if(who===G.caller){
    if(G.lastGrabber===G.caller){await finishBidding();return;}
    // Someone grabbed, so the caller gets the final "再抢/不抢" choice.
    if(who===PLAYER){
      showBidStep(who,'轮到你，请选择再抢地主或不抢');showBidControls('final');return;
    }
    hideBidControls();showBidStep(who,label+'正在思考是否再抢...');await sleep(1500);
    const finalGrab=await aiDecideBid(G.hands[who],false);
    if(finalGrab){playGameSound('voice_抢地主');G.lastGrabber=who;G.bidMult*=2;updateMultiplierDisplay();recordBid(who,'抢地主');bidResult(who,label+'：再抢（'+G.bidMult+'倍）');}
    else{playGameSound('voice_不抢');recordBid(who,'不抢');bidResult(who,label+'：不抢');}
    await sleep(1500);finishBidding();return;
  }
  if(G.grabActed[who]){G.bidCurrent=nextPlayer(who);doBidTurn();return;}
  if(who===PLAYER){
    showBidStep(who,'轮到你，请选择抢地主或不抢');showBidControls('grab');return;
  }
  hideBidControls();showBidStep(who,label+'正在思考是否抢地主...');await sleep(1500);
  const grab=await aiDecideBid(G.hands[who],false);G.grabActed[who]=true;
  if(grab){playGameSound('voice_抢地主');G.lastGrabber=who;G.bidMult*=2;updateMultiplierDisplay();recordBid(who,'抢地主');bidResult(who,label+'：抢地主（'+G.bidMult+'倍）');}
  else{playGameSound('voice_不抢');recordBid(who,'不抢');bidResult(who,label+'：不抢');}
  await sleep(1500);
  G.bidCurrent=nextPlayer(who);doBidTurn();
}

async function playerBid(grab){
  if(G.phase!=='bidding'||G.bidCurrent!==PLAYER)return;
  hideBidControls();
  if(G.bidPhase==='call'){
    G.callActed[PLAYER]=true;
    if(grab){
      G.caller=PLAYER;G.lastGrabber=PLAYER;G.bidMult=2;updateMultiplierDisplay();
      playGameSound('voice_叫地主');recordBid(PLAYER,'叫地主');bidResult(PLAYER,'你：叫地主（2倍）');await sleep(1500);
      G.bidPhase='grab';G.grabActed=[false,false,false];G.bidCurrent=nextPlayer(PLAYER);
    }else{
      playGameSound('voice_不抢');recordBid(PLAYER,'不叫');bidResult(PLAYER,'你：不叫');await sleep(1500);
      if(G.callActed.every(Boolean)){await finishBidding();return;}
      G.bidCurrent=nextPlayer(PLAYER);
    }
    doBidTurn();return;
  }

  if(PLAYER===G.caller){
    if(grab){playGameSound('voice_抢地主');G.lastGrabber=PLAYER;G.bidMult*=2;updateMultiplierDisplay();recordBid(PLAYER,'抢地主');bidResult(PLAYER,'你：再抢（'+G.bidMult+'倍）');}
    else{playGameSound('voice_不抢');recordBid(PLAYER,'不抢');bidResult(PLAYER,'你：不抢');}
    await sleep(1500);finishBidding();return;
  }
  G.grabActed[PLAYER]=true;
  if(grab){playGameSound('voice_抢地主');G.lastGrabber=PLAYER;G.bidMult*=2;updateMultiplierDisplay();recordBid(PLAYER,'抢地主');bidResult(PLAYER,'你：抢地主（'+G.bidMult+'倍）');}
  else{playGameSound('voice_不抢');recordBid(PLAYER,'不抢');bidResult(PLAYER,'你：不抢');}
  await sleep(1500);G.bidCurrent=nextPlayer(PLAYER);doBidTurn();
}

async function finishBidding(){
  hideBidControls();clearBidHighlight();
  const bidHistory=document.getElementById('bid-history');if(bidHistory)bidHistory.innerHTML='';
  ['played-left','played-right','played-player'].forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML='';});
  if(G.lastGrabber<0){showMsg('无人叫地主，重新发牌',1500);await sleep(1500);dealRound();return;}
  showMsg(PLAYER_NAMES[G.lastGrabber]+'成为地主！',1500);await sleep(1500);
  becomeLandlord(G.lastGrabber);
}

async function becomeLandlord(who){
  clearBidHighlight();
  G.landlord=who;
  // 记录地主信息到回放数据
  if(G.gameMoves)G.gameMoves.push({type:'landlord',player:who});
  G.hands[who].push(...G.landlordCards);sortCards(G.hands[who]);
  renderLandlordCards(true);
  renderOpponentCards(LEFT,G.hands[LEFT].length);
  renderOpponentCards(RIGHT,G.hands[RIGHT].length);
  if(who===PLAYER)renderPlayerHand();
  updateBadges();updateMultiplierDisplay();
  renderScoreTags();
  showMsg(PLAYER_NAMES[who]+' 成为地主！('+G.hands[who].length+'张牌)');await sleep(1000);
  G.current=who;G.phase='playing';G.lastPlay=null;G.passCount=0;
  clearAllPlayed();saveGameState();doPlayTurn();
}

async function doPlayTurn(){
  if(G.phase!=='playing')return;
  for(let i=0;i<3;i++){if(G.hands[i].length===0){endGame(i);return;}}
  G.phaseStep='turn_start';saveGameState();
  const isLeading=!G.lastPlay||G.lastPlay.player===G.current;
  if(G.current===PLAYER){
    G.phaseStep='player_waiting';
    document.getElementById('actions').style.display='flex';
    document.getElementById('btn-pass').disabled=isLeading;
    showMsg(isLeading?'你的回合，请出牌':'轮到你出牌');
    G.hintPlays=[];G.hintIdx=0;
  }else{
    renderBidStatus(G.current,PLAYER_NAMES[G.current]+'正在思考...');
    document.getElementById('actions').style.display='none';
    await sleep(1200+Math.random()*600);
    G.phaseStep='ai_thinking_done';
    const lastPat=(G.lastPlay&&!isLeading)?G.lastPlay.pattern:null;
    let play=null;
    try{play=await aiPlay(G.hands[G.current],lastPat);}catch(err){console.error('AI error:',err);play=null;}
    if(play){
      try{
        const pat=detectPattern(play);
        if(pat)await doPlayCards(G.current,play,pat);
        else await doPass(G.current);
      }catch(err){console.error('Play error:',err);await doPass(G.current);}
    }else{await doPass(G.current);}
  }
}

async function doPlayCards(who,cards,pattern){
  const ids=new Set(cards.map(c=>c.id));
  G.hands[who]=G.hands[who].filter(c=>!ids.has(c.id));
  G.playedHands[who].push(...cards);
  G.lastPlay={cards,pattern,player:who};G.passCount=0;
  if(G.gameMoves)G.gameMoves.push({type:'play',player:who,pattern:patternName(pattern.type),cards:cards.map(c=>{var nm=c.rank===16?'小王':c.rank===17?'大王':({3:'3',4:'4',5:'5',6:'6',7:'7',8:'8',9:'9',10:'10',11:'J',12:'Q',13:'K',14:'A',15:'2'})[c.rank]||c.rank;return c.rank>=16?nm:nm+(c.suit>=0?['♠','♥','♦','♣'][c.suit]:'');}).join(',')});
  if(who===G.landlord)G.landlordPlayCount++;
  else G.farmerPlayCount++;
  if(pattern.type==='BOMB'||pattern.type==='ROCKET'){
    G.bombMult*=2;updateMultiplierDisplay();
  }
  renderPlayedCards(who,cards);
  if(who===LEFT||who===RIGHT)renderOpponentCards(who,G.hands[who].length);
  if(who===PLAYER){G.selectedIds.clear();renderPlayerHand();}
  updateBadges();
  const pn=patternName(pattern.type);
  if(who===PLAYER)showMsg('你出了 '+pn);
  else showMsg(PLAYER_NAMES[who]+': '+pn);
  
  // === 出牌音效 ===
  try{
    const _isPress=G.lastPlay&&G.lastPlay.player!==who;
    if(pattern.type==='BOMB'){
      playGameSound('voice_炸弹');setTimeout(()=>playGameSound('炸弹_大'),300);
      bombEffect();showMsg((who===PLAYER?'你':PLAYER_NAMES[who])+' 出了 '+pn+'！倍数x'+(G.bidMult*G.bombMult),2500);
    }else if(pattern.type==='ROCKET'){
      playGameSound('voice_王炸');setTimeout(()=>playGameSound('炸弹_大'),300);
      bombEffect();showMsg((who===PLAYER?'你':PLAYER_NAMES[who])+' 出了 '+pn+'！倍数x'+(G.bidMult*G.bombMult),2500);
    }else if(pattern.type==='SINGLE'){
      const r=cards[0].rank;
      const nm={3:'三',4:'四',5:'五',6:'六',7:'七',8:'八',9:'九',10:'十',11:'J',12:'Q',13:'K',14:'尖',15:'二',16:'小王',17:'大王'};
      if(r===16)playGameSound('voice_小王');
      else if(r===17)playGameSound('voice_大王');
      else playGameSound('voice_'+(nm[r]||''));
      if(_isPress)playGameSound('voice_压你');
    }else if(pattern.type==='PAIR'){
      const r=cards[0].rank;
      const nm={3:'三',4:'四',5:'五',6:'六',7:'七',8:'八',9:'九',10:'十',11:'J',12:'Q',13:'K',14:'尖',15:'二'};
      playGameSound('voice_对'+(nm[r]||''));
      if(_isPress)playGameSound('voice_压你');
    }else if(pattern.type==='STRAIGHT'){
      if(_isPress)playGameSound('voice_压你');else playGameSound('voice_顺子');
    }else if(pattern.type==='STRAIGHT_PAIR'){
      if(_isPress)playGameSound('voice_压你');else playGameSound('voice_连对');
    }else if(pattern.type==='TRIPLE'){
      if(_isPress)playGameSound('voice_压你');else playGameSound('voice_三');
    }else if(pattern.type==='TRIPLE_ONE'){
      if(_isPress)playGameSound('voice_压你');else playGameSound('voice_三带一');
    }else if(pattern.type==='TRIPLE_TWO'){
      if(_isPress)playGameSound('voice_压你');else playGameSound('voice_三带二');
    }else{
      if(_isPress)playGameSound('voice_压你');
    }
  }catch(e){console.warn('sound err',e);}
  await sleep(800);
  G.phaseStep='round_resolved';G.current=nextPlayer(G.current);doPlayTurn();
}

async function doPass(who){
  if(who!==PLAYER&&typeof aiRecordPass==='function')aiRecordPass(who);
  renderPassText(who);G.passCount++;
  if(G.gameMoves)G.gameMoves.push({type:'pass',player:who});
  playGameSound('voice_过');
  if(who===PLAYER)showMsg('你：不出');
  if(G.passCount>=2){G.lastPlay=null;G.passCount=0;await sleep(600);clearAllPlayed();}
  await sleep(600);
  G.phaseStep='round_resolved';G.current=nextPlayer(G.current);doPlayTurn();
}

function playerPlay(){
  if(G.phase!=='playing'||G.current!==PLAYER)return;
  const selected=G.hands[PLAYER].filter(c=>G.selectedIds.has(c.id));
  if(selected.length===0){showMsg('请先选择卡牌');return;}
  const pat=detectPattern(selected);
  if(!pat){showMsg('牌型不合法，请重新选择');return;}
  const isLeading=!G.lastPlay||G.lastPlay.player===PLAYER;
  const lastPat=isLeading?null:G.lastPlay.pattern;
  if(lastPat&&!canBeat(pat,lastPat)){showMsg('打不过上家，请重新选择');return;}
  document.getElementById('actions').style.display='none';
  doPlayCards(PLAYER,selected,pat);
}

function playerPass(){
  if(G.phase!=='playing'||G.current!==PLAYER)return;
  const isLeading=!G.lastPlay||G.lastPlay.player===PLAYER;
  if(isLeading){showMsg('你必须出牌');return;}
  document.getElementById('actions').style.display='none';
  doPass(PLAYER);
}

async function playerHint(){
  if(G.phase!=='playing'||G.current!==PLAYER)return;
  const isLeading=!G.lastPlay||G.lastPlay.player===PLAYER;
  const lastPat=isLeading?null:G.lastPlay.pattern;

  // 优先调后端API获取提示
  try{
    const ctrl=new AbortController();
    const timer=setTimeout(()=>ctrl.abort(),3000);
    const res=await fetch(AI_API+'/hint',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      signal:ctrl.signal,
      body:JSON.stringify({
        hand:G.hands[PLAYER].map(c=>({id:c.id,r:c.rank,s:c.suit})),
        last:lastPat?{type:lastPat.type,main:lastPat.main,len:lastPat.len}:null,
        who:PLAYER,landlord:G.landlord,
        landlord_count:aiLandlordCount(),
        teammate_count:(function(){const p=aiPartner(PLAYER);return p>=0?(G.hands[p]||[]).length:99;})()
      })
    });
    clearTimeout(timer);
    const data=await res.json();
    if(data.ok&&data.plays&&data.plays.length>0){
      // 将后端返回的牌转换为前端card对象
      const plays=data.plays.map(p=>p.cards.map(a=>{
        const match=G.hands[PLAYER].find(c=>c.rank===a.r&&c.suit===a.s);
        return match||{id:-1,rank:a.r,suit:a.s};
      }));
      if(G.hintPlays.length===0||JSON.stringify(G.hintPlays)!==JSON.stringify(plays)){
        G.hintPlays=plays;G.hintIdx=0;
      }
      G.selectedIds.clear();
      G.hintPlays[G.hintIdx].forEach(c=>G.selectedIds.add(c.id));
      renderPlayerHand();
      G.hintIdx=(G.hintIdx+1)%G.hintPlays.length;
      return;
    }
  }catch(e){}

  // 降级：本地计算
  if(G.hintPlays.length===0){
    G.hintPlays=findAllBeatingPlays(G.hands[PLAYER],lastPat);G.hintIdx=0;
  }
  if(G.hintPlays.length===0){showMsg('没有能出的牌');return;}
  G.selectedIds.clear();
  G.hintPlays[G.hintIdx].forEach(c=>G.selectedIds.add(c.id));
  renderPlayerHand();
  G.hintIdx=(G.hintIdx+1)%G.hintPlays.length;
}

function renderSettlementHands(){
  const slots=[
    {id:'settlement-player',who:PLAYER},
    {id:'settlement-left',who:LEFT},
    {id:'settlement-right',who:RIGHT}
  ];
  slots.forEach(({id,who})=>{
    const box=document.getElementById(id);
    if(!box)return;
    const area=box.querySelector('.settlement-cards');
    const heading=box.querySelector('h4');
    if(heading)heading.textContent=(who===PLAYER?'你的剩余手牌':'电脑'+(who===LEFT?'A':'B')+'剩余手牌')+'（剩余'+(G.hands[who]||[]).length+'张）';
    area.innerHTML='';
    const remaining=[...(G.hands[who]||[])];
    sortCards(remaining);
    if(remaining.length===0){
      area.innerHTML='<span class=\"settlement-empty\">已出完</span>';
    }else{
      remaining.forEach(card=>area.appendChild(renderCardEl(card,'card-sm')));
    }
  });
}

function endGame(winner){
  // 回放模式下不显示游戏结束弹窗
  if(typeof isReplayMode!=='undefined'&&isReplayMode){
    return;
  }
  clearSavedGame();
  // Clear the final played card before showing the settlement modal.
  clearAllPlayed();
  G.phase='ended';
  document.getElementById('actions').style.display='none';

  // Spring/anti-spring detection
  let isSpring=false;
  const landlordHand=G.hands[G.landlord];
  // Check played cards count for each player
  // We need to track if farmers played any cards
  // Spring: landlord wins and both farmers never played (all 17 cards still in hand)
  // Anti-spring: farmers win and landlord only played once (17+ cards still in hand)
  // We track via G.springCheck set in doPlayCards
  
  const farmerPlayed=G.farmerPlayCount||0;
  const landlordPlayCount=G.landlordPlayCount||0;
  
  let springMult=1;
  if(winner===G.landlord&&farmerPlayed===0){
    isSpring=true;springMult=2;
  }else if(winner!==G.landlord&&landlordPlayCount<=1){
    isSpring=true;springMult=2;
  }
  roundScore=BASE_SCORE*G.bidMult*G.bombMult*springMult;
  updateMultiplierDisplay();

  // Calculate scores
  const isLandlordWin=winner===G.landlord;
  const score=roundScore;
  if(isLandlordWin){
    // Zero-sum settlement: landlord receives both farmers' stakes.
    for(let i=0;i<3;i++){
      if(i===G.landlord){sessionScores[i]+=score*2;G.roundScores[i]=score*2;}
      else{sessionScores[i]-=score;G.roundScores[i]=-score;}
    }
  }else{
    // Zero-sum settlement: both farmers receive their stake; landlord pays both.
    for(let i=0;i<3;i++){
      if(i===G.landlord){sessionScores[i]-=score*2;G.roundScores[i]=-score*2;}
      else{sessionScores[i]+=score;G.roundScores[i]=score;}
    }
  }
  renderScoreTags();
  renderSettlementHands();

  const titleEl=document.getElementById('result-title');
  const textEl=document.getElementById('result-text');
  const multEl=document.getElementById('result-mult');
  const scoresEl=document.getElementById('round-result-scores');
  const restartBtn=document.getElementById('btn-restart');

  // 胜负判定：玩家赢 ⇔ 胜者与玩家同阵营（同为地主或同为农民）
  const landlordWon=winner===G.landlord;
  const playerWon=landlordWon===(G.landlord===PLAYER);
  if(playerWon){
    titleEl.textContent='🎉 你赢了！';titleEl.style.color='#f0c040';
    playGameSound('voice_你赢了');
  }else{
    titleEl.textContent='😢 你输了';titleEl.style.color='#e74c3c';
    playGameSound('voice_你输了');
  }
  textEl.textContent=PLAYER_NAMES[winner]+' 出完了所有牌';

  // 记录战绩到后端
  try{
    const role=G.landlord===PLAYER?'landlord':'farmer';
    const result=playerWon?'win':'lose';
    recordGameResult(result,role,currentRound,0,G.gameMoves||[],G.bidMult*G.bombMult*BASE_SCORE*(result==='win'?1:-1),G.bidMult);
    // AI 学习回填（AI 视角胜负：与地主同阵营者 win）——与登录状态无关，游客局也执行
    try{
      const aiResults=[];
      [LEFT, RIGHT].forEach(w=>{
        const wWon=(G.landlord===w)===landlordWon;
        aiResults.push({who: w===LEFT?'LEFT':'RIGHT', result: wWon?'win':'lose'});
      });
      fetch(API_BASE + '/api/ai/backfill', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({round_id: LEARN.roundId, game_id: null, results: aiResults})
      }).catch(()=>{});
    }catch(e){console.warn('AI backfill fail',e);}
  }catch(e){console.warn('record fail',e);}
  multEl.textContent='';

  if(currentRound>=TOTAL_ROUNDS){
    scoresEl.innerHTML=showRoundScoreBreakdown()+'<h3 style="color:#f0c040;margin:12px 0 8px">🏆 10局累计总排名</h3>'+showFinalRanking();
    restartBtn.textContent='开始新一轮';
    restartBtn.disabled=false;
    document.getElementById('result-modal').classList.add('show');
    return;
  }else{
    scoresEl.innerHTML=showRoundScoreBreakdown();
    restartBtn.textContent='下一局';
    restartBtn.disabled=false;
  }
  document.getElementById('result-modal').classList.add('show');
}

// ==================== 局分结算渲染 ====================
function showRoundScoreBreakdown(){
  if(!G||!G.roundScores)return '<div style="color:#94a3b8;font-size:13px;padding:8px">本局得分暂无</div>';
  let html='<div style="margin:8px 0">';
  for(let i=0;i<3;i++){
    const s=G.roundScores[i]||0;
    const color=s>=0?'#4ade80':'#f87171';
    const sign=s>=0?'+':'';
    html+='<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:14px">'
      +'<span style="color:#e2e8f0">'+PLAYER_NAMES[i]+'</span>'
      +'<span style="color:'+color+';font-weight:700">'+sign+s+'</span></div>';
  }
  html+='</div>';
  return html;
}

function showFinalRanking(){
  const order=[0,1,2].map(i=>({name:PLAYER_NAMES[i],score:sessionScores[i]||0}))
    .sort((a,b)=>b.score-a.score);
  let html='<div style="margin:8px 0">';
  order.forEach((p,idx)=>{
    const medal=['🥇','🥈','🥉'][idx]||(idx+1)+'. ';
    const color=p.score>=0?'#4ade80':'#f87171';
    html+='<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:14px">'
      +'<span style="color:#e2e8f0">'+medal+' '+p.name+'</span>'
      +'<span style="color:'+color+';font-weight:700">'+(p.score>=0?'+':'')+p.score+'</span></div>';
  });
  html+='</div>';
  return html;
}

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

// ===== 叫地主 v4（改为后端 API 调用 + 简化 fallback） =====
async function aiDecideBid(hand, isCallPhase) {
  // 尝试后端 API
  const apiBid = await aiBidViaAPI(hand, isCallPhase);
  if (apiBid >= 0) return apiBid;

  // 降级：简化判断
  return fallbackBidSimple(hand);
}

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
        teammate_count: (function(){const p=aiPartner(who); return p>=0?(G.hands[p]||[]).length:99;})()
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
      body: JSON.stringify({ hand: hand.map(c => ({ id: c.id, r: c.rank, s: c.suit })), isCallPhase })
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

// ==================== UI RENDERING ====================
function renderCardEl(card,extraClass=''){
  const el=document.createElement('div');
  const color=getSuitColor(card.suit);
  el.className='card '+color+' '+extraClass;
  el.dataset.id=card.id;el.dataset.rank=card.rank;
  if(card.rank>=16){
    const jokerColor=card.rank===17?'#d32f2f':'#222';
    const label=card.rank===16?'小王':'大王';
    el.innerHTML=
      '<div style="position:absolute;top:6px;left:50%;transform:translateX(-50%);font-size:7px;color:'+jokerColor+';opacity:0.6">♛</div>'+
      '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;font-weight:900;color:'+jokerColor+';">'+
        '<span style="font-size:0.7em;letter-spacing:0;line-height:1.1">J</span>'+
        '<span style="font-size:0.7em;letter-spacing:0;line-height:1.1">O</span>'+
        '<span style="font-size:0.7em;letter-spacing:0;line-height:1.1">K</span>'+
        '<span style="font-size:0.7em;letter-spacing:0;line-height:1.1">E</span>'+
        '<span style="font-size:0.7em;letter-spacing:0;line-height:1.1">R</span>'+
      '</div>'+
      '<div style="position:absolute;bottom:4px;left:50%;transform:translateX(-50%);font-size:8px;color:'+jokerColor+';font-weight:700">'+label+'</div>';
  }else{
    const rn=getRankName(card.rank),ss=getSuitSymbol(card.suit);
    el.innerHTML='<div class="corner tl"><span class="rank">'+rn+'</span><span class="suit">'+ss+'</span></div>'+
      '<div class="center-suit">'+ss+'</div>'+
      '<div class="corner br"><span class="rank">'+rn+'</span><span class="suit">'+ss+'</span></div>';
  }
  return el;
}

function renderCardBack(extraClass=''){
  const el=document.createElement('div');el.className='card card-back '+extraClass;return el;
}

function renderLandlordCards(faceUp){
  const area=document.getElementById('landlord-area');area.innerHTML='';
  G.landlordCards.forEach(c=>{
    const el=faceUp?renderCardEl(c,'card-sm'):renderCardBack('card-sm');
    el.style.width='41px';el.style.height='54px';
    area.appendChild(el);
  });
}
function clearLandlordCards(){document.getElementById('landlord-area').innerHTML='';}

function renderOpponentCards(who,count){
  const container=document.getElementById(who===LEFT?'opp-left-cards':'opp-right-cards');
  container.innerHTML='';
  const show=Math.min(count,8);
  for(let i=0;i<show;i++)container.appendChild(renderCardBack());
}

function renderPlayerHand(){
  if(typeof isReplayMode!=='undefined'&&isReplayMode)return;
  const outer=document.getElementById('player-hand'),container=document.getElementById('player-hand-inner');if(!outer||!container)return;
  container.innerHTML='';const hand=(G&&G.hands&&G.hands[PLAYER])||[],styles=getComputedStyle(document.documentElement);
  const cardW=parseFloat(styles.getPropertyValue('--legacy-card-w'))||window.innerHeight*.065;
  const cardH=parseFloat(styles.getPropertyValue('--legacy-card-h'))||cardW*1.4;
  container.style.width=(cardW+(hand.length-1)*cardW*.55)+'px';
  hand.forEach(card=>{
    const el=renderCardEl(card);if(G.selectedIds.has(card.id))el.classList.add('selected');
    el.style.width=cardW+'px';el.style.height=cardH+'px';el.style.flex='0 0 '+cardW+'px';el.style.margin='0 0 0 '+(-cardW*.45)+'px';container.appendChild(el);
  });
  if(container.firstElementChild)container.firstElementChild.style.marginLeft='0';
}

function refreshSelectionVisuals(){
  handEl.querySelectorAll('.card').forEach(el=>{
    const id=Number(el.dataset.id);
    el.classList.toggle('selected',G.selectedIds.has(id));
  });
}

function toggleSelect(cardId){
  if(G.phase!=='playing')return;
  if(G.selectedIds.has(cardId))G.selectedIds.delete(cardId);
  else G.selectedIds.add(cardId);
  G.hintPlays=[];renderPlayerHand();
}

function renderPlayedCards(who,cards){
  const cid=who===LEFT?'played-left':(who===RIGHT?'played-right':'played-player');
  const container=document.getElementById(cid);container.innerHTML='';
  const gap=8,screenW=window.innerWidth;
  const maxGroupW=Math.min(screenW*.60,screenW-20);
  const baseW=screenW>=1100?72:Math.max(40,Math.min(window.innerHeight*.065,52));
  const cardW=Math.max(28,Math.min(baseW,(maxGroupW-gap*Math.max(0,cards.length-1))/Math.max(1,cards.length)));
  const cardH=cardW*(screenW>=1100?1.4:1.4);
  container.style.setProperty('--played-card-w',cardW+'px');
  container.style.setProperty('--played-card-h',cardH+'px');
  cards.forEach(c=>{
    const el=renderCardEl(c,'card-sm');
    el.style.width=cardW+'px';el.style.height=cardH+'px';
    el.style.margin='0';el.style.flex='0 0 '+cardW+'px';
    container.appendChild(el);
  });
}

function renderPassText(who){
  const cid=who===LEFT?'played-left':(who===RIGHT?'played-right':'played-player');
  document.getElementById(cid).innerHTML='<span class="pass-text">不出</span>';
}

function clearAllPlayed(){['played-left','played-right','played-player'].forEach(id=>{document.getElementById(id).innerHTML='';});}

function updateBadges(){
  document.getElementById('opp-left-count').textContent=G.hands[LEFT].length+'张';
  document.getElementById('opp-right-count').textContent=G.hands[RIGHT].length+'张';
  ['player-label','opp-left-label','opp-right-label'].forEach((id,i)=>{
    const el=document.getElementById(id);
    const old=el.querySelector('.landlord-icon');if(old)old.remove();
    if(G.landlord===i){const s=document.createElement('span');s.className='landlord-icon';s.textContent='地主';s.style.fontSize='15px';s.style.width='auto';s.style.padding='2px 8px';s.style.fontWeight='900';s.style.letterSpacing='1px';s.style.boxShadow='0 2px 8px rgba(240,192,64,0.5)';el.insertBefore(s,el.children[1]||null);}
  });
}

function updateMultiplierDisplay(){
  const total=G.bidMult*G.bombMult;
  const m='x'+total;
  ['opp-left-mult','opp-right-mult','player-mult'].forEach(id=>{document.getElementById(id).textContent=total>1?m:'';});
  document.getElementById('score-display').textContent='倍数'+m+' | 底分'+BASE_SCORE;
}

// ==================== MESSAGES & EFFECTS ====================
let msgTimer=null,lastMsgText='';
function showMsg(text,duration=2000){
  const el=document.getElementById('msg-toast');
  if(text===lastMsgText&&el.classList.contains('show'))return;
  lastMsgText=text;
  el.textContent=text;el.classList.add('show');
  clearTimeout(msgTimer);
  if(text)msgTimer=setTimeout(()=>el.classList.remove('show'),duration);
  else el.classList.remove('show');
}

function bombEffect(){
  const t=document.getElementById('game-table');
  t.classList.add('bomb-flash');
  setTimeout(()=>t.classList.remove('bomb-flash'),600);
}

function sleep(ms){return new Promise(r=>setTimeout(r,ms));}

// ==================== TOUCH SWIPE-TO-SELECT + MOUSE CLICK ====================
const handEl=document.getElementById('player-hand');
let swipeActive=false,swipeSelectedIds=new Set(),swipeDeselectedIds=new Set(),suppressNextClick=false;

function getCardAtX(x){
  const cards=Array.from(handEl.querySelectorAll('.card'));
  for(let i=cards.length-1;i>=0;i--){
    const rect=cards[i].getBoundingClientRect();
    if(x>=rect.left)return cards[i];
  }
  return cards[0];
}

handEl.addEventListener('touchstart',e=>{
  if(G.phase!=='playing')return;
  const cardEl=e.target.closest('.card');
  if(!cardEl)return;
  swipeActive=true;
  swipeSelectedIds.clear();
  swipeDeselectedIds.clear();
  const id=parseInt(cardEl.dataset.id);
  // Record initial state: if card was selected, mark for deselect; if not, mark for select
  if(G.selectedIds.has(id)){swipeDeselectedIds.add(id);}
  else{swipeSelectedIds.add(id);}
  // Apply immediately
  if(swipeSelectedIds.has(id))G.selectedIds.add(id);
  if(swipeDeselectedIds.has(id))G.selectedIds.delete(id);
  refreshSelectionVisuals();
},{passive:true});

handEl.addEventListener('touchmove',e=>{
  if(!swipeActive)return;
  e.preventDefault();
  const cardEl=getCardAtX(e.touches[0].clientX);
  if(!cardEl)return;
  const id=parseInt(cardEl.dataset.id);
  if(!swipeSelectedIds.has(id)&&!swipeDeselectedIds.has(id)){
    // This card hasn't been visited yet - apply same action as initial card
    if(swipeSelectedIds.size>0){
      // Initial was "select" mode
      swipeSelectedIds.add(id);
      G.selectedIds.add(id);
    }else{
      swipeDeselectedIds.add(id);
      G.selectedIds.delete(id);
    }
    refreshSelectionVisuals();
  }
},{passive:false});

handEl.addEventListener('touchend',e=>{
  swipeActive=false;
  suppressNextClick=true;
  setTimeout(()=>{suppressNextClick=false;},350);
  G.hintPlays=[];
});

// Mouse click to toggle single card
handEl.addEventListener('click',e=>{
  const cardEl=e.target.closest('.card');
  if(!cardEl||G.phase!=='playing'||suppressNextClick)return;
  const id=parseInt(cardEl.dataset.id);
  if(Number.isInteger(id))toggleSelect(id);
});

// ==================== EVENTS ====================
document.getElementById('btn-start-continue').onclick=startFromMenu;
document.getElementById('btn-continue-saved').onclick=continueFromMenu;
document.getElementById('btn-start-new').onclick=restartFromMenu;
document.getElementById('btn-play').onclick=playerPlay;
document.getElementById('btn-pass').onclick=playerPass;
document.getElementById('btn-hint').onclick=playerHint;
document.getElementById('bid-yes').onclick=()=>playerBid(true);
document.getElementById('bid-no').onclick=()=>playerBid(false);
document.getElementById('btn-restart').onclick=startNewGame;
document.getElementById('btn-back-to-lobby').onclick=goToLobby;
document.addEventListener('gesturestart',e=>e.preventDefault());
document.addEventListener('dblclick',e=>e.preventDefault());

function resizeResponsiveLayout(){
  // 强制横屏：竖屏时交换宽高，确保布局始终按横屏计算
  var rw=window.innerWidth,rh=window.innerHeight;
  var w=Math.max(rw,rh),h=Math.min(rw,rh);
  if(w<100)return;
  const root=document.documentElement,hand=(G.hands&&G.hands[PLAYER])||[],n=Math.max(1,hand.length);
  // 2026-08-04：手机横屏（宽<1100）按宽度算且明显放大，桌面按宽度算
  let cardW;
  if(w<1100)cardW=Math.min(52,Math.max(40,w*.058));
  else cardW=Math.min(80,Math.max(56,w*.042));
  const maxW=w*.94,needed=cardW+(n-1)*cardW*.55;
  if(needed>maxW)cardW=Math.max(40,maxW/(1+(n-1)*.55));
  const cardH=cardW*1.4;
  root.style.setProperty('--legacy-card-w',cardW+'px');root.style.setProperty('--legacy-card-h',cardH+'px');
  root.style.setProperty('--legacy-card-font',(cardH*.30)+'px');root.style.setProperty('--legacy-suit-font',(cardH*.26)+'px');
  const playedW=w>=1100?75:40;root.style.setProperty('--played-card-w',playedW+'px');root.style.setProperty('--played-card-h',(playedW*1.4)+'px');
  if(typeof renderPlayerHand==='function')renderPlayerHand();
}
window.addEventListener('resize',resizeResponsiveLayout,{passive:true});
window.addEventListener('orientationchange',()=>setTimeout(resizeResponsiveLayout,80),{passive:true});
if(window.visualViewport)window.visualViewport.addEventListener('resize',resizeResponsiveLayout);

// ==================== 手机端：页面隐藏/退出时自动存档 ====================
// 防止切后台/息屏/浏览器回收页面时，进度回退到上一个存档点
document.addEventListener('visibilitychange',()=>{if(document.hidden&&typeof saveGameState==='function')saveGameState();});
window.addEventListener('pagehide',()=>{if(typeof saveGameState==='function')saveGameState();});

// ==================== 防止背景拖动 ====================
document.addEventListener('touchmove', function(e) {
  // 手牌区域放行（允许拖拽选牌）
  if (e.target.closest && e.target.closest('#player-hand')) return;
  // 弹窗内的滚动放行
  if (e.target.closest && (e.target.closest('.profile-content') || e.target.closest('.settings-section') || e.target.closest('.replay-box') || e.target.closest('#login-modal') || e.target.closest('#start-modal') || e.target.closest('#result-modal'))) return;
  e.preventDefault();
}, {passive: false});

// ==================== 界面锁死横屏（2026-08-14） ====================
// 手机怎么转，界面布局都不动、不变形、不重排
// 仅当横屏反向（转180°换手拿）时整体翻转，保证内容朝上
function applyLockedLandscape(){
  var ori = (window.orientation!==undefined)?window.orientation:(screen.orientation?screen.orientation.angle:0);
  var app = document.getElementById('game-table');
  if(!app)return;
  // 仅横屏反向（180°）时整体翻转；横屏正向(0)和竖屏(90/-90)都不动
  if(ori === 180 || ori === -180){
    app.style.transform='rotate(180deg)';
  }else{
    app.style.transform='';
  }
}
window.addEventListener('orientationchange',function(){setTimeout(applyLockedLandscape,100);});
window.addEventListener('resize',applyLockedLandscape);
applyLockedLandscape();

// ==================== INIT ====================
const API_BASE = window.location.origin;

const _urlParams = new URLSearchParams(window.location.search);
const _replayId = _urlParams.get('replay');
if (_replayId) {
  // 回放模式：从页面加载起就隐藏开始弹窗，避免"开始游戏"弹窗闪现/拦截回放
  const _sm = document.getElementById('start-modal');
  if (_sm) _sm.classList.add('hidden');
} else {
  // 普通模式：显示干净的开始界面（仅"开始游戏"按钮，无提示文本）
  updateStartModal();
}

resizeResponsiveLayout();
// iOS 首次加载横屏时视口尺寸不稳定，延迟重算几次，避免底部白边/错位
setTimeout(resizeResponsiveLayout,400);
setTimeout(resizeResponsiveLayout,1200);

// 页面加载时从 localStorage 恢复音量设置
(function(){
  var bgmVol=localStorage.getItem('doudizhu_bgm_vol');
  if(bgmVol!==null&&typeof setBgmVolume==='function')setBgmVolume(bgmVol);
  var sfxVol=localStorage.getItem('doudizhu_sfx_vol');
  if(sfxVol!==null&&typeof setSfxVolume==='function')setSfxVolume(sfxVol);
})();

// 首次点击解锁声音（浏览器自动播放策略：必须有用户手势才能出声，2026-08-30 修复"点一下再点一下才有声音"）
(function(){
  var unlocked=false;
  document.addEventListener('click', function unlockSound(){
    if(unlocked)return;
    unlocked=true;
    var bgm=document.getElementById('bgm-audio');
    if(bgm&&!bgm.muted){
      bgm.volume=(localStorage.getItem('doudizhu_bgm_vol')||80)/100;
      bgm.play().catch(function(){});
    }
    document.removeEventListener('click', unlockSound);
  }, true);
})();

// 注册 Service Worker（PWA 离线缓存，仅 https/file 环境生效）
if('serviceWorker' in navigator){window.addEventListener('load',()=>{navigator.serviceWorker.register('./sw.js').catch(()=>{});});}



function openSettings() {
  document.getElementById('settings-modal').classList.add('show');
  loadStats();
  loadLeaderboard();
  loadAiProgress();
  // 同步音量滑块
  var bgmVol=localStorage.getItem('doudizhu_bgm_vol');
  var sfxVol=localStorage.getItem('doudizhu_sfx_vol');
  if(bgmVol!==null)setBgmVolume(bgmVol);
  if(sfxVol!==null)setSfxVolume(sfxVol);
  // 同步 toggle 状态
  updateUserInfoDisplay();
  // 注销按钮显隐
  var delBtn = document.getElementById('btn-delete-account');
  if (delBtn) delBtn.style.display = (currentUser && currentUser.name && currentUser.name !== '游客') ? 'block' : 'none';
}

function closeSettings() {
  document.getElementById('settings-modal').classList.remove('show');
}

function loadAiProgress() {
  var el = document.getElementById('ai-learning-content');
  if (!el) return;
  fetch(API + '/ai/learning/progress')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (!d.strategies || d.strategies.length === 0) {
        el.innerHTML = '<div class="learn-summary">暂无数据——打几局后自动开始记录。</div>';
        return;
      }
      var total = d.total || 0;
      var th = d.threshold || 30;
      var html = '<div class="learn-summary">共积累 <b style="color:#4ade80">' + total + '</b> 条决策记录，达标门槛 <b>' + th + '</b> 条/桶</div>';
      // 策略汇总
      html += '<div style="font-size:13px;color:#94a3b8;margin:8px 0 4px;font-weight:600">策略汇总</div>';
      for (var i = 0; i < d.strategies.length; i++) {
        var s = d.strategies[i];
        var pct = Math.min(100, Math.round(s.total / th * 100));
        var barClass = s.threshold_met ? 'green' : 'yellow';
        var tagClass = s.threshold_met ? 'ok' : 'wait';
        var tagText = s.threshold_met ? '已生效' : '积累中';
        html += '<div class="learn-stat-row">'
          + '<span class="learn-stat-label">' + s.action_type + '</span>'
          + '<div class="learn-stat-bar-wrap"><div class="learn-stat-bar ' + barClass + '" style="width:' + pct + '%"></div></div>'
          + '<span class="learn-stat-value">' + s.total + '/' + th + '</span>'
          + '<span class="learn-stat-tag ' + tagClass + '">' + tagText + '</span>'
          + '<span class="learn-stat-value" style="color:#94a3b8">' + (s.total > 0 ? Math.round(s.win_rate * 100) + '%' : '-') + '</span>'
          + '</div>';
      }
      // 桶级明细
      if (d.buckets.length > 0) {
        html += '<div style="font-size:13px;color:#94a3b8;margin:12px 0 4px;font-weight:600">桶级明细（策略×局面）</div>';
        for (var j = 0; j < d.buckets.length; j++) {
          var b = d.buckets[j];
          var bpct = Math.min(100, Math.round(b.total / th * 100));
          var bbar = b.threshold_met ? 'green' : 'yellow';
          var btag = b.threshold_met ? 'ok' : 'wait';
          var btext = b.threshold_met ? '已生效' : b.total + '/' + th;
          html += '<div class="learn-stat-row">'
            + '<span class="learn-stat-label" title="' + b.bucket + '">' + b.action_type + ' · ' + b.bucket + '</span>'
            + '<div class="learn-stat-bar-wrap"><div class="learn-stat-bar ' + bbar + '" style="width:' + bpct + '%"></div></div>'
            + '<span class="learn-stat-value">' + b.total + '/' + th + '</span>'
            + '<span class="learn-stat-tag ' + btag + '">' + btext + '</span>'
            + '</div>';
        }
      }
      el.innerHTML = html;
    })
    .catch(function() {
      el.innerHTML = '<div class="learn-summary">加载失败</div>';
    });
}

// 点击背景关闭
document.getElementById('settings-modal').addEventListener('click', function(e) {
  if (e.target === this) closeSettings();
});

// 旧的 toggleBGM/toggleSFX 已被音量滑块替代

// ==================== LOGIN SYSTEM ====================
// currentUser / currentTab 已提前到 <script> 开头声明，供 updateStartModal/saveGameState 在 INIT 阶段访问

function togglePwd(inputId, btn) {
  var input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🔒';
  } else {
    input.type = 'password';
    btn.textContent = '👁️';
  }
}

function switchTab(tab) {
  currentTab = tab;
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
  document.getElementById('login-submit-btn').textContent = tab === 'login' ? '登录' : '注册';
  document.getElementById('login-error').textContent = '';
  document.getElementById('input-password').value = '';
  var confirmGroup = document.getElementById('confirm-password-group');
  if (confirmGroup) confirmGroup.style.display = tab === 'register' ? 'block' : 'none';
  var confirmInput = document.getElementById('input-confirm-password');
  if (confirmInput) confirmInput.value = '';
}

function handleLogin(e) {
  e.preventDefault();
  const name = document.getElementById('input-name').value.trim();
  const password = document.getElementById('input-password').value;
  const errorEl = document.getElementById('login-error');
  
  if (!name) { errorEl.textContent = '请输入昵称'; return; }
  if (password.length < 4) { errorEl.textContent = '密码至少4位'; return; }
  if (currentTab === 'register') {
    var confirmPwd = document.getElementById('input-confirm-password');
    if (confirmPwd && !confirmPwd.value) { errorEl.textContent = '请确认密码'; return; }
    if (confirmPwd && confirmPwd.value !== password) { errorEl.textContent = '两次密码不一致'; return; }
  }
  
  const endpoint = currentTab === 'login' ? '/api/login' : '/api/register';
  const btn = document.getElementById('login-submit-btn');
  btn.textContent = '请稍候...';
  btn.disabled = true;
  
  fetch(API_BASE + endpoint, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, password})
  })
  .then(r => r.json())
  .then(data => {
    btn.disabled = false;
    if (data.error) {
      errorEl.textContent = data.error;
      btn.textContent = currentTab === 'login' ? '登录' : '注册';
      return;
    }
    currentUser = {name: data.name, token: data.token};
    // 勾选"记住密码"→ 保存账号和 token 到 localStorage；未勾选 → 不长期保存
    // 但 token 始终存 sessionStorage，保证本次会话内不因 token 丢失闪退回登录页
    const rememberEl = document.getElementById('remember-login');
    const remember = !rememberEl || rememberEl.checked;
    if (remember) {
      localStorage.setItem('doudizhu_user', JSON.stringify({name: data.name, token: data.token}));
    } else {
      localStorage.removeItem('doudizhu_user');
    }
    sessionStorage.setItem('doudizhu_user', JSON.stringify({name: data.name, token: data.token}));
    window.location.href = '/lobby?name=' + encodeURIComponent(data.name);
    return;
  })
  .catch(err => {
    btn.disabled = false;
    errorEl.textContent = '登录服务暂不可用，请使用游客模式';
    btn.textContent = currentTab === 'login' ? '登录' : '注册';
    console.error('Login error:', err);
  });
}

function guestPlay() {
  // 游客开始：用户手势后主动播放背景音乐
  var _bgm=document.getElementById('bgm-audio');
  if(_bgm&&!_bgm.muted){_bgm.volume=(localStorage.getItem('doudizhu_bgm_vol')||80)/100;_bgm.play().catch(function(){});}
  currentUser = {name: '游客', token: null};
  closeLoginModal();
  // 游客始终只显示"开始游戏"，不显示"继续/重新开始"选择
  updateStartModal();
}

// 自动登录逻辑已合并到下方的 localStorage 自动登录

function closeLoginModal() {
  document.getElementById('login-modal').classList.add('hidden');
  updateUserInfoDisplay();
}

function logoutUser() {
  currentUser = null;
  localStorage.removeItem('doudizhu_user');
  sessionStorage.removeItem('doudizhu_user');
  document.getElementById('user-name-display').textContent = '游客';
  document.getElementById('user-status').textContent = '未登录';
  document.getElementById('btn-logout').style.display = 'none';
  closeSettings();
  // 退出后重新弹出登录弹窗（可换号登录）
  document.getElementById('login-modal').classList.remove('hidden');
}

function deleteAccount() {
  if (!currentUser || !currentUser.name) { alert('请先登录'); return; }
  if (currentUser.name === '游客') { alert('游客无法注销'); return; }
  if (!confirm('⚠️ 注销账号将永久删除你的所有数据（战绩、存档等），且无法恢复！\n\n确定要注销吗？')) return;
  if (!confirm('最后一次确认：真的要注销账号「' + currentUser.name + '」吗？')) return;
  var pwd = prompt('请输入密码以确认注销');
  if (!pwd) return;
  fetch(API_BASE + '/api/delete-account', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: currentUser.name, password: pwd})
  })
  .then(function(r){ return r.json(); })
  .then(function(data){
    if (data.success) {
      localStorage.removeItem('doudizhu_user');
      sessionStorage.removeItem('doudizhu_user');
      currentUser = null;
      closeSettings();
      document.getElementById('login-modal').classList.remove('hidden');
      alert('账号已注销');
    } else {
      alert(data.error || '注销失败');
    }
  })
  .catch(function(){ alert('注销失败，请重试'); });
}

function updateUserInfoDisplay() {
  const nameEl = document.getElementById('user-name-display');
  const statusEl = document.getElementById('user-status');
  const logoutBtn = document.getElementById('btn-logout');
  if (currentUser && currentUser.name && currentUser.name !== '游客') {
    nameEl.textContent = currentUser.name;
    statusEl.textContent = '已登录';
    if (logoutBtn) logoutBtn.style.display = 'block';
  } else {
    nameEl.textContent = '游客';
    statusEl.textContent = '未登录';
    if (logoutBtn) logoutBtn.style.display = 'none';
  }
}

// 登录初始化：打开应用始终显示登录界面；记住的账号自动填入；从大厅回来（URL 带 name）才恢复登录
(function() {
  try {
    const params = new URLSearchParams(window.location.search);
    const urlName = params.get('name');
    // 从大厅点"开始游戏"跳转回来：恢复登录状态，不弹登录框
    if (urlName) {
      // 游客直接放行，不走验证
      if (urlName === '游客') {
        currentUser = {name: '游客', token: null};
        updateUserInfoDisplay();
        closeLoginModal();
        return;
      }
      const urlToken = params.get('token') || '';
      const saved = localStorage.getItem('doudizhu_user') || sessionStorage.getItem('doudizhu_user');
      let localToken = urlToken;
      if (saved) {
        try {
          const u = JSON.parse(saved);
          if (u.name === urlName && u.token) localToken = u.token;
        } catch(e){}
      }
      if (!localToken) {
        localStorage.removeItem('doudizhu_user');
        sessionStorage.removeItem('doudizhu_user');
        // 修复：token 丢失不再踢回登录页，降级游客模式继续玩
        currentUser = {name: '游客', token: null};
        updateUserInfoDisplay();
        closeLoginModal();
        return;
      }
      // 向后端验证 token
      fetch(API_BASE + '/api/auto-login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token: localToken})
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.success && data.name === urlName) {
          currentUser = {name: data.name, token: localToken};
          localStorage.setItem('doudizhu_user', JSON.stringify(currentUser));
          updateUserInfoDisplay();
          closeLoginModal();
        } else {
          localStorage.removeItem('doudizhu_user');
          sessionStorage.removeItem('doudizhu_user');
          // 修复：token 失效不再踢回登录页，降级游客模式继续玩
          currentUser = {name: '游客', token: null};
          updateUserInfoDisplay();
          closeLoginModal();
        }
      })
      .catch(function() {
        // 网络错误不清本地记录，静默放行
        if (saved) {
          try {
            const u = JSON.parse(saved);
            if (u.name === urlName) {
              currentUser = {name: u.name, token: u.token || null};
              updateUserInfoDisplay();
              closeLoginModal();
              return;
            }
          } catch(e){}
        }
      });
      return;
    }
    // 打开应用（根路径）：登录界面保持显示；勾选过"记住密码"则自动填好账号密码，点登录即进
    const saved = localStorage.getItem('doudizhu_user');
    if (saved) {
      try {
        const u = JSON.parse(saved);
        if (u && u.name) {
          const nameInput = document.getElementById('input-name');
          if (nameInput) nameInput.value = u.name;
        }
      } catch(e){}
    }
    // 未登录：登录弹窗保持显示
    currentUser = null;
  } catch(e) {}
})();
// 回放模式：自动登录完成后再启动
if (typeof _replayId !== 'undefined' && _replayId) {
    closeLoginModal();
    initReplayMode(_replayId);
}


// ==================== SOUND SYSTEM INTEGRATION ====================
// 播放音效（带开关检查）
function playGameSound(name) {
  if (typeof SoundSystem !== 'undefined') {
    SoundSystem.play(name);
  }
}

// ==================== GAME STATS RECORDING ====================
function recordGameResult(result, role, rounds, duration, aiDecisions, scoreChange, bidScore) {
  if (!currentUser || !currentUser.name || currentUser.name === '游客') return;
  if (!currentUser.token) return;
  
  fetch(API_BASE + '/api/game/end', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      name: currentUser.name,
      result: result,
      role: role,
      rounds: rounds,
      duration: duration,
      ai_decisions: aiDecisions || [],
      score_change: scoreChange || 0,
      bid_score: bidScore || 0
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      console.log('战绩已保存');
    }
  })
  .catch(err => {
    console.warn('战绩保存失败:', err);
  });
}

// ==================== ESC KEY CLOSE ====================
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    const settingsModal = document.getElementById('settings-modal');
    if (settingsModal.classList.contains('show')) {
      closeSettings();
    }
  }
});


// === 音量控制 ===
function setBgmVolume(val){
  val=parseInt(val);
  var bgm=document.getElementById('bgm-audio');
  if(bgm){
    bgm.volume=val/100;bgm.muted=false;  // 拖滑块=自动取消静音
    if(bgm.paused)bgm.play().catch(function(){});  // 2026-08-30：拖动时若未在播则立即播放，保证有声音变化反馈
  }
  var slider=document.getElementById('bgm-volume');
  if(slider){slider.value=val;slider.disabled=false;}  // 滑块永不禁用
  var el=document.getElementById('bgm-volume-val');
  if(el)el.textContent=val+'%';
  localStorage.setItem('doudizhu_bgm_vol',val);
  localStorage.setItem('doudizhu_bgm_muted','false');
  bgmMuted=false;
}
// 背景音乐开关
function toggleBgmMute(){
  bgmMuted=!bgmMuted;
  var bgm=document.getElementById('bgm-audio');
  var btn=document.getElementById('bgm-toggle');
  var slider=document.getElementById('bgm-volume');
  if(bgmMuted){
    if(bgm){bgm.pause();bgm.muted=true;}
    if(btn)btn.textContent='🔇';
  }else{
    // 恢复播放前先应用用户设置的音量
    var vol=parseInt(localStorage.getItem('doudizhu_bgm_vol')||'80');
    if(bgm){bgm.muted=false;bgm.volume=vol/100;bgm.play().catch(()=>{});}
    if(btn)btn.textContent='🔊';
    if(slider)slider.disabled=false;
  }
  localStorage.setItem('doudizhu_bgm_muted',bgmMuted);
}
// 恢复静音状态（默认开启）
(function(){
  var m=localStorage.getItem('doudizhu_bgm_muted');
  if(m==='true'){
    bgmMuted=true;
    var btn=document.getElementById('bgm-toggle');if(btn)btn.textContent='🔇';
    var bgm=document.getElementById('bgm-audio');if(bgm){bgm.muted=true;bgm.pause();}
    // 滑块不禁用（用户拖动即可调音量+自动取消静音）
  }else{
    bgmMuted=false;
    var btn=document.getElementById('bgm-toggle');if(btn)btn.textContent='🔊';
    var bgm=document.getElementById('bgm-audio');if(bgm){bgm.muted=false;bgm.volume=0.8;bgm.play().catch(()=>{});}
  }
})();
// 音效试听防抖计时器（拖动滑块时短间隔内只播一次试听音）
var _sfxTrialTimer=null;
function setSfxVolume(val){
  val=parseInt(val);
  if(typeof SoundSystem!=='undefined'){
    SoundSystem.sfxVolume=val/100;
    // 2026-08-30：拖动滑块立即试听音效，保证有反馈
    clearTimeout(_sfxTrialTimer);
    _sfxTrialTimer=setTimeout(function(){try{SoundSystem.play('voice_尖');}catch(e){}},180);
  }
  var slider=document.getElementById('sfx-volume');
  if(slider)slider.value=val;
  var el=document.getElementById('sfx-volume-val');
  if(el)el.textContent=val+'%';
  localStorage.setItem('doudizhu_sfx_vol',val);
}
// 初始化音量
(function(){
  var bgmVol=localStorage.getItem('doudizhu_bgm_vol');
  var sfxVol=localStorage.getItem('doudizhu_sfx_vol');
  if(bgmVol!==null){
    var el=document.getElementById('bgm-volume');
    if(el)el.value=bgmVol;
    setBgmVolume(bgmVol);
  }
  if(sfxVol!==null){
    var el=document.getElementById('sfx-volume');
    if(el)el.value=sfxVol;
    setSfxVolume(sfxVol);
  }
})();

// === 返回大厅 ===
function goToLobby(){
  if(currentUser&&currentUser.name){
    window.location.href="/lobby?name="+encodeURIComponent(currentUser.name);
  }else{
    window.location.href="/lobby";
  }
}

// === 战绩统计 ===
function loadStats(){
  const el=document.getElementById('stats-panel');
  const hint=document.getElementById('stats-login-hint');
  if(!currentUser||!currentUser.name){
    if(el)el.style.display='none';
    if(hint)hint.style.display='block';
    return;
  }
  if(el)el.style.display='grid';
  if(hint)hint.style.display='none';
  fetch('/api/stats/'+encodeURIComponent(currentUser.name))
    .then(r=>r.json())
    .then(d=>{
      document.getElementById('stat-total').textContent=d.total||0;
      document.getElementById('stat-wins').textContent=d.wins||0;
      document.getElementById('stat-rate').textContent=(d.win_rate||0)+'%';
      document.getElementById('stat-streak').textContent=d.streak||0;
    })
    .catch(e=>console.warn('stats err',e));
}
// === 排行榜 ===
function loadLeaderboard(){
  fetch('/api/leaderboard')
    .then(r=>r.json())
    .then(data=>{
      const empty=document.getElementById('lb-empty');
      const table=document.getElementById('lb-table');
      const body=document.getElementById('lb-body');
      if(!data||data.length===0){if(empty)empty.style.display='block';if(table)table.style.display='none';return;}
      if(empty)empty.style.display='none';
      if(table)table.style.display='table';
      body.innerHTML='';
      data.forEach(r=>{
        const tr=document.createElement('tr');
        tr.style.borderBottom='1px solid rgba(255,255,255,0.05)';
        const rankColor=r.rank<=3?['#fbbf24','#94a3b8','#cd7f32'][r.rank-1]:'#94a3b8';
        tr.innerHTML='<td style="padding:6px 8px;font-weight:700;color:'+rankColor+'">'+r.rank+'</td>'
          +'<td style="padding:6px 8px;color:#e2e8f0">'+r.name+'</td>'
          +'<td style="padding:6px 8px;text-align:center;color:#94a3b8">'+r.total+'</td>'
          +'<td style="padding:6px 8px;text-align:center;color:#4ade80">'+r.win_rate+'%</td>';
        body.appendChild(tr);
      });
    })
    .catch(e=>console.warn('lb err',e));
}