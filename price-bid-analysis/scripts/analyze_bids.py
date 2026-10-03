#!/usr/bin/env python3
"""校验 AI 已提取并确认口径的报价底稿；不直接解析原件或替代专业判断。"""
import argparse
import json
import math
import statistics
from pathlib import Path

DEFAULTS = dict(price_deviation_pct=.15, severe_deviation_pct=.30,
                material_impact_share=.01, arithmetic_tolerance_abs=1.,
                arithmetic_tolerance_pct=.001, total_tolerance_abs=1.,
                total_tolerance_pct=.0001)


def num(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('金额、数量和阈值必须为有限数值；未知值用 null')
    return value


def tol(value, cfg, prefix='arithmetic'):
    return max(cfg[prefix + '_tolerance_abs'], abs(value) * cfg[prefix + '_tolerance_pct'])


def located(source):
    return (isinstance(source, dict) and bool(source.get('file')) and
            (bool(source.get('page')) or (bool(source.get('sheet')) and
             bool(source.get('row') or source.get('cell')))))


def analyze(data):
    cfg = DEFAULTS.copy()
    for key, value in data.get('project', {}).get('thresholds', {}).items():
        if key not in cfg or num(value) is None or value < 0:
            raise ValueError('未知或非法阈值：' + key)
        cfg[key] = value
    if cfg['severe_deviation_pct'] < cfg['price_deviation_pct']:
        raise ValueError('明显偏离阈值不能小于一般偏离阈值')
    bidders = data.get('bidders', [])
    if not bidders:
        raise ValueError('至少需要一个投标人')
    ids = [b.get('bidder_id') for b in bidders]
    if any(not isinstance(x, str) or not x.strip() for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('bidder_id 必须非空且唯一')
    flags, rows, summaries = [], [], []
    mapping = {b['bidder_id']: b for b in bidders}
    sums = {k: 0 for k in ids}
    complete = {k: True for k in ids}
    reviewed = {k: True for k in ids}
    counts = {k: 0 for k in ids}
    seen = set()

    def flag(bidder, item, issue, source=None, **extra):
        flags.append(dict(bidder_id=bidder, item_key=item, issue=issue, source=source, **extra))

    for item in data.get('items', []):
        key = item.get('item_key')
        if not isinstance(key, str) or not key.strip() or key in seen:
            raise ValueError('item_key 必须非空且唯一；不要合并重复源行')
        seen.add(key)
        tq = num(item.get('tender_quantity'))
        bid_ids = [b.get('bidder_id') for b in item.get('bids', [])]
        if len(set(bid_ids)) != len(bid_ids) or any(x not in mapping for x in bid_ids):
            raise ValueError('同一项目有重复或未知投标人：' + key)
        group = []
        for bid in item.get('bids', []):
            bidder = bid['bidder_id']
            source = bid.get('source')
            if bid.get('review_status') == 'excluded':
                continue
            counts[bidder] += 1
            confirmed = bid.get('review_status') == 'confirmed' and located(source)
            valid = confirmed
            if not confirmed:
                flag(bidder, key, '来源缺失或尚未确认', source)
            q = num(bid.get('quoted_quantity'))
            p = num(bid.get('unit_price'))
            amount = num(bid.get('line_total'))
            basis = bid.get('price_basis', 'unknown')
            fields = ['material_unit_price', 'installation_unit_price', 'material_line_total', 'installation_line_total']
            parts = {f: num(bid.get(f)) for f in fields}
            derived = False
            if basis == 'split_additive' and bid.get('additivity_confirmed') is True:
                # 两列关系已由原件确认；分别验证，再形成派生综合值。
                for stem in ('material', 'installation'):
                    up, total = parts[stem + '_unit_price'], parts[stem + '_line_total']
                    if q is not None and up is not None and total is not None:
                        if abs(q * up - total) > tol(q * up, cfg):
                            valid = False
                            flag(bidder, key, stem + ' 分项算术差异', source, difference=total-q*up)
                combined_p = sum(parts[f] for f in fields[:2]) if all(parts[f] is not None for f in fields[:2]) else None
                combined_a = sum(parts[f] for f in fields[2:]) if all(parts[f] is not None for f in fields[2:]) else None
                for original, combined, label in ((p, combined_p, '综合单价'), (amount, combined_a, '综合合价')):
                    if original is not None and combined is not None and abs(original-combined) > tol(combined, cfg):
                        valid = False
                        flag(bidder, key, label + '与材料施工之和不一致', source, difference=original-combined)
                if p is None:
                    p, derived = combined_p, True
                if amount is None:
                    amount, derived = combined_a, True
            elif basis != 'comprehensive':
                valid = False
                flag(bidder, key, '材料施工包含关系或计价口径未确认', source)
            if q is None or p is None or amount is None:
                valid = False
                flag(bidder, key, '数量、单价或独立合价不完整', source)
            else:
                expected = q * p
                if abs(amount-expected) > tol(expected, cfg):
                    valid = False
                    flag(bidder, key, '数量乘单价与合价不一致', source, difference=amount-expected)
            if tq is not None and q is not None and q != tq:
                valid = False
                flag(bidder, key, '投标量与招标量不一致', source)
            if p == 0:
                flag(bidder, key, '零单价，需核实范围', source)
            if p is not None and p < 0:
                valid = False
                flag(bidder, key, '负单价需单独确认计价性质', source)
            if amount is None:
                complete[bidder] = False
            else:
                sums[bidder] += amount
            reviewed[bidder] &= valid
            row = dict(item_key=key, bidder_id=bidder, unit_price=p, line_total=amount,
                       quoted_quantity=q, derived_combined_value=derived, source=source,
                       eligible_for_comparison=valid and bid.get('comparable') is True
                       and item.get('mapping_confirmed') is True)
            rows.append(row)
            group.append(row)
        # items 应包括已知范围的全部项目；缺列不擅自认定漏项。
        for bidder in ids:
            active = any(r['bidder_id'] == bidder for r in group)
            if not active:
                complete[bidder] = False
                flag(bidder, key, '未见对应有效报价行；核实列项及范围差异')
        eligible = [r for r in group if r['eligible_for_comparison']]
        positive = [r['unit_price'] for r in eligible if r['unit_price'] > 0]
        median = statistics.median([r['unit_price'] for r in eligible]) if len(eligible) >= 2 else None
        control = num(item.get('control_unit_price')) if item.get('control_comparable') is True and located(item.get('control_source')) else None
        for row in group:
            row.update(peer_count=len(eligible), peer_median=median,
                       peer_max_min_ratio=max(positive)/min(positive) if len(positive)==len(eligible) and len(positive)>=2 else None)
            if not row['eligible_for_comparison']:
                continue
            for name, reference in [('控制价', control), ('同行中位数', median)]:
                if reference is None or reference <= 0:
                    continue
                deviation = row['unit_price']/reference - 1
                quantity = tq if tq is not None else row['quoted_quantity']
                impact = (row['unit_price']-reference)*quantity
                total = num(mapping[row['bidder_id']].get('stated_total'))
                share = abs(impact/total) if total else None
                if abs(deviation)>=cfg['price_deviation_pct'] or (share is not None and share>=cfg['material_impact_share']):
                    flag(row['bidder_id'], key, '价格偏离或金额影响提示', row['source'],
                         reference_type=name, reference_price=reference, deviation_pct=deviation,
                         amount_impact=impact, impact_share=share,
                         quantity_basis='招标量' if tq is not None else '投标量估算',
                         limitation='仅为价格线索；不自动认定不平衡报价或低于成本')

    for bidder in bidders:
        key = bidder['bidder_id']
        stated = num(bidder.get('stated_total'))
        for adjustment in bidder.get('total_adjustments', []):
            value = num(adjustment.get('amount'))
            if value is None:
                complete[key] = False
            else:
                sums[key] += value
            if adjustment.get('review_status') != 'confirmed' or not located(adjustment.get('source')):
                reviewed[key] = False
        coverage = bidder.get('coverage_confirmed') is True and complete[key] and counts[key] > 0
        difference = sums[key]-stated if stated is not None and counts[key] else None
        reconciled = coverage and reviewed[key] and bidder.get('stated_total_review_status') == 'confirmed' and located(bidder.get('source'))
        status = '无法完整核对'
        if reconciled and difference is not None:
            status = '一致' if abs(difference)<=tol(stated, cfg, 'total') else '不一致'
        summaries.append(dict(bidder_id=key, stated_total=stated,
                              extracted_sum=sums[key] if counts[key] and complete[key] else None,
                              partial_extracted_sum=sums[key] if counts[key] else None,
                              reconciliation_difference=difference, reconciliation_status=status,
                              ranking_eligible=status=='一致' and bidder.get('total_comparable') is True))
    # 只有全体报价范围可比且核验通过，才生成统一暂排；正式评标价由评审确认。
    if len(summaries)>=2 and all(s['ranking_eligible'] for s in summaries):
        values=sorted(set(s['stated_total'] for s in summaries))
        for s in summaries:
            s['provisional_rank']=values.index(s['stated_total'])+1
    return dict(schema='price-bid-analysis/v5', thresholds_used=cfg,
                bidder_summary=summaries, item_analysis=rows, review_signals=flags,
                limitations=['脚本结果限于输入底稿；来源与可比性需回查原件',
                             '缺失、未确认或算术异常记录不进入价格基准；暂排不等于正式评标价'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    result=analyze(json.loads(args.input.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
