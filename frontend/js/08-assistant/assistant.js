/* ============================================================
 * AI 复盘与问答助手（小气泡 + AI教练复盘）
 * 20260908 新建；第2轮修正重画（去AI味UI/抽屉可拖/预设置灰防连点）。
 * 红线：全局变量/函数一律 ast 前缀；禁止 window.onload 赋值；
 * 顶层禁止读 currentUser（lobby 的 let 在后面，TDZ）。
 * 游戏页(index.html)与大厅页(lobby.html)共用本文件。
 * ============================================================ */

/* === 状态（全部 let，声明在本文件最顶部，禁止重复 let）=== */
let astPendingReview = false;
let astHistory = [];          // 本会话用户提问（只传最近2轮 q）
let astSessionId = 'sess_' + Date.now().toString(36);
let astBusy = false;

/* === 常量 === */
const astPRESETS = ['三带一能带对子吗', '什么时候该叫地主', '队友出牌要不要压'];
const astAPIBASE = '/api/assist';
const astADMINSET = { '本地1234': 1, '线上1234': 1 };
const astTHINK_HTML = '<span class="ast-spinner"></span>正在思考中…';

/* ---------- 身份（两页两套体系，兼容表达式） ---------- */
function astUserName() {
  try {
    if (typeof currentUser === 'undefined' || !currentUser) return '';
    if (typeof currentUser === 'string') return currentUser;
    return (currentUser && currentUser.name) || '';
  } catch (e) { return ''; }
}
function astUserToken() {
  /* 页面身份=游客时绝不带 token：防止读到上一位登录者残留的 localStorage 被后端判冒名403 */
  if (astUserName() === '游客') return '';
  try {
    if (typeof currentUser === 'object' && currentUser && currentUser.token) return currentUser.token;
  } catch (e) {}
  var s = localStorage.getItem('doudizhu_user') || sessionStorage.getItem('doudizhu_user');
  if (s) { try { var j = JSON.parse(s); if (j && j.token) return j.token; } catch (e) {} }
  /* 第2轮修复: lobby 登录态在 URL 参数里(?name=..&token=..), 三处都取一遍 */
  try {
    var ut = new URLSearchParams(location.search).get('token');
    if (ut) return ut;
  } catch (e) {}
  return '';
}

/* ---------- API 公共 ---------- */
function astPost(path, body) {
  var payload = Object.assign({ token: astUserToken(), user_name: astUserName() }, body || {});
  return fetch(astAPIBASE + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(function (r) { return r.json().catch(function () { return { ok: false, error: 'bad_json' }; }); });
}

/* ---------- 小工具 ---------- */
function astEsc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function astClamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

/* ---------- spinner 保底 3.5 秒（jameswu: 像思考出来的; 真实耗时超过则如实等） ---------- */
function astMin2s(startPromise, startedAt) {
  return startPromise.then(function (res) {
    var wait = Math.max(0, 3500 - (Date.now() - startedAt));
    return new Promise(function (ok) { setTimeout(function () { ok(res); }, wait); });
  });
}

/* ---------- 反馈按钮（每条答案带；记录提示改首次打开一次性显示） ---------- */
function astFeedbackHtml(usageId) {
  if (!usageId) return '';
  return '<span class="ast-fb" data-uid="' + usageId + '">' +
         '<button class="ast-fb-btn" data-v="up">👍</button>' +
         '<button class="ast-fb-btn" data-v="down">👎</button></span>';
}

/* ---------- 通用请求期置灰（第2轮3.3: 慢也要看得见地活着） ---------- */
function astSetBusy(on) {
  astBusy = on;
  document.querySelectorAll('.ast-preset, #ast-send, .ast-rv-btn').forEach(function (b) { b.disabled = on; });
  var input = document.getElementById('ast-input');
  if (input) input.disabled = on;
}

/* ---------- 拖动公共实现（fab 与抽屉标题栏共用一套逻辑, 出界拉回, 不持久化）
   ⚠️position:fixed 元素 offsetLeft/offsetTop 恒为0(浏览器怪癖), 必须用
   getBoundingClientRect 取真实屏幕位置做基准——否则拖动坐标全错(第3轮实测教训)。 ---------- */
function astMakeDraggable(el, handle, onDblReset) {
  var drag = null;
  handle.addEventListener('pointerdown', function (e) {
    if (e.target.closest && e.target.closest('button')) return;   // 关闭按钮等不误拖
    e.preventDefault();
    var r = el.getBoundingClientRect();
    drag = { x: e.clientX, y: e.clientY, moved: false, px: r.left, py: r.top };
    try { handle.setPointerCapture(e.pointerId); } catch (err) {}
  });
  handle.addEventListener('pointermove', function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.moved && Math.abs(dx) + Math.abs(dy) > 8) drag.moved = true;
    if (!drag.moved) return;
    var w = el.offsetWidth, h = el.offsetHeight;
    // 以"按下瞬间的真实位置"为基准 + 本次总位移; 标题栏(top方向)永不离屏
    var L = astClamp(drag.px + (e.clientX - drag.x), 4, Math.max(4, window.innerWidth - w - 4));
    var T = astClamp(drag.py + (e.clientY - drag.y), 0, Math.max(4, window.innerHeight - 24));
    el.style.left = L + 'px'; el.style.top = T + 'px';
    el.style.right = 'auto'; el.style.bottom = 'auto';
  });
  function astUp(e) {
    if (!drag) return;
    var moved = drag.moved;
    drag = null;
    return moved;
  }
  handle.addEventListener('pointerup', function (e) {
    var moved = astUp(e);
    if (!moved && onDblReset.click) onDblReset.click();   // 单击(未拖动)回调: fab=开合抽屉
    // 松手后终校: 底部不许出界(高度可能因内容增长)
    if (moved) {
      var r = el.getBoundingClientRect(), h = el.offsetHeight;
      if (r.bottom > window.innerHeight - 4) {
        el.style.top = Math.max(0, window.innerHeight - h - 4) + 'px';
      }
      if (r.right > window.innerWidth - 4) {
        el.style.left = Math.max(4, window.innerWidth - r.width - 4) + 'px';
      }
    }
  });
  handle.addEventListener('pointercancel', function () { drag = null; });
  handle.addEventListener('dblclick', function () {
    if (onDblReset.dbl) onDblReset.dbl();                 // 双击=复位
  });
}

