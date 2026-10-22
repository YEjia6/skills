---
name: portable-rules-manager
description: 扫描多语言及混合仓库，创建或维护 .ai-rules 统一规则源，并只同步到「当前正在使用的 AI 编程工具」的原生规则入口（Codex AGENTS.md、Cursor MDC、Claude Code、Gemini CLI、Copilot、Windsurf、Trae）；支持把当前工具里的手工修改回写到 .ai-rules，方便切换工具时再生成。用户提出迁移、初始化、整理、生成、同步、回写或检查 AI 编程工具规则时使用。
---

# Portable Rules Manager · 多平台规则管理器

## 何时调用

当用户需要跨 AI 编程工具复用规则、从已有项目自动整理规则体系、扫描前后端/移动端/HMI 混合仓库、更新 `.ai-rules`、生成或回写当前工具的规则文件时调用。

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

   无法确定时**问用户**，禁止猜测。同一项目可同时存在多个工具的配置目录，文件痕迹不能证明当前会话身份。

1. **探测与查阅（交叉验证）**：运行 `python <skill_dir>/scripts/rules_manager.py --project <repo> detect`，查看项目内各工具的痕迹文件、当前工具的规则存放位置与加载机制。detect 输出仅供验证，不做身份判定。各工具详情见 `references/tool-adapters.md`。
2. **确认项目根目录**：以 Git 仓库根目录为优先。查看已有 `AGENTS.md`、`CLAUDE.md`、`.cursor/rules`、`.trae/rules` 等入口是否为手工维护。
3. **只读扫描**：`scan`。查看 `modules`、`confidence`、`evidence`，人工确认前端、后端、移动端、HMI，尤其数据分析目录。扫描推断不是确定性识别。
4. **初始化**：用户同意建立规则体系时运行 `init`。已有 `.ai-rules` Markdown 只索引为**禁用待审**；`manifest.json` 已存在则不覆盖。
5. **编辑唯一来源**：修改 `.ai-rules/manifest.json`、`.ai-rules/**/*.md`。每条规则必须定义 `anchor` 和 `globs`，保证真正的独立目录匹配。常规 Web UI 规范只放在明确的业务页面目录；图表分析规范只放在分析目录，禁止宽泛的全 Web 应用并试图依靠 `excludes` 抵消。
6. **只读预览**：`sync --tools <当前工具>`，审查每个 `CREATE/UPDATE/UNCHANGED/CONFLICT`。未指定 `--apply` 时绝不写原生规则。
7. **同步**：预览符合预期后 `sync --tools <当前工具> --apply`。遇到现有手写规则，停止并与用户审查；仅经明确授权后才用 `--force`（自动备份，拒绝覆写符号链接）。
8. **验收**：`check --tools <当前工具>` 和 `explain <path>`，再在当前工具中开启新会话测试正反案例。`check` 只能验证文件内容同步，不能保证模型实际加载或遵守。

## 回写流程（用户在当前工具里手改了规则文件后）

用户在当前工具的生成文件（如 `.trae/rules/ai-xxx.md`、`AGENTS.md`）里直接改进了规则，调用本 Skill 把改动回写到 `.ai-rules/` 唯一来源：

1. **预览**：`harvest --tools <当前工具>`。逐规则核对输出：
   - `HARVEST <rule-id>`：检测到漂移，将回写到对应源文件
   - `UNCHANGED`：与源文件一致
   - `ORPHAN`：合并文件前言区（rule-id 锚点之外）被手改——**永不自动回写**，报告给用户人工决定
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
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo sync --tools trae
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo sync --tools trae --apply
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo harvest --tools trae
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo harvest --tools trae --apply
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo check --tools trae
python /path/to/portable-rules-manager/scripts/rules_manager.py --project /path/to/repo explain apps/web/src/features/analytics/chart.tsx
```

### 必须遵守的操作边界

- **sync/harvest 必须显式 `--tools <当前工具>`**；禁止不带 `--tools` 全量同步，除非用户明确要求初始化全部工具。
- `harvest` 一次只回写一个工具；`--tools all/configured/多值` 会被拒绝。
- **不得自动执行** `--apply --force` 或 `--prune`；必须有用户明确授权。
- `init` 只提供保守模板；**不要把项目扫描猜测当作真实架构**，不应自行推断 HMI 安全策略、后端认证、数据库方案或真实测试命令。
- `AGENTS.md` 根目录和其他平台生成文件**一律不作为唯一修改源**。实际权威内容在 `.ai-rules`。
- `harvest` 永不回写 ORPHAN（rule-id 锚点之外的手工改动）与 UNKNOWN-RULE 内容。
- 必须同时检查 `AGENTS.md` 和各平台专用入口在同时加载时是否重复/冲突（例如 Trae 会同时加载根 `AGENTS.md` 与 `.trae/rules/*.md`，因此 core 规则只放 `AGENTS.md`，`.trae/rules/` 只承载 domain 规则）。
- 没有原生 `exclude` 的工具，不能声称能够排除已经被广义 glob 匹配的目录；应拆分业务目录或禁用该规则。
- 不修改用户目录的全局规则或权限设置，不执行网络操作，不安装依赖，不调用模型 API。

## 关于规则语义与优先级

- 项目约定的分层仅用于**治理**：工程底线 → 技术域 → 功能场景 → 目录局部规则。不能声称此结构会凌驾工具的 system/developer 指令。
- 场景化规则只替换相关的视觉偏好，不得取消安全、数据准确性、可访问性等工程底线。
- 历史错误案例先当候选规则进行人工审核，不得因一次事故永久追加全局绝对禁令。
- `manifest.json` 的 `targets` 字段是「项目声明在用哪些工具」的元数据；实际同步始终以显式 `--tools <当前工具>` 为准。

更详细的 manifest 格式、适配矩阵、兼容性限制见 `references/SCHEMA_AND_COMPATIBILITY.md` 与 `references/tool-adapters.md`，完整操作手册见 `README.md`。如更新工具适配器，应核对各工具最新版官方文档后修改脚本和测试。
