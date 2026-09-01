// ============================================================
// 斗地主终极版 · 用户系统 / 设置面板
// 职责：设置弹窗开关
// 来源：game.js 第 1914-1934 行（模块化拆分，代码未做改动）
// ============================================================
function openSettings() {
  document.getElementById('settings-modal').classList.add('show');
  loadStats();
  loadLeaderboard();
  loadAiProgress();
  // 同步音量滑块
  var bgmVol=localStorage.getItem('doudizhu_bgm_vol');
  var sfxVol=localStorage.getItem('doudizhu_sfx_vol');
  if(bgmVol!==null)setBgmVolume(bgmVol);
  if(sfxVol!==null)setSfxVolume(sfxVol);
  // 同步 toggle 状态
  updateUserInfoDisplay();
  // 注销按钮显隐
  var delBtn = document.getElementById('btn-delete-account');
  if (delBtn) delBtn.style.display = (currentUser && currentUser.name && currentUser.name !== '游客') ? 'block' : 'none';
}

function closeSettings() {
  document.getElementById('settings-modal').classList.remove('show');
}
