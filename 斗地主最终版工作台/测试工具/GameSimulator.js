// ⚠️ 已过时（2026-09-01 标注）：独立 JS 玩具，重写了套牌逻辑，与真实后端引擎脱钩，结果不可用于判断真实游戏。
/**
 * 牌局模拟器
 * 用于生成测试牌局和模拟游戏过程
 */

class GameSimulator {
  constructor() {
    // 扑克牌定义
    this.suits = ['♠', '♥', '♦', '♣'];
    this.ranks = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2'];
    this.jokers = ['小王', '大王'];
    
    // 牌力值映射
    this.cardValues = {
      '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
      'J': 11, 'Q': 12, 'K': 13, 'A': 14, '2': 15, '小王': 16, '大王': 17
    };
  }

  /**
   * 生成完整的扑克牌组（54张）
   */
  generateFullDeck() {
    const deck = [];
    
    // 生成普通牌
    for (const suit of this.suits) {
      for (const rank of this.ranks) {
        deck.push(`${suit}${rank}`);
      }
    }
    
    // 添加大小王
    deck.push(...this.jokers);
    
    return deck;
  }

  /**
   * 洗牌（Fisher-Yates算法）
   */
  shuffleDeck(deck) {
    const shuffled = [...deck];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
  }

  /**
   * 发牌（斗地主：17+17+17+3底牌）
   */
  dealCards(deck) {
    const shuffled = this.shuffleDeck(deck);
    
    return {
      player1: shuffled.slice(0, 17),
      player2: shuffled.slice(17, 34),
      player3: shuffled.slice(34, 51),
      landlordCards: shuffled.slice(51, 54)
    };
  }

  /**
   * 生成随机牌局
   */
  generateRandomGame() {
    const deck = this.generateFullDeck();
    const cards = this.dealCards(deck);
    
    return {
      players: [cards.player1, cards.player2, cards.player3],
      landlordCards: cards.landlordCards,
      landlordId: Math.floor(Math.random() * 3), // 随机选择地主
      timestamp: Date.now()
    };
  }

  /**
   * 从真实回放数据生成测试牌局
   */
  createFromReplay(replayData) {
    // 解析回放数据格式
    // 假设回放数据格式：{players: [[手牌], [手牌], [手牌]], landlordCards: [底牌]}
    return {
      players: replayData.players || [[], [], []],
      landlordCards: replayData.landlordCards || [],
      landlordId: replayData.landlordId || 0,
      timestamp: Date.now(),
      source: 'replay'
    };
  }

  /**
   * 计算牌力值
   */
  calculateCardValue(card) {
    // 处理大小王
    if (card === '小王') return 16;
    if (card === '大王') return 17;
    
    // 处理普通牌
    const rank = card.slice(1); // 去掉花色
    return this.cardValues[rank] || 0;
  }

  /**
   * 计算手牌总牌力
   */
  calculateHandStrength(hand) {
    let totalValue = 0;
    
    for (const card of hand) {
      totalValue += this.calculateCardValue(card);
    }
    
    // 计算平均牌力
    const avgValue = hand.length > 0 ? totalValue / hand.length : 0;
    
    // 计算大牌数量（2和王）
    const bigCards = hand.filter(card => 
      card === '2' || card === '小王' || card === '大王'
    ).length;
    
    // 计算炸弹数量
    const bombCount = this.countBombs(hand);
    
    return {
      totalValue,
      avgValue: avgValue.toFixed(2),
      bigCards,
      bombCount,
      handSize: hand.length
    };
  }

  /**
   * 计算炸弹数量
   */
  countBombs(hand) {
    const rankCount = {};
    
    // 统计每个点数的牌数
    for (const card of hand) {
      const rank = card === '小王' || card === '大王' ? card : card.slice(1);
      rankCount[rank] = (rankCount[rank] || 0) + 1;
    }
    
    // 计算炸弹（四张相同点数）
    let bombCount = 0;
    for (const rank in rankCount) {
      if (rankCount[rank] === 4) {
        bombCount++;
      }
    }
    
    // 检查火箭（大小王）
    if (hand.includes('小王') && hand.includes('大王')) {
      bombCount++;
    }
    
    return bombCount;
  }

  /**
   * 运行模拟游戏
   */
  async runSimulation(gameSetup, aiStrategy, maxMoves = 100) {
    const startTime = Date.now();
    const moves = [];
    
    // 简化的游戏模拟
    let currentPlayer = gameSetup.landlordId;
    let hands = [...gameSetup.players];
    
    // 地主拿底牌
    hands[gameSetup.landlordId] = [
      ...hands[gameSetup.landlordId],
      ...gameSetup.landlordCards
    ];
    
    // 模拟出牌过程
    for (let moveCount = 0; moveCount < maxMoves; moveCount++) {
      const currentHand = hands[currentPlayer];
      
      if (currentHand.length === 0) {
        // 当前玩家出完牌，游戏结束
        return {
          winner: currentPlayer,
          landlordId: gameSetup.landlordId,
          moves,
          duration: Date.now() - startTime,
          moveCount: moves.length
        };
      }
      
      // 使用AI策略决定出牌
      const decision = await aiStrategy.decidePlay(currentHand, {
        currentPlayer,
        landlordId: gameSetup.landlordId,
        hands: hands.map(h => h.length)
      });
      
      if (!decision || !decision.cards || decision.cards.length === 0) {
        // 跳过当前玩家（不出）
        moves.push({
          player: currentPlayer,
          action: 'pass',
          timestamp: Date.now()
        });
      } else {
        // 出牌
        moves.push({
          player: currentPlayer,
          action: 'play',
          cards: decision.cards,
          type: decision.type,
          timestamp: Date.now()
        });
        
        // 从手牌中移除出的牌
        hands[currentPlayer] = currentHand.filter(
          card => !decision.cards.includes(card)
        );
      }
      
      // 下一个玩家
      currentPlayer = (currentPlayer + 1) % 3;
    }
    
    // 达到最大步数，游戏平局
    return {
      winner: -1, // 平局
      landlordId: gameSetup.landlordId,
      moves,
      duration: Date.now() - startTime,
      moveCount: moves.length,
      draw: true
    };
  }

  /**
   * 批量模拟测试
   */
  async batchSimulation(gameCount, aiStrategy) {
    const results = [];
    
    for (let i = 0; i < gameCount; i++) {
      const gameSetup = this.generateRandomGame();
      const result = await this.runSimulation(gameSetup, aiStrategy);
      results.push(result);
    }
    
    // 统计结果
    const landlordWins = results.filter(r => r.winner === r.landlordId).length;
    const farmerWins = results.filter(r => r.winner !== -1 && r.winner !== r.landlordId).length;
    const draws = results.filter(r => r.winner === -1).length;
    
    return {
      totalGames: gameCount,
      landlordWins,
      farmerWins,
      draws,
      landlordWinRate: (landlordWins / gameCount * 100).toFixed(2) + '%',
      farmerWinRate: (farmerWins / gameCount * 100).toFixed(2) + '%',
      avgMoves: (results.reduce((sum, r) => sum + r.moveCount, 0) / gameCount).toFixed(2),
      avgDuration: (results.reduce((sum, r) => sum + r.duration, 0) / gameCount).toFixed(2) + 'ms',
      results
    };
  }
}

// 导出模拟器
if (typeof module !== 'undefined' && module.exports) {
  module.exports = GameSimulator;
}

// 浏览器环境下的全局对象
if (typeof window !== 'undefined') {
  window.GameSimulator = GameSimulator;
}