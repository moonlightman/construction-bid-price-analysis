"""导入已复核的结构化底稿；逐条保存、回执落盘、重跑按库内记录去重。"""
import argparse
import hashlib
import json
from pathlib import Path
from history_store import put, configured_db, dump


def save_receipt(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(dump(value)+'\n',encoding='utf-8')
    tmp.replace(path)


def import_records(db, batch, receipt_path):
    if not isinstance(batch.get('batch_id'),str) or not batch['batch_id'].strip():
        raise ValueError('需稳定 batch_id，重试沿用原批次编号')
    records=batch.get('records')
    if not isinstance(records,list):raise ValueError('records 必须为数组')
    expected=batch.get('expected_revisions',{})
    if not isinstance(expected,dict):raise ValueError('expected_revisions 必须为对象')
    ids=[r.get('record_id') for r in records if isinstance(r,dict)]
    if any(x is not None and ids.count(x)>1 for x in ids):
        raise ValueError('批次内 record_id 重复，先核对清单映射')
    result={'schema':'inquiry-history-receipt/v2','batch_id':batch['batch_id'],
            'input_sha256':hashlib.sha256(dump(batch).encode()).hexdigest(),
            'status':'running','total':len(records),'processed':0,'items':[],
            'cloud_status':'not_synced'}
    save_receipt(receipt_path,result)
    for index,record in enumerate(records):
        item={'index':index,'input_record_id':record.get('record_id') if isinstance(record,dict) else None,
              'source':record.get('source') if isinstance(record,dict) else None}
        try:
            if not isinstance(record,dict):raise ValueError('记录必须为对象')
            item.update(put(db,record,expected.get(record.get('record_id'))))
            item['review_status']=record['status']
        except (ValueError,TypeError) as error:
            item.update(status='failed',error=str(error))
        result['items'].append(item);result['processed']+=1
        save_receipt(receipt_path,result)
    counts={name:sum(x['status']==name for x in result['items'])
            for name in ('saved_local','unchanged','duplicate_source','failed')}
    result.update(status='partial' if counts['failed'] else 'complete',counts=counts,
                  pending_review=sum(x.get('review_status')=='pending' for x in result['items']))
    save_receipt(receipt_path,result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',default=str(Path(__file__).resolve().parents[1]/'config/storage.json'))
    p.add_argument('--db');p.add_argument('--input',required=True);p.add_argument('--receipt')
    a=p.parse_args();db=a.db or configured_db(a.config)
    batch=json.loads(Path(a.input).read_text(encoding='utf-8-sig'))
    receipt=a.receipt or str(Path(db).parent/'imports'/
                (hashlib.sha256(str(batch.get('batch_id','')).encode()).hexdigest()[:24]+'.json'))
    result=import_records(db,batch,receipt)
    print(dump({'status':result['status'],'counts':result['counts'],
                'pending_review':result['pending_review'],'receipt':str(Path(receipt).resolve())}))
    if result['counts']['failed']:raise SystemExit(2)


if __name__=='__main__':main()
