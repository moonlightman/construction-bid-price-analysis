"""Validate AI-reviewed construction-content evidence; never infer semantic equivalence."""
import argparse
import json
from pathlib import Path

DIMENSIONS = ('specification', 'supply', 'work_steps', 'inclusions', 'acceptance',
              'measurement', 'conditions', 'exclusions')

def located(s):
    return isinstance(s, dict) and bool(s.get('file')) and bool(s.get('page') or
        (s.get('sheet') and (s.get('row') or s.get('cell'))))

def normalized(s):
    return ''.join(s.split()) if isinstance(s, str) else ''

def review_scope(project, item, bid):
    review = bid.get('scope_review')
    required = project.get('scope_review_required') is True or 'construction_content' in item or 'construction_content' in bid or review is not None
    if not required:
        return dict(status='not_run', eligible=True, issues=['旧底稿未执行施工内容复核；兼容计算不代表已完成该检查'], differences=[])
    if not isinstance(review, dict):
        return dict(status='pending', eligible=False, issues=['缺少施工内容复核底稿'], differences=[])
    issues, differences = [], []
    reference, quoted = review.get('reference', {}), review.get('quoted', {})
    if not isinstance(reference, dict) or not isinstance(quoted, dict):
        return dict(status='pending', eligible=False, issues=['两侧内容结构不正确'], differences=[])
    if reference.get('kind') not in ('tender', 'peer'):
        issues.append('未明确招标依据或同行参照')
    for label, side in [('参照', reference), ('报价', quoted)]:
        if not normalized(side.get('text')) or not located(side.get('source')):
            issues.append(label + '原文或来源缺失')
    # Registered raw text, when supplied, must not be replaced by a different review text.
    for raw, side in [(item.get('construction_content'), reference), (bid.get('construction_content'), quoted)]:
        if raw is not None and normalized(raw) != normalized(side.get('text')):
            issues.append('复核原文与提取原文不一致')
    dims = review.get('dimensions', [])
    if not isinstance(dims, list):
        dims = []
    keys = [d.get('dimension') for d in dims if isinstance(d, dict)]
    if len(keys) != len(dims) or len(keys) != len(set(keys)) or set(keys) != set(DIMENSIONS):
        issues.append('八维检查缺失、重复或存在未知维度')
    if not any(isinstance(d, dict) and d.get('status') in ('same', 'equivalent', 'different') for d in dims):
        issues.append('没有实际可核查的比较维度')
    for d in dims:
        if not isinstance(d, dict):
            continue
        status, key = d.get('status'), d.get('dimension')
        if status not in ('same', 'equivalent', 'different', 'unknown', 'not_applicable'):
            issues.append(str(key) + '状态无效'); continue
        if not d.get('reason'):
            issues.append(str(key) + '缺少判断理由')
        if status == 'unknown':
            issues.append(str(key) + '尚未确认'); continue
        if status == 'not_applicable':
            continue
        left, right = normalized(d.get('reference_evidence')), normalized(d.get('quoted_evidence'))
        valid_evidence = bool(left and right and left in normalized(reference.get('text')) and right in normalized(quoted.get('text')))
        if not valid_evidence:
            issues.append(str(key) + '证据摘录不在两侧原文中')
        if status == 'same' and left != right:
            issues.append(str(key) + '文字不同不能标为same；需说明是否等效')
        if status == 'different' and valid_evidence:
            differences.append(d)
    if review.get('review_status') != 'confirmed' or review.get('coverage_confirmed') is not True:
        issues.append('施工内容复核或覆盖未确认')
    status = 'different' if differences else 'pending' if issues else 'equivalent'
    return dict(status=status, eligible=status == 'equivalent', issues=issues, differences=differences,
                reference_kind=reference.get('kind'), reference_source=reference.get('source'),
                quoted_source=quoted.get('source'), dimensions=dims,
                limitation='程序验证记录与证据完整性，不代替AI逐项语义复核；同行差异不等于违反招标要求')

def run(data):
    return [dict(item_key=i.get('item_key'), bidder_id=b.get('bidder_id'),
                 **review_scope(data.get('project', {}), i, b))
            for i in data.get('items', []) for b in i.get('bids', [])]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path); parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(run(json.loads(args.input.read_text(encoding='utf-8-sig'))), ensure_ascii=False, indent=2), encoding='utf-8')
