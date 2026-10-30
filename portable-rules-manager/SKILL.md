---
name: portable-rules-manager
description: 扫描多语言及混合仓库，创建或维护 .ai-rules 统一规则源，并只同步到「当前正在使用的 AI 编程工具」的原生规则入口（Codex AGENTS.md、Cursor MDC、Claude Code、Gemini CLI、Copilot、Windsurf、Trae、DeepSeek Harness）；支持作为资深软件架构师全面分析项目代码、业务逻辑、UI 组件与现有规范，自动生成一套统一 Rules 体系（业务规则/功能规范/UI 规范/开发规范，含根 AGENTS.md 规则索引与 docs/rules/ 规则文档库）；支持标准化创建新规则（编程行为规则与工程流程规范，含 new-rule 骨架生成与 rule-authoring 质量规范），以及把当前工具里的手工修改回写到 .ai-rules。用户提出迁移、初始化、整理、创建/新增/编写规则、制定规范、规范落地、生成、同步、回写或检查 AI 编程工具规则时，或要求全面分析项目并自动生成规则体系/规范文档时使用。
---

# Portable Rules Manager · 多平台规则管理器

## 何时调用

当用户需要跨 AI 编程工具复用规则、从已有项目自动整理规则体系、扫描前后端/移动端/HMI 混合仓库、**为项目创建/新增规则或落地一套规范（编程行为规则或工程流程规范）**、更新 `.ai-rules`、生成或回写当前工具的规则文件时调用。用户要求「全面分析项目并自动生成一套统一规则体系 / Rules 体系」时也调用本 Skill，走下方「规则体系生成流程」。

本 Skill 是**规则构建与管理流程**，不是直接约束所有编程行为的常驻 Rules。它不会自动在未安装或没有激活本 Skill 的工具中运行，也不会改变平台指令优先级。

**核心原则：一次只服务当前工具。** 不一次性生成全部 AI 工具的规则文件；只生成「当前会话所在工具」的入口。用户切换到别的工具时，由那个工具里的 AI 再次调用本 Skill 生成它自己的入口。

## 操作步骤

0. **确认当前工具身份（必做）**：根据你所处的运行环境自报工具名，映射为 `--tools` 参数：

   | 你的运行环境 | `--tools` 值 |
   |-------------|-------------|
   | Trae（字节 AI IDE） | `trae` |
   | Cursor | `cursor` |
   | Claude Code | `claude` |
   | Codex / OpenAI Agents | `codex` |
   | Gemini CLI | `gemini` |
   | GitHub Copilot | `copilot` |
   | Windsurf / Cascade | `windsurf` |
   | DeepSeek Harness（DSH） | `dsh` |

   无法确定时**问用户**，禁止猜测。同一项目可同时存在多个工具的配置目录，文件痕迹不能证明当前会话身份。

1. **探测与查阅（交叉验证）**：运行 `python <skill_dir>/scripts/rules_manager.py --project <repo> detect`，查看项目内各工具的痕迹文件、当前工具的规则存放位置与加载机制。detect 输出仅供验证，不做身份判定。各工具详情见 `references/tool-adapters.md`。
2. **确认项目根目录**：以 Git 仓库根目录为优先。查看已有 `AGENTS.md`、`CLAUDE.md`、`.cursor/rules`、`.trae/rules` 等入口是否为手工维护。
3. **只读扫描**：`scan`。查看 `modules`、`confidence`、`evidence`，人工确认前端、后端、移动端、HMI，尤其数据分析目录。扫描推断不是确定性识别。
4. **初始化**：用户同意建立规则体系时运行 `init`。已有 `.ai-rules` Markdown 只索引为**禁用待审**；`manifest.json` 已存在则不覆盖。
5. **编辑唯一来源**：修改 `.ai-rules/manifest.json`、`.ai-rules/**/*.md`。每条规则必须定义 `anchor` 和 `globs`，保证真正的独立目录匹配。常规 Web UI 规范只放在明确的业务页面目录；图表分析规范只放在分析目录，禁止宽泛的全 Web 应用并试图依靠 `excludes` 抵消。
6. **只读预览**：`sync --tools <当前工具>`，审查每个 `CREATE/UPDATE/UNCHANGED/CONFLICT`。未指定 `--apply` 时绝不写原生规则。
7. **同步**：预览符合预期后 `sync --tools <当前工具> --apply`。遇到现有手写规则，停止并与用户审查；仅经明确授权后才用 `--force`（自动备份，拒绝覆写符号链接）。
8. **验收**：`check --tools <当前工具>` 和 `explain <path>`，再在当前工具中开启新会话测试正反案例。`check` 只能验证文件内容同步，不能保证模型实际加载或遵守。

## 创建规则流程（新增规则 / 规范体系落地时使用）

为项目新增一条规则（编程行为规则或工程流程规范）时走本流程。**禁止直接在生成文件（`AGENTS.md`、`.trae/rules/*.md` 等）里手写新规则**——生成文件会被下次 sync 覆盖。

