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
document.getElementById('btn-back-to-lobby').onclick=()=>goToLobby();
document.addEventListener('gesturestart',e=>e.preventDefault());
document.addEventListener('dblclick',e=>e.preventDefault());
