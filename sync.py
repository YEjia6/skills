#!/usr/bin/env python3
"""把本地自建 skills 仓库同步到各已安装 AI 编程工具的 skills 目录。

约定：
  - 仓库根目录下，每个包含 SKILL.md 的顶层目录视为一个 skill 包
    （含 references/ scripts/ tests/ 等子目录，一并同步）。
  - 版本：优先读取包内 VERSION 文件；缺失时回退到该包的 git 提交短哈希。
  - 目标：自动探测已存在的工具 skills 目录，或用 --tool 显式指定。

用法：
  python sync.py status                         # 各工具 × 各 skill 的安装状态
  python sync.py install [--dry-run]            # 只补缺失文件，绝不覆盖
  python sync.py update  [--dry-run]            # 覆盖内容有变化的文件
  python sync.py pull    [--dry-run]            # git pull --recurse-submodules 后 update
  python sync.py init-hooks                     # 安装 .git/hooks/post-merge 钩子
  python sync.py schedule | unschedule          # 注册 / 删除 Windows 计划任务
  python sync.py update --force --prune         # 强制覆盖 + 删除源中已不存在的文件

只使用标准库。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows 控制台默认使用 GBK，强制 UTF-8 输出，避免中文乱码
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
PACKAGE_FILE = "SKILL.md"
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", ".workbuddy"}
SKIP_FILES = {".gitignore"}
LOG_FILE = Path(tempfile.gettempdir()) / "skills-autosync.log"
TASK_NAME = "skills-autosync"

# 各工具的 skills 根目录；同一个根目录下的工具共用一份安装
SKILL_DIRS = {
    "claude": Path.home() / ".claude" / "skills",
    "codex": Path.home() / ".codex" / "skills",
    "agents": Path.home() / ".agents" / "skills",   # OpenAI Agents / Gemini 风格
    "trae": Path.home() / ".trae-cn" / "skills",
    "cursor": Path.home() / ".cursor" / "skills",
}


# --------------------------------------------------------------------------
# git 辅助
# --------------------------------------------------------------------------
def git(*args: str) -> str | None:
    """运行 git，成功返回去空白后的 stdout，失败返回 None。"""
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def git_pull() -> bool:
    """拉取仓库与 submodule 的最新代码。"""
    ok = True
    for args in (
        ("pull", "--recurse-submodules"),
        ("submodule", "update", "--init", "--recursive"),
    ):
        proc = subprocess.run(["git", "-C", str(ROOT), *args])
        if proc.returncode != 0:
            ok = False
    return ok


# --------------------------------------------------------------------------
# skill 包发现与版本
# --------------------------------------------------------------------------
def discover_skills() -> list[Path]:
    skills = []
    for entry in sorted(ROOT.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if (entry / PACKAGE_FILE).is_file():
            skills.append(entry)
    return skills


def package_files(directory: Path) -> list[Path]:
    files = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(directory).parts
        if set(parts) & SKIP_DIRS or path.name in SKIP_FILES:
            continue
        files.append(path)
    return files


def read_version(directory: Path) -> str | None:
    version_file = directory / "VERSION"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip() or None
    # submodule（.git 是文件或目录）
    if (directory / ".git").exists():
        return git("-C", str(directory), "rev-parse", "--short", "HEAD")
    # 位于仓库内的普通受管目录：取最近一次改动它的提交
    try:
        rel = directory.relative_to(ROOT)
    except ValueError:
        return None
    return git("-C", str(ROOT), "log", "-1", "--format=%h", "--", str(rel))


# --------------------------------------------------------------------------
# 目标解析
# --------------------------------------------------------------------------
def tool_targets(names: list[str] | None) -> dict[str, Path]:
    if names:
        return {name: SKILL_DIRS[name] for name in names}
    # 自动探测已存在的工具目录
    return {name: directory for name, directory in SKILL_DIRS.items() if directory.is_dir()}


def sync_package(source: Path, target: Path, overwrite: bool, dry_run: bool, prune: bool) -> list[str]:
    """把单个 skill 包同步到 target。返回动作日志行。"""
    actions: list[str] = []
    seen: set[Path] = set()
    for src in package_files(source):
        relative = src.relative_to(source)
        dst = target / relative
        seen.add(relative)
        if dst.is_file():
            if dst.read_bytes() == src.read_bytes():
                continue
            if not overwrite:
                actions.append(f"SKIP   {relative}")
                continue
            actions.append(f"UPDATE {relative}")
        else:
            actions.append(f"CREATE {relative}")
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    if prune and target.is_dir():
        for existing in sorted(target.rglob("*")):
            if not existing.is_file():
                continue
            relative = existing.relative_to(target)
            if relative in seen or set(relative.parts) & SKIP_DIRS or existing.name in SKIP_FILES:
                continue
            actions.append(f"DELETE {relative}")
            if not dry_run:
                existing.unlink()
    return actions


# --------------------------------------------------------------------------
# 子命令
# --------------------------------------------------------------------------
def cmd_status(args: argparse.Namespace) -> int:
    skills = discover_skills()
    if not skills:
        print(f"仓库 {ROOT} 下未发现任何含 {PACKAGE_FILE} 的 skill 目录")
        return 1
    for name, root in tool_targets(None).items():
        print(f"[{name}] {root}")
        for skill in skills:
            target = root / skill.name
            installed = read_version(target)
            source = read_version(skill) or "unknown"
            if installed:
                state = "已安装 " + installed
            elif target.is_dir():
                state = "目录存在但缺少版本"
            else:
                state = "未安装"
            flag = "" if installed == source else "  (可更新)"
            print(f"  {skill.name:<28} 源 {source:<10} {state}{flag}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    skills = discover_skills()
    if not skills:
        print(f"仓库 {ROOT} 下未发现任何含 {PACKAGE_FILE} 的 skill 目录")
        return 1
    if args.skill:
        skills = [s for s in skills if s.name in set(args.skill)]
        if not skills:
            raise SystemExit(f"未找到 skill：{', '.join(args.skill)}")
    try:
        targets = tool_targets(args.tool)
    except KeyError as exc:
        raise SystemExit(f"未知工具：{exc.args[0]}；可选 {', '.join(SKILL_DIRS)}")

    overwrite = args.command in ("update", "pull") or args.force
    quiet = getattr(args, "quiet", False)
    total = 0
    for name, root in targets.items():
        if not quiet:
            print(f"[{name}] {root}")
        for skill in skills:
            actions = sync_package(skill, root / skill.name, overwrite, args.dry_run, args.prune)
            total += sum(1 for a in actions if not a.startswith("SKIP"))
            if not actions:
                if not quiet:
                    print(f"  {skill.name:<28} 已是最新")
                continue
            for action in actions:
                if not quiet:
                    print(f"  {skill.name:<28} {action}")
    if not quiet:
        if args.dry_run:
            print(f"预览完成：{total} 个文件待写入（未实际修改）")
        else:
            print(f"完成：{total} 个文件已写入")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    log(f"开始拉取 {ROOT}")
    if args.dry_run:
        print("（预览）将执行：git pull --recurse-submodules && git submodule update --init --recursive")
        return 0
    if not git_pull():
        message = "git pull 失败（网络/凭据问题），已中止同步，本地文件未改动"
        print(message, file=sys.stderr)
        log(message)
        return 1
    # 复用 update 逻辑
    return cmd_sync(args)


def cmd_init_hooks(args: argparse.Namespace) -> int:
    hooks_dir = ROOT / ".git" / "hooks"
    if not hooks_dir.is_dir():
        raise SystemExit(f"未找到 git 钩子目录：{hooks_dir}")
    hook = hooks_dir / "post-merge"
    content = (
        "#!/bin/sh\n"
        "# 自动把仓库最新 skills 同步到各 AI 编程工具（由 sync.py init-hooks 安装）\n"
        'python "$(git rev-parse --show-toplevel)/sync.py" update --quiet || true\n'
    )
    hook.write_text(content, encoding="utf-8")
    hook.chmod(0o755)
    print(f"已安装钩子：{hook}")
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    if args.subcommand == "unschedule":
        subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], check=False)
        print(f"已删除计划任务：{TASK_NAME}")
        return 0

    python = sys.executable
    argument = f'"{ROOT / "sync.py"}" pull --scheduled'
    script = f"""$ErrorActionPreference = "Stop"
