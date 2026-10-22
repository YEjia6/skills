"""把 portable-rules-manager 安装或更新到各 AI 编程工具的 skills 目录。

用法：
  python install.py status
  python install.py install --dry-run
  python install.py install
  python install.py update --tool trae,claude

install 只补齐缺失文件，不覆盖已有安装；update 覆盖内容有变化的文件。
两者都支持 --dry-run 预览。只使用标准库。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PACKAGE = "portable-rules-manager"
ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "__pycache__"}
SKIP_FILES = {".gitignore"}

# 各工具的 skills 根目录；同一根目录下的工具共用一份安装
SKILL_DIRS = {
    "trae": Path.home() / ".trae-cn" / "skills",
    "claude": Path.home() / ".claude" / "skills",
    "agents": Path.home() / ".agents" / "skills",
    "cursor": Path.home() / ".cursor" / "skills",
}
TOOL_ALIASES = {"codex": "agents", "gemini": "agents"}


def package_files() -> list[Path]:
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(ROOT).parts
        if set(parts) & SKIP_DIRS or path.name in SKIP_FILES:
            continue
        files.append(path)
    return files


def read_version(directory: Path) -> str | None:
    try:
        return (directory / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return None


def skill_targets(names: list[str]) -> dict[str, Path]:
    targets = {}
    for name in names:
        key = TOOL_ALIASES.get(name, name)
        if key not in SKILL_DIRS:
            raise SystemExit(f"未知工具：{name}；可选 trae,claude,codex,gemini,cursor")
        targets[name] = SKILL_DIRS[key] / PACKAGE
    return targets


def default_targets() -> dict[str, Path]:
    existing = [name for name, directory in SKILL_DIRS.items() if directory.is_dir()]
    if not existing:
        raise SystemExit("未检测到任何工具的 skills 目录；请用 --tool 明确指定")
    return skill_targets(existing)


def sync_package(target: Path, overwrite: bool, dry_run: bool) -> list[str]:
    actions = []
    for source in package_files():
        relative = source.relative_to(ROOT)
        destination = target / relative
        if destination.is_file():
            if destination.read_bytes() == source.read_bytes():
                continue
            if not overwrite:
                actions.append(f"SKIP   {relative}")
                continue
            actions.append(f"UPDATE {relative}")
        else:
            actions.append(f"CREATE {relative}")
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    return actions


def print_status() -> int:
    print(f"源版本 {read_version(ROOT) or 'unknown'}  ({ROOT})")
    for name, directory in SKILL_DIRS.items():
        target = directory / PACKAGE
        version = read_version(target)
        if version:
            state = f"已安装 {version}"
        elif target.is_dir():
            state = "目录存在但缺少 VERSION"
        else:
            state = "未安装"
        print(f"{name:<8}{target}  {state}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="安装或更新 portable-rules-manager 到各 AI 编程工具的 skills 目录")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="列出各工具安装目录与已安装版本")
    for command in ("install", "update"):
        action = sub.add_parser(command, help="补齐缺失文件" if command == "install" else "覆盖内容有变化的文件")
        action.add_argument("--tool", help="trae,claude,codex,gemini,cursor；默认自动检测已存在的工具目录")
        action.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    args = parser.parse_args()

    if args.command == "status":
        return print_status()

    names = [n.strip() for n in args.tool.split(",") if n.strip()] if args.tool else []
    targets = skill_targets(names) if names else default_targets()
    overwrite = args.command == "update"
    total = 0
    for name, target in targets.items():
        actions = sync_package(target, overwrite, args.dry_run)
        total += sum(1 for a in actions if not a.startswith("SKIP"))
        print(f"[{name}] {target}")
        if not actions:
            print("  内容已是最新，无需操作")
        for action in actions:
            print("  " + action)
    if args.dry_run:
        print(f"预览完成：{total} 个文件待写入（未实际修改）")
    else:
        print(f"完成：{total} 个文件已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
