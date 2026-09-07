// ============================================================
// 斗地主终极版 · 用户系统 / 战绩排行
// 职责：战绩统计、排行榜、回大厅
// 来源：game.js 第 2250-2290 + 2371-2424 行（模块化拆分，代码未做改动）
// ============================================================
function recordGameResult(result, role, rounds, duration, aiDecisions, scoreChange, bidScore) {
  if (!currentUser || !currentUser.name || currentUser.name === '游客') return;
  if (!currentUser.token) return;
  
  fetch(API_BASE + '/api/game/end', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      name: currentUser.name,
      result: result,
      role: role,
      rounds: rounds,
      duration: duration,
      ai_decisions: aiDecisions || [],
      score_change: scoreChange || 0,
      bid_score: bidScore || 0
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      console.log('战绩已保存');
    }
  })
  .catch(err => {
    console.warn('战绩保存失败:', err);
  });
}

// ==================== ESC KEY CLOSE ====================
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    const settingsModal = document.getElementById('settings-modal');
    if (settingsModal.classList.contains('show')) {
      closeSettings();
    }
  }
});


// === 音量控制 ===
function goToLobby(){
  if(currentUser&&currentUser.name){
    window.location.href="/lobby?name="+encodeURIComponent(currentUser.name);
  }else{
    window.location.href="/lobby";
  }
}

// === 战绩统计 ===
function loadStats(){
  const el=document.getElementById('stats-panel');
  const hint=document.getElementById('stats-login-hint');
  if(!currentUser||!currentUser.name){
    if(el)el.style.display='none';
    if(hint)hint.style.display='block';
    return;
  }
  if(el)el.style.display='grid';
  if(hint)hint.style.display='none';
  fetch('/api/stats/'+encodeURIComponent(currentUser.name))
    .then(r=>r.json())
    .then(d=>{
      document.getElementById('stat-total').textContent=d.total||0;
      document.getElementById('stat-wins').textContent=d.wins||0;
      document.getElementById('stat-rate').textContent=(d.win_rate||0)+'%';
      document.getElementById('stat-streak').textContent=d.streak||0;
    })
    .catch(e=>console.warn('stats err',e));
}
// HTML 转义：用户名等不可信字符串拼进 innerHTML 前必须转义，否则有存储型 XSS
function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}

// === 排行榜 ===
function loadLeaderboard(){
  fetch('/api/leaderboard')
    .then(r=>r.json())
    .then(data=>{
      const empty=document.getElementById('lb-empty');
      const table=document.getElementById('lb-table');
      const body=document.getElementById('lb-body');
      if(!data||data.length===0){if(empty)empty.style.display='block';if(table)table.style.display='none';return;}
      if(empty)empty.style.display='none';
      if(table)table.style.display='table';
      body.innerHTML='';
      data.forEach(r=>{
        const tr=document.createElement('tr');
        tr.style.borderBottom='1px solid rgba(255,255,255,0.05)';
        const rankColor=r.rank<=3?['#fbbf24','#94a3b8','#cd7f32'][r.rank-1]:'#94a3b8';
        tr.innerHTML='<td style="padding:6px 8px;font-weight:700;color:'+rankColor+'">'+r.rank+'</td>'
          +'<td style="padding:6px 8px;color:#e2e8f0">'+escapeHtml(r.name)+'</td>'
          +'<td style="padding:6px 8px;text-align:center;color:#94a3b8">'+r.total+'</td>'
          +'<td style="padding:6px 8px;text-align:center;color:#4ade80">'+r.win_rate+'%</td>';
        body.appendChild(tr);
      });
    })
    .catch(e=>console.warn('lb err',e));
}
