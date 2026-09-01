// ============================================================
// 斗地主终极版 · 游戏流程 / 开局发牌
// 职责：开始新游戏、发牌
// 来源：game.js 第 798-856 行（模块化拆分，代码未做改动）
// ============================================================
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
