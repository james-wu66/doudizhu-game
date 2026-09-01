// ============================================================
// 斗地主终极版 · 界面 / 卡牌渲染
// 职责：手牌、底牌、出牌区渲染
// 来源：game.js 第 1595-1713 行（模块化拆分，代码未做改动）
// ============================================================
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
