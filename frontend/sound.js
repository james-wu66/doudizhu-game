/**
 * 斗地主音效系统
 * 统一管理所有游戏音效的播放
 */

const SoundSystem = {
    basePath: (function() {
        // 检测是否通过 HTTP 服务器访问
        if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
            return '/audio/';
        }
        // 本地直接打开时用相对路径
        return '../audio/';
    })(),
    enabled: true,
    sfxVolume: 1.0,  // 音效音量 0-1
    
    // 音频缓存
    cache: {},

    // 获取音频URL（自动检测 .ogg / .mp3）
    _getUrl(name) {
        // 优先尝试 .ogg，回退 .mp3
        return this.basePath + name + '.mp3';
    },
    
    // 预加载音频
    preload() {
        const files = [
            'voice_过', 'voice_尖', 'voice_二', 'voice_三', 'voice_四', 'voice_五',
            'voice_六', 'voice_七', 'voice_八', 'voice_九', 'voice_十',
            'voice_J', 'voice_Q', 'voice_K',
            'voice_对尖', 'voice_对二', 'voice_对三', 'voice_对四', 'voice_对五',
            'voice_对六', 'voice_对七', 'voice_对八', 'voice_对九', 'voice_对十',
            'voice_对J', 'voice_对Q', 'voice_对K',
            'voice_大王', 'voice_小王',
            'voice_顺子', 'voice_连对', 'voice_飞机',
            'voice_炸弹', 'voice_王炸', 'voice_压你',
            'voice_三带一', 'voice_三带二',
            'voice_叫地主', 'voice_抢地主', 'voice_不抢', 'voice_要不起',
            'voice_开始游戏', 'voice_你赢了', 'voice_你输了',
            'effect_失败', '炸弹_大', '补充_欢呼掌声'
        ];
        
        files.forEach(name => {
            const audio = new Audio(this._getUrl(name));
            audio.preload = 'auto';
            this.cache[name] = audio;
        });
    },
    
    // 播放音效
    play(name) {
        if (!this.enabled) return;
        try {
            let audio = this.cache[name];
            if (!audio) {
                audio = new Audio(this._getUrl(name));
                this.cache[name] = audio;
            }
            audio.volume = this.sfxVolume;
            audio.currentTime = 0;
            audio.play().catch(() => {});
        } catch(e) {}
    },
    
    // 同时播放两个音效
    playBoth(name1, name2) {
        this.play(name1);
        setTimeout(() => this.play(name2), 200);
    },
    
    // === 具体场景播放方法 ===
    
    // 游戏开始
    gameStart() {
        this.play('voice_开始游戏');
    },
    
    // 出单张
    playSingle(rank) {
        const map = {
            'A': 'voice_尖', '2': 'voice_二', '3': 'voice_三', '4': 'voice_四',
            '5': 'voice_五', '6': 'voice_六', '7': 'voice_七', '8': 'voice_八',
            '9': 'voice_九', '10': 'voice_十', 'J': 'voice_J', 'Q': 'voice_Q', 'K': 'voice_K'
        };
        this.play(map[rank] || 'voice_' + rank);
    },
    
    // 出对子
    playPair(rank) {
        const map = {
            'A': 'voice_对尖', '2': 'voice_对二', '3': 'voice_对三', '4': 'voice_对四',
            '5': 'voice_对五', '6': 'voice_对六', '7': 'voice_对七', '8': 'voice_对八',
            '9': 'voice_对九', '10': 'voice_对十', 'J': 'voice_对J', 'Q': 'voice_对Q', 'K': 'voice_对K'
        };
        this.play(map[rank] || 'voice_对' + rank);
    },
    
    // 出大王/小王
    playJoker(isBig) {
        this.play(isBig ? 'voice_大王' : 'voice_小王');
    },
    
    // 出牌型（首次出）
    playPattern(type) {
        const map = {
            'straight': 'voice_顺子',
            'pairStraight': 'voice_连对',
            'airplane': 'voice_飞机',
            'bomb': 'voice_炸弹',
            'rocket': 'voice_王炸'
        };
        if (type === 'bomb') {
            this.playBoth('voice_炸弹', '炸弹_大');
        } else if (type === 'rocket') {
            this.playBoth('voice_王炸', '炸弹_大');
        } else {
            this.play(map[type] || '');
        }
    },
    
    // 压牌（顺子压顺子、连对压连对、飞机压飞机）
    playCounter() {
        this.play('voice_压你');
    },
    
    // 过/不出
    playPass() {
        this.play('voice_过');
    },
    
    // 赢了
    playWin() {
        this.play('voice_你赢了');
    },
    
    // 输了
    playLose() {
        this.playBoth('voice_你输了', 'effect_失败');
    },
    
    // 开关音效
    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
};

// 页面加载后预加载音效
document.addEventListener('DOMContentLoaded', () => {
    SoundSystem.preload();
});
