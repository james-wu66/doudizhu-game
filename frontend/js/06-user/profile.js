// ============================================================
// 斗地主终极版 · 用户系统 / 个人信息
// 职责：用户信息与 AI 学习进度
// 来源：game.js 第 1935-1997 + 2134-2234 行（模块化拆分，代码未做改动）
// ============================================================

// 登录态失效降级为游客时提示：否则战绩会静默丢失，用户完全无感知
function showGuestFallbackTip(name) {
  console.warn('[登录态失效] 账号 ' + name + ' 已降级为游客，本局战绩不会保存');
  var tip = document.createElement('div');
  tip.style.cssText = 'position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:9999;'
    + 'background:#7f1d1d;color:#fecaca;padding:10px 18px;border-radius:8px;font-size:14px;'
    + 'box-shadow:0 4px 16px rgba(0,0,0,.4);max-width:90vw;text-align:center';
  tip.textContent = '登录状态已失效（' + name + '），本局战绩不会保存。请重新登录。';
  document.body.appendChild(tip);
  setTimeout(function () { if (tip.parentNode) tip.parentNode.removeChild(tip); }, 6000);
}

function loadAiProgress() {
  var el = document.getElementById('ai-learning-content');
  if (!el) return;
  fetch(API + '/ai/learning/progress')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (!d.strategies || d.strategies.length === 0) {
        el.innerHTML = '<div class="learn-summary">暂无数据——打几局后自动开始记录。</div>';
        return;
      }
      var total = d.total || 0;
      var th = d.threshold || 30;
      var html = '<div class="learn-summary">共积累 <b style="color:#4ade80">' + total + '</b> 条决策记录，达标门槛 <b>' + th + '</b> 条/桶</div>';
      // 策略汇总
      html += '<div style="font-size:13px;color:#94a3b8;margin:8px 0 4px;font-weight:600">策略汇总</div>';
      for (var i = 0; i < d.strategies.length; i++) {
        var s = d.strategies[i];
        var pct = Math.min(100, Math.round(s.total / th * 100));
        var barClass = s.threshold_met ? 'green' : 'yellow';
        var tagClass = s.threshold_met ? 'ok' : 'wait';
        var tagText = s.threshold_met ? '已生效' : '积累中';
        html += '<div class="learn-stat-row">'
          + '<span class="learn-stat-label">' + s.action_type + '</span>'
          + '<div class="learn-stat-bar-wrap"><div class="learn-stat-bar ' + barClass + '" style="width:' + pct + '%"></div></div>'
          + '<span class="learn-stat-value">' + s.total + '/' + th + '</span>'
          + '<span class="learn-stat-tag ' + tagClass + '">' + tagText + '</span>'
          + '<span class="learn-stat-value" style="color:#94a3b8">' + (s.total > 0 ? Math.round(s.win_rate * 100) + '%' : '-') + '</span>'
          + '</div>';
      }
      // 桶级明细
      if (d.buckets.length > 0) {
        html += '<div style="font-size:13px;color:#94a3b8;margin:12px 0 4px;font-weight:600">桶级明细（策略×局面）</div>';
        for (var j = 0; j < d.buckets.length; j++) {
          var b = d.buckets[j];
          var bpct = Math.min(100, Math.round(b.total / th * 100));
          var bbar = b.threshold_met ? 'green' : 'yellow';
          var btag = b.threshold_met ? 'ok' : 'wait';
          var btext = b.threshold_met ? '已生效' : b.total + '/' + th;
          html += '<div class="learn-stat-row">'
            + '<span class="learn-stat-label" title="' + b.bucket + '">' + b.action_type + ' · ' + b.bucket + '</span>'
            + '<div class="learn-stat-bar-wrap"><div class="learn-stat-bar ' + bbar + '" style="width:' + bpct + '%"></div></div>'
            + '<span class="learn-stat-value">' + b.total + '/' + th + '</span>'
            + '<span class="learn-stat-tag ' + btag + '">' + btext + '</span>'
            + '</div>';
        }
      }
      el.innerHTML = html;
    })
    .catch(function() {
      el.innerHTML = '<div class="learn-summary">加载失败</div>';
    });
}

