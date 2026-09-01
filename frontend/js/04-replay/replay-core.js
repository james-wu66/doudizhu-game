// ============================================================
// 斗地主终极版 · 回放 / 播放控制
// 职责：回放初始化、播放、暂停、快进、退出
// 来源：game.js 第 224-317 + 524-728 行（模块化拆分，代码未做改动）
// ============================================================
async function initReplayMode(gameId){
  isReplayMode=true;
  document.body.classList.add('replay-mode');
  // 修复4：注入回放专用CSS——解除出牌区容器高度限制（媒体查询把 played-left/right 高度锁在 8vh/10vh，导致牌被压瘪成扁牌）
  if(!document.getElementById('replay-style-fix')){
    var rs=document.createElement('style');
    rs.id='replay-style-fix';
    rs.textContent=''
      +'body.replay-mode #played-left,body.replay-mode #played-right{height:auto!important;min-height:60px!important;width:auto!important;max-width:42vw!important;display:flex!important;align-items:center!important;justify-content:center!important;overflow:visible!important;z-index:50!important;}'
      +'body.replay-mode #played-player{height:auto!important;min-height:60px!important;width:auto!important;max-width:50vw!important;display:flex!important;align-items:center!important;justify-content:center!important;overflow:visible!important;z-index:50!important;}'
      +'body.replay-mode #opp-left,body.replay-mode #opp-right{width:auto!important;height:auto!important;min-height:0!important;display:grid!important;align-items:center!important;justify-content:flex-start!important;overflow:visible!important;z-index:60!important;top:12vh!important;grid-template-columns:auto auto!important;grid-template-rows:auto auto auto!important;gap:2px 10px!important;}'
      +'body.replay-mode #opp-left .opp-label{grid-column:1;grid-row:1;justify-content:center!important;}'
      +'body.replay-mode #opp-left .opp-avatar{grid-column:1;grid-row:2;margin:0 auto!important;}'
      +'body.replay-mode #opp-left .opp-badge{grid-column:1;grid-row:3;justify-content:center!important;margin:0!important;}'
      +'body.replay-mode #opp-left .opp-info{grid-column:2;grid-row:1/4;align-items:center!important;margin-left:8px!important;}'
      +'body.replay-mode #opp-right .opp-label{grid-column:2;grid-row:1;justify-content:center!important;}'
      +'body.replay-mode #opp-right .opp-avatar{grid-column:2;grid-row:2;margin:0 auto!important;}'
      +'body.replay-mode #opp-right .opp-badge{grid-column:2;grid-row:3;justify-content:center!important;margin:0!important;}'
      +'body.replay-mode #opp-right .opp-info{grid-column:1;grid-row:1/4;align-items:center!important;margin-right:8px!important;}'
      +'body.replay-mode .opp-cards{display:block!important;position:relative!important;margin:0!important;max-width:none!important;overflow:visible!important;width:auto!important;height:auto!important;}'
      +'body.replay-mode .opp-cards .card{width:auto!important;height:auto!important;margin:0!important;flex:none!important;flex-basis:auto!important;max-width:none!important;max-height:none!important;}'
      +'body.replay-mode .played-cards{display:flex!important;flex-wrap:nowrap!important;gap:0!important;align-items:center!important;justify-content:center!important;overflow:visible!important;width:max-content!important;max-width:none!important;}'
      +'body.replay-mode .played-cards .card{margin:0!important;flex:none!important;flex-basis:auto!important;width:auto!important;height:auto!important;max-width:none!important;max-height:none!important;}';
    document.head.appendChild(rs);
  }
  try{
    const resp=await fetch(API_BASE+'/api/games/'+gameId+'/replay');
    const data=await resp.json();
    if(!data.success||!data.moves||data.moves.length===0){
      alert('该局没有回放数据');
      var _urlName = new URLSearchParams(window.location.search).get('name');
      window.location.href='/lobby'+(_urlName?'?name='+encodeURIComponent(_urlName):'');
      return;
    }
    replayData=data.moves;
    // 待办2：设置局数并刷新显示
    if(data.rounds&&data.rounds>0){
      currentRound=data.rounds;
      if(typeof renderRoundDisplay==='function')renderRoundDisplay();
    }
    // 新问题4：保存发牌数据用于窗口变化重绘
    window._replayDealMove=replayData.find(function(m){return m.type==='deal';});
    // 回放模式窗口变化重绘（避免横竖屏切换手牌错位）
    window._replayResizeHandler=function(){
      if(typeof isReplayMode!=='undefined'&&isReplayMode&&window._replayDealMove){
        if(typeof renderReplayHands==='function')renderReplayHands(window._replayDealMove);
      }
    };
    if(window._replayResizeBound)window.removeEventListener('resize',window._replayResizeBound);
    window.addEventListener('resize',window._replayResizeHandler);
    window._replayResizeBound=window._replayResizeHandler;
    // 隐藏开始弹窗和操作按钮
    var sm=document.getElementById('start-modal');
    if(sm)sm.classList.add('hidden');
    // 调用布局计算，确保CSS变量生效
    if(typeof resizeResponsiveLayout==='function')resizeResponsiveLayout();
    var acts=document.getElementById('actions');
    if(acts)acts.style.display='none';
    var bids=document.getElementById('bid-actions');
    if(bids)bids.style.display='none';
    var hand=document.getElementById('player-hand');
    if(hand)hand.style.pointerEvents='none';
    // 显示回放控制条
    showReplayBar();
    // 解析初始牌局
    var dealMove=replayData.find(m=>m.type==='deal');
    if(dealMove){
      renderReplayHands(dealMove);
      var lc=document.getElementById('landlord-area');
      if(lc&&dealMove.landlordCards){
        lc.innerHTML='';
        dealMove.landlordCards.forEach(function(rc){
          // 解析底牌（兼容对象和旧数字格式）
          var rk=(typeof rc==='object'&&rc!==null)?rc.rank:rc;
          var st=(typeof rc==='object'&&rc!==null)?rc.suit:0;
          var el=renderCardEl({id:Math.random(),suit:st,rank:rk});
          el.style.width='45px';el.style.height='63px';
          el.style.flexShrink='0';
          lc.appendChild(el);
        });
      }
    }
    // 开始自动回放
    replayIndex=1;
    startReplayPlayback();
  }catch(e){
    console.warn('回放加载失败',e);
    alert('回放加载失败');
    var _urlName2 = new URLSearchParams(window.location.search).get('name');
    window.location.href='/lobby'+(_urlName2?'?name='+encodeURIComponent(_urlName2):'');
  }
}

