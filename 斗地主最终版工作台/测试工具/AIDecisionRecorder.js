// ⚠️ 已过时（2026-09-01 标注）：独立脚本，未接真实引擎，结果不可用于判断真实游戏。
/**
 * AI决策记录器
 * 用于记录AI决策过程和分析决策质量
 */

class AIDecisionRecorder {
  constructor() {
    this.decisions = [];
    this.sessionId = this.generateSessionId();
    this.startTime = Date.now();
  }

  /**
   * 生成会话ID
   */
  generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * 记录AI决策
   */
  record(playerId, gameState, decision, reasoning = '') {
    const decisionRecord = {
      id: this.decisions.length + 1,
      timestamp: Date.now(),
      sessionId: this.sessionId,
      playerId,
      gameState: this.sanitizeGameState(gameState),
      decision,
      reasoning,
      metadata: {
        gameTime: gameState.gameTime || 0,
        moveNumber: gameState.moveNumber || 0,
        currentPlayer: gameState.currentPlayer
      }
    };

    this.decisions.push(decisionRecord);
    return decisionRecord;
  }

  /**
   * 清理游戏状态（移除敏感信息）
   */
  sanitizeGameState(gameState) {
    // 只保留必要的游戏状态信息
    return {
      hand: gameState.hand || [],
      handSize: (gameState.hand || []).length,
      landlordCards: gameState.landlordCards || [],
      landlordId: gameState.landlordId,
      otherPlayersHands: (gameState.otherPlayersHands || []).map(h => h.length),
      lastPlay: gameState.lastPlay || null,
      lastPlayer: gameState.lastPlayer,
      bombsUsed: gameState.bombsUsed || 0,
      bigCardsPlayed: gameState.bigCardsPlayed || []
    };
  }

  /**
   * 记录出牌决策
   */
  recordPlayDecision(playerId, hand, playOptions, selectedPlay, reasoning) {
    const gameState = {
      hand,
      handSize: hand.length,
      moveNumber: this.decisions.length + 1
    };

    return this.record(playerId, gameState, {
      type: 'play',
      cards: selectedPlay.cards,
      playType: selectedPlay.type,
      alternatives: playOptions.length,
      selectedRank: this.calculatePlayRank(selectedPlay)
    }, reasoning);
  }

  /**
   * 记录叫地主决策
   */
  recordBidDecision(playerId, hand, bidDecision, handStrength) {
    const gameState = {
      hand,
      handSize: hand.length,
      moveNumber: this.decisions.length + 1
    };

    return this.record(playerId, gameState, {
      type: 'bid',
      decision: bidDecision,
      handStrength,
      bidAmount: bidDecision ? 1 : 0
    }, `手牌强度: ${handStrength.totalValue}, 大牌: ${handStrength.bigCards}, 炸弹: ${handStrength.bombCount}`);
  }

  /**
   * 记录让牌决策
   */
  recordPassDecision(playerId, gameState, passReason) {
    return this.record(playerId, gameState, {
      type: 'pass',
      reason: passReason,
      cardsPassed: gameState.lastPlay ? gameState.lastPlay.cards : []
    }, passReason);
  }

  /**
   * 计算出牌优先级
   */
  calculatePlayRank(play) {
    const typeRanks = {
      'single': 1,
      'pair': 2,
      'triple': 3,
      'triple_one': 4,
      'triple_two': 5,
      'straight': 6,
      'pair_straight': 7,
      'airplane': 8,
      'bomb': 9,
      'rocket': 10
    };

    return typeRanks[play.type] || 0;
  }

  /**
   * 导出决策日志为JSON
   */
  exportToJSON() {
    return JSON.stringify({
      sessionId: this.sessionId,
      startTime: this.startTime,
      endTime: Date.now(),
      duration: Date.now() - this.startTime,
      totalDecisions: this.decisions.length,
      decisions: this.decisions
    }, null, 2);
  }

  /**
   * 导出决策日志为CSV
   */
  exportToCSV() {
    const headers = [
      'ID', '时间戳', '玩家', '决策类型', '出牌', '推理'
    ];

    const rows = this.decisions.map(d => [
      d.id,
      new Date(d.timestamp).toISOString(),
      d.playerId,
      d.decision.type,
      d.decision.cards ? d.decision.cards.join(';') : '',
      `"${d.reasoning.replace(/"/g, '""')}"`
    ]);

    return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  }

