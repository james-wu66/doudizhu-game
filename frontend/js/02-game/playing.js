// ============================================================
// 斗地主终极版 · 游戏流程 / 出牌
// 职责：出牌、不出、提示
// 来源：game.js 第 1000-1169 行（模块化拆分，代码未做改动）
// ============================================================
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
