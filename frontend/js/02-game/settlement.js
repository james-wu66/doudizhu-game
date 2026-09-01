// ============================================================
// 斗地主终极版 · 游戏流程 / 结算
// 职责：单局结算与最终排名
// 来源：game.js 第 1170-1326 行（模块化拆分，代码未做改动）
// ============================================================
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
