// ============================================================
// 斗地主终极版 · 界面 / 提示与特效
// 职责：提示语、炸弹特效
// 来源：game.js 第 1714-1732 行（模块化拆分，代码未做改动）
// ============================================================
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
