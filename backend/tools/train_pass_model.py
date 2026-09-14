# -*- coding: utf-8 -*-
"""
TASK-011：PASS 决策胜率监督模型 —— 离线训练脚本（试点：仅 PASS 一个切入点）

定位：ai_kb 同款隔离思路 —— 不在 Flask 进程内训练，本脚本离线跑，
  训练过程只读 ai_learning 表，禁止任何写操作；产出 LogisticRegression
  系数导出为纯 JSON（backend/ai/model_pass/pass_model.json），
  推理侧（learning.py）纯 Python 点分 + sigmoid，禁止 import sklearn。

数据口径（关键坑，用户 20260914 拍板）：
  - ai_learning 表的 game_id 列全 NULL，判 sim/real 必须看 round_id 前缀：
      sim_   前缀 = 自我对弈（本地库约 7.2 万条 PASS 有效行）
      1788   前缀 = 真人局（本地库仅约 784 条 PASS 有效行）
    其余前缀（test-、test_、final、vp、vm 等）一律显式排除。
  - 训练数据源由 backend/ai/config.json 的 model_pass.source 决定：
      "sim"（本地默认）/ "real"（线上默认），禁止 both 混训。
  - 真人局样本极少（<2000 条即拒训），线上需攒够真人数据再训练启用。

标签口径：沿用整局胜负（result IN (win,lose)，用户拍板不动写入口径）。

切分：按 round（局）为单位、按局首条记录时间排序，后 15% 的局留作测试集，
  禁止随机切分防同局泄漏（同局多行标签相同，随机切必然虚高）。

用法:
  python tools/train_pass_model.py            # 按 config 的 source 训练
  python tools/train_pass_model.py --source real   # 临时切换数据源试跑
"""
import json
import os
import sqlite3
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.abspath(os.path.join(_HERE, '..'))
_DB_PATH = os.path.join(_BACKEND, 'database', 'doudizhu.db')
_CONFIG_PATH = os.path.join(_BACKEND, 'ai', 'config.json')
_MODEL_DIR = os.path.join(_BACKEND, 'ai', 'model_pass')
_MODEL_PATH = os.path.join(_MODEL_DIR, 'pass_model.json')

# 真人局最低样本量门槛：低于此值拒训（线上需攒数据）
REAL_MIN_SAMPLES = 2000
# 测试集比例：按局数后 15%
TEST_RATIO = 0.15

FEATURE_ORDER = [
    'is_beat',           # 1 = beat 对照行（实际选择了压牌），0 = pass 行（实际选择了让牌）
    'role_farmerPrev',   # 让牌/压牌者是地主上家（门板）
    'role_farmerNext',   # 让牌/压牌者是地主下家
    'role_landlord',     # 让牌者是地主（beat 桶无地主行，仅 pass 桶有）
    'band_lt3',          # 地主剩牌 <=3（冲刺档）
    'band_lt8',          # 地主剩牌 4~8（中盘档）
    'band_gt8',          # 地主剩牌 >8（前期档）
    'hand_norm',         # 决策者自身手牌张数 / 20（连续特征）
    'hand_le4',          # 决策者自身手牌 <=4（濒临出完档）
]


def load_config_source(override=None):
    src = override
    if not src:
        try:
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                src = json.load(f).get('model_pass', {}).get('source', 'sim')
        except Exception:
            src = 'sim'
    if src not in ('sim', 'real'):
        print(f'[拒训] model_pass.source 配置非法: {src!r}（只允许 sim/real，禁止混训）')
        sys.exit(1)
    return src


def fetch_rows(source):
    """只读查询 ai_learning 表。按 round_id 前缀隔离数据源，显式排除其余前缀。"""
    if source == 'sim':
        cond = "round_id LIKE 'sim_%'"
    else:
        cond = "round_id LIKE '1788%'"
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT round_id, step_number, hand_state, action_taken, bucket, result, created_at "
        "FROM ai_learning "
        "WHERE action_type = 'PASS' AND result IN ('win','lose') AND " + cond
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def row_feature(row):
    """单行 -> (特征向量, 标签)。解析不了的字段宁缺毋滥（缺字段该行跳过）。"""
    try:
        hs = json.loads(row['hand_state'] or '{}')
        action = json.loads(row['action_taken'] or '[]')
    except Exception:
        return None
    role = hs.get('role', '')
    hand_count = hs.get('hand_count')
    if role not in ('landlord', 'farmerPrev', 'farmerNext') or hand_count is None:
        return None
    band = 'lt3' if (row['bucket'] or '').endswith(':lt3') else \
           ('lt8' if (row['bucket'] or '').endswith(':lt8') else
            ('gt8' if (row['bucket'] or '').endswith(':gt8') else None))
    if band is None:
        return None
    is_beat = 1 if (row['bucket'] or '').startswith('beat:') else 0
    # beat 行 action_taken 是所出的牌；pass 行恒为空列表。字段仅做存在性自检，
    # 不进特征（pass 行无牌信息，进了会导致两个反事实不可比）。
    if is_beat and not isinstance(action, list):
        return None
    return {
        'is_beat': is_beat,
        'role_farmerPrev': 1 if role == 'farmerPrev' else 0,
        'role_farmerNext': 1 if role == 'farmerNext' else 0,
        'role_landlord': 1 if role == 'landlord' else 0,
        'band_lt3': 1 if band == 'lt3' else 0,
        'band_lt8': 1 if band == 'lt8' else 0,
        'band_gt8': 1 if band == 'gt8' else 0,
        'hand_norm': hand_count / 20.0,
        'hand_le4': 1 if hand_count <= 4 else 0,
    }, (1 if row['result'] == 'win' else 0)


