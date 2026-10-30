# skills

本地自建的 AI 编程工具 Skill 集合，远程仓库为 GitHub（`YEjia6/skills`）。

## 目录约定

仓库根目录下，**每个包含 `SKILL.md` 的顶层目录 = 一个 skill 包**。包的子目录（`references/`、`scripts/`、`tests/` 等）会整体同步。

- 版本号：包内 `VERSION` 文件；缺失时回退到该包的 git 提交短哈希。
- `*.zip` / `*.tar.gz` 是打包产物，被 `.gitignore` 排除，不入库。
- `GordenPPT` 是 git submodule（见 `.gitmodules`）。

## 同步到已安装工具

各 AI 编程工具读取 skills 的标准目录（`sync.py` 会自动探测哪些目录已存在）：

| 工具 | 目录 |
|---|---|
| Claude Code | `~/.claude/skills` |
| Codex | `~/.codex/skills` |
| OpenAI Agents / Gemini | `~/.agents/skills` |
| Trae | `~/.trae-cn/skills` |
| Cursor | `~/.cursor/skills` |

DSH（DeepSeek Harness）会自动聚合扫描以上目录，无需单独配置。

### 常用命令

```bash
python sync.py status                  # 查看各工具 × 各 skill 的安装状态
python sync.py install --dry-run       # 预览：只补缺失文件
python sync.py update --dry-run        # 预览：覆盖内容有变化的文件
python sync.py update                  # 实际同步（默认不覆盖未变化、不删除多余文件）
python sync.py update --tool codex,claude   # 只同步到指定工具
python sync.py update --skill portable-rules-manager   # 只同步指定 skill
python sync.py pull                    # git pull --recurse-submodules 后自动 update
python sync.py update --force --prune  # 强制覆盖 + 删除源里已不存在的文件
```

- `install`：只补缺失文件，**绝不覆盖**已安装文件。
- `update`：按字节比对，只覆盖内容有变化的文件；默认**不删除**目标目录里源中已不存在的文件（需显式 `--prune`）。
- 两者都支持 `--dry-run` 预览，只写文件不删不覆盖未变化内容。

## 自动获取最新版本

两种机制叠加，实现「真正的自动更新」：

### 1. `git pull` 后自动同步（post-merge 钩子）

```bash
python sync.py init-hooks
```

安装 `.git/hooks/post-merge`：此后每次 `git pull` 成功都会自动执行 `sync.py update`。

### 2. 系统定时自动拉取 + 同步（Windows 计划任务）

```bash
python sync.py schedule     # 注册任务 skills-autosync（登录时 + 每日 09:00）
python sync.py unschedule   # 删除任务
```

任务动作等价于：

```
git -C <仓库> pull --recurse-submodules && git -C <仓库> submodule update --init --recursive && python <仓库>/sync.py pull --scheduled
```

执行日志写入 `%TEMP%\skills-autosync.log`；拉取失败只记日志，不清空任何已安装的 skills。

## 新增一个 skill

在仓库根目录新建一个目录并放入 `SKILL.md`（可选 `VERSION`），`git push` 即可。`sync.py` 会自动发现并同步，无需改动脚本。

## 备选：junction 零拷贝模式（未实现，仅记录）

把工具目录中的 skill 条目替换为指向仓库的目录 junction（`mklink /J`），`git pull` 后各工具直接读到最新文件，无拷贝。

风险：Windows 软链（`mklink /D`）需管理员/开发者模式；junction（`/J`）虽无需管理员，但部分工具会清空/重写自身 skills 目录，可能误删 junction。故默认采用上面的拷贝同步方案，更稳健、可回滚、可逐文件 diff。

## 网络与凭据

- 仓库应为 public；若为 private，请先配置 Git 凭据管理器（`git config --global credential.helper manager`）。
- 若直连 GitHub 被重置（如公司/地区网络），可在 `git` 中配置 HTTP 代理，或将 remote 换成 Gitee 等镜像地址。
