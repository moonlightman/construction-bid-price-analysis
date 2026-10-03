#!/usr/bin/env python3
"""对独立提取、已配对的 Excel/PDF 字段做差异检查，不自动确认版本或选择优先文件。"""
import argparse
import json
import math
from pathlib import Path
from analyze_bids import located


def compare(data):
    tolerance=data.get('numeric_tolerance',0)
    if isinstance(tolerance,bool) or not isinstance(tolerance,(int,float)) or not math.isfinite(tolerance) or tolerance<0:
        raise ValueError('numeric_tolerance 必须为有限非负数')
    if tolerance and not data.get('tolerance_reason'):
        raise ValueError('非零跨格式容差必须说明理由')
    results=[]
    seen=set()
    for pair in data.get('pairs',[]):
        key=pair.get('pair_id')
        if not isinstance(key,str) or not key or key in seen:
            raise ValueError('pair_id 必须非空且唯一')
        seen.add(key)
        left,right=pair.get('excel',{}),pair.get('pdf',{})
        fields=pair.get('fields',[])
        differences=[]
        valid=pair.get('same_version_confirmed') is True
        valid &= located(left.get('source')) and located(right.get('source'))
        valid &= left.get('review_status')=='confirmed' and right.get('review_status')=='confirmed'
        if not fields or len(set(fields))!=len(fields):
            raise ValueError('每组需提供非空且不重复的核对字段')
        for field in fields:
            a,b=left.get('values',{}).get(field),right.get('values',{}).get(field)
            status='一致'
            if a is None or b is None:
                status='缺失，未完成核对'
            elif isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
                if not math.isfinite(a) or not math.isfinite(b):
                    raise ValueError('比较值不得为 NaN 或无穷大')
                status='一致' if abs(a-b)<=tolerance else '差异'
            elif type(a)!=type(b) or a!=b:
                status='差异'
            if status!='一致':
                differences.append(dict(field=field,excel_value=a,pdf_value=b,status=status))
        results.append(dict(pair_id=key,status=('待确认版本/来源/识别' if not valid else '有差异或缺失' if differences else '已核对字段一致'),
                            checked_fields=fields,differences=differences,
                            excel_source=left.get('source'),pdf_source=right.get('source')))
    unmatched=data.get('unmatched',[])
    full=data.get('coverage_confirmed') is True and not unmatched and bool(results)
    return dict(schema='source-reconciliation/v1',numeric_tolerance=tolerance,
                coverage_status='登记范围已完整配对' if full else '仅核对已登记字段，覆盖范围未完整确认',
                all_compared_fields_equal=bool(results) and all(r['status']=='已核对字段一致' for r in results),
                full_reconciliation_passed=full and all(r['status']=='已核对字段一致' for r in results),
                pairs=results,unmatched=unmatched,
                limitation='覆盖声明来自输入登记；脚本不读取原件、不证明未登记页面已被核对')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=compare(json.loads(args.input.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