1. **明确因果链**：先与用户确认这条规则要解决什么问题、适用于哪个目录、违反后果是什么、有哪些例外。规则质量标准（ID 命名、layer/strength 选择、必备章节、写法要求、反模式、自检清单）见 `references/rule-authoring.md`。
2. **查重**：通读 `.ai-rules/manifest.json` 与现有规则正文，确认不与已有规则重复或冲突；**改进已有规则优先于新增**。
3. **生成骨架**：

   ```bash
   python <skill_dir>/scripts/rules_manager.py --project <repo> new-rule \
     --id BACKEND-XXX --file domains/backend/xxx.md --anchor <适用目录> \
     --layer domain --strength must --description "一句话说明"
   ```

   - `--anchor .` 仅限 core 层全仓库底线；domain 及以下必须指向真实存在的独立目录
   - `--disabled` 登记为待审候选（`enabled:false`，不参与同步）
   - 命令自动校验 ID 唯一性、anchor 存在性、互斥组目录重叠；校验失败自动回滚
4. **填写正文**：按骨架章节（适用范围 → 规则 MUST/SHOULD/MAY → 禁止事项 → 验收）填写，每条 MUST 必须可被客观判定违反，写清因果；完成后删除骨架提示语。
5. **同步验收**：`sync --tools <当前工具>` 预览 → `--apply` → `check --tools <当前工具>` PASS → `explain <示例路径>` 确认作用域符合预期。
6. **实际加载验证**：在当前工具开启新会话，用正反案例确认规则被遵守。


## 规则体系生成流程（从零自动生成一套统一 Rules 体系）

适用：项目尚无 `.ai-rules`/规则体系，或用户明确要求「全面分析项目并自动生成一套统一 Rules 体系」。本流程 = 「操作步骤」的只读取证 + 「创建规则流程」的规则落地，质量标准仍以 `references/rule-authoring.md` 为准；典型目标组合是 `sync --tools codex,trae,dsh --apply`（多工具仅限用户点名授权）。

1. **只读取证（不做任何写操作）**：通读项目代码、README/现有文档、组件库与样式常量、路由与状态流转，从四个维度提取证据，并写入每条规则的「适用范围/验收」章节：
   - 业务规则：业务流程、状态流转、排序规则、操作权限；识别点检、巡检、保养等同族模块的共性规则并归并为一条通用规则，各自差异单独成条
   - 功能规范：按模块整理功能行为、交互逻辑与验收标准
   - UI 规范：先量测组件库/样式常量（抽屉宽度、页面间距、表格/表单/按钮既有约定），写可检验的数值而非空话
   - 开发规范：分层架构、代码风格、组件复用、接口调用约定与既有开发约束
2. **证据分级与冲突检查**：每条结论标注【已确认规则】（用户/文档明确）/【代码现状】（注明出处文件）/【建议规则】；跨模块不一致处不擅自决定业务规则，列入「待确认问题」清单，并以 `new-rule --disabled` 登记为待审候选。
3. **落地**：`init`（已有体系则跳过）→ 按类别 `new-rule`（建议源文件目录：`business/`、`features/`、`ui/`、`domains/`，跨模块底线放 `core/`）→ `sync --tools <用户点名的工具清单> --apply` → `export-docs --apply` 生成 `docs/rules/` 规则文档库 → `check --tools <最后同步的工具>` 验收。
4. **统一入口与按需加载**：根 `AGENTS.md` = core 底线 + 自动生成的 rules-index 索引表（规则/层级/强度/说明/作用域/源文件）；AI 只在改动命中某条作用域时才读对应源文件或 `docs/rules/` 对应文档，避免全量常驻；Codex/DSH 还可按 `<anchor>/AGENTS.md` 就近加载；Trae 的 core 只放根 `AGENTS.md`（详见 `references/tool-adapters.md`）。
5. **持续维护**：功能增改时先 `explain <相关路径>` 找到作用域内的规则 → 改 `.ai-rules` 源文件 → `sync --apply` → `export-docs --apply` 刷新文档库 → `check` 验收；改进已有规则优先于新增。
6. **输出契约**：完成后向用户汇报：①目录结构（`.ai-rules` 树 + 各工具生成入口 + `docs/rules/` 树）②核心规则摘要（按业务/功能/UI/开发四类分列）③「待确认问题」清单（含所有 `--disabled` 待审候选与跨模块冲突）。

### 体系生成的执行原则

- 基于现有代码提取，不凭空编造；项目已有的规范文件优先复用/索引，不重复另写。
- 只生成规则文件与必要配置，不改业务代码。
- 不确定的业务决策一律列入「待确认问题」，不写成 MUST。
- `docs/rules/` 与 rules-index 索引区是托管生成文件，手改会被要求 `--force` 或被覆盖；修改只能走 `.ai-rules` 源。
- 多工具 `--tools` 仅限用户点名授权（如 `codex,trae,dsh`），不得默认全量同步。

## 回写流程（用户在当前工具里手改了规则文件后）

用户在当前工具的生成文件（如 `.trae/rules/ai-xxx.md`、`AGENTS.md`）里直接改进了规则，调用本 Skill 把改动回写到 `.ai-rules/` 唯一来源：