// 点击背景关闭
document.getElementById('settings-modal').addEventListener('click', function(e) {
  if (e.target === this) closeSettings();
});

// 旧的 toggleBGM/toggleSFX 已被音量滑块替代

// ==================== LOGIN SYSTEM ====================
// currentUser / currentTab 已提前到 <script> 开头声明，供 updateStartModal/saveGameState 在 INIT 阶段访问

function updateUserInfoDisplay() {
  const nameEl = document.getElementById('user-name-display');
  const statusEl = document.getElementById('user-status');
  const logoutBtn = document.getElementById('btn-logout');
  if (currentUser && currentUser.name && currentUser.name !== '游客') {
    nameEl.textContent = currentUser.name;
    statusEl.textContent = '已登录';
    if (logoutBtn) logoutBtn.style.display = 'block';
  } else {
    nameEl.textContent = '游客';
    statusEl.textContent = '未登录';
    if (logoutBtn) logoutBtn.style.display = 'none';
  }
}

// 登录初始化：打开应用始终显示登录界面；记住的账号自动填入；从大厅回来（URL 带 name）才恢复登录
(function() {
  try {
    const params = new URLSearchParams(window.location.search);
    const urlName = params.get('name');
    // 从大厅点"开始游戏"跳转回来：恢复登录状态，不弹登录框
    if (urlName) {
      // 游客直接放行，不走验证
      if (urlName === '游客') {
        currentUser = {name: '游客', token: null};
        updateUserInfoDisplay();
        closeLoginModal();
        return;
      }
      const urlToken = params.get('token') || '';
      const saved = localStorage.getItem('doudizhu_user') || sessionStorage.getItem('doudizhu_user');
      let localToken = urlToken;
      if (saved) {
        try {
          const u = JSON.parse(saved);
          if (u.name === urlName && u.token) localToken = u.token;
        } catch(e){}
      }
      if (!localToken) {
        localStorage.removeItem('doudizhu_user');
        sessionStorage.removeItem('doudizhu_user');
        // 修复：token 丢失不再踢回登录页，降级游客模式继续玩
        currentUser = {name: '游客', token: null};
        updateUserInfoDisplay();
        closeLoginModal();
        showGuestFallbackTip(urlName);
        return;
      }
      // 向后端验证 token
      fetch(API_BASE + '/api/auto-login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token: localToken})
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.success && data.name === urlName) {
          currentUser = {name: data.name, token: localToken};
          localStorage.setItem('doudizhu_user', JSON.stringify(currentUser));
          updateUserInfoDisplay();
          closeLoginModal();
        } else {
          localStorage.removeItem('doudizhu_user');
          sessionStorage.removeItem('doudizhu_user');
          // 修复：token 失效不再踢回登录页，降级游客模式继续玩
          currentUser = {name: '游客', token: null};
          updateUserInfoDisplay();
          closeLoginModal();
          showGuestFallbackTip(urlName);
        }
      })
      .catch(function() {
        // 网络错误不清本地记录，静默放行
        if (saved) {
          try {
            const u = JSON.parse(saved);
            if (u.name === urlName) {
              currentUser = {name: u.name, token: u.token || null};
              updateUserInfoDisplay();
              closeLoginModal();
              return;
            }
          } catch(e){}
        }
      });
      return;
    }
    // 打开应用（根路径）：登录界面保持显示；勾选过"记住密码"则自动填好账号密码，点登录即进
    const saved = localStorage.getItem('doudizhu_user');
    if (saved) {
      try {
        const u = JSON.parse(saved);
        if (u && u.name) {
          const nameInput = document.getElementById('input-name');
          if (nameInput) nameInput.value = u.name;
        }
      } catch(e){}
    }
    // 未登录：登录弹窗保持显示
    currentUser = null;
  } catch(e) {}
})();
// 回放模式：自动登录完成后再启动
