<p align="center">
  <img src="assets/screenshots/game-bidding.png" width="90%" alt="斗地主对战界面预览">
</p>

<h1 align="center">斗地主终极版（会会斗地主）</h1>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-3.x-green?logo=flask&logoColor=white">
  <img alt="JavaScript" src="https://img.shields.io/badge/JavaScript-ES6+-yellow?logo=javascript&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-blue?logo=docker&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-yellowgreen">
</p>

一个**全栈网页版斗地主游戏**：原生 JS 前端 + Flask 后端 + Python 启发式 AI 引擎（带数据驱动学习闭环）+ **基于混合检索（RAG）的规则知识库问答助手**，支持账号系统、战绩回放、排行榜与 AI 用量控制台，Docker 容器化部署在腾讯云 CloudBase，GitHub Actions 推送即部署。

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

家里长辈退休后想玩斗地主，但市面上的 App 广告多、需要充值、操作复杂。于是做了一个**免费、无广告、打开网页就能玩**的版本，给长辈用手机号注册即可开局。后来逐步迭代出多策略 AI 对战、用户系统、战绩回放，直至云端部署、AI 学习闭环与知识库问答助手。

## 界面预览

| 对战（叫牌阶段） | 登录界面 | 大厅（战绩 / 排行榜） |
|---|---|---|
| <img src="assets/screenshots/game-bidding.png" width="100%" alt="对战界面"> | <img src="assets/screenshots/login.png" width="100%" alt="登录界面"> | <img src="assets/screenshots/lobby.png" width="100%" alt="大厅界面"> |

## 功能特性

| 功能 | 说明 |
|---|---|
| AI 对战 | 三个 AI 对手（地主 / 门板农民 / 下家农民），具备手数分析、拆牌罚分、让牌三原则、概率记牌推算等策略，非随机出牌 |
| 农民配合 | 门板顶牌、下家冲锋的角色分工；不压队友红线（浪费压制=0） |
| AI 学习闭环 | 每局按"局面分桶"记录关键决策与胜负写入数据库，样本达门槛后以 ±20 分修正影响后续决策——**变的是数据，不是代码**；另设 PASS 决策监督模型试点（离线训练 → JSON 导出 → 纯 Python 推理） |
| AI 教练复盘 | 打完一局自动生成复盘：24 种局面场景 × 106 句人写文案模板，填入该局真实数据（手数 / 炸弹 / 关键回合），**本地模板引擎生成，零模型调用、零 token、毫秒级响应** |
| 规则问答助手 | 右下角小气泡随时提问（如「三带一能带对子吗」）：**混合检索知识库**（语义向量 + BM25 关键词 → RRF 融合）切片送入大模型，回答自动附手册出处且服务端防幻觉校验 |
| 知识库管理 | 手册/文档上传 → 审批（pending→published）→ 增量切片索引，支持 internal 内部文档与问答池隔离 |
| 差评回流 | 助手回答可点踩：差评按问题自动归并进"差评队列"管理后台，修复手册后挂钩金样评测集——**用户反馈直达知识改进** |
| 用量控制台 | `/xk-usage.html` 白名单访问：调用审计、按用户/时间筛选、花费估算、差评队列、导出 CSV |
| 用户系统 | 注册 / 登录 / 自动登录 / 注销、头像上传、隐私开关 |
| 战绩与回放 | 保存每局完整操作序列，支持逐步回放复盘 |
| 排行榜 | 多用户胜场 / 胜率排行（用户名做 HTML 转义防 XSS） |
| 响应式 | 适配电脑与手机（含横屏），回放界面有独立移动端缩放 |
| 音效 | 背景音乐 + 出牌语音（"单勾""对圈""大王"等）+ 炸弹倍数提示 |

## 技术栈

