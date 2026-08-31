# 多AI三角色协作架构设计（v2）

> 创建时间：2026-08-31
> 项目：斗地主AI引擎升级
> 状态：设计阶段（优化版）
> 版本：v2.0

---

## 📌 设计目标

构建一个高效、可落地的三角色AI协作系统，专注斗地主AI引擎升级项目。通过明确分工、简化流程、提供具体实现示例，确保架构可直接实施。

---

## 🎭 角色定义（精简版）

### 1. 提示词工程师（我）
**核心职责**：需求分析 → 策略设计 → 提示词撰写 → 方案审阅
**产出物**：
- 提示词文档（中文纯文字，无代码）
- 验收清单（可验证的数值化标准）
- 决策记录（ADR）

**工具**：保险库、任务看板、文档编辑器

### 2. 代码执行者（另一个AI Agent）
**核心职责**：根据提示词执行代码修改 → 生成执行日志
**约束**：
- 只有用户明确说"你现在改/你来改/去改"时才动代码
- 严格只改AI/引擎逻辑，禁止动UI
- 每修改一个点立即自行测试

**产出物**：修改后的代码 + 执行日志

### 3. 测试验证者（新增）
**核心职责**：运行测试 → 验证功能 → 发现问题 → 生成报告
**测试范围**（按优先级）：
1. **功能测试**：叫地主、出牌、胜负判断
2. **AI策略测试**：验证AI决策是否符合预期
3. **单元测试**：关键函数正确性
4. **性能测试**：响应时间（后期）

**产出物**：测试报告 + 问题清单

---

## 🔄 协作流程（简化版）

### 标准流程
```
提示词设计 → 用户确认 → 代码执行 → 测试验证 → 交付/返工
```

### 关键节点
1. **用户确认点**：提示词完成后，必须用户明确说"你现在改/你来改/去改"
2. **测试验证点**：代码修改后，必须通过测试验证
3. **返工决策点**：测试失败时，由提示词工程师决定返工方向

### 错误处理规则
**测试发现问题后的决策流程**：
1. **代码错误**（语法、运行时）→ 返回代码执行者修复
2. **设计错误**（策略不合理）→ 提示词工程师修改设计
3. **测试错误**（用例不全）→ 修改测试用例

---

## 📊 状态管理（简化版）

### 四个核心状态
1. **待处理**：任务已创建，等待开始
2. **进行中**：角色正在执行任务
3. **测试中**：测试验证者正在测试
4. **已完成**：测试通过，正式交付

### 状态流转规则
```
待处理 → 进行中（提示词工程师）→ 进行中（代码执行者）→ 测试中 → 已完成/待处理（返工）
```

### 状态更新责任
- 提示词工程师：更新"进行中（提示词）"状态
- 代码执行者：更新"进行中（代码）"状态
- 测试验证者：更新"测试中"和"已完成"状态

---

## 🛠️ 工具集成（具体配置）

### 测试框架选择
**斗地主项目推荐方案**：
1. **单元测试**：Jest（前端JavaScript） + Pytest（后端Python）
2. **功能测试**：自定义测试脚本（基于游戏逻辑）
3. **性能测试**：后期集成Lighthouse或Locust

### 具体配置示例

#### Jest配置（前端测试）
```javascript
// jest.config.js
module.exports = {
  testEnvironment: 'jsdom',
  coverageDirectory: 'coverage',
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80
    }
  }
};
```

#### Pytest配置（后端测试）
```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = --verbose --tb=short
```

### 斗地主专用测试工具

#### 1. 牌局模拟器设计
```javascript
// 牌局模拟器示例
class GameSimulator {
  // 生成随机牌局
  static generateRandomGame() {
    // 返回：{players: [[手牌], [手牌], [手牌]], landlordCards: [底牌]}
  }
  
  // 从真实牌局生成
  static createFromReplay(replayData) {
    // 解析回放数据，生成测试牌局
  }
  
  // 运行模拟游戏
  static runSimulation(gameSetup, aiStrategy) {
    // 返回：{winner, moves: [...], duration}
  }
}
```

#### 2. AI决策记录器
```javascript
// AI决策记录器示例
class AIDecisionRecorder {
  constructor() {
    this.decisions = [];
  }
  
  // 记录AI决策
  record(playerId, gameState, decision, reasoning) {
    this.decisions.push({
      timestamp: Date.now(),
      playerId,
      gameState: {...gameState},
      decision,
      reasoning
    });
  }
  
  // 导出决策日志
  exportToJSON() {
    return JSON.stringify(this.decisions, null, 2);
  }
}
```

#### 3. 胜率统计器
```javascript
// 胜率统计器示例
class WinRateCalculator {
  constructor() {
    this.games = [];
  }
  
  // 添加游戏结果
  addGameResult(winner, landlordId, moves) {
    this.games.push({winner, landlordId, moves, timestamp: Date.now()});
  }
  
  // 计算胜率
  calculateWinRate(playerId) {
    const totalGames = this.games.length;
    const wins = this.games.filter(g => g.winner === playerId).length;
    return {
      totalGames,
      wins,
      winRate: (wins / totalGames * 100).toFixed(2) + '%'
    };
  }
}
```

---

## 📈 质量保障（具体指标）

### 分阶段目标

