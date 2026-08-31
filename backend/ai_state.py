"""
斗地主游戏状态管理模块

替代前端 JS 中的全局 G 对象，用于后端 AI 决策。
"""

# 常量
PLAYER = 0
LEFT = 1
RIGHT = 2
PLAYER_NAMES = {0: '玩家', 1: '电脑A', 2: '电脑B'}


class GameState:
    """
    游戏状态类，管理斗地主对局的所有状态信息。
    
    所有字段都可从外部读取/设置（public）。
    """
    
    def __init__(self):
        """初始化游戏状态"""
        # 三个玩家手牌（每张牌是 {id, rank, suit}）
        self.hands = [[], [], []]
        # 当前出牌玩家（0=PLAYER, 1=LEFT, 2=RIGHT）
        self.current = PLAYER
        # 地主座位（-1=未定）
        self.landlord = -1
        # 底牌（3张）
        self.landlordCards = []
        # 上一手牌 {cards, pattern, player}，null 表示无
        self.lastPlay = None
        # 每个玩家已出的牌（用于记牌器）
        self.playedHands = [[], [], []]
        # 连续过牌次数
        self.passCount = 0
        # 对局记录
        self.gameMoves = []
        # 叫分倍率
        self.bidMult = 1
        # 炸弹倍率
        self.bombMult = 1
        # 游戏阶段
        self.phase = 'dealing'
        # 阶段子状态
        self.phaseStep = ''
        # 是否叫过分
        self.callActed = [False, False, False]
        # 是否抢过分
        self.grabActed = [False, False, False]
        # 前端选中的牌 ID（Set），保留但可能不需要在后端使用
        self.selectedIds = set()
        # 前端传入的真实张数（替代从不完整 hands 计算）
        self.landlord_count_override = -1
        self.teammate_count_override = -1
    
    @classmethod
    def from_dict(cls, d):
        """
        从 JSON 字典恢复状态（前端传来的）。
        
        Args:
            d: 字典，包含游戏状态字段
            
        Returns:
            GameState 实例
        """
        state = cls()
        # 复制基本字段
        if 'hands' in d:
            state.hands = d['hands']
        if 'current' in d:
            state.current = d['current']
        if 'landlord' in d:
            state.landlord = d['landlord']
        if 'landlordCards' in d:
            state.landlordCards = d['landlordCards']
        if 'lastPlay' in d:
            state.lastPlay = d['lastPlay']
        if 'playedHands' in d:
            state.playedHands = d['playedHands']
        if 'passCount' in d:
            state.passCount = d['passCount']
        if 'gameMoves' in d:
            state.gameMoves = d['gameMoves']
        if 'bidMult' in d:
            state.bidMult = d['bidMult']
        if 'bombMult' in d:
            state.bombMult = d['bombMult']
        if 'phase' in d:
            state.phase = d['phase']
        if 'phaseStep' in d:
            state.phaseStep = d['phaseStep']
        if 'callActed' in d:
            state.callActed = d['callActed']
        if 'grabActed' in d:
            state.grabActed = d['grabActed']
        if 'selectedIds' in d:
            # selectedIds 可能是列表或 Set
            if isinstance(d['selectedIds'], list):
                state.selectedIds = set(d['selectedIds'])
            else:
                state.selectedIds = d['selectedIds']
        return state
    
    def to_dict(self):
        """
        序列化成 JSON 字典（只含后端需要的字段，不含前端 DOM 相关的）。
        
        Returns:
            dict: 可序列化的字典
        """
        return {
            'hands': self.hands,
            'current': self.current,
            'landlord': self.landlord,
            'landlordCards': self.landlordCards,
            'lastPlay': self.lastPlay,
            'playedHands': self.playedHands,
            'passCount': self.passCount,
            'gameMoves': self.gameMoves,
            'bidMult': self.bidMult,
            'bombMult': self.bombMult,
            'phase': self.phase,
            'phaseStep': self.phaseStep,
            'callActed': self.callActed,
            'grabActed': self.grabActed,
            # selectedIds 是前端 DOM 相关的，可以不包含在后端需要的字段中
            # 如果需要，可以取消注释：
            # 'selectedIds': list(self.selectedIds),
        }
    
    def get_hand(self, who):
        """
        返回指定玩家手牌。
        
        Args:
            who: 玩家编号（PLAYER, LEFT, RIGHT）
            
        Returns:
            list: 手牌列表
        """
        if who < 0 or who > 2:
            raise ValueError(f"无效玩家编号: {who}")
        return self.hands[who]
    
    def get_landlord_hand(self):
        """
        返回地主手牌。
        
        Returns:
            list: 地主手牌列表，如果未定地主则返回空列表
        """
        if self.landlord == -1:
            return []
        return self.hands[self.landlord]
    
    def get_current_role(self):
        """
        返回当前出牌玩家角色（'landlord'/'farmerNext'/'farmerPrev'）。
        
        Returns:
            str: 角色字符串
        """
        if self.current == self.landlord:
            return 'landlord'
        # 农民角色：next 和 prev 相对于地主
        # 假设地主是 0，则 next 是 1，prev 是 2
        # 但需要根据实际座位确定
        # 这里简化处理：如果当前玩家是地主的下家，则为 farmerNext，否则为 farmerPrev
        if (self.landlord + 1) % 3 == self.current:
            return 'farmerNext'
        else:
            return 'farmerPrev'
    
    def get_role(self, who):
        """
        返回指定玩家角色。
        
        Args:
            who: 玩家编号
            
        Returns:
            str: 角色字符串
        """
        if who == self.landlord:
            return 'landlord'
        if (self.landlord + 1) % 3 == who:
            return 'farmerNext'
        else:
            return 'farmerPrev'
    
    def get_partner(self, who):
        """
        返回指定玩家的队友。
        
        Args:
            who: 玩家编号
            
        Returns:
            int: 队友编号，如果 who 是地主则返回 -1
        """
        if who == self.landlord:
            return -1  # 地主没有队友
        # 农民的队友是另一个农民
        if (self.landlord + 1) % 3 == who:
            # who 是地主的下家，队友是地主的上家
            return (self.landlord + 2) % 3
        else:
            # who 是地主的上家，队友是地主的下家
            return (self.landlord + 1) % 3
    
    def get_landlord_count(self):
        """
        返回地主剩余张数。
        优先使用前端传入的真实值（landlord_count_override），
        仅当 override 为 -1 时才从 hands 计算。
        
        Returns:
            int: 地主手牌数量，如果未定地主则返回 0
        """
        if self.landlord_count_override >= 0:
            return self.landlord_count_override
        if self.landlord == -1:
            return 0
        return len(self.hands[self.landlord])
    
    def get_threat_count(self, who):
        """
        返回威胁张数（即玩家手牌中大于当前最大牌的数量）。
        
        注意：这里简化处理，返回手牌数量。实际威胁张数需要根据当前最大牌计算。
        
        Args:
            who: 玩家编号
            
        Returns:
            int: 威胁张数
        """
        # 简化实现：返回手牌数量
        # 实际威胁张数需要根据当前最大牌和手牌计算
        return len(self.hands[who])
    
    def is_leading(self):
        """
        是否是主动出牌（lastPlay 为 null 或 passCount > 0）。
        
        Returns:
            bool: True 表示主动出牌，False 表示跟牌
        """
        return self.lastPlay is None or self.passCount > 0