1. **预览**：`harvest --tools <当前工具>`。逐规则核对输出：
   - `HARVEST <rule-id>`：检测到漂移，将回写到对应源文件
   - `UNCHANGED`：与源文件一致
   - `ORPHAN`：合并文件前言区（rule-id 锚点之外）被手改——**永不自动回写**，报告给用户人工决定
   - `INDEX-DIFF`：根 `AGENTS.md` 的规则索引区落后于 `.ai-rules/manifest.json`（多为仅改过清单）——不算手改，运行 `sync --tools <当前工具> --apply` 刷新即可
   - `UNKNOWN-RULE`：rule-id 不在 manifest 中——跳过并报告
2. **回写**：确认后 `harvest --tools <当前工具> --apply`。工具会先备份原源文件与被覆盖的生成文件到 `.ai-rules/backups/<时间戳>-harvest/`，写回源文件后**自动重渲染当前工具的全部生成文件**并更新托管状态，保证 `check` 立即通过。
3. **验收**：`check --tools <当前工具>` 应为 PASS。

## 切换工具流程（用户换了 AI 编程工具）

1. 在新工具的会话中调用本 Skill → 确认新工具身份（步骤 0）。
2. `sync --tools <新工具>` 预览 → `--apply`，从 `.ai-rules/` 生成新工具的原生入口。
3. 旧工具的生成文件：保留（推荐，多工具共存）或经用户确认后清理。

## 命令

```bash
# 所有命令从任意位置调用；--project 在子命令前
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo detect
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo scan
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo init
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo new-rule --id BACKEND-XXX --file domains/backend/xxx.md --anchor services/api --layer domain --strength must --description "一句话说明"
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo sync --tools trae
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo sync --tools trae --apply
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo sync --tools codex,trae,dsh --apply   # 体系生成：多工具仅限用户点名授权
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo harvest --tools trae
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo harvest --tools trae --apply
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo check --tools trae
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo export-docs
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo export-docs --apply
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo explain apps/web/src/features/analytics/chart.tsx
```

### 必须遵守的操作边界

- **sync/harvest 必须显式 `--tools <当前工具>`**；禁止不带 `--tools` 全量同步，除非用户明确要求初始化全部工具。
- `harvest` 一次只回写一个工具；`--tools all/configured/多值` 会被拒绝。
- **不得自动执行** `--apply --force` 或 `--prune`；必须有用户明确授权。
- `init` 只提供保守模板；**不要把项目扫描猜测当作真实架构**，不应自行推断 HMI 安全策略、后端认证、数据库方案或真实测试命令。
- `new-rule` 只生成骨架并登记 manifest；**未填写正文的骨架不得 sync 落地**（骨架里的占位章节会被同步到工具入口，污染上下文）。新规则一律经 `.ai-rules` 唯一来源创建，禁止只改生成文件。
- `AGENTS.md` 根目录和其他平台生成文件**一律不作为唯一修改源**。实际权威内容在 `.ai-rules`。
- `harvest` 永不回写 ORPHAN（rule-id 锚点之外的手工改动）与 UNKNOWN-RULE 内容。
- 必须同时检查 `AGENTS.md` 和各平台专用入口在同时加载时是否重复/冲突（例如 Trae 会同时加载根 `AGENTS.md` 与 `.trae/rules/*.md`，因此 core 规则只放 `AGENTS.md`，`.trae/rules/` 只承载 domain 规则）。
- 没有原生 `exclude` 的工具，不能声称能够排除已经被广义 glob 匹配的目录；应拆分业务目录或禁用该规则。
- 体系生成流程产出的多值 `--tools`（如 `--tools codex,trae,dsh`）仅限用户点名授权后使用；平时仍守「一次只服务当前工具」。
- 根 `AGENTS.md` 的 `<!-- rules-index:begin/end -->` 索引区与 `docs/rules/` 目录均为托管生成内容，由 sync/export-docs 维护；手改会在下次导出时被要求 `--force`，harvest 遇索引落后会提示 INDEX-DIFF（属重新 sync 范畴，不算手改）。
- 不修改用户目录的全局规则或权限设置，不执行网络操作，不安装依赖，不调用模型 API。

## 关于规则语义与优先级

- 项目约定的分层仅用于**治理**：工程底线 → 技术域 → 功能场景 → 目录局部规则。不能声称此结构会凌驾工具的 system/developer 指令。
- 场景化规则只替换相关的视觉偏好，不得取消安全、数据准确性、可访问性等工程底线。
- 历史错误案例先当候选规则进行人工审核，不得因一次事故永久追加全局绝对禁令。
- `manifest.json` 的 `targets` 字段是「项目声明在用哪些工具」的元数据；实际同步始终以显式 `--tools <当前工具>` 为准。

更详细的 manifest 格式、适配矩阵、兼容性限制见 `references/SCHEMA_AND_COMPATIBILITY.md` 与 `references/tool-adapters.md`，规则编写质量标准见 `references/rule-authoring.md`，完整操作手册见 `README.md`。如更新工具适配器，应核对各工具最新版官方文档后修改脚本和测试。