// 渲染三个人的牌（透视模式）
function setReplaySpeed(speed){
  replaySpeed=speed;
  document.querySelectorAll('.replay-speed-btn').forEach(btn=>{
    btn.classList.toggle('active',parseInt(btn.dataset.speed)===speed);
  });
  if(replayTimer){clearInterval(replayTimer);startReplayPlayback();}
}

// 第8项：回放暂停/继续
var replayPaused=false;
function toggleReplayPause(){
  if(!replayTimer&&replayIndex>=replayData.length)return;
  replayPaused=!replayPaused;
  var btn=document.getElementById('replay-pause-btn');
  if(replayPaused){
    // 暂停：清除定时器
    if(replayTimer){clearInterval(replayTimer);replayTimer=null;}
    if(btn)btn.textContent='继续';
  }else{
    // 继续：从当前位置重启定时器
    if(btn)btn.textContent='暂停';
    startReplayPlayback();
  }
}

// 待办3：前进/后退10秒（真实跳转）
function replaySkip(seconds){
  if(!replayData||replayData.length===0)return;
  // 步间隔：1500ms / 倍速 → 10秒对应的步数
  var intervalMs=1500/replaySpeed;
  var steps=Math.max(1,Math.round(10000/intervalMs));
  var target;
  if(seconds<0){
    target=replayIndex-steps;
    if(target<1)target=1;
  }else{
    target=replayIndex+steps;
    if(target>replayData.length)target=replayData.length;
  }
  if(target===replayIndex)return;
  // 清除定时器
  if(replayTimer){clearInterval(replayTimer);replayTimer=null;}
  // 待办5：前进和后退都重绘画面（先恢复初始，再快进到目标步）
  // 修复5：重置手牌状态为发牌初始（_init置false触发重新初始化），再逐步执行到目标步
  if(window._replayDealMove&&typeof renderReplayHands==='function'){
    if(window._replayHands)window._replayHands._init=false;
    renderReplayHands(window._replayDealMove);
  }
  ['played-player','played-left','played-right'].forEach(function(id){
    var el=document.getElementById(id);
    if(el)el.innerHTML='';
  });
  replayIndex=1;
  while(replayIndex<target){
    executeReplayStep(replayData[replayIndex]);
    replayIndex++;
  }
  var prog=document.getElementById('replay-progress');
  if(prog)prog.textContent=replayIndex+'/'+replayData.length;
  // 从新位置继续播放
  startReplayPlayback();
}


function exitReplay(){
  if(replayTimer)clearInterval(replayTimer);
  if(currentUser&&currentUser.name){
    window.location.href='/lobby?name='+encodeURIComponent(currentUser.name);
  }else{
    window.location.href='/lobby';
  }
}

// 自动回放播放
function startReplayPlayback(){
  var interval=1500/replaySpeed;
  replayTimer=setInterval(function(){
    if(replayIndex>=replayData.length){
      clearInterval(replayTimer);replayTimer=null;
      showMsg('游戏结束',3000);
      return;
    }
    executeReplayStep(replayData[replayIndex]);
    replayIndex++;
    var prog=document.getElementById('replay-progress');
    if(prog)prog.textContent=replayIndex+'/'+replayData.length;
  },interval);
}