$py = {ps_lit(python)}
$arg = {ps_lit(argument)}
$t1 = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
$t2 = New-ScheduledTaskTrigger -Daily -At "09:00"
$a = New-ScheduledTaskAction -Execute $py -Argument $arg
$p = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Limited
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "{TASK_NAME}" -Trigger $t1,$t2 -Action $a -Principal $p -Settings $s -Description "Auto-sync skills from GitHub (YEjia6/skills)" -Force | Out-Null
"""
    tmp = Path(tempfile.gettempdir()) / "skills-autosync-setup.ps1"
    tmp.write_text(script, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(tmp)],
        )
    finally:
        tmp.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise SystemExit(f"计划任务注册失败（退出码 {proc.returncode}）")
    print(f"已注册计划任务：{TASK_NAME}（登录时 + 每日 09:00）")
    print(f"  动作：{python} {argument}")
    return 0


def ps_lit(value: str) -> str:
    """把字符串转为 PowerShell 单引号字面量。"""
    return "'" + value.replace("'", "''") + "'"


def log(message: str) -> None:
    import datetime

    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {message}"
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="同步本地自建 skills 仓库到各 AI 编程工具的 skills 目录"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="列出各工具各 skill 的安装状态")

    for command in ("install", "update"):
        action = sub.add_parser(
            command,
            help="只补缺失文件（install）" if command == "install" else "覆盖内容有变化的文件（update）",
        )
        _add_sync_flags(action)

    pull = sub.add_parser("pull", help="git pull --recurse-submodules 后自动 update")
    _add_sync_flags(pull)
    pull.add_argument("--scheduled", action="store_true", help="供计划任务调用：追加日志并静默输出")

    sub.add_parser("init-hooks", help="安装 .git/hooks/post-merge 钩子")

    schedule = sub.add_parser("schedule", help="注册 Windows 计划任务")
    schedule.set_defaults(subcommand="schedule")
    unschedule = sub.add_parser("unschedule", help="删除 Windows 计划任务")
    unschedule.set_defaults(subcommand="unschedule")

    return parser


def _add_sync_flags(action: argparse.ArgumentParser) -> None:
    action.add_argument("--tool", help="逗号分隔：claude,codex,agents,trae,cursor；默认自动检测已存在的目录")
    action.add_argument("--skill", nargs="*", help="只同步指定 skill 目录名")
    action.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    action.add_argument("--force", action="store_true", help="无条件覆盖（默认仅覆盖与源不同的文件）")
    action.add_argument("--prune", action="store_true", help="删除目标目录中源里已不存在的文件")
    action.add_argument("--quiet", action="store_true", help="静默模式：不打印逐文件动作")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in ("status",):
        return cmd_status(args)
    if args.command in ("install", "update"):
        return cmd_sync(args)
    if args.command == "pull":
        if args.scheduled:
            log("计划任务触发")
        return cmd_pull(args)
    if args.command == "init-hooks":
        return cmd_init_hooks(args)
    if args.command in ("schedule", "unschedule"):
        return cmd_schedule(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
