// ============================================================
// 斗地主终极版 · 音效 / 音量控制
// 职责：背景音乐与音效的音量、静音
// 来源：game.js 第 2243-2249 + 2291-2370 行（模块化拆分，代码未做改动）
// ============================================================
function playGameSound(name) {
  if (typeof SoundSystem !== 'undefined') {
    SoundSystem.play(name);
  }
}

// ==================== GAME STATS RECORDING ====================
function setBgmVolume(val){
  val=parseInt(val);
  var bgm=document.getElementById('bgm-audio');
  if(bgm){
    bgm.volume=val/100;bgm.muted=false;  // 拖滑块=自动取消静音
    if(bgm.paused)bgm.play().catch(function(){});  // 2026-08-30：拖动时若未在播则立即播放，保证有声音变化反馈
  }
  var slider=document.getElementById('bgm-volume');
  if(slider){slider.value=val;slider.disabled=false;}  // 滑块永不禁用
  var el=document.getElementById('bgm-volume-val');
  if(el)el.textContent=val+'%';
  localStorage.setItem('doudizhu_bgm_vol',val);
  localStorage.setItem('doudizhu_bgm_muted','false');
  bgmMuted=false;
}
// 背景音乐开关
function toggleBgmMute(){
  bgmMuted=!bgmMuted;
  var bgm=document.getElementById('bgm-audio');
  var btn=document.getElementById('bgm-toggle');
  var slider=document.getElementById('bgm-volume');
  if(bgmMuted){
    if(bgm){bgm.pause();bgm.muted=true;}
    if(btn)btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:1em;height:1em;vertical-align:-0.14em"><path d="M11 5 6.5 8.5H3v7h3.5L11 19V5Z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/></svg>';
  }else{
    // 恢复播放前先应用用户设置的音量
    var vol=parseInt(localStorage.getItem('doudizhu_bgm_vol')||'80');
    if(bgm){bgm.muted=false;bgm.volume=vol/100;bgm.play().catch(()=>{});}
    if(btn)btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:1em;height:1em;vertical-align:-0.14em"><path d="M11 5 6.5 8.5H3v7h3.5L11 19V5Z"/><path d="M15.5 8.7a4.6 4.6 0 0 1 0 6.6"/><path d="M18.3 6.2a8.4 8.4 0 0 1 0 11.6"/></svg>';
    if(slider)slider.disabled=false;
  }
  localStorage.setItem('doudizhu_bgm_muted',bgmMuted);
}
// 恢复静音状态（默认开启）
(function(){
  var m=localStorage.getItem('doudizhu_bgm_muted');
  if(m==='true'){
    bgmMuted=true;
    var btn=document.getElementById('bgm-toggle');if(btn)btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:1em;height:1em;vertical-align:-0.14em"><path d="M11 5 6.5 8.5H3v7h3.5L11 19V5Z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/></svg>';
    var bgm=document.getElementById('bgm-audio');if(bgm){bgm.muted=true;bgm.pause();}
    // 滑块不禁用（用户拖动即可调音量+自动取消静音）
  }else{
    bgmMuted=false;
    var btn=document.getElementById('bgm-toggle');if(btn)btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:1em;height:1em;vertical-align:-0.14em"><path d="M11 5 6.5 8.5H3v7h3.5L11 19V5Z"/><path d="M15.5 8.7a4.6 4.6 0 0 1 0 6.6"/><path d="M18.3 6.2a8.4 8.4 0 0 1 0 11.6"/></svg>';
    var bgm=document.getElementById('bgm-audio');if(bgm){bgm.muted=false;bgm.volume=0.8;bgm.play().catch(()=>{});}
  }
})();
// 音效试听防抖计时器（拖动滑块时短间隔内只播一次试听音）
var _sfxTrialTimer=null;
function setSfxVolume(val){
  val=parseInt(val);
  if(typeof SoundSystem!=='undefined'){
    SoundSystem.sfxVolume=val/100;
    // 2026-08-30：拖动滑块立即试听音效，保证有反馈
    clearTimeout(_sfxTrialTimer);
    _sfxTrialTimer=setTimeout(function(){try{SoundSystem.play('voice_尖');}catch(e){}},180);
  }
  var slider=document.getElementById('sfx-volume');
  if(slider)slider.value=val;
  var el=document.getElementById('sfx-volume-val');
  if(el)el.textContent=val+'%';
  localStorage.setItem('doudizhu_sfx_vol',val);
}
// 初始化音量
(function(){
  var bgmVol=localStorage.getItem('doudizhu_bgm_vol');
  var sfxVol=localStorage.getItem('doudizhu_sfx_vol');
  if(bgmVol!==null){
    var el=document.getElementById('bgm-volume');
    if(el)el.value=bgmVol;
    setBgmVolume(bgmVol);
  }
  if(sfxVol!==null){
    var el=document.getElementById('sfx-volume');
    if(el)el.value=sfxVol;
    setSfxVolume(sfxVol);
  }
})();

// === 返回大厅 ===
