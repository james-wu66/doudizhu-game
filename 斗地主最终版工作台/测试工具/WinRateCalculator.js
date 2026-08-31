/**
 * 胜率统计器
 * 用于统计AI胜率和生成分析报告
 */

class WinRateCalculator {
  constructor() {
    this.games = [];
    this.sessions = [];
    this.currentSession = null;
  }

  /**
   * 开始新的游戏会话
   */
  startSession(sessionName = '') {
    this.currentSession = {
      id: `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: sessionName || `会话 ${this.sessions.length + 1}`,
      startTime: Date.now(),
      games: [],
      players: {}
    };
    
    this.sessions.push(this.currentSession);
    return this.currentSession.id;
  }

  /**
   * 添加游戏结果
   */
  addGameResult(winner, landlordId, moves, playerIds = [0, 1, 2]) {
    const gameResult = {
      id: this.games.length + 1,
      timestamp: Date.now(),
      winner,
      landlordId,
      moves,
      moveCount: moves.length,
      duration: moves.length > 0 ? 
        moves[moves.length - 1].timestamp - moves[0].timestamp : 0,
      winnerType: winner === landlordId ? 'landlord' : 'farmer',
      sessionId: this.currentSession ? this.currentSession.id : null
    };

    this.games.push(gameResult);
    
    if (this.currentSession) {
      this.currentSession.games.push(gameResult);
    }

    // 更新玩家统计
    this.updatePlayerStats(gameResult, playerIds);
    
    return gameResult;
  }

  /**
   * 更新玩家统计数据
   */
  updatePlayerStats(gameResult, playerIds) {
    if (!this.currentSession) return;

    playerIds.forEach((playerId, index) => {
      if (!this.currentSession.players[playerId]) {
        this.currentSession.players[playerId] = {
          gamesPlayed: 0,
          wins: 0,
          landlordGames: 0,
          landlordWins: 0,
          farmerGames: 0,
          farmerWins: 0,
          totalMoves: 0,
          totalDuration: 0
        };
      }

      const stats = this.currentSession.players[playerId];
      stats.gamesPlayed++;
      stats.totalMoves += gameResult.moveCount;
      stats.totalDuration += gameResult.duration;

      if (gameResult.winner === playerId) {
        stats.wins++;
      }

      if (index === gameResult.landlordId) {
        stats.landlordGames++;
        if (gameResult.winner === playerId) {
          stats.landlordWins++;
        }
      } else {
        stats.farmerGames++;
        if (gameResult.winner === playerId) {
          stats.farmerWins++;
        }
      }
    });
  }

  /**
   * 计算指定玩家的胜率
   */
  calculateWinRate(playerId) {
    const playerGames = this.games.filter(
      game => game.moves.some(move => move.player === playerId)
    );

    if (playerGames.length === 0) {
      return {
        playerId,
        totalGames: 0,
        wins: 0,
        winRate: '0.00%',
        landlordWinRate: '0.00%',
        farmerWinRate: '0.00%'
      };
    }

    const totalGames = playerGames.length;
    const wins = playerGames.filter(game => game.winner === playerId).length;

    // 地主场次
    const landlordGames = playerGames.filter(
      game => game.landlordId === playerId
    );
    const landlordWins = landlordGames.filter(
      game => game.winner === playerId
    ).length;

    // 农民场次
    const farmerGames = playerGames.filter(
      game => game.landlordId !== playerId
    );
    const farmerWins = farmerGames.filter(
      game => game.winner === playerId
    ).length;

    return {
      playerId,
      totalGames,
      wins,
      winRate: (wins / totalGames * 100).toFixed(2) + '%',
      landlordGames: landlordGames.length,
      landlordWins,
      landlordWinRate: landlordGames.length > 0 ? 
        (landlordWins / landlordGames.length * 100).toFixed(2) + '%' : '0.00%',
      farmerGames: farmerGames.length,
      farmerWins,
      farmerWinRate: farmerGames.length > 0 ? 
        (farmerWins / farmerGames.length * 100).toFixed(2) + '%' : '0.00%'
    };
  }

  /**
   * 计算总体胜率统计
   */
  calculateOverallStats() {
    if (this.games.length === 0) {
      return {
        totalGames: 0,
        landlordWins: 0,
        farmerWins: 0,
        landlordWinRate: '0.00%',
        farmerWinRate: '0.00%',
        averageMoves: 0,
        averageDuration: 0
      };
    }

    const totalGames = this.games.length;
    const landlordWins = this.games.filter(g => g.winnerType === 'landlord').length;
    const farmerWins = this.games.filter(g => g.winnerType === 'farmer').length;

    const totalMoves = this.games.reduce((sum, g) => sum + g.moveCount, 0);
    const totalDuration = this.games.reduce((sum, g) => sum + g.duration, 0);

    return {
      totalGames,
      landlordWins,
      farmerWins,
      landlordWinRate: (landlordWins / totalGames * 100).toFixed(2) + '%',
      farmerWinRate: (farmerWins / totalGames * 100).toFixed(2) + '%',
      averageMoves: (totalMoves / totalGames).toFixed(2),
      averageDuration: (totalDuration / totalGames).toFixed(2) + 'ms',
      draws: this.games.filter(g => g.winner === -1).length
    };
  }

  /**
   * 生成胜率报告
   */
  generateReport() {
    const overallStats = this.calculateOverallStats();
    const playerStats = [];

    // 收集所有玩家ID
    const allPlayerIds = new Set();
    this.games.forEach(game => {
      game.moves.forEach(move => {
        allPlayerIds.add(move.player);
      });
    });

    // 计算每个玩家的统计
    allPlayerIds.forEach(playerId => {
      playerStats.push(this.calculateWinRate(playerId));
    });

    // 分析胜率趋势
    const trends = this.analyzeTrends();

    return {
      summary: {
        reportTime: new Date().toISOString(),
        totalGames: overallStats.totalGames,
        totalSessions: this.sessions.length
      },
      overallStats,
      playerStats,
      trends,
      recommendations: this.generateRecommendations(overallStats, playerStats)
    };
  }

  /**
   * 分析胜率趋势
   */
  analyzeTrends() {
    if (this.games.length < 10) {
      return {
        trend: '数据不足',
        suggestion: '需要更多游戏数据来分析趋势'
      };
    }

    // 将游戏分成前半部分和后半部分
    const midpoint = Math.floor(this.games.length / 2);
    const firstHalf = this.games.slice(0, midpoint);
    const secondHalf = this.games.slice(midpoint);

    // 计算前后半部分的地主胜率
    const firstHalfLandlordWinRate = firstHalf.filter(g => g.winnerType === 'landlord').length / firstHalf.length;
    const secondHalfLandlordWinRate = secondHalf.filter(g => g.winnerType === 'landlord').length / secondHalf.length;

    // 计算胜率变化
    const change = secondHalfLandlordWinRate - firstHalfLandlordWinRate;
    const changePercentage = (change * 100).toFixed(2);

    let trend;
    if (Math.abs(change) < 0.05) {
      trend = '稳定';
    } else if (change > 0) {
      trend = '上升';
    } else {
      trend = '下降';
    }

    return {
      trend,
      change: changePercentage + '%',
      firstHalfLandlordWinRate: (firstHalfLandlordWinRate * 100).toFixed(2) + '%',
      secondHalfLandlordWinRate: (secondHalfLandlordWinRate * 100).toFixed(2) + '%',
      suggestion: this.getTrendSuggestion(trend, change)
    };
  }

  /**
   * 获取趋势建议
   */
  getTrendSuggestion(trend, change) {
    switch (trend) {
      case '上升':
        return 'AI表现正在改善，继续保持当前策略';
      case '下降':
        return 'AI表现有所下降，建议检查策略是否需要调整';
      case '稳定':
        return 'AI表现稳定，可以尝试优化策略以提升胜率';
      default:
        return '需要更多数据来分析趋势';
    }
  }

  /**
   * 生成优化建议
   */
  generateRecommendations(overallStats, playerStats) {
    const recommendations = [];

    // 基于总体胜率的建议
    if (overallStats.landlordWinRate < '40%') {
      recommendations.push({
        type: '策略优化',
        suggestion: '地主胜率偏低，建议优化地主策略',
        priority: 'high'
      });
    }

    if (overallStats.farmerWinRate < '50%') {
      recommendations.push({
        type: '策略优化',
        suggestion: '农民胜率偏低，建议优化农民协作策略',
        priority: 'high'
      });
    }

    // 基于平均步数的建议
    if (parseFloat(overallStats.averageMoves) > 50) {
      recommendations.push({
        type: '效率提升',
        suggestion: '游戏步数较多，建议优化出牌效率',
        priority: 'medium'
      });
    }

    // 基于玩家表现的建议
    playerStats.forEach(stats => {
      if (stats.totalGames >= 10) {
        if (parseFloat(stats.landlordWinRate) < '30%') {
          recommendations.push({
            type: '角色优化',
            suggestion: `玩家${stats.playerId}地主胜率偏低，建议针对地主角色进行优化`,
            priority: 'medium'
          });
        }
      }
    });

    return recommendations;
  }

  /**
   * 导出数据为JSON
   */
  exportToJSON() {
    return JSON.stringify({
      exportTime: new Date().toISOString(),
      totalGames: this.games.length,
      totalSessions: this.sessions.length,
      games: this.games,
      sessions: this.sessions.map(s => ({
        id: s.id,
        name: s.name,
        startTime: s.startTime,
        gameCount: s.games.length
      }))
    }, null, 2);
  }

  /**
   * 导出数据为CSV
   */
  exportToCSV() {
    const headers = [
      '游戏ID', '时间戳', '赢家', '地主ID', '步数', '时长(ms)', '赢家类型'
    ];

    const rows = this.games.map(g => [
      g.id,
      new Date(g.timestamp).toISOString(),
      g.winner,
      g.landlordId,
      g.moveCount,
      g.duration,
      g.winnerType
    ]);

    return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  }

  /**
   * 重置统计
   */
  reset() {
    this.games = [];
    this.sessions = [];
    this.currentSession = null;
  }

  /**
   * 获取简要统计
   */
  getSummary() {
    const stats = this.calculateOverallStats();
    return {
      总场次: stats.totalGames,
      地主胜率: stats.landlordWinRate,
      农民胜率: stats.farmerWinRate,
      平均步数: stats.averageMoves,
      平均时长: stats.averageDuration
    };
  }
}

// 导出统计器
if (typeof module !== 'undefined' && module.exports) {
  module.exports = WinRateCalculator;
}

// 浏览器环境下的全局对象
if (typeof window !== 'undefined') {
  window.WinRateCalculator = WinRateCalculator;
}