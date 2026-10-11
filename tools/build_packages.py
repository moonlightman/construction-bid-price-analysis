#!/usr/bin/env python3
"""生成根目录SKILL.md安装包，校验引用/配置/内容；不包含业务数据与开发测试。"""
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {'price-bid-analysis':'6.1','experience-memory':'2.1'}


def eligible(path):
    return not any(part in ('tests','__pycache__','data','.pytest_cache','.git') for part in path.parts) and path.suffix not in ('.pyc','.db','.sqlite','.sqlite3')


def main():
    configs = [json.loads((ROOT/name/'config/feishu-library.json').read_text(encoding='utf-8')) for name in VERSIONS]
    if configs[0] != configs[1]:
        raise ValueError('两个Skill的固定库配置不一致')
    manifest = dict(release_date='2026-10-11',packages=[],
        note='哈希与包结构验证不是飞书读写或真实项目算法验收')
    for name,version in VERSIONS.items():
        skill = ROOT/name
        files = sorted(p for p in skill.rglob('*') if p.is_file() and eligible(p.relative_to(skill)))
        for p in files:
            if p.suffix=='.md':
                for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
                    if '://' in link or link.startswith('#') or not link.endswith(('.md','.json','.py','.yaml','.txt')):
                        continue
                    target=(p.parent/link).resolve()
                    if not target.is_relative_to(skill.resolve()) or not target.is_file() or not eligible(target.relative_to(skill.resolve())):
                        raise ValueError(f'安装包引用缺失或越界：{p}: {link}')
        output = ROOT/f'{name}-v{version}.zip'
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
            for p in files:
                # 固定时间戳便于同内容重建复现哈希。
                info=zipfile.ZipInfo(p.relative_to(skill).as_posix(),date_time=(2026,10,8,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,p.read_bytes())
        with zipfile.ZipFile(output) as z:
            assert z.testzip() is None
            assert 'SKILL.md' in z.namelist()
            assert all(eligible(Path(n)) for n in z.namelist())
            assert all(z.read(p.relative_to(skill).as_posix())==p.read_bytes() for p in files)
        manifest['packages'].append(dict(file=output.name,version=version,files=len(files),
            sha256=hashlib.sha256(output.read_bytes()).hexdigest()))
    previous=ROOT/'release-manifest.json'
    if previous.exists():
        old=json.loads(previous.read_text(encoding='utf-8'))
        if 'source_archives' in old:manifest['source_archives']=old['source_archives']
    previous.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