def split_by_round(samples):
    """按局切分：局按该局首条记录时间排序，后 15% 局为测试集。
    samples 元素为 {'round_id','created_at','feat','label'}。"""
    rounds = {}
    for s in samples:
        rounds.setdefault(s['round_id'], []).append(s)
    round_ids = sorted(rounds.keys(), key=lambda rid: min(x['created_at'] or '' for x in rounds[rid]))
    n_test = max(1, int(len(round_ids) * TEST_RATIO))
    test_ids = set(round_ids[-n_test:])
    train, test = [], []
    for rid in round_ids:
        (test if rid in test_ids else train).extend(rounds[rid])
    return train, test, len(round_ids), round_ids[-n_test] if n_test else ''


def to_matrix(group):
    import numpy as np
    X = np.array([[s['feat'][k] for k in FEATURE_ORDER] for s in group], dtype=float)
    y = np.array([s['label'] for s in group], dtype=int)
    return X, y


def sigmoid(z):
    return 1.0 / (1.0 + pow(2.718281828459045, -z))


def main():
    override = None
    for i, a in enumerate(sys.argv[1:]):
        if a == '--source' and i + 2 <= len(sys.argv) - 1:
            override = sys.argv[i + 2]
    source = load_config_source(override)
    print(f'[1/5] 数据源 source={source}（sim_=自对弈 / 1788=真人局，其余前缀显式排除）')
    rows = fetch_rows(source)
    print(f'[2/5] 取到 PASS 有效行 {len(rows)} 条')
    if source == 'real' and len(rows) < REAL_MIN_SAMPLES:
        print(f'[拒训] 真人局样本不足：仅 {len(rows)} 条 < 门槛 {REAL_MIN_SAMPLES} 条。'
              f'线上需攒够真人数据再训练启用，本次不产出模型文件，退出码 2。')
        sys.exit(2)

    parsed = []
    for r in rows:
        s = row_feature(r)
        if s is not None:
            parsed.append({'round_id': r['round_id'], 'created_at': r['created_at'],
                           'feat': s[0], 'label': s[1]})
    print(f'[3/5] 特征解析成功 {len(parsed)} 行（解析失败跳过 {len(rows) - len(parsed)} 行）')
    train, test, n_rounds, split_rid = split_by_round(parsed)
    print(f'    共 {n_rounds} 局，按局首时间排序后切分：训练 {len(train)} 行 / 测试 {len(test)} 行，'
          f'测试集起始局 {split_rid}')

    Xtr, ytr = to_matrix(train)
    Xte, yte = to_matrix(test)
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    clf = LogisticRegression(max_iter=1000)
    clf.fit(Xtr, ytr)

    p_te = clf.predict_proba(Xte)[:, 1]
    auc = roc_auc_score(yte, p_te)
    acc = ((p_te >= 0.5).astype(int) == yte).mean()
    majority = max(yte.mean(), 1 - yte.mean())
    print(f'[4/5] 测试集：AUC={auc:.4f}  准确率={acc:.4f}  多数类基准={majority:.4f}  '
          f'增益={+(acc - majority) * 100:.2f}pp')

    # 校准：预测概率 10 桶
    print('    校准表（预测概率桶 -> 预测均值 / 实际均值 / 条数）：')
    calib = []
    for b in range(10):
        lo, hi = b / 10, (b + 1) / 10
        m = (p_te >= lo) & (p_te < hi if b < 9 else p_te <= hi)
        if m.sum() == 0:
            calib.append({'lo': lo, 'hi': hi, 'n': 0, 'pred': None, 'actual': None})
            continue
        pred, act = float(p_te[m].mean()), float(yte[m].mean())
        calib.append({'lo': round(lo, 1), 'hi': round(hi, 1), 'n': int(m.sum()),
                      'pred': round(pred, 4), 'actual': round(act, 4)})
        gap = abs(pred - act)
        flag = 'OK' if gap <= 0.08 else '超差'
        print(f'      [{lo:.1f},{hi:.1f}) n={int(m.sum()):5d}  pred={pred:.3f}  actual={act:.3f}  gap={gap:.3f} {flag}')

    coefs = [round(float(v), 6) for v in clf.coef_[0]]
    intercept = round(float(clf.intercept_[0]), 6)
    print(f'[5/5] 特征系数（顺序={FEATURE_ORDER}）：')
    for k, v in zip(FEATURE_ORDER, coefs):
        print(f'      {k:18s} {v:+.4f}')
    print(f'      intercept         {intercept:+.4f}')

    model = {
        'version': 'TASK-011-pass-v1',
        'trained_at': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': source,
        'feature_order': FEATURE_ORDER,
        'coef': coefs,
        'intercept': intercept,
        'meta': {
            'n_rows': len(parsed), 'n_train': len(train), 'n_test': len(test),
            'n_rounds': n_rounds, 'test_start_round': split_rid,
            'auc': round(float(auc), 4), 'acc': round(float(acc), 4),
            'majority_acc': round(float(majority), 4),
            'calibration': calib,
        },
    }
    os.makedirs(_MODEL_DIR, exist_ok=True)
    with open(_MODEL_PATH, 'w', encoding='utf-8') as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
    print(f'模型系数已导出: {_MODEL_PATH}')


if __name__ == '__main__':
    main()