#### 第一阶段（基础功能）
- 功能测试覆盖率：100%核心功能
- 单元测试覆盖率：≥60%
- AI决策准确率：≥70%

#### 第二阶段（优化提升）
- 功能测试覆盖率：100%
- 单元测试覆盖率：≥80%
- AI决策准确率：≥85%
- 性能指标：AI决策响应时间<200ms

#### 第三阶段（全面完善）
- 所有测试覆盖率达标
- 性能指标：AI决策响应时间<100ms
- 完整的回归测试体系

### 代码质量标准
- 遵守现有代码风格
- 关键函数有注释
- 无语法错误、无运行时错误

---

## 🚀 实施计划（渐进式）

### 第一阶段：基础搭建（2-3天）
**目标**：建立基本协作流程，验证可行性

1. **提示词工程师**：
   - 选择斗地主AI升级的一个小功能（如"手数分析"）
   - 撰写详细提示词文档
   - 准备验收清单

2. **代码执行者**：
   - 根据提示词执行代码修改
   - 生成执行日志

3. **测试验证者**：
   - 创建基础测试用例
   - 运行功能测试
   - 生成测试报告

**交付物**：一个完整功能的开发-测试闭环

### 第二阶段：工具集成（3-4天）
**目标**：集成测试框架，建立自动化测试

1. **配置测试环境**：
   - 安装配置Jest和Pytest
   - 创建测试目录结构
   - 编写测试配置文件

2. **创建测试工具**：
   - 实现牌局模拟器基础版
   - 创建AI决策记录器
   - 建立胜率统计器

3. **编写测试用例**：
   - 基础牌局测试
   - AI策略测试
   - 边界情况测试

**交付物**：完整的测试框架和基础测试用例

### 第三阶段：流程优化（持续）
**目标**：优化协作流程，提升效率

1. **收集反馈**：
   - 记录执行过程中的问题
   - 收集角色间的沟通痛点
   - 评估测试效果

2. **优化流程**：
   - 简化不必要的步骤
   - 增强关键环节
   - 改进沟通机制

3. **扩展应用**：
   - 应用到AI引擎升级的其他要点
   - 建立标准作业程序
   - 培训其他团队成员

**交付物**：优化后的协作流程和标准作业程序

---

## 📋 斗地主项目测试用例示例

### 1. 功能测试用例
```javascript
// 测试用例：叫地主功能
describe('叫地主功能测试', () => {
  test('牌力评分正确性', () => {
    // 测试牌力评分系统是否准确
    const hand = ['大王', '2', 'A', 'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3'];
    const score = calculateHandStrength(hand);
    expect(score).toBeGreaterThan(80); // 好牌应该得分高
  });
  
  test('叫地主决策逻辑', () => {
    // 测试AI是否在合适时叫地主
    const gameState = {handStrength: 85, position: 'first'};
    const decision = aiDecideBid(gameState);
    expect(decision).toBe(true); // 强牌应该叫地主
  });
});
```

### 2. AI策略测试用例
```javascript
// 测试用例：出牌策略
describe('出牌策略测试', () => {
  test('拆牌决策', () => {
    // 测试AI是否合理拆牌
    const hand = ['大王', '2', '2', 'A', 'A', 'K', 'K', 'Q', 'Q', 'J', 'J', '10', '10', '9', '9'];
    const gameState = {landlordCards: ['A', 'K', 'Q']};
    const decision = aiDecidePlay(hand, gameState);
    // 验证拆牌决策是否合理
    expect(decision.type).not.toBe('拆炸弹'); // 不应该拆炸弹
  });
  
  test('让牌决策', () => {
    // 测试让牌原则
    const gameState = {position: 'farmer', teammateIsLandlord: false};
    const shouldLet = aiDecideLet(gameState);
    expect(shouldLet).toBe(true); // 农民应该让队友出牌
  });
});
```

### 3. 边界测试用例
```javascript
// 测试用例：边界情况
describe('边界情况测试', () => {
  test('空手牌处理', () => {
    // 测试空手牌时的处理
    const hand = [];
    expect(() => aiDecidePlay(hand, {})).not.toThrow();
  });
  
  test('极端牌局', () => {
    // 测试极端牌局（如全是单牌）
    const hand = ['大王', '2', 'A', 'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3'];
    const decision = aiDecidePlay(hand, {});
    expect(decision).toBeDefined();
  });
});
```

---

## 🎯 成功标准

### 流程成功标准
1. **角色分工明确**：每个角色清楚自己的职责边界
2. **沟通效率高**：角色间沟通顺畅，无重复工作
3. **质量可控**：测试覆盖率达标，bug发现率提高

### 项目成功标准
1. **功能完整性**：AI引擎升级六大要点全部完成
2. **代码质量**：无严重bug，性能达标
3. **文档完整**：提示词文档、测试报告、决策记录齐全

---

## 📝 注意事项（精简版）

### 角色边界
- 每个角色只做自己职责范围内的事
- 需要协作时，通过正式渠道沟通

### 沟通规范
- 使用标准文档格式
- 重要决策必须记录（ADR）
- 测试结果必须量化

### 质量要求
- 每个阶段产出必须可验证
- 测试必须全面，不遗漏关键场景
- 问题必须追根溯源，不表面修复

---

*本设计文档针对斗地主项目特点进行了优化，提供了具体的实现示例和渐进式实施计划。*