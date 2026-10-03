#!/usr/bin/env python3
"""生成项目文件 SHA-256 清单，保留本次输入输出快照的核验依据。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="为回标分析项目目录生成文件哈希清单。")
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--project", default="")
    parser.add_argument("--tender-no", default="")
    parser.add_argument("--task-id", default="")
    args = parser.parse_args()

    root = args.project_dir.resolve()
    if not root.is_dir():
        raise SystemExit(f"项目目录不存在：{root}")
    output = (args.output or root / "05_审计记录" / "audit-manifest.json").resolve()

    files = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.resolve() == output:
            continue
        stat = path.stat()
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": stat.st_size,
                "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "sha256": sha256(path),
            }
        )

    payload = {
        "schema": "xinchen-price-bid-audit-manifest/v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "project": args.project,
        "tender_no": args.tender_no,
        "task_id": args.task_id,
        "root": root.name,
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