/* ============================================================
 * 一、问答小气泡（两页）
 * ============================================================ */
function astBuildBubble() {
  var wrap = document.createElement('div');
  wrap.id = 'ast-bubble-root';
  wrap.innerHTML =
    '<div id="ast-fab" title="斗地主小助手"><span id="ast-fab-char">斗</span></div>' +
    '<div id="ast-drawer">' +
      '<div id="ast-head"><span id="ast-title">斗地主小助手</span>' +
        '<button id="ast-close" aria-label="关闭">✕</button></div>' +
      '<div id="ast-chat"></div>' +
      '<div id="ast-presets"></div>' +
      '<div id="ast-input-row">' +
        '<input id="ast-input" type="text" maxlength="200" placeholder="问点斗地主的事…">' +
        '<button id="ast-send">发送</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(wrap);

  var fab = document.getElementById('ast-fab');
  var drawer = document.getElementById('ast-drawer');
  var head = document.getElementById('ast-head');

  /* 默认位（C1: 不做跨页/刷新保持, 每次进页都回默认） */
  function astResetFab() {
    fab.style.left = ''; fab.style.top = '';
    fab.style.right = '20px'; fab.style.bottom = '30vh';
  }
  function astResetDrawer() {
    drawer.style.left = ''; drawer.style.top = '';
    drawer.style.right = '20px'; drawer.style.bottom = 'calc(30vh + 54px)';
  }
  astMakeDraggable(fab, fab, { click: astToggleDrawer, dbl: astResetFab });
  astMakeDraggable(drawer, head, { click: null, dbl: astResetDrawer });   // 第2轮2.1: 抽屉标题栏可拖

  /* 抽屉内点击 */
  document.getElementById('ast-close').addEventListener('click', function () {
    drawer.classList.remove('ast-open');
  });
  var pres = document.getElementById('ast-presets');
  astPRESETS.forEach(function (q) {
    var b = document.createElement('button');
    b.className = 'ast-preset'; b.textContent = q;
    b.addEventListener('click', function () { astAsk(q); });
    pres.appendChild(b);
  });
  document.getElementById('ast-send').addEventListener('click', function () {
    var v = document.getElementById('ast-input').value.trim();
    if (v) { document.getElementById('ast-input').value = ''; astAsk(v); }
  });
  document.getElementById('ast-input').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { var v = e.target.value.trim(); if (v) { e.target.value = ''; astAsk(v); } }
  });
  /* 👍👎 事件委托 */
  document.getElementById('ast-chat').addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('.ast-fb-btn') : null;
    if (btn) astVote(btn);
  });
  /* 视口变化时拉回边界内 */
  window.addEventListener('resize', function () {
    [fab, drawer].forEach(function (el) {
      if (!el.style.left) return;
      var w = el.offsetWidth, h = el.offsetHeight;
      el.style.left = astClamp(el.offsetLeft, 4, Math.max(4, window.innerWidth - w - 4)) + 'px';
      el.style.top = astClamp(el.offsetTop, 4, Math.max(4, window.innerHeight - h - 4)) + 'px';
    });
  });
}
function astToggleDrawer() {
  var d = document.getElementById('ast-drawer');
  d.classList.toggle('ast-open');
  var chat = document.getElementById('ast-chat');
  if (d.classList.contains('ast-open') && !chat.querySelector('.ast-msg')) {
    astAppendBot('想问什么都行，规则、打法、配合，尽管开口。');
    var note = document.createElement('div');
    note.className = 'ast-note'; note.textContent = '提问与回答会被记录，用于改进助手';
    chat.appendChild(note);
  }
}
function astAppendUser(q) {
  var chat = document.getElementById('ast-chat');
  var d = document.createElement('div');
  d.className = 'ast-msg ast-user';
  d.innerHTML = '<div class="ast-bubble">' + astEsc(q) + '</div>';
  chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
}
function astAppendBot(html, usageId) {
  var chat = document.getElementById('ast-chat');
  var d = document.createElement('div');
  d.className = 'ast-msg ast-bot';
  var fb = usageId ? astFeedbackHtml(usageId) : '';
  d.innerHTML = '<div class="ast-bubble">' + html + fb + '</div>';
  chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
  return d;
}
function astAsk(q) {
  if (astBusy) return;
  astAppendUser(q);
  var chat = document.getElementById('ast-chat');
  var think = document.createElement('div');
  think.className = 'ast-msg ast-bot';
  think.innerHTML = '<div class="ast-bubble ast-think">' + astTHINK_HTML + '</div>';
  chat.appendChild(think); chat.scrollTop = chat.scrollHeight;
  astSetBusy(true);                                        // 第2轮3.3: 标签+输入+发送全部置灰

  var t0 = Date.now();
  astMin2s(astPost('/ask', { question: q, session_id: astSessionId,
                             history: astHistory.slice(-2) }), t0)
    .then(function (d) {
      think.remove();
      if (d && d.ok) {
        astAppendBot(astEsc(d.answer), d.usage_id);
        astHistory.push({ q: q });
      } else {
        astAppendBot('哎呀，刚才走神了，你稍等会儿再试试～');
      }
    })
    .catch(function () { think.remove(); astAppendBot('哎呀，刚才走神了，你稍等会儿再试试～'); })
    .finally(function () { astSetBusy(false); });
}
function astVote(btn) {
  if (!btn) return;
  var span = btn.parentNode;
  if (!span || span.dataset.voted) return;
  span.dataset.voted = '1';
  var uid = span.dataset.uid, v = btn.dataset.v;
  span.innerHTML = (v === 'up' ? '👍 已反馈' : '👎 已反馈');
  astPost('/feedback', { usage_id: Number(uid), vote: v }).catch(function () {});
}

