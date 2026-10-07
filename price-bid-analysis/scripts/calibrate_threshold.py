#!/usr/bin/env python3
"""贝叶斯优化一个已冻结异常分数的候选阈值；项目隔离验证，不自动改变业务规则。"""
import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def metrics(rows, threshold):
    tp = sum(r['label'] == 1 and r['score'] >= threshold for r in rows)
    fn = sum(r['label'] == 1 and r['score'] < threshold for r in rows)
    fp = sum(r['label'] == 0 and r['score'] >= threshold for r in rows)
    tn = sum(r['label'] == 0 and r['score'] < threshold for r in rows)
    return dict(tp=tp, fn=fn, fp=fp, tn=tn, recall=tp/(tp+fn) if tp+fn else None,
                precision=tp/(tp+fp) if tp+fp else None, review_fraction=(tp+fp)/len(rows))


def run(data):
    rows = data.get('samples', [])
    test = set(data.get('holdout_project_ids', []))
    if not data.get('score_definition') or data.get('score_direction') != 'higher_more_unusual':
        raise ValueError('需冻结分数定义且分数越大越异常')
    if data.get('scores_oof_confirmed') is not True or not data.get('validation_source'):
        raise ValueError('需已核对的项目外评分和验证来源；批内LOF/KDE结果不能直接作为独立验证')
    seen = set()
    for r in rows:
        sid = r.get('sample_id')
        if not sid or sid in seen:
            raise ValueError('样本ID需唯一，不能重复版本充当样本')
        seen.add(sid)
        if not r.get('project_id') or not finite(r.get('score')) or type(r.get('label')) is not int or r['label'] not in (0,1):
            raise ValueError('需项目、有限分数和0/1人工复核标签')
        if r.get('label_status') != 'confirmed' or not r.get('label_source'):
            raise ValueError('标签需确认和来源；未查出问题不等于正常标签')
        training = set(r.get('model_training_project_ids', []))
        if not training or r['project_id'] in training or training & test:
            raise ValueError('模型训练项目包含本样本或最终留出项目，或未提供训练项目清单')
        if date.fromisoformat(r['training_cutoff']) >= date.fromisoformat(r['scored_at']):
            raise ValueError('训练截止必须早于评分日期')
    train_rows = [r for r in rows if r['project_id'] not in test]
    test_rows = [r for r in rows if r['project_id'] in test]
    train_groups = sorted({r['project_id'] for r in train_rows})
    if len(train_groups) < 4 or len(test) < 2 or {r['project_id'] for r in test_rows} != test:
        raise ValueError('本工具要求至少4个校准项目、2个实际留出项目；不是统计充分性的保证')
    if any({r['label'] for r in partition} != {0,1} for partition in (train_rows,test_rows)):
        raise ValueError('校准集与留出集均需已确认正反例；不能用单一类别声称验证有效')
    baseline = data.get('baseline_threshold')
    if not finite(baseline):
        raise ValueError('需预先登记基础方法的阈值')
    weights = data.get('loss_weights', {})
    if set(weights) != {'false_negative', 'false_positive', 'review'} or any(not finite(v) or v < 0 for v in weights.values()) or not any(weights.values()):
        raise ValueError('显式填写非负且非全零的漏报、误报、复核负担权重')
    result = dict(schema='bid-threshold-calibration/v1', status='candidate_only',
        input_sha256=hashlib.sha256(json.dumps(data,sort_keys=True,allow_nan=False).encode()).hexdigest(),
        calibration_projects=train_groups, holdout_projects=sorted(test), loss_weights=weights,
        limitations=['仅优化冻结分数的阈值，不训练PCA/聚类模型，不自动采用新阈值',
                    '评分来源与标签仍须审计；脚本不能证明输入声明真实',
                    '测试集只用于最终比较；不能看结果后反复调参并继续称独立测试'])
    try:
        import skopt
        from skopt import gp_minimize
        from skopt.space import Real
    except ImportError as exc:
        return {**result, 'status':'dependency_unavailable', 'reason':str(exc)}
    lo, hi = min(r['score'] for r in train_rows), max(r['score'] for r in train_rows)
    if lo == hi:
        return {**result,'status':'not_evaluable','reason':'校准分数恒定'}
    padding = max((hi-lo)*.01, 1e-9)
    def loss(params):
        t = params[0]
        costs = []
        for group in train_groups:
            subset = [r for r in train_rows if r['project_id']==group]
            m = metrics(subset, t)
            costs.append((weights['false_negative']*m['fn']+weights['false_positive']*m['fp'])/len(subset)
                         + weights['review']*m['review_fraction'])
        return sum(costs)/len(costs)  # 项目等权，避免大项目支配目标
    fit = gp_minimize(loss, [Real(lo-padding,hi+padding)], n_calls=24,
                      n_initial_points=8, random_state=42)
    threshold = float(fit.x[0])
    result.update(runtime=dict(skopt=skopt.__version__), candidate_threshold=threshold,
        calibration_loss=float(fit.fun), baseline_calibration_loss=loss([baseline]),
        baseline_threshold=baseline,
        holdout_candidate=metrics(test_rows,threshold), holdout_baseline=metrics(test_rows,baseline),
        holdout_by_project={g:dict(candidate=metrics([r for r in test_rows if r['project_id']==g],threshold),
                                  baseline=metrics([r for r in test_rows if r['project_id']==g],baseline)) for g in sorted(test)},
        trials=[dict(threshold=float(x[0]),loss=float(y)) for x,y in zip(fit.x_iters,fit.func_vals)])
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    output = run(json.loads(args.input.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
