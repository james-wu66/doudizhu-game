// ============================================================
// 斗地主终极版 · 回放 / 画面渲染
// 职责：回放手牌与出牌区渲染
// 来源：game.js 第 318-523 + 729-768 行（模块化拆分，代码未做改动）
// ============================================================
function renderReplayHands(dealMove){
  // 调用布局计算，确保CSS变量生效
  if(typeof resizeResponsiveLayout==='function')resizeResponsiveLayout();
  // 解析牌数据（兼容新格式{rank,suit}和旧格式纯数字）
  function parseCard(c){
    // 字符串rank映射
    var rankMap={'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15,'小王':16,'大王':17};
    if(typeof c==='object'&&c!==null){
      var r=c.rank;
      if(typeof r==='string')r=rankMap[r]!==undefined?rankMap[r]:parseInt(r)||0;
      return{rank:r,suit:c.suit||0};
    }
    if(typeof c==='string')return{rank:rankMap[c]!==undefined?rankMap[c]:parseInt(c)||0,suit:0};
    return{rank:c,suit:0};
  }
  // 修复5（核心）：维护"当前手牌状态"，出牌时从这里真实移除，渲染用状态而不是发牌原始数据
  if(!window._replayHands||window._replayHands._init!==true){
    window._replayHands=[
      (dealMove.myHand||[]).map(parseCard),
      (dealMove.leftHand||[]).map(parseCard),
      (dealMove.rightHand||[]).map(parseCard)
    ];
    window._replayHands._init=true;
  }
  // 渲染你的牌（底部，正常大小）——从状态读，排序后渲染
  var myHand=window._replayHands[0].slice();
  // 第2项：按斗地主大小降序（大王17>小王16>2> A>K>Q>J>10...>3）
  myHand.sort(function(a,b){return b.rank-a.rank;});
  var myContainer=document.getElementById('player-hand-inner');
  if(myContainer){
    myContainer.innerHTML='';
    var styles=getComputedStyle(document.documentElement);
    var cardW=parseFloat(styles.getPropertyValue('--legacy-card-w'))||window.innerHeight*.065;
    var cardH=parseFloat(styles.getPropertyValue('--legacy-card-h'))||cardW*1.4;
    myContainer.style.width=(cardW+(myHand.length-1)*cardW*.55)+'px';
    myHand.forEach(function(c,i){
      var el=renderCardEl({id:Math.random(),suit:c.suit,rank:c.rank});
      el.style.width=cardW+'px';el.style.height=cardH+'px';
      el.style.flex='0 0 '+cardW+'px';
      el.style.margin=(i===0?'0':'0 0 0 '+(-cardW*.45)+'px');
      // 待办2：角标和中央花色单独设置字号（防堆叠）
      var rF=cardH*0.30,sF=cardH*0.234,cF=cardH*0.495;
      var corners=el.querySelectorAll('.corner');
      corners.forEach(function(corner){
        corner.style.fontSize=sF+'px';
        var rn=corner.querySelector('.rank');if(rn)rn.style.fontSize=rF+'px';
        var su=corner.querySelector('.suit');if(su)su.style.fontSize=sF+'px';
      });
      var cs=el.querySelector('.center-suit');if(cs)cs.style.fontSize=cF+'px';
      myContainer.appendChild(el);
    });
  }
  // 渲染电脑A的牌（左上，正面透视）——从状态读
  renderReplayOpponent('opp-left',window._replayHands[1],'电脑A');
  // 渲染电脑B的牌（右上，正面透视）——从状态读
  renderReplayOpponent('opp-right',window._replayHands[2],'电脑B');
}

// 渲染对手的牌（正面透视+整齐两行，尺寸与玩家手牌一致）
function renderReplayOpponent(containerId,cards,label){
  var container=document.getElementById(containerId);
  if(!container)return;
  var cardsDiv=container.querySelector('.opp-cards')||container;
  cardsDiv.innerHTML='';
  cardsDiv.style.display='flex';
  cardsDiv.style.flexWrap='wrap';
  cardsDiv.style.gap='0';
  cardsDiv.style.justifyContent='flex-start';
  // 修复1：按斗地主大小降序（大王17>小王16>2>A>K>Q>J>10...>3），修乱码/排序错乱
  var sorted=cards.slice().sort(function(a,b){
    var ra=(typeof a==='object'&&a!==null)?a.rank:a;
    var rb=(typeof b==='object'&&b!==null)?b.rank:b;
    return rb-ra;
  });
  // 与玩家手牌同尺寸基础上整体缩小20%（等比例：花纹/数字字号随牌高自动缩）
  var styles=getComputedStyle(document.documentElement);
  function r2(n){return Math.round(n*100)/100;}
  var replayScale=(window.innerWidth<1100)?0.72:0.8;
  var cw=r2((parseFloat(styles.getPropertyValue('--legacy-card-w'))||window.innerHeight*.065)*replayScale);
  var ch=r2((parseFloat(styles.getPropertyValue('--legacy-card-h'))||cw*1.4)*replayScale);
  // 两行排布：第一行固定10张（17张=10+7，20张=10+10），重叠比例同玩家手牌（45%）
  var rowCount=10;
  var overlap=r2(cw*.45);
  var step=r2(cw-overlap); // 每张牌占位宽度
  var rowW=r2(cw+(rowCount-1)*step); // 第一行10张总宽
  var rowH=r2(ch+6); // 每行高度（牌高+行距）
  // 绝对定位钉死每张牌的位置：第1~10张第1行，第11张起第2行（永不裂开）
  cardsDiv.style.setProperty('max-width',rowW+'px','important');
  cardsDiv.style.setProperty('width',rowW+'px','important');
  cardsDiv.style.setProperty('height','auto','important');
  cardsDiv.style.setProperty('min-width','0','important');
  sorted.forEach(function(c,idx){
    var suit=(typeof c==='object'&&c!==null)?c.suit:0;
    var rank=(typeof c==='object'&&c!==null)?c.rank:c;
    var el=renderCardEl({id:Math.random(),suit:suit,rank:rank});
    // 全部用 setProperty 带 important，避免被全局 .opp-cards .card !important 覆盖
    el.style.setProperty('width',cw+'px','important');
    el.style.setProperty('height',ch+'px','important');
    el.style.setProperty('flex','0 0 '+cw+'px','important');
    el.style.setProperty('flex-shrink','0','important');
    el.style.setProperty('position','absolute','important');
    el.style.setProperty('box-sizing','border-box','important');
    // 钉死位置：left = 行内序号×step，top = 行号×rowH
    var row=Math.floor(idx/rowCount),col=idx%rowCount;
    el.style.setProperty('left',r2(col*step)+'px','important');
    el.style.setProperty('top',r2(row*rowH)+'px','important');
    el.style.setProperty('margin','0','important');
    // 花纹与牌等比缩放：点数=牌高*30%，花色=牌高*26%，中央=牌高*55%
    var rFont=ch*0.30;
    var sFont=ch*0.186;
    var cFont=ch*0.314;
    var corners=el.querySelectorAll('.corner');
    corners.forEach(function(corner){
      corner.style.setProperty('font-size',sFont+'px','important');
      var rn=corner.querySelector('.rank');if(rn)rn.style.setProperty('font-size',rFont+'px','important');
      var su=corner.querySelector('.suit');if(su)su.style.setProperty('font-size',sFont+'px','important');
    });
    var cs=el.querySelector('.center-suit');if(cs)cs.style.setProperty('font-size',cFont+'px','important');
    cardsDiv.appendChild(el);
  });
  // 容器高度按实际行数撑开（1行=rowH，2行=2*rowH）
  var rows=Math.ceil(sorted.length/rowCount);
  cardsDiv.style.setProperty('height',r2(rows*rowH)+'px','important');
  // 名字放到头像上面、张数标签放到头像下面（用户明确要求）
  var labelEl=container.querySelector('.opp-label');
  var avatar=container.querySelector('.opp-avatar');
  if(labelEl&&avatar&&labelEl.parentNode!==container){
    container.insertBefore(labelEl,avatar);
  }
  var countId=containerId==='opp-left'?'opp-left-count':'opp-right-count';
  var countEl=document.getElementById(countId);
  if(countEl){
    countEl.textContent=sorted.length+'张';
    if(avatar&&countEl.parentNode!==container){
      // 插到头像后面（下一个兄弟节点前）；没有兄弟则追加到末尾
      var next=avatar.nextSibling;
      if(next)container.insertBefore(countEl,next);
      else container.appendChild(countEl);
    }
    countEl.style.position='relative';
    countEl.style.zIndex='70';
  }
}

// 回放专用出牌渲染（45px基准，叠法同手牌，≥16张自动缩小）
function renderReplayPlayedCards(who,cards){
  var containerId=who===0?'played-player':who===1?'played-left':'played-right';
  var container=document.getElementById(containerId);
  if(!container)return;
  container.innerHTML='';
  container.classList.add('played-cards');
  var n=cards.length;
  var baseW=(window.innerWidth<1100)?34:55;
  // 玩家自己的出牌区较宽，1~20张保持45px
  var autoShrink=(who!==0&&n>=16);
  var cardW=baseW;
  if(autoShrink){
    var cw=container.clientWidth||410;
    cardW=cw/(1+0.55*(n-1));
    if(cardW<28)cardW=28;
  }
  var cardH=cardW*1.4;
  // 出牌区牌垂直居中（与回放CSS保持一致，不顶到顶部，避免"不平"）
  container.style.alignItems='center';
  cards.forEach(function(c,i){
    var el=renderCardEl({id:Math.random(),suit:c.suit,rank:c.rank});
    el.style.setProperty('width',cardW+'px','important');
    el.style.setProperty('height',cardH+'px','important');
    el.style.setProperty('flex','0 0 '+cardW+'px','important');
    el.style.setProperty('flex-shrink','0','important');
    el.style.setProperty('margin',(i===0?'0':'0 0 0 '+(-cardW*0.45)+'px'),'important');
    // 待办1：角标和中央花色按牌面比例设置字号
    var rF=cardH*0.30,sF=cardH*0.186,cF=cardH*0.314;
    var corners=el.querySelectorAll('.corner');
    corners.forEach(function(corner){
      corner.style.setProperty('font-size',sF+'px','important');
      var rn=corner.querySelector('.rank');if(rn)rn.style.setProperty('font-size',rF+'px','important');
      var su=corner.querySelector('.suit');if(su)su.style.setProperty('font-size',sF+'px','important');
    });
    var cs=el.querySelector('.center-suit');if(cs)cs.style.setProperty('font-size',cF+'px','important');
    container.appendChild(el);
  });
}


// 显示回放控制条
function showReplayBar(){
  var bar=document.createElement('div');
  bar.id='replay-bar';
  bar.style.cssText='position:fixed;bottom:0;left:0;right:0;background:rgba(0,0,0,0.85);padding:12px 20px;display:flex;align-items:center;justify-content:center;gap:16px;z-index:9999;';
  bar.innerHTML='<span style="color:#94a3b8;font-size:13px">回放速度：</span>'
    +'<button onclick="setReplaySpeed(1)" class="replay-speed-btn active" data-speed="1">1x</button>'
    +'<button onclick="setReplaySpeed(2)" class="replay-speed-btn" data-speed="2">2x</button>'
    +'<button onclick="setReplaySpeed(4)" class="replay-speed-btn" data-speed="4">4x</button>'
    +'<button onclick="setReplaySpeed(8)" class="replay-speed-btn" data-speed="8">8x</button>'
    +'<span style="color:#64748b;font-size:12px" id="replay-progress">0/'+replayData.length+'</span>'
    +'<button onclick="toggleReplayPause()" id="replay-pause-btn" style="padding:6px 16px;border-radius:6px;border:1px solid rgba(96,165,250,0.4);background:rgba(96,165,250,0.15);color:#60a5fa;font-size:13px;cursor:pointer">暂停</button>'
    +'<button onclick="replaySkip(-10)" title="后退10秒" style="padding:6px 14px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:transparent;color:#e2e8f0;font-size:13px;cursor:pointer">⏪ 10秒</button>'
    +'<button onclick="replaySkip(10)" title="前进10秒" style="padding:6px 14px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:transparent;color:#e2e8f0;font-size:13px;cursor:pointer">⏩ 10秒</button>'
    +'<button onclick="exitReplay()" style="padding:6px 16px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:transparent;color:#ef4444;font-size:13px;cursor:pointer;margin-left:24px">退出回放</button>';
  document.body.appendChild(bar);
  var style=document.createElement('style');
  style.textContent='.replay-speed-btn{padding:4px 12px;border-radius:6px;border:1px solid rgba(255,255,255,0.15);background:transparent;color:#94a3b8;font-size:13px;cursor:pointer;}.replay-speed-btn.active{background:rgba(96,165,250,0.2);color:#60a5fa;border-color:#60a5fa;}';
  document.head.appendChild(style);
}

function removeCardsFromHand(containerId,cardsStr){
  var container=document.getElementById(containerId);
  if(!container)return;
  var cards=cardsStr.split(',');
  // 牌面名称 → 内部rank数字
  var rankToNum={'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15,'小王':16,'大王':17};
  // 旧格式数字点数 → 内部rank（兼容老数据）
  var numMap={'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'11':11,'12':12,'13':13,'14':14,'15':15,'16':16,'17':17};
  cards.forEach(function(cardStr){
    cardStr=cardStr.trim();
    if(!cardStr)return;
    var targetRank;
    if(cardStr==='小王')targetRank=16;
    else if(cardStr==='大王')targetRank=17;
    else{
      // 可能是"牌面+花色"(A♠) 或 旧格式"数字+花色"(14♠) 或 纯数字
      var rankStr;
      if(cardStr.length===1){rankStr=cardStr;}
      else{
        var lastCh=cardStr.slice(-1);
        if(lastCh==='♠'||lastCh==='♥'||lastCh==='♦'||lastCh==='♣')rankStr=cardStr.slice(0,-1);
        else rankStr=cardStr;
      }
      targetRank=rankToNum[rankStr]!==undefined?rankToNum[rankStr]:(numMap[rankStr]!==undefined?numMap[rankStr]:null);
    }
    if(targetRank===null)return;
    // 用 dataset.rank 匹配（renderCardEl 设置了 dataset.rank）
    var els=container.querySelectorAll('.card');
    for(var i=0;i<els.length;i++){
      var el=els[i];
      if(el.dataset.rank!==undefined&&Number(el.dataset.rank)===targetRank){
        el.remove();
        break;
      }
    }
  });
}


// 回放记录辅助函数