/* ============================================================
 * 二、AI 教练复盘卡（大厅；结算弹窗只加链接）
 * ============================================================ */
function astIsLobby() { return location.pathname === '/lobby'; }
function astIsGuest() { var n = astUserName(); return !n || n === '游客'; }

function astBuildReviewCard() {
  if (!astIsLobby() || astIsGuest()) return;   // 游客隐藏复盘入口（V4）
  var anchor = document.querySelector('.stats-card');
  if (!anchor || !anchor.parentNode) return;
  var card = document.createElement('div');
  card.id = 'reviewCard';
  card.className = 'ast-review-card';
  card.innerHTML =
    '<div id="ast-rv-head">' +
      '<span class="ast-rv-badge">斗</span>' +
      '<span id="ast-rv-title">AI教练复盘</span>' +
      '<span id="ast-rv-btns">' +
        '<button class="ast-rv-btn" data-n="1">上一局复盘</button>' +
        '<button class="ast-rv-btn" data-n="3">三局复盘</button>' +
        '<button class="ast-rv-btn" data-n="5">五局复盘</button>' +
      '</span></div>' +
    '<div id="ast-rv-body"></div>';
  anchor.parentNode.insertBefore(card, anchor);
  card.querySelectorAll('.ast-rv-btn').forEach(function (b) {
    b.addEventListener('click', function () { astGenReview(Number(b.dataset.n)); });
  });
}
function astGenReview(n) {
  var body = document.getElementById('ast-rv-body');
  if (!body || astBusy) return;
  astSetBusy(true);
  body.innerHTML = '<div class="ast-think">' + astTHINK_HTML + '</div>';
  var t0 = Date.now();
  astMin2s(astPost('/review', { n: n }), t0).then(function (d) {
    if (!d || !d.ok) { body.innerHTML = astEsc('哎呀，刚才走神了，你稍等会儿再试试～'); return; }
    var hint = d.hint ? '<div class="ast-hint">' + astEsc(d.hint) + '</div>' : '';
    /* 第2轮4.5: 不显示"降级"标签, 答案本文统一呈现 */
    body.innerHTML = hint + '<div class="ast-rv-answer">' + astEsc(d.answer) +
      (d.usage_id ? astFeedbackHtml(d.usage_id) : '') + '</div>';
    var fb = body.querySelector('.ast-fb');
    fb && fb.addEventListener('click', function (e) {
      var btn = e.target.closest ? e.target.closest('.ast-fb-btn') : null;
      if (btn) astVote(btn);
    });
  }).catch(function () {
    body.innerHTML = '哎呀，刚才走神了，你稍等会儿再试试～';
  }).finally(function () { astSetBusy(false); });
}

