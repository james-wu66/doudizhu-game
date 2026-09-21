// ============================================================
// 斗地主终极版 · 界面 / 选牌交互
// 职责：点击与滑动选牌
// 来源：game.js 第 1733-1812 行（模块化拆分，代码未做改动）
// ============================================================

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

// 触屏标志：touchstart 已即时翻转选中后，浏览器补发的合成 click 必须吞掉。
// 原来只靠 touchend 后 350ms 计时器压制，主线程忙（音效+重渲染）时 click 晚到
// 就漏网，同一次点牌被翻转两次（表现为第一张牌偶发点了没反应）。标志位与计时器
// 无关，晚到多久都能吞。suppressNextClick 保留给桌面 mousedown→click 路径用。
let sawTouch=false;

handEl.addEventListener('touchstart',e=>{
  if(G.phase!=='playing')return;
  const cardEl=e.target.closest('.card');
  if(!cardEl)return;
  sawTouch=true;
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

// ==================== MOUSE DRAG-TO-SELECT (desktop) ====================
handEl.addEventListener('mousedown',e=>{
  if(G.phase!=='playing')return;
  const cardEl=e.target.closest('.card');
  if(!cardEl)return;
  e.preventDefault();
  swipeActive=true;
  swipeSelectedIds.clear();
  swipeDeselectedIds.clear();
  const id=parseInt(cardEl.dataset.id);
  if(G.selectedIds.has(id)){swipeDeselectedIds.add(id);}
  else{swipeSelectedIds.add(id);}
  if(swipeSelectedIds.has(id))G.selectedIds.add(id);
  if(swipeDeselectedIds.has(id))G.selectedIds.delete(id);
  refreshSelectionVisuals();
  document.body.style.userSelect='none';
});

document.addEventListener('mousemove',e=>{
  if(!swipeActive)return;
  e.preventDefault();
  const cardEl=getCardAtX(e.clientX);
  if(!cardEl)return;
  const id=parseInt(cardEl.dataset.id);
  if(!swipeSelectedIds.has(id)&&!swipeDeselectedIds.has(id)){
    if(swipeSelectedIds.size>0){
      swipeSelectedIds.add(id);
      G.selectedIds.add(id);
    }else{
      swipeDeselectedIds.add(id);
      G.selectedIds.delete(id);
    }
    refreshSelectionVisuals();
  }
});

document.addEventListener('mouseup',e=>{
  if(!swipeActive)return;
  swipeActive=false;
  document.body.style.userSelect='';
  suppressNextClick=true;
  setTimeout(()=>{suppressNextClick=false;},350);
  G.hintPlays=[];
});

// Mouse click to toggle single card
handEl.addEventListener('click',e=>{
  const cardEl=e.target.closest('.card');
  if(!cardEl||G.phase!=='playing'||suppressNextClick)return;
  if(sawTouch){sawTouch=false;return;}  // 吞掉本次 tap 的合成 click（touchstart 已处理）
  const id=parseInt(cardEl.dataset.id);
  if(Number.isInteger(id))toggleSelect(id);
});

handEl.addEventListener('touchcancel',()=>{swipeActive=false;});

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
document.getElementById('btn-back-to-lobby').onclick=()=>goToLobby();
document.addEventListener('gesturestart',e=>e.preventDefault());
document.addEventListener('dblclick',e=>e.preventDefault());
