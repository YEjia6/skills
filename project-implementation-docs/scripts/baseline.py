"""从标准输入读取分析范围内的相对文件路径，比较或保存内容基线。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="项目根目录")
    parser.add_argument("snapshot", type=Path, help="交付目录中的基线文件")
    parser.add_argument("--save", action="store_true", help="确认核对后保存基线")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    current = {}
    for line in sys.stdin:
        name = line.rstrip("\r\n")
        if not name:
            continue
        path = root / name
        if Path(name).is_absolute() or not path.resolve(strict=True).is_relative_to(root):
            parser.error(f"路径超出项目范围：{name}")
        with path.open("rb") as stream:
            current[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    if not current:
        parser.error("缺少分析文件列表")
    previous = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot.exists() else {}
    changes = {
        "新增": sorted(current.keys() - previous.keys()),
        "删除": sorted(previous.keys() - current.keys()),
        "变更": sorted(k for k in previous.keys() & current.keys() if previous[k] != current[k]),
    }
    print(json.dumps(changes, ensure_ascii=False, indent=2))
    if args.save:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.snapshot.parent,
                                         prefix=".baseline-", delete=False) as stream:
            json.dump(current, stream, ensure_ascii=False, indent=2, sort_keys=True)
        Path(stream.name).replace(args.snapshot)


if __name__ == "__main__":
    main()
