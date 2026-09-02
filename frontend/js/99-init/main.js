// ============================================================
// 斗地主终极版 · 启动装配 / 初始化
// 职责：页面启动、回放入口、音量恢复，必须最后加载
// 来源：game.js 第 1867-1913 + 2235-2242 行（模块化拆分，代码未做改动）
// ============================================================
// ==================== INIT ====================

const _urlParams = new URLSearchParams(window.location.search);
const _replayId = _urlParams.get('replay');
if (_replayId) {
  // 回放模式：从页面加载起就隐藏开始弹窗，避免"开始游戏"弹窗闪现/拦截回放
  const _sm = document.getElementById('start-modal');
  if (_sm) _sm.classList.add('hidden');
} else {
  // 普通模式：显示干净的开始界面（仅"开始游戏"按钮，无提示文本）
  updateStartModal();
}

resizeResponsiveLayout();
// iOS 首次加载横屏时视口尺寸不稳定，延迟重算几次，避免底部白边/错位
setTimeout(resizeResponsiveLayout,400);
setTimeout(resizeResponsiveLayout,1200);

// 页面加载时从 localStorage 恢复音量设置
(function(){
  var bgmVol=localStorage.getItem('doudizhu_bgm_vol');
  if(bgmVol!==null&&typeof setBgmVolume==='function')setBgmVolume(bgmVol);
  var sfxVol=localStorage.getItem('doudizhu_sfx_vol');
  if(sfxVol!==null&&typeof setSfxVolume==='function')setSfxVolume(sfxVol);
})();

// 首次点击解锁声音（浏览器自动播放策略：必须有用户手势才能出声，2026-08-30 修复"点一下再点一下才有声音"）
(function(){
  var unlocked=false;
  document.addEventListener('click', function unlockSound(){
    if(unlocked)return;
    unlocked=true;
    var bgm=document.getElementById('bgm-audio');
    if(bgm&&!bgm.muted){
      bgm.volume=(localStorage.getItem('doudizhu_bgm_vol')||80)/100;
      bgm.play().catch(function(){});
    }
    document.removeEventListener('click', unlockSound);
  }, true);
})();

// Service Worker 已移除：sw.js 文件从未存在，注册始终静默失败（如需 PWA 离线需先补 sw.js）



if (typeof _replayId !== 'undefined' && _replayId) {
    closeLoginModal();
    initReplayMode(_replayId);
}


// ==================== SOUND SYSTEM INTEGRATION ====================
// 播放音效（带开关检查）
