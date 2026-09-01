// ============================================================
// 斗地主终极版 · 游戏流程 / 叫地主
// 职责：叫地主与抢地主全流程
// 来源：game.js 第 857-999 行（模块化拆分，代码未做改动）
// ============================================================
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
