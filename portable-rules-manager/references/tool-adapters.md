# 各 AI 编程工具的规则存放与调用机制（适配器手册）

本文件是 `detect` 命令输出与 SKILL.md 步骤 1 的参考依据。每个工具一节：规则存放位置、加载机制、探测线索、本 Skill 适配器输出、已知限制。

> 维护提示：工具加载行为随版本变化，更新适配器前应核对 `SCHEMA_AND_COMPATIBILITY.md` 末尾列出的官方文档。

## 汇总表

| 工具 | `--tools` | 规则入口 | 探测线索（项目内） | 加载机制 |
| --- | --- | --- | --- | --- |
| Trae | `trae` | `.trae/rules/*.md` + 根 `AGENTS.md` | `.trae/` 目录 | 会话启动加载，纯 markdown，无 frontmatter |
| Cursor | `cursor` | `.cursor/rules/*.mdc`（+ 共享 `AGENTS.md`） | `.cursor/` 目录 | frontmatter 控制：`alwaysApply` 常驻或按 `globs` 匹配 |
| Claude Code | `claude` | `CLAUDE.md` + `.claude/rules/*.md` | `.claude/`、`CLAUDE.md` | `CLAUDE.md` 常驻（`@` 导入）；rules 按 `paths` 匹配 |
| Codex | `codex` | 根与子目录 `AGENTS.md` | `AGENTS.md`（弱信号，多工具共享） | 会话位置匹配根与最近祖先目录 |
| Gemini CLI | `gemini` | `GEMINI.md`、局部 `GEMINI.md` | `GEMINI.md`、`.gemini/` | `@./AGENTS.md` 导入，目录级层级 |
| GitHub Copilot | `copilot` | `.github/copilot-instructions.md` + `.github/instructions/*.instructions.md` | 同上两个路径 | 仓库级常驻 + `applyTo` glob 匹配 |
| Windsurf / Cascade | `windsurf` | `AGENTS.md`（`.windsurfrules` 为旧入口） | `.windsurf/`、`.windsurfrules` | Cascade 原生读取 `AGENTS.md` |

**探测的局限**：`detect` 只检查文件痕迹。同一项目可同时存在多个工具的配置目录（例如 `.trae/` 与 `.cursor/` 并存），痕迹不能证明"当前会话"属于哪个工具。**AI 必须根据运行环境自报身份**；detect 输出仅供交叉验证。`AGENTS.md` 被 Codex/Trae/Windsurf 共享，单独出现不足以判定 Codex。

## Trae（`trae`）

- **规则存放**：`.trae/rules/*.md`（项目级规则目录）+ 根 `AGENTS.md`。
- **加载机制**：会话启动时两者都会加载；纯 markdown，**无 frontmatter、无 glob 匹配**。
- **适配器输出**：
  - `AGENTS.md`（根）— 承载 core 规则（`anchor == "."`）
  - `.trae/rules/ai-<rule-id>.md` — 每个 domain 规则一份
- **关键设计**：core 规则**只**放 `AGENTS.md`，`.trae/rules/` 跳过 core。因为 Trae 同时加载两者，若 core 重复出现会同一会话加载两次。
- **已知限制**：无 exclude 语义；无路径匹配（全部常驻），因此 domain 规则即使是针对子目录的也会全量进入上下文——保持规则正文简短。

## Cursor（`cursor`）

- **规则存放**：`.cursor/rules/*.mdc`。
- **加载机制**：mdc frontmatter：`description` + `globs` + `alwaysApply`。`alwaysApply: true` 常驻；`false` 时按 globs 路径匹配。Cursor 也会读取 `AGENTS.md`。
- **适配器输出**：`.cursor/rules/ai-<rule-id>.mdc`（`alwaysApply: false` + globs 来自规则定义）；core 规则只放共享 `AGENTS.md`，避免与 Always 规则重复。
- **已知限制**：无 exclude；手写 `alwaysApply: true` 的 mdc 与 `AGENTS.md` 内容重复时会双重加载——迁移时应删除手写重复文件。

