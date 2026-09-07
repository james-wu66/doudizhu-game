"""
斗地主 AI 引擎 - 模块化版本

模块结构：
- config.json: 配置权重
- state.py: 游戏状态管理
- pattern.py: 牌型检测（锁死）
- candidates.py: 候选出牌生成（锁死）
- evaluation.py: 价值评估（高手级）
- strategy.py: 出牌策略（灵活部分）
- learning.py: 学习机制
- bid.py: 叫地主模块
- engine.py: AI 引擎主入口
"""
