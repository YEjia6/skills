# Portable Rules Manager — 可移植 AI 编程规则管理 Skill

用于同时包含前端、后端、移动端、HMI 等多技术域的代码仓库。采用 Agent Skills 标准的 `SKILL.md` 格式，可被支持该标准的工具发现；也可以不通过 AI，直接用 Python 命令运行规则管理器。

## 你会得到什么？

- 只读扫描：根据项目目录、常见构建标记和框架依赖给出技术域候选。
- 工具探测：`detect` 列出项目内各 AI 工具的规则入口痕迹、存放位置与加载机制。
- 规则源：创建 `.ai-rules/manifest.json` + `core/` / `domains/` Markdown 模板。
- 标准化建规则：`new-rule` 生成规则骨架并登记 manifest（自动校验 ID 唯一性、anchor 存在性、互斥组重叠，失败自动回滚）；`references/rule-authoring.md` 提供编写规范（ID 命名、layer/strength、必备章节、反模式、自检清单），覆盖编程行为规则与工程流程规范。
- 场景隔离：普通 Web UI 与图表分析 UI 按目录单独匹配；HMI 独立。
- 多平台适配：生成 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、Cursor `.mdc`、Copilot `.instructions.md`、Trae `.trae/rules/*.md`，并支持 Windsurf/Cascade 的原生 `AGENTS.md`。
- 当前工具优先：推荐 `sync --tools <当前工具>` 只生成你正在使用的工具入口，不为闲置工具产生文件。
- 回写闭环：`harvest --tools <当前工具>` 把生成文件里的手工改进回写到 `.ai-rules` 源，切换到其他工具时再生成。
- 安全同步：默认预览；拒绝覆盖手工修改；备份、文件 hash 状态、静态差异检查。
- 迁移旧规范：已有 `.ai-rules` 下 Markdown 不会被覆盖，未收录的旧规范作为 `enabled:false` 待审候选索引。

## 系统要求

Python 3.10+，仅标准库；适用于 macOS / Linux / Windows。无需联网、额外依赖或 API key。

## 安装与更新

仓库根目录就是可直接安装的 Skill 包（含 `SKILL.md`）。两种方式二选一：

**方式一：git clone 直装（更新即 `git pull`）**

```bash
git clone <仓库地址> ~/.claude/skills/portable-rules-manager
git -C ~/.claude/skills/portable-rules-manager pull    # 以后更新
```

| 工具 | 常见用户级 Skills 目录 |
| --- | --- |
| Trae | `~/.trae-cn/skills/portable-rules-manager/` |
| Claude Code | `~/.claude/skills/portable-rules-manager/` |
| Codex / Cursor / Gemini CLI | `~/.agents/skills/portable-rules-manager/`（Cursor 也可用 `~/.cursor/skills/`） |

**方式二：用 `install.py` 安装（安装目录不需要保留 git）**

```bash
python install.py status            # 列出各工具安装目录与已安装版本
python install.py install --dry-run
python install.py install            # 只补齐缺失文件，不覆盖已有安装
python install.py update --dry-run
python install.py update             # 覆盖内容有变化的文件
```

默认只处理本机已存在的工具目录，也可 `--tool trae,claude` 指定。**开发请改源仓库，不要改安装目录**，否则 `git pull` 或 `update` 会覆盖改动。

确认当前版本：

```bash
python scripts/rules_manager.py version
```

不同工具及版本的发现机制、是否支持用户级共享目录可能不同；如果 AI 未识别 Skill，可直接运行命令行脚本。Skill 本身不必复制进每个项目，用 `--project` 指向项目即可。

**注意**：安装 Skill 只提供管理工具；要让某项目规则生效，仍需在该项目运行 `init`（首次）和 `sync --apply`（后续）。

## 发布新版本（维护者）

```bash
python -m unittest discover -s tests -v    # 1. 测试通过
# 2. 同步更新 VERSION 与 CHANGELOG.md
git add -A && git commit -m "feat: ..."
git tag -a v1.1.0 -m "v1.1.0"              # 3. tag 与 VERSION 保持一致
git push origin main --tags
```

已安装的用户执行 `git pull` 或 `python install.py update` 即可升级。若另外发布到技能市场（zip 分发），包内 `VERSION` 必须与 tag 一致。

## 快速开始

把 `/path/to/portable-rules-manager` 替换为解压后的文件夹：

```bash
# 0. 探测项目内各 AI 工具的规则入口痕迹（交叉验证；当前工具身份由你确认）
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo detect

# 1. 查看项目实际模块，不写入
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo scan

# 2. 初始化 .ai-rules 和规则清单
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo init

# 3. 检查 .ai-rules/manifest.json，并手动调整各个规则 scope
# 4. 预览同步计划（只针对当前工具，示例为 trae）
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo sync --tools trae

# 5. 确认后写入（默认不会覆盖已有手写文件）
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo sync --tools trae --apply

# 6. 检查生成文件是否与规则源同步
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo check --tools trae

# 7. 验证一个图表页面将命中哪些规范
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo explain apps/web/src/features/analytics/charts.tsx
```