## Claude Code（`claude`）

- **规则存放**：`CLAUDE.md`（根，常驻）+ `.claude/rules/*.md`。
- **加载机制**：`CLAUDE.md` 支持 `@<path>` 导入语法；`.claude/rules/*.md` 用 frontmatter `paths:` 列表做路径匹配。
- **适配器输出**：`CLAUDE.md`（内容为 `@AGENTS.md` 导入）+ `.claude/rules/ai-<rule-id>.md`（`paths` frontmatter）。
- **已知限制**：无 exclude；导入失败的 `@` 路径会被静默忽略。

## Codex（`codex`）

- **规则存放**：根 `AGENTS.md` + 任意子目录 `AGENTS.md`。
- **加载机制**：按会话工作位置读取根与最近祖先目录的 `AGENTS.md`，层级叠加。
- **适配器输出**：根 `AGENTS.md`（core 合并）+ 每个非根 `anchor` 一份 `<anchor>/AGENTS.md`。
- **已知限制**：子目录叠加行为依赖 Codex 版本；globs 无法自定义（v1 限制为 `anchor/**/*`）。

## Gemini CLI（`gemini`）

- **规则存放**：`GEMINI.md`（根与目录级）。
- **加载机制**：`@./AGENTS.md` 导入，不直接复制内容；目录级层级。
- **适配器输出**：根 `GEMINI.md`（导入 `AGENTS.md`）+ `<anchor>/GEMINI.md`。
- **已知限制**：实际内容以 `AGENTS.md` 为准，Gemini 侧只是导入壳。

## GitHub Copilot（`copilot`）

- **规则存放**：`.github/copilot-instructions.md`（仓库级，常驻）+ `.github/instructions/*.instructions.md`。
- **加载机制**：instructions 文件用 frontmatter `applyTo: "glob"` 做路径匹配；具体客户端能力有差异（IDE 与 Copilot Coding Agent 不完全一致）。
- **适配器输出**：`.github/copilot-instructions.md`（core 合并）+ `.github/instructions/ai-<rule-id>.instructions.md`。
- **已知限制**：`applyTo` 不支持 exclude；部分客户端对多文件 instructions 的支持不一致。

## Windsurf / Cascade（`windsurf`）

- **规则存放**：根与子目录 `AGENTS.md`（当前 Cascade 原生自动识别）；`.windsurfrules` 为旧入口。
- **适配器输出**：复用共享 `AGENTS.md` 体系，**不额外生成** `.devin/rules` 或 `.windsurfrules`，避免与 AGENTS.md 重复。
- **已知限制**：旧 `.windsurfrules` 若手写存在且与 `AGENTS.md` 内容重复，会双重加载——迁移时应删除旧文件。

## harvest 回写的文件归属

`harvest --tools <t>` 只收集以下路径内、且已被托管（`.generated-state.json` 有记录）的文件：

| 工具 | 收集路径 |
| --- | --- |
| codex | `AGENTS.md`、`<subdir>/AGENTS.md` |
| cursor | `.cursor/rules/` |
| claude | `.claude/rules/`、`CLAUDE.md` |
| gemini | `GEMINI.md`、`<subdir>/GEMINI.md` |
| copilot | `.github/copilot-instructions.md`、`.github/instructions/` |
| windsurf | `AGENTS.md`、`<subdir>/AGENTS.md` |
| trae | `.trae/rules/`、`AGENTS.md`、`<subdir>/AGENTS.md` |

- `AGENTS.md` 系列为多工具共享入口，codex/trae/windsurf 各自 harvest 时都在自己的收集范围内——单工具 harvest 天然只处理当前工具视角。
- 单规则文件（`ai-<rule-id>.md/.mdc/.instructions.md`）整体回写；合并文件按 `<!-- rule-id: XXX -->` 锚点拆分回写；锚点之外的改动为 ORPHAN，永不自动回写。
