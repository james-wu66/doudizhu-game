// ============================================================
// 斗地主终极版 · 核心基础 / 存档与开局
// 职责：本地存档读写与开始菜单
// 来源：game.js 第 25-103 行（模块化拆分，代码未做改动）
// ============================================================
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