// 执行单步回放
function executeReplayStep(move){
  if(move.type==='deal')return;
  // 旧数据兼容：没有type但有cards的，当作出牌（player可能是字符串）
  if(!move.type&&move.cards){
    move.type='play';
  }
  var who=move.player;
  // 旧数据兼容：player 可能是名字字符串（'你'/'电脑A'/'电脑B'），映射回数字
  if(typeof who==='string'){
    var pm={'你':0,'电脑A':1,'电脑B':2};
    if(pm[who]!==undefined)who=pm[who];
    else who=0;
  }
  var name=PLAYER_NAMES[who]||'玩家';
  if(move.type==='landlord'){
    showMsg(name+'成为地主！');
    // 新问题2：定地主后，地主手牌+3张底牌（同步到手牌状态，保证重画不丢）
    var dealMove=replayData[0];
    if(dealMove&&dealMove.landlordCards){
      if(!window._replayHands||window._replayHands._init!==true){
        window._replayHands=[[],[],[]];
      }
      var handsArr=window._replayHands[who]||(window._replayHands[who]=[]);
      var rankMapL={'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15,'小王':16,'大王':17};
      dealMove.landlordCards.forEach(function(rc){
        var rk=(typeof rc==='object'&&rc!==null)?rc.rank:rc;
        var st=(typeof rc==='object'&&rc!==null)?rc.suit:0;
        if(typeof rk==='string')rk=rankMapL[rk]!==undefined?rankMapL[rk]:parseInt(rk)||0;
        handsArr.push({rank:rk,suit:st});
      });
      // 重画三份手牌（实时同步，张数+3）
      if(window._replayDealMove&&typeof renderReplayHands==='function')renderReplayHands(window._replayDealMove);
    }
    return;
  }
  if(move.type==='bid'){
    showMsg(name+'：'+(move.action||'叫地主')+'（'+(move.mult||1)+'倍）');
    // 在出牌区显示叫牌状态
    var playedId=who===0?'played-player':who===1?'played-left':'played-right';
    var played=document.getElementById(playedId);
    if(played){
      played.innerHTML='<div class="bid-status">'+name+'：'+(move.action||'叫地主')+'</div>';
    }
    // 第9项：刷新倍数显示（位置与正常游戏一致）
    var mult=move.mult||1;
    var multText=mult>1?('x'+mult):'';
    ['opp-left-mult','opp-right-mult','player-mult'].forEach(function(id){
      var el=document.getElementById(id);
      if(el)el.textContent=multText;
    });
    var sd=document.getElementById('score-display');
    if(sd)sd.textContent='倍数'+multText+' | 底分'+BASE_SCORE;
    return;
  }
  if(move.type==='pass'){
    showMsg(name+'：不出');
    // 在出牌区显示"不出"
    var playedId=who===0?'played-player':who===1?'played-left':'played-right';
    var played=document.getElementById(playedId);
    if(played){
      played.innerHTML='<div class="pass-text">不出</div>';
    }
    return;
  }
  if(move.type==='play'){
    // 第6项：提示文字用牌面名称，不显示数字
    var patName=move.pattern||'';
    var cardNames=(move.cards||'').split(',').map(function(cs){
      cs=cs.trim();
      if(cs==='小王')return '小王';
      if(cs==='大王')return '大王';
      var nm=cs.slice(0,-1);
      var nmMap={'J':'勾','Q':'圈','K':'K','A':'尖','2':'2'};
      var disp=nmMap[nm]!==undefined?nmMap[nm]:nm;
      return patName==='单张'||patName==='单'?('单'+disp):disp;
    }).join(' ');
    showMsg(name+'出了 '+patName+(cardNames?'：'+cardNames:''));
    // 解析牌面（兼容旧数据：没有type字段但有player和cards的也按出牌处理）
    var cardStrs=(move.cards||'').split(',');
    var cards=cardStrs.map(function(s){
      if(!s)return null;
      s=s.trim();
      // 大小王完整匹配
      if(s==='小王')return{id:Math.random(),suit:-1,rank:16};
      if(s==='大王')return{id:Math.random(),suit:-2,rank:17};
      // 兼容旧格式：数字点数+花色（如 14♠、16、17）
      var suitMap={'♠':0,'♥':1,'♦':2,'♣':3};
      var rankMap={'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15};
      if(s==='16')return{id:Math.random(),suit:-1,rank:16};
      if(s==='17')return{id:Math.random(),suit:-2,rank:17};
      var suitChar=s.slice(-1);
      var rankStr=s.slice(0,-1);
      var suit=suitMap[suitChar]!==undefined?suitMap[suitChar]:0;
      var rank=rankMap[rankStr]!==undefined?rankMap[rankStr]:(parseInt(rankStr)||0);
      return{id:Math.random(),suit:suit,rank:rank};
    }).filter(function(c){return c!==null;});
    // 渲染到出牌区（回放专用45px渲染）
    renderReplayPlayedCards(who,cards);
    // 修复5（核心）：从"当前手牌状态"中按点数+花色真实移除，再重画三份手牌（实时同步，出多少减多少）
    if(window._replayHands&&window._replayHands._init===true){
      var handsArr=window._replayHands[who]||[];
      cards.forEach(function(c){
        for(var j=0;j<handsArr.length;j++){
          if(handsArr[j].rank===c.rank&&handsArr[j].suit===c.suit){
            handsArr.splice(j,1);break;
          }
        }
      });
      if(window._replayDealMove&&typeof renderReplayHands==='function')renderReplayHands(window._replayDealMove);
    }
    return;
  }
}

// 从手牌中移除已出的牌
