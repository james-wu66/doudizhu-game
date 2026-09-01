// ============================================================
// 斗地主终极版 · 游戏流程 / 局面状态
// 职责：一局的初始状态、比分与回合显示
// 来源：game.js 第 769-797 行（模块化拆分，代码未做改动）
// ============================================================
function recordBid(who,action){if(G.gameMoves)G.gameMoves.push({type:'bid',player:who,action:action,mult:G.bidMult||1});}

function initGame(){G={phase:'idle',deck:[],hands:[[],[],[]],landlordCards:[],landlord:-1,
    current:0,lastPlay:null,passCount:0,multiplier:1,
    selectedIds:new Set(),hintPlays:[],hintIdx:0,
    bidStarter:0,bidCurrent:0,bidCount:0,lastGrabber:-1,
    bidPhase:'call',caller:-1,callActed:[false,false,false],grabActed:[false,false,false],
    farmerPlayCount:0,landlordPlayCount:0,bidMult:1,bombMult:1,
    playedHands:[[],[],[]],phaseStep:'round_resolved',gameMoves:[]};
}


// 分数标签渲染（restoreGameState/dealRound/endGame 都会调用，不能删）
function renderScoreTags(){
  if(!sessionScores)return;
  var tags=['player-scores','opp-left-scores','opp-right-scores'];
  for(var i=0;i<3;i++){
    var el=document.getElementById(tags[i]);
    if(!el)continue;
    var s=sessionScores[i]||0;
    var cls=s>=0?'score-positive':'score-negative';
    el.innerHTML='<span class="score-tag '+cls+'">'+(s>=0?'+':'')+s+'</span>';
  }
}
// 回合显示渲染（restoreGameState/dealRound 都会调用，不能删）
function renderRoundDisplay(){
  var el=document.getElementById('round-display');
  if(el)el.textContent='第'+(currentRound||1)+'局 / 共'+TOTAL_ROUNDS+'局';
}