| 层 | 技术 | 规模 |
|---|---|---|
| 前端 | 原生 HTML/CSS/JS，无框架，按功能分 9 组 27 个模块 | ~3,200 行 JS |
| 后端路由 | Python 3 + Flask + Blueprint（auth / user / game_data / ai / ai_assist / kb / static 7 组路由） | ~1,500 行 |
| AI 引擎 | 纯 Python 决策引擎（评估 / 策略 / 候选生成 / 门板成本模型 / 队友模型 / 学习修正） | ~5,600 行 |
| 知识库检索 | **混合检索（RAG）**：fastembed + BGE 中文嵌入模型（ONNX/CPU）+ rank_bm25 + RRF 融合，父子块分层索引 | ~1,100 行 |
| 数据库 | 生产：腾讯云 TDSQL-C MySQL；本地：自动降级 SQLite（双模式，凭据全部环境变量注入） | 7 张核心表 |
| 部署 | Docker（嵌入模型打入镜像、离线加载）+ CloudBase 云托管 + GitHub Actions CI/CD | 推送即部署 |

## 架构

```
浏览器（frontend/js 27模块 + AI 小助手气泡）
   │  fetch /api/*
   ▼
Flask 后端（backend/app.py + routes/ 7 组蓝图）
   │
   ├── 出牌决策 ──► AI 引擎（backend/ai/）
   │     ├─ engine.py        决策总入口（幸存过滤 / 炸弹纪律 / 三角色决策门）
   │     ├─ evaluation.py    候选打分（接入学习修正分）
   │     ├─ strategy.py      记牌概率推算 / 拆牌罚分 / 让牌三原则
   │     ├─ candidates.py    候选牌型生成
   │     ├─ gate_cost.py     门板顶牌成本模型
   │     ├─ partner_model.py 队友配合模型（送牌/渡牌/接队友）
   │     ├─ bid.py           叫/抢地主决策（含 BID 学习修正）
   │     ├─ learning.py      学习闭环：分桶账本查询 + 修正分（±20）
   │     └─ pattern.py / state.py / config.json
   │
   └── 问答助手 ──► 知识库检索（backend/ai_kb/）
         ├─ embedder.py   语义向量（BGE 中文模型，ONNX/CPU）
         ├─ chunker.py    章父块 + 滑窗子块分层切片（表格不拆、增量哈希）
         ├─ retriever.py  向量+BM25 双路召回 → RRF 融合 → 父块回传
         ├─ pipeline.py   文档状态机（上传→审批→发布→归档）
         └─ ingest.py     docx/pdf 文本抽取
   │
   ▼
MySQL（TDSQL-C，环境变量注入凭据）/ SQLite（本地自动降级）
   ├─ users          账号
   ├─ game_records   战绩 + 完整操作序列（回放数据源）
   ├─ ai_learning    决策分桶账本（学习数据源）
   ├─ ai_usage       AI 助手调用审计（用量控制台 / 差评队列数据源）
   ├─ kb_chunk       知识块 + 向量索引（增量更新）
   ├─ kb_document    知识文档审批状态机
   └─ kb_badcase     差评归并队列（知识改进闭环）
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
每局决策 → 按局面分桶写入 ai_learning（BID/PASS/beat/COUNTER/SPLIT/BOMB/LEAD…）
        → 局终回填胜负 → 某桶样本 ≥30 条 → 按桶胜率给候选 ±20 分修正
        → 60 秒缓存刷新，AI 行为随真实战绩缓慢演化
```

PASS 决策另有监督模型试点：sklearn 离线训练（自我对弈/真人数据按前缀分账、禁混训，按局切分防泄漏）→ 系数导出纯 JSON → 线上纯 Python 推理，失败自动回退统计修正。

### AI 助手：问答链路与知识改进闭环

```
问答（走模型，双模型容灾）
用户提问 → 领域过滤 → 敏感词过滤 → 追问改写（多轮指代消解）
        → 混合检索：语义向量(BGE) + BM25 双路召回 → RRF 融合 → 取 top3 子块回传整章
        → 主模型 qwen3.8-flash → 限流/失败自动切备胎 DeepSeek-V4-Flash（60 秒冷却）
        → 回答自动附手册出处，服务端校验章号（编造引用直接剥掉）
        → 全量写入 ai_usage 审计表（含 token/花费/命中明细）

知识改进（差评回流，不走模型）
用户点踩 → 差评按问题自动归并进 kb_badcase 队列 → 管理员修手册/上传文档
        → 审批发布 → 增量重算 embedding、原子切换索引 → 金样评测集回归验证
```

