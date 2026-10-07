#!/usr/bin/env python3
"""四维结构底稿：只读已复核报价；统计线索不构成价格、成本或串标认定。"""
import argparse
import hashlib
import json
import math
import statistics as st
from pathlib import Path
from analyze_bids import analyze, located, num


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def describe(values):
    if len(values) < 2:
        return dict(n=len(values), median=None, mean=None, cv_population=None, mad=None)
    mean = st.mean(values)
    median = st.median(values)
    return dict(n=len(values), median=median, mean=mean,
                cv_population=st.pstdev(values)/abs(mean) if mean != 0 else None,
                mad=st.median(abs(x-median) for x in values))


def run(data):
    base = analyze(data)  # 同一数据准入与算术规则，不绕过原引擎
    items = {x['item_key']: x for x in data.get('items', [])}
    rows = base['item_analysis']
    ids = [x['bidder_id'] for x in data['bidders']]
    totals = [x for x in base['bidder_summary'] if x['ranking_eligible']]
    total_stats = describe([x['stated_total'] for x in totals])
    total_result = []
    for x in base['bidder_summary']:
        ref = total_stats['median'] if x['ranking_eligible'] else None
        total_result.append({**x, 'peer_deviation': x['stated_total']/ref-1 if ref and ref > 0 else None})
    details, item_stats, grouped = [], [], {}
    for key, item in items.items():
        all_rows = [r for r in rows if r['item_key'] == key]
        eligible = [r for r in all_rows if r['eligible_for_comparison']]
        stats = describe([r['unit_price'] for r in eligible])
        positive = len(eligible) >= 2 and all(r['unit_price'] > 0 for r in eligible)
        q = num(item.get('tender_quantity'))
        weight = q * stats['median'] if positive and q is not None and q >= 0 else None
        item_stats.append(dict(item_key=key, **stats, positive_ratio_eligible=positive,
                               baseline_amount=weight,
                               included_bidder_ids=[r['bidder_id'] for r in eligible],
                               excluded_bidder_ids=[b for b in ids if b not in [r['bidder_id'] for r in eligible]],
                               reference_type='current_project_peer_median_not_market_price'))
        for r in all_rows:
            admitted = r['eligible_for_comparison'] and positive
            p, ref = r['unit_price'], stats['median']
            peers = [z['unit_price'] for z in eligible if z['bidder_id'] != r['bidder_id']]
            loo = st.median(peers) if admitted and peers else None
            d = dict(item_key=key, bidder_id=r['bidder_id'], source=r['source'],
                     eligible=r['eligible_for_comparison'], unit_price=p,
                     reference_price=ref if r['eligible_for_comparison'] else None,
                     relative_index=p/ref if admitted else None,
                     deviation=p/ref-1 if admitted else None,
                     leave_one_out_deviation=p/loo-1 if loo and loo > 0 else None,
                     impact_amount=(p-ref)*q if admitted and q is not None and q >= 0 else None,
                     quantity_basis='tender_quantity' if q is not None else 'unavailable',
                     baseline_amount=weight if admitted else None)
            details.append(d)
            grouped[(r['bidder_id'], key)] = d
    # 全体共同可比集合；金额权重来自统一数量与同行中位数，不由某家极端报价决定。
    common = [s['item_key'] for s in item_stats if len(s['included_bidder_ids']) == len(ids)
              and s['baseline_amount'] is not None]
    profiles = []
    for bidder in ids:
        selected = [grouped[(bidder, key)] for key in common]
        denominator = sum(r['baseline_amount'] for r in selected)
        positive_impact = sum(max(0, r['impact_amount']) for r in selected)
        negative_impact = sum(min(0, r['impact_amount']) for r in selected)
        profiles.append(dict(bidder_id=bidder, common_item_keys=common,
            common_item_count=len(common), total_item_count=len(items),
            common_baseline_amount=denominator,
            weighted_deviation=sum(r['impact_amount'] for r in selected)/denominator if denominator > 0 else None,
            positive_impact=positive_impact if selected else None,
            negative_impact=negative_impact if selected else None,
            gross_absolute_impact=positive_impact-negative_impact if selected else None,
            net_impact=positive_impact+negative_impact if selected else None,
            limitation='仅共同可比清单子集；正负价差不代表节省，不跨投标人累加'))
    relationships = []
    for rel in data.get('structural_analysis', {}).get('relationships', []):
        required = ('relationship_id', 'numerator_item', 'denominator_item', 'reason')
        if not all(rel.get(k) for k in required):
            raise ValueError('关联检查缺少标识、清单键或业务理由')
        a, b = rel['numerator_item'], rel['denominator_item']
        if a not in items or b not in items or a == b:
            raise ValueError('关联检查需两个存在且不同的清单键')
        enabled = rel.get('confirmed') is True and located(rel.get('source'))
        for bidder in ids:
            ra, rb = grouped.get((bidder, a)), grouped.get((bidder, b))
            ok = enabled and ra and rb and ra['relative_index'] is not None and rb['relative_index'] is not None
            relationships.append(dict(relationship_id=rel['relationship_id'], bidder_id=bidder,
                relative_index_ratio=ra['relative_index']/rb['relative_index'] if ok else None,
                source=rel.get('source'), numerator_source=ra['source'] if ra else None,
                denominator_source=rb['source'] if rb else None, reason=rel['reason'],
                status='descriptive_only' if ok else 'not_evaluable',
                limitation='相对价格指数之比；不是物理消耗比、成本比例或因果关系'))
    scenarios = []
    for sc in data.get('structural_analysis', {}).get('scenarios', []):
        key = sc.get('item_key')
        dq = num(sc.get('delta_quantity'))
        if not sc.get('scenario_id') or key not in items or dq is None:
            raise ValueError('情景需标识、有效清单键及有限增减量')
        q = num(items[key].get('tender_quantity'))
        if q is None or q < 0 or q+dq < 0:
            raise ValueError('情景缺少有效原工程量或调整后工程量为负')
        confirmed = sc.get('basis_confirmed') is True and located(sc.get('source'))
        for bidder in ids:
            r = grouped.get((bidder, key))
            ok = confirmed and r and r['relative_index'] is not None
            scenarios.append(dict(scenario_id=sc['scenario_id'], item_key=key, bidder_id=bidder,
                delta_quantity=dq, scenario_source=sc.get('source'), source=r['source'] if r else None,
                incremental_payment=r['unit_price']*dq if ok else None,
                incremental_reference_gap=(r['unit_price']-r['reference_price'])*dq if ok else None,
                status='conditional_estimate' if ok else 'not_evaluable',
                limitation='假设适用原单价的条件测算；非预计变更、实际节省或最终结算'))
    return dict(schema='price-bid-structure/v1', input_sha256=digest(data),
        total_statistics=total_stats, total_analysis=total_result,
        excluded_total_bidder_ids=[s['bidder_id'] for s in base['bidder_summary'] if not s['ranking_eligible']],
        item_statistics=item_stats, item_structure=details, bidder_profiles=profiles,
        relationships=relationships, scenarios=scenarios,
        analysis_scope='current_project_descriptive',
        limitations=['算法诊断另用 structure_algorithms.py，不在此自动拟合模型',
                    '未知值保留 null；总体CV口径，极小均值及小样本不作推断',
                    '未确认或算术异常仍留原底稿，不参与基准；不自动写库'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = run(json.loads(args.input.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