  /**
   * 分析决策质量
   */
  analyzeDecisionQuality() {
    const analysis = {
      totalDecisions: this.decisions.length,
      decisionTypes: {},
      averageReasoningLength: 0,
      commonPatterns: []
    };

    // 统计决策类型
    this.decisions.forEach(d => {
      const type = d.decision.type;
      analysis.decisionTypes[type] = (analysis.decisionTypes[type] || 0) + 1;
    });

    // 计算平均推理长度
    const reasoningLengths = this.decisions
      .filter(d => d.reasoning)
      .map(d => d.reasoning.length);
    
    if (reasoningLengths.length > 0) {
      analysis.averageReasoningLength = reasoningLengths.reduce((a, b) => a + b, 0) / reasoningLengths.length;
    }

    // 分析常见决策模式
    const playDecisions = this.decisions.filter(d => d.decision.type === 'play');
    const typeCount = {};
    
    playDecisions.forEach(d => {
      const playType = d.decision.playType;
      typeCount[playType] = (typeCount[playType] || 0) + 1;
    });

    analysis.commonPatterns = Object.entries(typeCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([type, count]) => ({ type, count, percentage: (count / playDecisions.length * 100).toFixed(2) + '%' }));

    return analysis;
  }

  /**
   * 生成决策报告
   */
  generateReport() {
    const analysis = this.analyzeDecisionQuality();
    
    return {
      sessionId: this.sessionId,
      summary: {
        startTime: new Date(this.startTime).toISOString(),
        endTime: new Date().toISOString(),
        duration: ((Date.now() - this.startTime) / 1000).toFixed(2) + '秒',
        totalDecisions: analysis.totalDecisions
      },
      decisionTypes: analysis.decisionTypes,
      qualityMetrics: {
        averageReasoningLength: analysis.averageReasoningLength.toFixed(2),
        decisionConsistency: this.calculateDecisionConsistency()
      },
      commonPatterns: analysis.commonPatterns,
      recommendations: this.generateRecommendations(analysis)
    };
  }

  /**
   * 计算决策一致性
   */
  calculateDecisionConsistency() {
    // 简化的一致性计算：基于决策类型的分布
    const types = Object.values(this.analyzeDecisionQuality().decisionTypes);
    const total = types.reduce((a, b) => a + b, 0);
    
    if (total === 0) return 0;
    
    // 计算熵值（越低越一致）
    const entropy = types.reduce((sum, count) => {
      const p = count / total;
      return sum - (p * Math.log2(p));
    }, 0);
    
    // 归一化到0-1范围
    const maxEntropy = Math.log2(types.length || 1);
    return maxEntropy > 0 ? (1 - entropy / maxEntropy).toFixed(2) : 1;
  }

  /**
   * 生成优化建议
   */
  generateRecommendations(analysis) {
    const recommendations = [];
    
    // 基于决策类型分布的建议
    if (analysis.decisionTypes['pass'] > analysis.totalDecisions * 0.5) {
      recommendations.push({
        type: '策略调整',
        suggestion: '让牌频率过高，考虑调整让牌策略',
        priority: 'medium'
      });
    }
    
    if (analysis.commonPatterns.length > 0) {
      const topPattern = analysis.commonPatterns[0];
      if (topPattern.percentage > '60%') {
        recommendations.push({
          type: '多样性',
          suggestion: `出牌类型过于单一（${topPattern.type}占${topPattern.percentage}），建议增加出牌多样性`,
          priority: 'low'
        });
      }
    }
    
    if (analysis.averageReasoningLength < 10) {
      recommendations.push({
        type: '决策质量',
        suggestion: '推理说明较短，建议增加决策理由的详细程度',
        priority: 'low'
      });
    }
    
    return recommendations;
  }

  /**
   * 清空记录
   */
  clear() {
    this.decisions = [];
    this.sessionId = this.generateSessionId();
    this.startTime = Date.now();
  }

  /**
   * 获取指定玩家的决策历史
   */
  getPlayerDecisions(playerId) {
    return this.decisions.filter(d => d.playerId === playerId);
  }

  /**
   * 获取指定类型的决策
   */
  getDecisionsByType(type) {
    return this.decisions.filter(d => d.decision.type === type);
  }
}

// 导出记录器
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AIDecisionRecorder;
}

// 浏览器环境下的全局对象
if (typeof window !== 'undefined') {
  window.AIDecisionRecorder = AIDecisionRecorder;
}