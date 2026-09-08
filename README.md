<p align="center">
  <img src="assets/screenshots/game-bidding.png" width="90%" alt="斗地主对战界面预览">
</p>

<h1 align="center">斗地主终极版（会会斗地主）</h1>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-3.x-green?logo=flask&logoColor=white">
  <img alt="JavaScript" src="https://img.shields.io/badge/JavaScript-ES6+-yellow?logo=javascript&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-blue?logo=docker&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-yellowgreen">
</p>

一个**全栈网页版斗地主游戏**：原生 JS 前端 + Flask 后端 + Python 启发式 AI 引擎，支持账号系统、战绩回放、排行榜与基于真实对局数据的 AI 学习闭环，Docker 容器化部署在腾讯云 CloudBase。

- 🔗 在线演示：https://doudizhu-game-294184-6-1420872702.sh.run.tcloudbase.com

---

## 目录

- [项目起源](#项目起源)
- [界面预览](#界面预览)
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [架构](#架构)
- [项目结构](#项目结构)
- [本地运行](#本地运行)
- [部署](#部署)
- [质量保障](#质量保障)
- [路线图](#路线图)
- [License](#license)

---

## 项目起源

家里长辈退休后想玩斗地主，但市面上的 App 广告多、需要充值、操作复杂。于是做了一个**免费、无广告、打开网页就能玩**的版本，给长辈用手机号注册即可开局。后来逐步迭代出多策略 AI 对战、用户系统、战绩回放，直至云端部署与 AI 学习闭环。

## 界面预览

登录、大厅与对战的三个核心界面：

对战、登录与大厅三个核心界面（顶部的对战图为叫牌阶段，进入出牌后 AI 会依据下方「AI 策略六要点」决策，配合角色分工与学习闭环持续进化）：

| 登录界面 | 大厅（战绩 / 排行榜） |
|---|---|
| <img src="assets/screenshots/login.png" width="100%" alt="登录界面"> | <img src="assets/screenshots/lobby.png" width="100%" alt="大厅界面"> |

## 功能特性

| 功能 | 说明 |
|---|---|
| AI 对战 | 三个 AI 对手（地主 / 门板农民 / 下家农民），具备手数分析、拆牌罚分、让牌三原则、概率记牌推算等策略，非随机出牌 |
| 农民配合 | 门板顶牌、下家冲锋的角色分工；不压队友红线（浪费压制=0） |
| AI 学习闭环 | 每局按"分桶"记录关键决策与结果写入数据库，样本量达门槛后以 ±20 分修正影响后续决策——**变的是数据，不是代码** |
| AI 教练复盘 | 打完一局自动生成复盘：24 种局面场景 + 106 句人写文案模板，填入该局真实数据（手数 / 炸弹 / 关键回合），**本地模板引擎生成，零模型调用、毫秒级响应** |
| 规则问答助手 | 右下角小气泡随时问「三带一能带对子吗」：621 行规则手册切片检索 + 双模型容灾（主 DeepSeek-V4-Flash / 备 mimo-v2.5，限流自动切换） |
| 用量后台 | `/xk-usage.html` 白名单访问：调用审计、按用户 / 时间筛选、导出 CSV |
| AI 教练复盘 | 打完一局自动生成复盘：24 种局面场景 × 106 句人写文案模板，用该局真实数据填空，**本地模板引擎生成，零模型调用、零 token、毫秒级响应** |
| 规则问答助手 | 右下角小气泡随时提问（如「三带一能带对子吗」）：621 行规则手册切片检索 + 双模型容灾（主模型 DeepSeek-V4-Flash，限流 / 失败自动切备胎 mimo-v2.5） |
| 用量后台 | `/xk-usage.html` 白名单访问：调用审计、按用户筛选、导出 CSV |
| AI 教练复盘 | 打完一局自动生成复盘：24 种局面场景 × 106 句人写文案模板，用该局真实数据填空，**本地模板引擎生成，零模型调用、零 token、毫秒级响应** |
| 规则问答助手 | 右下角小气泡随时提问（如「三带一能带对子吗」）：621 行规则手册切片检索 + 双模型容灾（主 DeepSeek-V4-Flash，限流 / 失败自动切备胎 mimo-v2.5） |
| 用量后台 | `/xk-usage.html` 白名单访问：调用审计、按用户筛选、导出 CSV |
| 用户系统 | 注册 / 登录 / 自动登录 / 注销、头像上传、隐私开关 |
| 战绩与回放 | 保存每局完整操作序列，支持逐步回放复盘 |
| 排行榜 | 多用户胜场 / 胜率排行（用户名做 HTML 转义防 XSS） |
| 响应式 | 适配电脑与手机（含横屏），回放界面有独立移动端缩放 |
| 音效 | 背景音乐 + 出牌语音（"单勾""对圈""大王"等）+ 炸弹倍数提示 |

## 技术栈

| 层 | 技术 | 规模 |
|---|---|---|
| 前端 | 原生 HTML/CSS/JS，无框架，按功能分 9 组 27 个模块 | ~3,000 行 JS |
| 后端 | Python 3 + Flask + Blueprint（auth / user / game_data / ai / ai_assist / static 6 组路由） | ~2,300 行 |
| AI 引擎 | 纯 Python 决策引擎（评估 / 策略 / 候选生成 / 门板成本模型 / 队友模型 / 学习修正） | ~4,400 行 |
| AI 知识库 | 规则手册 621 行 + 复盘句库 106 句 + 敏感词表 856 词（纯文本 / JSON，随镜像打包） | 1,718 行 |
| 数据库 | 生产：腾讯云 TDSQL-C MySQL；本地：自动降级 SQLite（双模式，凭据全部环境变量注入） | 4 张核心表 |
| 部署 | Docker + CloudBase 云托管 + GitHub Actions CI/CD | 推送即部署 |

## 架构

```
浏览器（frontend/js 27模块 + AI 小助手气泡）
   │  fetch /api/*
   ▼
Flask 后端（backend/app.py + routes/）
   │  出牌决策
   ▼
AI 引擎（backend/ai/）
   ├─ engine.py        决策总入口（统一评分候选出牌）
   ├─ evaluation.py    手牌评估 / 概率记牌推算（只看公开信息，不看暗手）
   ├─ strategy.py      出牌策略与让牌三原则
   ├─ candidates.py    候选牌型生成
   ├─ gate_cost.py     门板顶牌成本模型
   ├─ partner_model.py 队友配合模型（送牌/渡牌/接队友）
   ├─ bid.py           叫/抢地主决策
   ├─ learning.py      学习闭环：分桶记录 + 查账修正（±20）
   └─ state.py/pattern.py/config.json
   │
   ▼
MySQL（TDSQL-C，环境变量注入凭据）/ SQLite（本地自动降级）
   ├─ users          账号
   ├─ game_records   战绩 + 完整操作序列（回放数据源）
   ├─ ai_learning    决策分桶账本（学习数据源）
   └─ ai_usage       AI 助手调用审计（用量后台数据源）
```

### AI 策略六要点

1. **手数分析**：估算打完剩余手牌的最少回合数，优先走出牌后手数更少的方案
2. **拆牌罚分层级**：拆顺子/连对按代价分级罚分，不破坏关键牌型
3. **禁用大牌当带牌**：2 和王不做三带/四带的 kicker，保留控制力
4. **让牌三原则**：位置（是否队友先出）、牌型（能否便宜接）、代价（让完是否失控）
5. **概率记牌推算**：基于已出牌与对手剩余张数推算持牌概率——不读暗手，公平可解释
6. **角色分工**：门板农民顶住地主、下家农民冲锋跑牌；红线是绝不浪费压制队友

### 学习闭环（数据驱动，不改代码）

```
每局决策 → 按局面分桶写入 ai_learning（BID/PASS/COUNTER/SPLIT/BOMB…）
        → 某桶样本 ≥30 条 → 查账员按桶胜率给候选 ±20 分修正
        → 60 秒缓存刷新，AI 行为随真实战绩缓慢演化
```

### AI 复盘与问答助手（两条链路）

```
问答链路（走模型，双模型容灾）
用户提问 → 领域过滤（非斗地主问题直接挡回）→ 敏感词过滤
        → 规则手册切片检索（621 行按章节切分，只送相关片段，省 token 也省延迟）
        → 主模型 DeepSeek-V4-Flash → 限流 / 返回空 → 自动切备胎 mimo-v2.5（60 秒冷却）
        → 结果写入 ai_usage 审计表（供 /xk-usage.html 后台统计）

复盘链路（不走模型，零 token）
该局真实数据（手数 / 炸弹 / 关键回合 / 座位角色）
        → 匹配 24 种局面场景 → 从 106 句人写文案挑句 → 真数填空 → 毫秒级输出
```

知识库文件用 `.txt` / `.json` 而非 `.md`，是因为 `.dockerignore` 排除了 `*.md`——必须绕过它，否则知识文件进不了线上镜像，AI 助手会在云端「裸奔」。

## 项目结构

```
├── backend/
│   ├── app.py              # Flask 入口：建表、诊断接口 /api/diag
│   ├── utils.py            # 数据库双模式连接（MySQL/SQLite 自动降级）
│   ├── routes/             # 6 组 Blueprint：auth / user / game_data / ai / ai_assist / static
│   ├── knowledge/          # AI 助手知识库：rules.txt / review_lines.json / blocked_words.txt
│   └── ai/                 # AI 引擎（10 个模块，见上方架构图）
├── frontend/
│   ├── index.html          # 游戏主界面
│   ├── lobby.html          # 大厅：登录、排行榜、回放入口
│   ├── xk-usage.html       # 用量后台（白名单访问）
│   ├── sound.js / style.css / manifest.json
│   └── js/
│       ├── 01-core/        # 常量、状态、牌型识别
│       ├── 02-game/        # 发牌、叫地主、出牌、结算
│       ├── 03-ai/          # 前端 AI 兜底与后端调用
│       ├── 04-replay/      # 回放控制与渲染
│       ├── 05-ui/          # 卡牌渲染、布局、交互
│       ├── 06-user/        # 登录注册、战绩、排行榜
│       ├── 07-audio/       # 音效控制
│       ├── 08-assistant/   # AI 小助手气泡 + 复盘入口（含 vendor/ 本地化前端资源）
│       └── 99-init/        # 启动装配
├── audio/                  # 背景音乐与出牌语音
├── assets/screenshots/     # README 界面预览截图
├── .github/workflows/deploy.yml  # push main → 自动构建部署到 CloudBase
├── Dockerfile              # python:3.11-slim + Flask
├── requirements.txt        # flask / flask-cors / gunicorn / Pillow / pymysql
└── 启动斗地主.bat          # Windows 一键本地启动
```

## 本地运行

```bash
# 1. 安装依赖（Python 3.10+）
pip install -r requirements.txt

# 2. 启动（默认 8080 端口）
cd backend
python app.py

# 3. 浏览器访问 http://localhost:8080
#    Windows 用户也可直接双击项目根目录的「启动斗地主.bat」
```

无需配置数据库：检测不到 MySQL 凭据时自动降级为本地 SQLite（`backend/database/doudizhu.db`），本地数据与线上数据完全隔离。

连接生产 MySQL 需注入环境变量：`DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME`（凭据不入库，在 CloudBase 云托管服务设置中配置）。

## 部署

```
git push origin main
   → GitHub Actions 读取 Secrets（TCB_SECRET_ID / TCB_SECRET_KEY / TCB_ENV_ID）
   → tcb CLI 构建 Docker 镜像并部署到 CloudBase 云托管
   → 约 2 分钟生效，访问 GET /api/diag 验证（db_mode=mysql, db_ok=true）
```

### 环境变量（均不入库，在 CloudBase 云托管控制台配置）

| 变量 | 用途 | 缺失时行为 |
|---|---|---|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | 生产 MySQL 连接 | 自动降级本地 SQLite |
| `ASSIST_API_KEY` / `ASSIST_BASE_URL` / `ASSIST_MODEL` | 问答主模型（商汤 DeepSeek-V4-Flash） | 问答降级，复盘不受影响 |
| `BACKUP_API_KEY` / `BACKUP_BASE_URL` / `BACKUP_MODEL` | 容灾备胎（小米 mimo-v2.5） | 主模型失败时无备胎可切 |

本地开发把真实值写进 `backend/config_local.py`（已在 `.gitignore`，永不入库）。

## 质量保障

- 行为回归基线（quality gate）：500 局自动对拍 + 关键决策快照比对，任何策略改动必须过门
- 红线探针：浪费压队友 / 炸弹压队友 / 乱炸 三项恒为 0 的纪律断言
- 真人实测：策略迭代以真实对局回放对账定案

## 路线图

- [ ] 用户密码 bcrypt 化（当前 SHA-256）
- [ ] 统一鉴权中间件与 API 测试覆盖
- [ ] 学习数据真人/模拟分账
- [ ] 社交功能：好友、他人主页与最近对局回放

---

## License

[MIT License](LICENSE) © 2026 James Wu
