// ============================================================
// 斗地主终极版 · 核心基础 / 常量配置
// 职责：花色、点数、座位、局数等常量
// 来源：game.js 第 13-24 行（模块化拆分，代码未做改动）
// ============================================================
// ==================== CONSTANTS ====================
const SUITS=['♠','♥','♦','♣'];
const SUIT_COLORS=['black','red','red','black'];
const RANK_NAMES={3:'3',4:'4',5:'5',6:'6',7:'7',8:'8',9:'9',10:'10',11:'J',12:'Q',13:'K',14:'A',15:'2',16:'小',17:'大'};
const PLAYER=0,LEFT=1,RIGHT=2;
const PLAYER_NAMES=['你','电脑A','电脑B'];
const TOTAL_ROUNDS=10;
const BASE_SCORE=3;

// ==================== SESSION STATE ====================
// sessionScores / currentRound / roundScore / cardIdCounter 已提前到 <script> 开头声明
const SAVE_KEY='doudizhu_ultimate_saved_game_v1';
const API_BASE = window.location.origin;