在当前工具里手工改进了生成文件后，回写到 `.ai-rules` 唯一来源：

```bash
# 预览哪些规则块发生漂移（ORPHAN/UNKNOWN-RULE 永不自动回写）
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo harvest --tools trae

# 确认后回写源文件并自动重渲染当前工具的生成文件（先备份）
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo harvest --tools trae --apply
```

切换到其他 AI 工具时，在该工具会话中再执行一次 `sync --tools <新工具> --apply`，即从 `.ai-rules` 生成它自己的入口。多工具指定：

```bash
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo sync --tools claude,cursor --apply
```

### 新增一条规则（规范体系落地）

```bash
# 1. 生成规则骨架并登记 manifest（anchor 必须是已存在的独立目录；校验失败自动回滚）
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo new-rule \
  --id BACKEND-CUSTOM-API --file domains/backend/custom-api.md --anchor services/api \
  --layer domain --strength must --description "自定义后端约定"

# 2. 按 references/rule-authoring.md 填写骨架正文，删除提示语
# 3. 预览并同步到当前工具，然后验收
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo sync --tools trae --apply
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/my-repo check --tools trae
```

`--disabled` 可登记为待审候选（`enabled:false`，不参与同步）。填写标准：每条 MUST 可被客观判定违反并写清因果，禁止「尽量/注意」类不可验收措辞。

如遇目标文件已存在且为手工管理，**默认不覆盖**。建议将原文件内容迁入 `.ai-rules` 进行审查；仅经人工批准才能使用 `--force` 自动备份并覆盖。

## 示例：初始化后的目录

```text
my-repo/
  .ai-rules/
    manifest.json                 # 唯一清单，务必检查并版本管理
    core/engineering.md           # 全仓库底线
    domains/web/ui-baseline.md    # 所有 Web 页面可用性规则
    domains/web/regular-ui.md     # 仅业务界面，不要求图表遵守
    domains/web/analytics.md      # 仅图表分析场景
    domains/backend/api.md
    domains/mobile/interaction.md
    domains/hmi/interaction.md
    .generated-state.json         # 已生成文件的 hash 记录
  AGENTS.md
  CLAUDE.md
  GEMINI.md
  .cursor/rules/ai-*.mdc
  .claude/rules/ai-*.md
  .trae/rules/ai-*.md
  .github/copilot-instructions.md
  .github/instructions/ai-*.instructions.md
  apps/web/AGENTS.md
  apps/web/src/features/business/AGENTS.md
  apps/web/src/features/analytics/AGENTS.md
  ...
```

只有在扫描确认相应目录存在、规则启用时，才会生成对应的局部文件。对于当前无法确定场景的普通 Web UI 规则，`init` 会先将其设为禁用，避免误套图表。

## AI 对话示例

你可以在已安装 Skill 的编程工具中说：

> 使用 portable-rules-manager 扫描当前 Git 项目，识别前端、后端、移动端、HMI 与图表分析目录；生成或审查 `.ai-rules`，先列出规则冲突和变更预览，不要自动覆盖手工规则。获得我确认后再执行 sync --apply。

## 重要边界

1. 这是 **v1 规则编译器**，主要支持目录级精确作用域。它不会把任意复杂 glob、路径排除、文件名正则完美映射到所有平台。遇到无法无歧义表达的规则时会拒绝同步。
2. 扫描的是**技术候选**，不能替代对代码和业务的理解。某个 `.qml` 文件不等于已经验证了 HMI 设备安全性。
3. `check` 验证同步，不验证 AI 是否阅读或遵守。仍需在目标工具中用反例任务检查。
4. 各平台可能同时加载多份适用指令，应尽量避免手工与生成规则重复或互相矛盾；项目级规范不能覆盖更高优先级的系统/开发者指令。
5. 如果项目把普通业务页面与图表放在同一目录，优先拆分为独立功能目录，再启用专项规则。不能简单写 `excludes` 期待所有工具生效。
6. 安全硬性要求需要 CI、Lint、测试、权限、Hooks 配合，不能只靠自然语言 Rules。

## 本地自测

```bash
cd /path/to/portable-rules-manager
python -m unittest discover -s tests -v
```

更多 schema 字段与真实平台路径参考 `references/SCHEMA_AND_COMPATIBILITY.md`；各工具的存放位置、加载机制、探测线索、已知限制与 harvest 文件归属见 `references/tool-adapters.md`；规则编写质量标准（两类规则、必备章节、反模式、自检清单）见 `references/rule-authoring.md`。