/* ---------- 结算弹窗「AI 复盘」链接（settlement.js 只加 1 行调用本函数，红线6） ---------- */
function astSettleLink() {
  var modal = document.getElementById('result-modal');
  if (!modal) return;
  var box = modal.querySelector('.result-box');
  if (!box) return;
  var link = document.getElementById('ast-settle-link');
  if (!link) {
    link = document.createElement('a');
    link.id = 'ast-settle-link';
    link.textContent = '查看AI复盘';
    link.href = 'javascript:void(0)';
    link.addEventListener('click', function () {
      location.href = '/lobby?name=' + encodeURIComponent(astUserName() || '') +
                      '&token=' + encodeURIComponent(astUserToken()) + '&review=1';
    });
    box.appendChild(link);
  }
  /* endGame 调用时机弹窗即将展示，此刻 currentUser 已赋值，游客直接不显示 */
  link.style.display = astIsGuest() ? 'none' : 'block';
}

/* ---------- lobby 顶部「AI用量」按钮（仅白名单可见） ---------- */
function astAdminButton() {
  if (!astIsLobby()) return;
  var nameEl = document.getElementById('userName');
  if (!nameEl || !nameEl.parentNode) return;
  var wait = 0;
  var timer = setInterval(function () {
    var n = astUserName();
    if (!n && wait++ < 20) return;            // 等 lobby 初始化 currentUser
    clearInterval(timer);
    if (!astADMINSET[n]) return;              // 普通玩家无此入口
    var b = document.createElement('button');
    b.className = 'btn-logout';
    b.style.cssText = 'margin-left:10px;border-color:#f0c040;color:#f0c040;';
    b.textContent = 'AI用量';
    b.addEventListener('click', function () { location.href = '/xk-usage.html'; });
    nameEl.parentNode.insertBefore(b, nameEl.nextSibling.nextSibling);
  }, 100);
}

/* ============================================================
 * 初始化：一律 addEventListener（禁止 window.onload 赋值）
 * ============================================================ */
window.addEventListener('load', function () {
  astBuildBubble();
  astBuildReviewCard();
  astAdminButton();
  if (astIsLobby()) {
    /* 结算页跳转过来 ?review=1 → 自动生成一次（V13，唯一例外） */
    try {
      var p = new URLSearchParams(location.search);
      if (p.get('review') === '1' && !astPendingReview && !astIsGuest()) {
        astPendingReview = true;
        var body = document.getElementById('ast-rv-body');
        if (body) body.parentNode.scrollIntoView({ behavior: 'smooth' });
        astGenReview(1);
      }
    } catch (e) {}
  }
});
