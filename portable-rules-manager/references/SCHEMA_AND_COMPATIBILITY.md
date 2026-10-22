# 清单格式与工具适配说明

## `.ai-rules/manifest.json` v1

本 Skill 使用标准 JSON（不需要 PyYAML），源规则为纯 Markdown。示例：

```json
{
  "schema_version": 1,
  "project": {"name": "example"},
  "targets": ["codex", "cursor", "claude", "gemini", "copilot", "windsurf", "trae"],
  "rules": [
    {
      "id": "CORE-ENGINEERING",
      "file": "core/engineering.md",
      "anchor": ".",
      "globs": ["**/*"],
      "excludes": [],
      "enabled": true,
      "description": "全仓库强制工程底线",
      "layer": "core",
      "strength": "must",
      "conflict_group": ""
    },
    {
      "id": "WEB-ANALYTICS",
      "file": "domains/web/analytics.md",
      "anchor": "apps/web/src/features/analytics",
      "globs": ["apps/web/src/features/analytics/**/*"],
      "excludes": [],
      "enabled": true,
      "description": "图表和分析页面的独立规则",
      "layer": "scenario",
      "strength": "must",
      "conflict_group": "web-visual-mode"
    }
  ]
}
```

- `file` 相对于 `.ai-rules/`，必须实际存在，禁止符号链接逃逸。
- `anchor` 是需要生成局部 `AGENTS.md` / `GEMINI.md` 的**实际存在的目录**；`.` 代表仓库根目录。
- `globs` 目前必须恰好为 `anchor/**/*`（根目录则为 `**/*`）；这一 v1 限制是有意的，防止部分平台使用无法严格表达的作用域并误加载规则。
- `excludes` 必须为空，除非该规则被禁用。**不要误以为把 excludes 写进 JSON，各平台就会自动排除文件。** 如果业务页面和图表文件混杂在同一目录，先重整文件夹或在生成器增加经过测试的具体平台适配支持。
- `enabled: false` 表示仅作为候选，不会生成到任何工具。
- `layer`（`core/domain/scenario/local`）表示治理层级，`strength`（`must/should/may`）表示强度。这些是本管理器语义字段，**不是**模型内建的指令优先级。
- `conflict_group` 用于标注互斥场景（例如常规 Web 视觉与图表视觉均使用 `web-visual-mode`）。编译前检查同组启用规则的目录是否重叠，重叠时拒绝生成。
- 默认扫描根据目录名、构建配置和少量文件扩展名做启发式识别，无法理解真实业务语义；人工审核是必要步骤。

## 实际生成的文件

| 目标工具 | 输出 / 加载路径 | 备注 |
| --- | --- | --- |
| Codex | 根目录及子目录 `AGENTS.md` | 层级读取依赖会话位置和 Codex 版本 |
| Cursor | 共享 `AGENTS.md` 与 `.cursor/rules/ai-*.mdc` | 路径模式触发；可能与嵌套 `AGENTS.md` 同时提供相同规则 |
| Claude Code | `CLAUDE.md`（正式 `@AGENTS.md` 导入）与 `.claude/rules/ai-*.md` | 路径匹配，避免普通文案“请读取”替代导入 |
| Gemini CLI | `GEMINI.md`、局部 `GEMINI.md` | 用 `@./AGENTS.md` 导入，不直接复制内容 |
| GitHub Copilot | `.github/copilot-instructions.md` 与 `.github/instructions/ai-*.instructions.md` | `applyTo` 路径匹配，具体客户端能力有差异 |
| Windsurf / Cascade | 根目录和子目录 `AGENTS.md` | 当前文档中是原生自动识别方式；为减少重复，默认不另写 `.devin/rules` |
| Trae | 根 `AGENTS.md`（承载 core）与 `.trae/rules/ai-*.md`（仅 domain 规则） | Trae 同时加载两者；core 只放 `AGENTS.md`，避免同一会话重复加载 |

**重要**：同一仓库同时生成多个适配器时，个别工具可能既发现 `AGENTS.md` 也发现自己的规则文件，造成同一条约束在上下文出现两次。由于同一仓库面向多工具，这个权衡目前无法完全自动化消除。建议实际使用中按工具执行 `sync --tools ...`，并核实激活来源。各工具的存放位置、加载机制、探测线索与已知限制详见 `references/tool-adapters.md`。

## 命名与规则质量

建议：规则 ID 大写 `WEB-ANALYTICS-APPS-WEB`；源文件使用 `domains/web/analytics.md`；生成文件统一 `ai-<规则ID>.mdc/.md`。目录 `core/` 放不可牺牲的工程底线，`domains/` 放技术领域要求，`workflows/` 放流程（自行扩展）。

规范要有：适用范围、触发条件、MUST/SHOULD/MAY、可接受的例外与验收条件。不要堆叠描述同一历史错误的全局禁令。

## 安全与运维

- `scan` 与 `detect` 为只读；`init` 仅新增不存在的源文件和清单；`sync` 默认只输出预览。
- `sync --apply` 拒绝覆盖未托管或已经被手工修改的文件。`sync --apply --force` 先备份再覆盖。符号链接从不强制覆盖。
- `--prune` 才会移除状态记录里已不再生成的旧目标，并备份。不存在状态记录的用户文件不会被 `--prune` 清理。
- `harvest --tools <单个工具>` 默认预览；`--apply` 把漂移的规则块回写到 `.ai-rules` 源文件，备份后重渲染当前工具全部生成文件。ORPHAN（rule-id 锚点之外的改动）与 UNKNOWN-RULE 永不自动回写。
- `check` 验证当前生成文件与预期文本一致，但**不验证模型行为**。
- 所有修改都发生在明确指定的项目根目录，不写入操作系统级 AI 配置文件。

## 参考官方资料（生成器适配时须复核）

- Agent Skills: https://agentskills.io/specification
- Codex: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Cursor: https://prod.cursor.com/docs/rules
- Claude Code: https://code.claude.com/docs/en/memory
- Gemini CLI: https://geminicli.com/docs/cli/gemini-md/
- GitHub Copilot: https://docs.github.com/en/copilot/how-tos/copilot-in-your-ide/customize-copilot/configure-custom-instructions/add-repository-instructions-in-your-ide
- Windsurf / Cascade: https://docs.devin.ai/desktop/cascade/memories
