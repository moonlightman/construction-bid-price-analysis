"""本地历史价格版本库；不执行飞书请求、不把候选自动认定为可比。"""
from contextlib import closing
import argparse
import hashlib
import json
import math
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path


def dump(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, allow_nan=False)


def validate(r):
    for k in ('record_id', 'kind', 'name', 'status'):
        if not isinstance(r.get(k),str) or not r[k].strip(): raise ValueError('缺少 '+k)
    if r['kind'] not in ('price','experience','reference'): raise ValueError('非法 kind')
    if r['status'] not in ('confirmed','pending','inactive'): raise ValueError('非法 status')
    if r.get('source') is not None and not isinstance(r['source'],dict): raise ValueError('source 必须是对象')
    for k in ('pricing_date','valid_from','valid_to'):
        if r.get(k): date.fromisoformat(r[k])
    if r.get('valid_from') and r.get('valid_to') and r['valid_from']>r['valid_to']:
        raise ValueError('有效期颠倒')
    feedback = r.get('analysis_feedback')
    if feedback is not None:
        if r['kind'] not in ('experience', 'reference') or not isinstance(feedback, dict):
            raise ValueError('算法发现/反馈只能保存为experience或reference，不能伪装价格')
        if not r.get('project_id') and r['kind'] == 'experience':
            raise ValueError('分析发现需关联项目')
        if not feedback.get('finding_id') or feedback.get('dimension') not in ('total','core_item','linkage','behavior'):
            raise ValueError('分析反馈需finding_id和合法dimension')
        outcome = feedback.get('review_outcome')
        if outcome not in ('unreviewed','confirmed_issue','cleared','unresolved'):
            raise ValueError('非法review_outcome')
        if outcome in ('confirmed_issue','cleared'):
            if not feedback.get('review_source') or not feedback.get('reviewed_at'):
                raise ValueError('复核结论需真实来源和日期')
            date.fromisoformat(feedback['reviewed_at'])
        elif r['kind'] == 'experience' and r['status'] == 'confirmed':
            raise ValueError('未复核或仍存疑的分析发现不能作为confirmed经验')
        if feedback.get('assessment_type') not in ('exploratory','validated'):
            raise ValueError('需明确探索性或已验证的assessment_type')
        if feedback['assessment_type'] == 'validated' and not feedback.get('validation_evidence'):
            raise ValueError('validated需要独立验证证据，运行成功不是验证')
    if r['kind']=='price':
        if not r.get('project_id'): raise ValueError('价格需 project_id')
        if r.get('level') not in ('item','total'): raise ValueError('需 item/total 层级')
        if r.get('price_type') not in ('quote','final_negotiated','awarded','contract','settlement','unknown'):
            raise ValueError('非法价格类型')
        for k in ('quantity','unit_price','line_total','total_price','material_unit_price','material_line_total','installation_unit_price','installation_line_total'):
            v=r.get(k)
            if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)):
                raise ValueError(k+' 必须为有限数值或 null')
            if isinstance(v,(int,float)) and v<0 and not r.get('reason'): raise ValueError('负值需 reason')
        if r['level']=='total' and r.get('unit_price') is not None: raise ValueError('总价不得伪装成分项单价')
        if r['status']=='confirmed':
            s=r.get('source') or {}
            if not isinstance(s,dict) or not any(s.get(k) for k in ('file','file_token','url')):
                raise ValueError('确认记录需来源')
            if not (s.get('page') or s.get('location') or (s.get('sheet') and (s.get('row') or s.get('cell')))):
                raise ValueError('确认记录需页或表行定位')
            amounts=('total_price',) if r['level']=='total' else ('unit_price','line_total','material_unit_price','installation_unit_price')
            if not any(r.get(k) is not None for k in amounts) or r['price_type']=='unknown':
                raise ValueError('确认记录需真实价格及明确阶段')


IDENTITY_FIELDS = ('kind','project_id','level','price_type','bidder_id','round_id','item_key')


def source_key(record):
    source=record.get('source') or {}
    row=source.get('row')
    if row is None and source.get('cell'):
        match=re.fullmatch(r'\$?[A-Za-z]+\$?(\d+)',str(source['cell']))
        if match:row=int(match.group(1))
    locator=[source.get('member'),source.get('sheet'),str(row) if row is not None else source.get('cell'),
             source.get('page'),source.get('location')]
    if not source.get('sha256') or not any(locator[1:]): return None
    return dump([record.get('kind'),source['sha256'],locator,record.get('level'),
                 record.get('price_type'),record.get('round_id'),record.get('bidder_id') or record.get('supplier')])


