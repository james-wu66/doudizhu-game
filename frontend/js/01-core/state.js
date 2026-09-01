// ============================================================
// 斗地主终极版 · 核心基础 / 全局状态
// 职责：所有全局变量集中声明，必须最先加载，防止 TDZ 报错
// 来源：game.js 第 1-11 + 213-223 行（模块化拆分，代码未做改动）
// ============================================================
// ==================== GLOBAL STATE (提前声明，避免 updateStartModal/saveGameState 等在 INIT 阶段触发 TDZ) ====================
let currentUser = null;
let currentTab = 'login';
let sessionScores = [0, 0, 0];
let currentRound = 0;
let roundScore = 0;
let cardIdCounter = 0;
let bgmMuted = false;
let sfxMuted = false;
// ===== AI 学习（LEARN）模块状态 =====
const LEARN = {loaded: false, base: {}, buckets: {}, roundId: '', step: 0};
// ==================== GAME STATE ====================
let G={};

// ==================== 回放模式 ====================
let isReplayMode=false;
let replayData=[];
let replayIndex=0;
let replaySpeed=1;
let replayTimer=null;

// 回放模式初始化
