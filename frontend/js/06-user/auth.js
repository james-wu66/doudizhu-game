// ============================================================
// 斗地主终极版 · 用户系统 / 登录注册
// 职责：登录、注册、游客、注销、删号
// 来源：game.js 第 1998-2133 行（模块化拆分，代码未做改动）
// ============================================================
function togglePwd(inputId, btn) {
  var input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🔒';
  } else {
    input.type = 'password';
    btn.textContent = '👁️';
  }
}

function switchTab(tab) {
  currentTab = tab;
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
  document.getElementById('login-submit-btn').textContent = tab === 'login' ? '登录' : '注册';
  document.getElementById('login-error').textContent = '';
  document.getElementById('input-password').value = '';
  var confirmGroup = document.getElementById('confirm-password-group');
  if (confirmGroup) confirmGroup.style.display = tab === 'register' ? 'block' : 'none';
  var confirmInput = document.getElementById('input-confirm-password');
  if (confirmInput) confirmInput.value = '';
}

function handleLogin(e) {
  e.preventDefault();
  const name = document.getElementById('input-name').value.trim();
  const password = document.getElementById('input-password').value;
  const errorEl = document.getElementById('login-error');
  
  if (!name) { errorEl.textContent = '请输入昵称'; return; }
  if (password.length < 4) { errorEl.textContent = '密码至少4位'; return; }
  if (currentTab === 'register') {
    var confirmPwd = document.getElementById('input-confirm-password');
    if (confirmPwd && !confirmPwd.value) { errorEl.textContent = '请确认密码'; return; }
    if (confirmPwd && confirmPwd.value !== password) { errorEl.textContent = '两次密码不一致'; return; }
  }
  
  const endpoint = currentTab === 'login' ? '/api/login' : '/api/register';
  const btn = document.getElementById('login-submit-btn');
  btn.textContent = '请稍候...';
  btn.disabled = true;
  
  fetch(API_BASE + endpoint, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, password})
  })
  .then(r => r.json())
  .then(data => {
    btn.disabled = false;
    if (data.error) {
      errorEl.textContent = data.error;
      btn.textContent = currentTab === 'login' ? '登录' : '注册';
      return;
    }
    currentUser = {name: data.name, token: data.token};
    // 勾选"记住密码"→ 保存账号和 token 到 localStorage；未勾选 → 不长期保存
    // 但 token 始终存 sessionStorage，保证本次会话内不因 token 丢失闪退回登录页
    const rememberEl = document.getElementById('remember-login');
    const remember = !rememberEl || rememberEl.checked;
    if (remember) {
      localStorage.setItem('doudizhu_user', JSON.stringify({name: data.name, token: data.token}));
    } else {
      localStorage.removeItem('doudizhu_user');
    }
    sessionStorage.setItem('doudizhu_user', JSON.stringify({name: data.name, token: data.token}));
    window.location.href = '/lobby?name=' + encodeURIComponent(data.name);
    return;
  })
  .catch(err => {
    btn.disabled = false;
    errorEl.textContent = '登录服务暂不可用，请使用游客模式';
    btn.textContent = currentTab === 'login' ? '登录' : '注册';
    console.error('Login error:', err);
  });
}

function guestPlay() {
  // 游客开始：用户手势后主动播放背景音乐
  var _bgm=document.getElementById('bgm-audio');
  if(_bgm&&!_bgm.muted){_bgm.volume=(localStorage.getItem('doudizhu_bgm_vol')||80)/100;_bgm.play().catch(function(){});}
  currentUser = {name: '游客', token: null};
  closeLoginModal();
  // 游客始终只显示"开始游戏"，不显示"继续/重新开始"选择
  updateStartModal();
}

// 自动登录逻辑已合并到下方的 localStorage 自动登录

function closeLoginModal() {
  document.getElementById('login-modal').classList.add('hidden');
  updateUserInfoDisplay();
}

function logoutUser() {
  currentUser = null;
  localStorage.removeItem('doudizhu_user');
  sessionStorage.removeItem('doudizhu_user');
  document.getElementById('user-name-display').textContent = '游客';
  document.getElementById('user-status').textContent = '未登录';
  document.getElementById('btn-logout').style.display = 'none';
  closeSettings();
  // 退出后重新弹出登录弹窗（可换号登录）
  document.getElementById('login-modal').classList.remove('hidden');
}

function deleteAccount() {
  if (!currentUser || !currentUser.name) { alert('请先登录'); return; }
  if (currentUser.name === '游客') { alert('游客无法注销'); return; }
  if (!confirm('⚠️ 注销账号将永久删除你的所有数据（战绩、存档等），且无法恢复！\n\n确定要注销吗？')) return;
  if (!confirm('最后一次确认：真的要注销账号「' + currentUser.name + '」吗？')) return;
  var pwd = prompt('请输入密码以确认注销');
  if (!pwd) return;
  fetch(API_BASE + '/api/delete-account', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: currentUser.name, password: pwd})
  })
  .then(function(r){ return r.json(); })
  .then(function(data){
    if (data.success) {
      localStorage.removeItem('doudizhu_user');
      sessionStorage.removeItem('doudizhu_user');
      currentUser = null;
      closeSettings();
      document.getElementById('login-modal').classList.remove('hidden');
      alert('账号已注销');
    } else {
      alert(data.error || '注销失败');
    }
  })
  .catch(function(){ alert('注销失败，请重试'); });
}