def check_revision(old, new):
    for key in IDENTITY_FIELDS:
        previous=old.get(key)
        if previous not in (None,'','unknown') and previous!=new.get(key):
            raise ValueError('记录身份改变：'+key+'；不同项目/轮次/阶段另建记录，录入身份错误应停用旧记录后更正')
    if not isinstance(new.get('reason'),str) or not new['reason'].strip():
        raise ValueError('修订需填写 reason')


def put(path, record, expected_revision=None):
    validate(record)
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    payload=dump(record); rev=hashlib.sha256(payload.encode()).hexdigest()
    with closing(sqlite3.connect(p)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS versions (seq INTEGER PRIMARY KEY, record_id TEXT, revision TEXT, previous_revision TEXT, payload TEXT, created_at TEXT, UNIQUE(record_id,revision))')
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT revision,payload FROM versions WHERE record_id=? ORDER BY seq DESC LIMIT 1',(record['record_id'],)).fetchone()
        if old and old[0]==rev: return {'status':'unchanged','revision_id':rev,'cloud_status':'not_synced'}
        if old and old[0]!=expected_revision: raise ValueError('版本冲突或未提供 expected_revision')
        if not old and expected_revision: raise ValueError('当前不存在该记录，不能跳过前驱版本')
        if old: check_revision(json.loads(old[1]),record)
        fingerprint=source_key(record)
        if fingerprint:
            latest=db.execute('SELECT v.record_id,v.revision,v.payload FROM versions v JOIN (SELECT record_id,MAX(seq) n FROM versions GROUP BY record_id) x ON v.seq=x.n').fetchall()
            for other_id,other_rev,other_json in latest:
                other=json.loads(other_json)
                if other_id==record['record_id'] or other.get('status')=='inactive' or source_key(other)!=fingerprint: continue
                if {k:v for k,v in other.items() if k!='record_id'}=={k:v for k,v in record.items() if k!='record_id'}:
                    return {'status':'duplicate_source','record_id':other_id,'revision_id':other_rev,'cloud_status':'not_synced'}
                raise ValueError('同一来源行已有记录 '+other_id+'；请核对后沿用其编号修订，不能再次新增')
        if old and db.execute('SELECT 1 FROM versions WHERE record_id=? AND revision=?',(record['record_id'],rev)).fetchone():
            raise ValueError('不能重放旧版本；以新修订原因生成新版本')
        db.execute('INSERT INTO versions(record_id,revision,previous_revision,payload,created_at) VALUES(?,?,?,?,?)',
                   (record['record_id'],rev,old[0] if old else None,payload,datetime.now(timezone.utc).isoformat()))
    return {'status':'saved_local','record_id':record['record_id'],'revision_id':rev,'cloud_status':'not_synced'}


def current(path):
    p=Path(path)
    if not p.is_file(): raise FileNotFoundError('已配置本地库不存在')
    db=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        rows=db.execute('SELECT v.payload,v.revision FROM versions v JOIN (SELECT record_id,MAX(seq) n FROM versions GROUP BY record_id) x ON v.seq=x.n').fetchall()
        return [{**json.loads(payload),'revision_id':revision} for payload,revision in rows]
    finally: db.close()


def query(path, request, source_root=None):
    library=request.get('library_type','history_price')
    kinds={'history_price':'price','experience':'experience','reference':'reference'}
    if library not in kinds: raise ValueError('非法 library_type')
    result={'schema':'inquiry-history-query/v2','library_type':library,'records':[], 'total_matches':0,'truncated':False,
            'limitations':['返回候选，需 AI 核对可比性；本地读取不证明飞书已同步']}
    if not path: return {**result,'status':'not_configured'}
    try: rows=[r for r in current(path) if r['kind']==kinds[library]]
    except (OSError,sqlite3.Error,ValueError): return {**result,'status':'unavailable'}
    if not rows:return {**result,'status':'empty'}
    if library=='history_price':
        if not request.get('name'): raise ValueError('价格查询需 name')
        if request.get('as_of'):date.fromisoformat(request['as_of'])
        else:result['limitations'].append('本次计价日未知，仅供候选阅读；不能据此建立有时点约束的历史基准')
    candidates=[]
    for r in rows:
        if r['status']=='inactive' or r.get('project_id')==request.get('exclude_project') and request.get('exclude_project'):continue
        if request.get('name','').casefold() not in r['name'].casefold():continue
        if library=='history_price' and r.get('level')!='item':continue
        if request.get('as_of') and r.get('pricing_date') and r['pricing_date']>request['as_of']:continue
        notes=[]
        if r['status']!='confirmed':notes.append('待复核记录')
        if library=='history_price':
            if not request.get('as_of'):notes.append('本次计价日未知，不能确认时间可比性')
            for key in ('spec','unit','scope','region','plant','currency','tax_basis','freight_basis','installation_basis','price_type','pricing_date'):
                if not r.get(key) or r.get(key)=='unknown':notes.append(key+' 未知')
                elif request.get(key) is not None and request[key]!=r[key]:notes.append(key+' 与本次条件不同')
            if r.get('valid_to') and request.get('as_of') and r['valid_to']<request['as_of']:notes.append('原合同有效期已结束，需时间调整判断')
            if r.get('unit_price') is None:notes.append('无综合单价，不可直接参与单价统计')
        resolution=resolve_source(r.get('source') or {},source_root)
        if any(v.get('status') in ('missing','root_not_configured') for v in resolution.values()):
            notes.append('本地来源未能定位，引用前须恢复原件或核对其他证据')
        candidates.append({**r,'source_resolution':resolution,'candidate_limitations':notes,'requires_comparability_review':True})
    candidates.sort(key=lambda r:(len(r['candidate_limitations']),r['record_id']))
    limit=request.get('limit',20)
    if type(limit)!=int or limit<1:raise ValueError('limit 必须为正整数')
    return {**result,'status':'available' if candidates else 'no_match','records':candidates[:limit],
            'total_matches':len(candidates),'truncated':len(candidates)>limit}


def initialize(path):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(p)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS versions (seq INTEGER PRIMARY KEY, record_id TEXT, revision TEXT, previous_revision TEXT, payload TEXT, created_at TEXT, UNIQUE(record_id,revision))')
    return {'status':'ready_local','cloud_status':'not_synced'}


def export_versions(path):
    p=Path(path)
    with closing(sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        rows=db.execute('SELECT record_id,revision,previous_revision,payload,created_at FROM versions ORDER BY seq').fetchall()
    return {'schema':'inquiry-history-migration/v2','cloud_status':'not_synced',
            'versions':[dict(record_id=a,revision_id=b,previous_revision=c,record=json.loads(d),created_at=e) for a,b,c,d,e in rows],
            'current_revisions':{r['record_id']:r['revision_id'] for r in current(path)}}


def resolve_source(source, root):
    result={}
    for key in ('file','snapshot'):
        value=source.get(key)
        if not value:continue
        if str(value).startswith(('https://','http://')):
            result[key]={'status':'remote_not_checked','url':value};continue
        path=Path(value)
        if not path.is_absolute():
            if root is None:
                result[key]={'status':'root_not_configured'};continue
            path=Path(root)/path
        path=path.resolve()
        result[key]={'status':'available' if path.is_file() else 'missing','path':str(path)}
    return result


def configured_source_root(config):
    p=Path(config).resolve()
    c=json.loads(p.read_text(encoding='utf-8-sig'))
    value=c.get('source_root')
    if not value:return None
    root=Path(value)
    return str(root if root.is_absolute() else (p.parent/root).resolve())


def configured_db(config):
    p=Path(config).resolve()
    c=json.loads(p.read_text(encoding='utf-8-sig'))
    if c.get('backend')!='local': raise ValueError('此工具仅执行 local 后端；飞书需宿主工具，不自动降级')
    if not c.get('local_db'): raise ValueError('未配置 local_db')
    target=Path(c['local_db'])
    return str(target if target.is_absolute() else (p.parent/target).resolve())


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--db');ap.add_argument('--source-root');ap.add_argument('--config',default=str(Path(__file__).resolve().parents[1]/'config/storage.json'))
    sp=ap.add_subparsers(dest='command',required=True)
    p=sp.add_parser('put');p.add_argument('--record',required=True);p.add_argument('--expected-revision')
    p=sp.add_parser('query');p.add_argument('--request',required=True)
    sp.add_parser('export');sp.add_parser('init');sp.add_parser('export-all')
    for p in sp.choices.values():p.add_argument('--output')
    a=ap.parse_args()
    if not a.db:
        a.db=configured_db(a.config)
        if a.source_root is None:a.source_root=configured_source_root(a.config)
    if a.command=='put':r=put(a.db,json.loads(Path(a.record).read_text(encoding='utf-8-sig')),a.expected_revision)
    elif a.command=='query':r=query(a.db,json.loads(Path(a.request).read_text(encoding='utf-8-sig')),a.source_root)
    elif a.command=='init':r=initialize(a.db)
    elif a.command=='export-all':r=export_versions(a.db)
    else:r={'records':current(a.db),'cloud_status':'not_synced'}
    value=dump(r)+'\n'
    if a.output:
        p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding='utf-8')
    else:print(value)


if __name__=='__main__':main()
