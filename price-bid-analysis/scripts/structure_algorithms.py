#!/usr/bin/env python3
"""对显式复核的同口径特征矩阵执行探索性 PCA/K-means/LOF/KDE；不自动定性或写库。"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def run(data):
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()
    result = dict(schema='bid-algorithm-diagnostics/v1', input_sha256=digest,
                  status='not_evaluable', excluded_samples=[], diagnostics={},
                  limitations=['当前批次探索性分析，不是独立测试、风险概率或正式评标结论',
                               '极端结构需回查清单、金额和来源；簇标签不代表串标',
                               '本工具不持久化模型、不自动写库或学习'])
    names = data.get('feature_names', [])
    rows = data.get('samples', [])
    if not names or any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
        raise ValueError('feature_names 必须非空且唯一')
    if data.get('sample_unit') not in ('bidder_project', 'comparable_item'):
        raise ValueError('明确 sample_unit：bidder_project 或 comparable_item')
    if not data.get('cohort_basis') or data.get('cohort_confirmed') is not True:
        raise ValueError('需要明确且已复核的 cohort_basis')
    if data.get('feature_basis_confirmed') is not True or not data.get('feature_definitions'):
        raise ValueError('需要已复核的特征定义、单位与变换说明')
    definitions = data['feature_definitions']
    if set(definitions) != set(names) or any(not isinstance(v, str) or not v.strip() for v in definitions.values()):
        raise ValueError('feature_definitions 必须逐一说明全部特征')
    seen, entities, valid = set(), set(), []
    for row in rows:
        sid = row.get('sample_id')
        if not isinstance(sid, str) or not sid or sid in seen:
            raise ValueError('sample_id 必须非空且唯一')
        seen.add(sid)
        entity = row.get('entity_key')
        if not isinstance(entity, str) or not entity or entity in entities:
            raise ValueError('entity_key 必须唯一；同一来源/业务对象的版本不能充当独立样本')
        entities.add(entity)
        values = row.get('values', [])
        if len(values) != len(names):
            raise ValueError('特征维数与字段名不一致')
        for x in values:
            if x is not None and (isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)):
                raise ValueError('特征必须是有限数值或 null')
        reason = None
        if row.get('review_status') != 'confirmed' or row.get('comparable') is not True or not row.get('source_refs') or not row.get('project_id'):
            reason = '未复核、不可比或缺少来源/项目'
        elif any(x is None for x in values):
            reason = '存在缺失特征；不自动补零或插补'
        if reason:
            result['excluded_samples'].append(dict(sample_id=sid, reason=reason))
        else:
            valid.append(row)
    result.update(sample_count=len(valid), independent_project_count=len({r['project_id'] for r in valid}),
                  included_sample_ids=[r['sample_id'] for r in valid],
                  source_refs={r['sample_id']:r['source_refs'] for r in valid},
                  feature_definitions=definitions, cohort_basis=data['cohort_basis'])
    if len(valid) < 6:
        result['reason'] = '少于6个有效对象；本工具的探索性起点未满足，并非通用统计充分性门槛'
        return result
    try:
        import numpy as np
        import sklearn
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA
        from sklearn.metrics import silhouette_score, adjusted_rand_score
        from sklearn.neighbors import LocalOutlierFactor, KernelDensity
        from sklearn.preprocessing import RobustScaler
    except ImportError as exc:
        result.update(status='dependency_unavailable', reason=str(exc))
        return result
    result['runtime'] = dict(numpy=np.__version__, sklearn=sklearn.__version__)
    x = np.asarray([r['values'] for r in valid], dtype=float)
    keep = np.ptp(x, axis=0) > 0
    result['dropped_constant_features'] = [n for n, k in zip(names, keep) if not k]
    if not keep.any():
        result['reason'] = '所有特征恒定；没有结构差异可拟合'
        return result
    retained = [n for n, k in zip(names, keep) if k]
    # 不静默裁剪极端值；RobustScaler使用中位数/IQR，保留真实异常。
    scaler = RobustScaler()
    z = scaler.fit_transform(x[:, keep])
    if not np.isfinite(z).all():
        raise ValueError('缩放后出现非有限值；检查量纲和极端输入')
    n, d = z.shape
    if d > max(1, n//3):
        result['reason'] = '维数相对对象数过高；先按业务聚合特征，不用PCA掩盖样本不足'
        return result
    result.update(status='exploratory', features_used=retained,
                  preprocessing=dict(method='RobustScaler', center=scaler.center_.tolist(), scale=scaler.scale_.tolist()),
                  original_feature_deviations=[dict(sample_id=r['sample_id'],
                    top_features=[dict(feature=retained[int(j)], scaled_deviation=float(z[i,j]))
                        for j in np.argsort(-np.abs(z[i]))[:min(5,d)]]) for i,r in enumerate(valid)])
    pca = PCA(n_components=.9, svd_solver='full').fit(z)
    transformed = pca.transform(z)
    residual = np.mean((z-pca.inverse_transform(transformed))**2, axis=1)
    result['diagnostics']['pca'] = dict(components=pca.components_.tolist(),
        explained_variance_ratio=pca.explained_variance_ratio_.tolist(),
        scores=transformed.tolist(), reconstruction_mse=residual.tolist(),
        use='解释冗余与残差；K-means/LOF继续使用原缩放特征，不丢弃低方差风险')
    unique = len(np.unique(z, axis=0))
    candidates = []
    for k in range(2, min(5, n//3, unique-1)+1):
        model = KMeans(n_clusters=k, n_init=10, random_state=42).fit(z)
        if len(set(model.labels_)) != k:
            continue
        stability = []
        for seed in (7, 19):
            other = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(z)
            stability.append(float(adjusted_rand_score(model.labels_, other)))
        candidates.append(dict(k=k, silhouette=float(silhouette_score(z, model.labels_)),
            seed_ari=stability, labels=model.labels_.tolist(), centers=model.cluster_centers_.tolist(),
            centroid_distance=np.linalg.norm(z-model.cluster_centers_[model.labels_], axis=1).tolist()))
    result['diagnostics']['kmeans'] = dict(candidates=candidates,
        selected_k=max(candidates,key=lambda c:c['silhouette'])['k'] if candidates else None,
        seed=42, n_init=10, limitation='轮廓系数仅内部探索；小簇和距离不是风险标签')
    neighbors = sorted({max(2,min(n-1,n//4)), max(2,min(n-1,n//2))})
    lof_runs = []
    for k in neighbors:
        model = LocalOutlierFactor(n_neighbors=k, contamination='auto', novelty=False).fit(z)
        lof_runs.append(dict(n_neighbors=k, scores=(-model.negative_outlier_factor_).tolist()))
    result['diagnostics']['lof'] = dict(runs=lof_runs, score_direction='higher_more_locally_unusual',
        limitation='批内检测；不采用固定异常比例，不将分数换算为风险概率')
    # KDE仅逐特征进行，留一法避免把本记录自己的核密度当作独立证据。
    kde = []
    for j, name in enumerate(retained):
        if len(np.unique(z[:,j])) < 3:
            kde.append(dict(feature=name, status='not_evaluable', reason='不同取值少于3'))
            continue
        bandwidth = max(float(np.std(z[:,j])) * n**(-.2), .05)
        variants = []
        for factor in (.5, 1., 2.):
            h = bandwidth*factor
            scores = []
            for i in range(n):
                training = np.delete(z[:,[j]], i, axis=0)
                model = KernelDensity(kernel='gaussian', bandwidth=h).fit(training)
                scores.append(float(model.score_samples(z[i:i+1,[j]])[0]))
            variants.append(dict(bandwidth=h, leave_one_out_log_density=scores))
        kde.append(dict(feature=name, status='exploratory', variants=variants))
    result['diagnostics']['kde'] = dict(features=kde,
        limitation='低密度不等于高风险；不同特征的密度不直接相加；此为批内探索，非跨项目验证')
    # 所有 numpy 浮点都已转成内置类型；最终拒绝非有限结果。
    json.dumps(result, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = run(json.loads(args.input.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
