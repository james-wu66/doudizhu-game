// ============================================================
// 斗地主终极版 · 界面 / 布局适配
// 职责：响应式布局、横屏锁定
// 来源：game.js 第 1813-1866 行（模块化拆分，代码未做改动）
// ============================================================
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
