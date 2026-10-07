"""将回标 v5 底稿转换为待复核报价记录；不推断最终谈判价。"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path


# 优先级由调用处给出；明确填写 null 表示未知，不能用上层默认值覆盖。
ALIASES = {'scope': ('scope_note',), 'tax_basis': ('tax_mode',)}
CONTEXT_FIELDS = (
    'scope', 'pricing_date', 'valid_from', 'valid_to', 'region', 'plant',
    'currency', 'tax_basis', 'tax_rate', 'freight_basis', 'installation_basis',
    'discount_basis', 'payment_terms', 'price_basis', 'report_url',
)
LINE_FIELDS = (
    'unit_price', 'line_total', 'material_unit_price', 'material_line_total',
    'installation_unit_price', 'installation_line_total', 'additivity_confirmed',
)


def inherit(field, *layers):
    for layer in layers:
        for key in (field, *ALIASES.get(field, ())):
            if key in layer:
                return deepcopy(layer[key])
    return None


def identifier(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('需稳定且非空的 ' + label)
    if value != value.strip():
        raise ValueError(label + ' 首尾不能有空格，请先核对标识')
    return value


def record_id(project_id, bidder_id, round_id, item_key, is_total=False):
    # 沿用已有 v2 记录的散列方式，避免同一底稿升级后重复入库。
    key = [project_id, bidder_id, round_id, item_key, 'quote']
    encoded = json.dumps(key, ensure_ascii=is_total).encode()
    return hashlib.sha256(encoded).hexdigest()[:24]


def check_round(layer, round_id):
    if 'round_id' in layer and layer['round_id'] != round_id:
        raise ValueError('底稿包含不一致或未知 round_id，请分轮次转换')


def convert(data, project_id, round_id=None):
    project_id = identifier(project_id, 'project_id')
    project = data.get('project', {})
    if 'project_id' in project and project['project_id'] != project_id:
        raise ValueError('传入 project_id 与底稿不一致')
    if round_id is None:
        round_id = project.get('round_id')
    round_id = identifier(round_id, 'round_id')
    check_round(project, round_id)

    bidders = {}
    for bidder in data.get('bidders', []):
        bidder_id = identifier(bidder.get('bidder_id'), 'bidder_id')
        if bidder_id in bidders:
            raise ValueError('重复 bidder_id，先核对投标人')
        check_round(bidder, round_id)
        bidders[bidder_id] = bidder

    out = []
    for item in data.get('items', []):
        item_key = identifier(item.get('item_key'), 'item_key')
        check_round(item, round_id)
        for bid in item.get('bids', []):
            if bid.get('review_status') == 'excluded':
                continue
            bidder_id = identifier(bid.get('bidder_id'), 'bidder_id')
            if bidder_id not in bidders:
                raise ValueError('报价关联的 bidder_id 不在投标人表中: ' + bidder_id)
            check_round(bid, round_id)
            bidder = bidders[bidder_id]
            record = {
                'record_id': record_id(project_id, bidder_id, round_id, item_key),
                'kind': 'price', 'status': 'pending', 'project_id': project_id,
                'project_name': project.get('name'), 'bidder_id': bidder_id,
                'supplier': bidder.get('name'), 'round_id': round_id,
                'item_key': item_key, 'name': inherit('name', bid, item),
                'spec': inherit('spec', bid, item), 'unit': inherit('unit', bid, item),
                'level': 'item', 'price_type': 'quote',
                # 投标人 source 定位的是汇总总价，不能冒充某一分项的来源。
                'source': deepcopy(bid['source']) if 'source' in bid else {},
                'quantity': bid.get('quoted_quantity'),
            }
            if 'name' not in bid and 'name' not in item:
                record['name'] = item_key
            record.update({field: inherit(field, bid, item, bidder, project)
                           for field in CONTEXT_FIELDS})
            record.update({field: deepcopy(bid.get(field)) for field in LINE_FIELDS})
            for field in ('review_status', 'comparable', 'reason'):
                if field in bid:
                    record[field] = deepcopy(bid[field])
            if 'mapping_confirmed' in item:
                record['mapping_confirmed'] = item['mapping_confirmed']
            out.append(record)

    for bidder_id, bidder in bidders.items():
        if bidder.get('stated_total') is None:
            continue
        record = {
            'record_id': record_id(project_id, bidder_id, round_id, 'total', True),
            'kind': 'price', 'status': 'pending', 'project_id': project_id,
            'project_name': project.get('name'), 'bidder_id': bidder_id,
            'supplier': bidder.get('name'), 'round_id': round_id,
            'name': '报价总价', 'level': 'total', 'price_type': 'quote',
            'total_price': bidder['stated_total'],
            'source': deepcopy(bidder['source']) if 'source' in bidder else {},
        }
        record.update({field: inherit(field, bidder, project) for field in CONTEXT_FIELDS})
        for field in ('stated_total_review_status', 'coverage_confirmed',
                      'total_comparable', 'total_adjustments', 'reason'):
            if field in bidder:
                record[field] = deepcopy(bidder[field])
        out.append(record)

    ids = [record['record_id'] for record in out]
    if len(ids) != len(set(ids)):
        raise ValueError('重复映射，先核对投标人/轮次/项目键；分项键不得与总价键 total 重合')
    return {'schema': 'inquiry-history-import/v2', 'status': 'pending_review', 'records': out}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--round-id', help='底稿尚未登记轮次时，显式提供本次稳定轮次编号')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = convert(json.loads(Path(args.input).read_text(encoding='utf-8-sig')),
                     args.project_id, args.round_id)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