金样评测集（32 道领域题 + 6 道无关题）持续对照新旧检索方案的命中率，防知识库改动退化；无关题前置拦截保证助手不答非斗地主问题。

知识库文件用 `.txt` / `.json` 而非 `.md`，是因为 `.dockerignore` 排除了 `*.md`——必须绕过它，否则知识文件进不了线上镜像，AI 助手会在云端「裸奔」。

## 项目结构

```
├── backend/
│   ├── app.py              # Flask 入口：建表、诊断接口 /api/diag
│   ├── utils.py            # 数据库双模式连接（MySQL/SQLite 自动降级）
│   ├── auth_utils.py       # 统一鉴权（token 反查 + 角色校验）
│   ├── routes/             # 7 组 Blueprint：auth / user / game_data / ai / ai_assist / kb / static
│   ├── ai/                 # AI 决策引擎（13 个模块，见上方架构图）
│   │   └── model_pass/     # PASS 监督模型系数（离线训练产物，纯 JSON）
│   ├── ai_kb/              # 知识库检索：embedder / chunker / retriever / pipeline / ingest
│   ├── knowledge/          # 手册 rules.txt / 复盘句库 / 敏感词表 / 金样评测集
│   ├── kb_docs/            # 审批发布的上传文档
│   └── tools/              # 离线训练脚本（如 PASS 决策模型）
├── frontend/
│   ├── index.html          # 游戏主界面
│   ├── lobby.html          # 大厅：登录、排行榜、回放入口
│   ├── xk-usage.html       # 用量控制台（白名单访问，含差评队列）
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
├── tests/                  # 质量保障：行为回归 / A/B 门控 / 影子对局 / jest 单测
├── .github/workflows/deploy.yml  # push main → 自动构建部署到 CloudBase
├── Dockerfile              # python:3.11-slim（嵌入模型打入镜像、离线加载）
├── requirements.txt        # flask / flask-cors / gunicorn / pymysql / fastembed / rank-bm25 / numpy 等
└── 启动斗地主.bat          # Windows 一键本地启动
```

## 本地运行

```bash
# 1. 安装依赖（Python 3.11+）
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
| `ASSIST_API_KEY` / `ASSIST_BASE_URL` / `ASSIST_MODEL` | 问答主模型（qwen3.8-flash） | 问答降级，复盘不受影响 |
| `BACKUP_API_KEY` / `BACKUP_BASE_URL` / `BACKUP_MODEL` | 容灾备胎（DeepSeek-V4-Flash） | 主模型失败时无备胎可切 |
| `KB_MODEL_DIR` | 嵌入模型目录（生产镜像已内置并离线加载） | 默认系统临时目录，首启联网下载 |

本地开发把真实值写进 `backend/config_local.py`（已在 `.gitignore`，永不入库）。

## 质量保障

- **行为回归基线（quality gate）**：500 局自动对拍 + 关键决策快照比对，任何策略改动必须过门
- **红线探针**：浪费压队友 / 炸弹压队友 / 乱炸 三项恒为 0 的纪律断言
- **知识库金样评测**：32 道领域题 + 6 道无关题，新旧检索方案对照命中率，防知识/代码改动退化
- **功能验收套件**：追问改写/引用校验（kbtest_012）、差评队列全链路（kbtest_013，含双数据库行形态回归）等
- **前端单测**：jest 覆盖牌型识别与核心规则
- **真人实测**：策略迭代以真实对局回放对账定案

## 路线图

- [ ] 用户密码 bcrypt 化（当前 SHA-256）
- [ ] 检索重排器（cross-encoder 精排 top 候选）
- [ ] 助手答案级自动评测（金样扩容 + LLM 裁判）
- [ ] 多轮对话带上轮回答上下文
- [ ] 统一鉴权中间件与 API 测试覆盖
- [ ] 社交功能：好友、他人主页与最近对局回放

---

## License

[MIT License](LICENSE) © 2026 James Wu
