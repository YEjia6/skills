# 更新日志

版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)，与 Git tag 一一对应（tag 形如 `v1.1.0`）。
发布新版本时必须同时修改 `VERSION` 与本文件。

## [1.2.0] - 2026-10-22

### 新增

- `new-rule` 命令：标准化创建新规则——生成含「适用范围 / 规则 MUST-SHOULD-MAY / 禁止事项 / 验收」章节的骨架文件并登记 manifest；自动校验规则 ID 唯一性、anchor 目录存在性、互斥组目录重叠，校验失败自动回滚全部改动；`--disabled` 支持登记为待审候选。覆盖编程行为规则与工程流程规范两类规则的创建。
- `references/rule-authoring.md`：规则编写规范手册——ID 命名、layer/anchor 选择、strength 语义、必备章节、条目写法（可执行可检验、一条一事、因果链）、manifest 登记规范、反模式（宽泛 globs + excludes 抵消、历史事故禁令堆砌等）、合格示例与创建自检清单。
- 5 个 `new-rule` 测试用例（骨架创建与同步、缺 init 拒绝、非法输入拒绝、互斥组重叠回滚、disabled 候选）。

### 变更

- `SKILL.md`：description 与「何时调用」增加「创建/新增/编写规则、制定规范、规范落地」触发场景；新增「创建规则流程」章节（因果链 → 查重 → new-rule 骨架 → 填写正文 → 同步验收 → 加载验证）；操作边界补充「未填写正文的骨架不得 sync 落地」。

## [1.1.0] - 2026-10-22

### 新增

- Trae 适配器：生成根 `AGENTS.md`（承载 core 规则）与 `.trae/rules/ai-*.md`（仅 domain 规则），避免 Trae 同时加载两个入口导致 core 重复。
- `detect` 命令：只读探测项目内各 AI 工具的规则入口痕迹、规则存放位置与加载机制，用于交叉验证当前工具身份。
- `harvest` 命令：把当前工具生成文件中的手工修改按 `rule-id` 锚点回写到 `.ai-rules` 唯一来源；`ORPHAN` 与 `UNKNOWN-RULE` 永不自动回写，回写前自动备份并重渲染。
- `references/tool-adapters.md`：7 个工具的规则存放位置、加载机制、探测线索、适配器输出与 harvest 文件归属。

### 变更

- `SKILL.md` 工作流改为「一次只服务当前工具」：先确认工具身份，再 `detect` 交叉验证，然后扫描项目、生成规则。
- `sync` / `check` 推荐显式 `--tools <当前工具>`，不再默认全量生成所有工具入口。
- `rules_manager.py` 增加 `version` 子命令，版本号从 `VERSION` 文件读取。

## [1.0.0] - 2026-10-22

### 新增

- `.ai-rules` 唯一规则源（`manifest.json` + Markdown）。
- `scan` / `init` / `sync` / `check` / `explain` 命令。
- Codex、Cursor、Claude Code、Gemini CLI、GitHub Copilot、Windsurf 适配器。
- 托管状态 hash、冲突拒绝、`--force` 备份、`--prune` 清理。
