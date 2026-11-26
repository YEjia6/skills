---
name: point-config-generator
description: 将 PLC 人员提供的数采点位 Excel + 系统数采规则，生成规范的设备数采点位 Excel（设备点位配置表）与可执行 SQL 脚本。触发词：数采点位/点位配置表/点位采集/设备点位配置/point config/生成点位配置SQL。
---

# point-config-generator — 设备数采点位配置生成

把 PLC 人员的《设备PLC点位采集表》转换为：规范的《设备点位配置表》Excel（复刻 16 列标准格式）+ 可执行 SQL（equipment_point_config 业务配置表）。术语见 [GLOSSARY.md](GLOSSARY.md)；状态编码规则依据 [ADR-0001](docs/adr/0001-status-encoding-from-plc-annotation.md)。

## 环境约定

- Python 必须带 openpyxl。DSH 环境用捆绑运行时：
  `C:\Users\6001790\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe -X utf8`
  失败再回退 `python -X utf8`。项目文件格式为自定义 YAML 子集，**不要引入 pyyaml 依赖**。
- 所有路径参数用原始字符串；Excel 打不开（TypeError: Fill）的文件提示用户另存为 .xlsx。

## 工作流（四阶段，勿跳步）

### 阶段 1 解析输入

```bash
python scripts/parse_input.py <PLC点位表.xlsx> -o <工作目录>/points.json
```

- 标准输入 = 5 列《设备PLC》格式（设备编号|设备名称/IP|点位名称|PLC地址|Modbus地址/备注），第 1 行表头，设备组用合并单元格。空白模板在 `assets/设备PLC点位采集模板.xlsx`（含填写说明 sheet），交给 PLC 人员填写。
- 解析器自动处理：合并单元格前向填充、`名称\nIP:端口`、`【读】/【写】`标记、状态注释→state_map、Modbus 备注（`data=CDAB;S=1;42001`、`42021+42022`、`4x16384`、`（给PLC）`）。
- **厂商原始表**（如 GX-12-3 地址表、IP 地址表）：先展示解析到的设备/点位清单请用户确认设备与 IP 的对应关系；列结构与标准格式不符时，AI 按"设备编号规则=项目约定、点位名称保留原文、地址列对应转换"整理成标准格式（说明哪些列被映射），再走标准流程。
- 设备编号为 `—` 的组 = 产线联动信号，标记为不进业务配置表。

### 阶段 2 生成映射表骨架 → AI 语义映射 → 用户确认

```bash
python scripts/build_outputs.py points.json --skeleton --project projects/<项目>.yaml -o <工作目录>
```

生成 `点位语义映射表_<项目>.csv`。然后 AI 逐行核对修正（核心工作，规则如下）：

1. **词表优先**：数采点位=var_前缀语义蛇形；词表在 `assets/semantic-vocab.csv`（匹配词→英文词/类型/分类默认值，start/end 列即信号默认值）。码垛/机器人类设备自动加前缀 `main_/left_/right_`。
2. **description 命名规则**（阶段4库比对验证）：标准生产单机的点位名称去设备名前缀并归一字典规范名（灌装机状态→设备状态、OK数→合格数）；机器人/网关类设备**保留完整语义名含实体前缀**（机械手网络心跳、左码垛产量）——不要机械去前缀。产线级/新增设备无从比对时保留原名。
2. **点位类型**必须取自字典 `assets/point-type-dict.csv`（27 项枚举：设备状态=device_status、运行状态=run_status、总产量=total_output、实时产量=realtime_output、开关点位=1、告警=warn、速度=speed、时间类、计数类、信号类等）。新类型先加字典再加映射。
3. **状态信号**：以 PLC 注释为唯一依据（ADR-0001）——注释里 运行值=启动信号、待机值=结束信号、故障值=故障信号；无注释默认 1/0/空并保留"请核对"备注。⚠️ 历史副本可能有人工错误（如山东258 M160116 应为 2/0/1），不要照抄副本。
4. **采集分类**（枚举 show/signal/state/warn）：主实体的状态/产量/产能/统计数默认 `show`；左右子实体/时间/监控/位信号默认空。生产单机族（库证据 M160102 整表 show，含时间类）在 project.yaml `show_all_eqp` 中配置整表 show；检测类设备（如瓶检重秤）时间类为 NULL，词表默认即可，**勿凭同族推断加入 show_all_eqp**。山东258 基线：show_all_eqp=[M160102,103,106,108]；M160116/M160114 走词表；M1613 仅 var_main_run_status/var_main_warn/var_main_output/var_left_output/var_right_output。
5. **排除规则**：`【写】`点位默认排除；设备编号`—`产线联动排除；工艺参数类点位（延时/温度设定等）建议排除并备注；单位/最小值/最大值/阀门两列一律占位不填。
6. **产出前把映射表关键决策呈现给用户确认**（展示每个设备纳入/排除的点数、变量命名清单），确认后才进入阶段 3。

### 阶段 3 生成交付物

```bash
python scripts/build_outputs.py points.json --mapping 点位语义映射表.csv --project projects/<项目>.yaml -o <输出目录>
```

默认输出三件套（输出到输入文件同目录，文件名含项目名）：
- `设备点位配置表_<项目>.xlsx`：R1 标题"设备点位配置表报表"(A1:P1 居中 Calibri12)、R2"导出人:金旺智能"(右对齐)、R3 表头 16 列宋体11、数据宋体10、列宽 A15/B34.56/C15/H22.33/I15、行高 25；第二 sheet 为校验报告。
- `设备点位配置SQL_<项目>.sql`：事务包裹，按 eqp_code 先 DELETE 后 INSERT（幂等可重跑），id=时间戳+序号 19 位，description=中文点位名、point_name=NULL、point_class=NULL、pointclass=采集分类、relevance_eqp_code=设备编号、is_write_value='0'；列清单运行时从 `assets/ddl.sql`（四张表真源 DDL）解析。
- `设备点位配置SQL_<项目>_rollback.sql`：按生成的 id 回删。

选项：`--excel-only` 只要 Excel 不要 SQL；`--sql-excel` 追加 SQL语句清单_*.xlsx（序号|目标表|操作|设备编号|SQL语句）；`--with-collection` 追加采集层 equipment_plc / equipment_plc_point 的 INSERT（plc_type 按端口映射 102=S7、502/503=MODBUSTCP，字段缺失列 NULL，属预留功能，列清单以 ddl.sql 为准）。

### 阶段 4 校验与验收

1. 校验 7 项自动执行并写入校验报告 sheet：数采点位重复 / 设备编号缺失 / IP端口缺失 / Modbus地址非法(1-65535) / 点位类型不在字典 / 状态信号缺失 / Modbus地址重叠。警告不阻塞交付，但必须向用户逐条说明。
2. **有库真源时逐字段比对（阶段4验收，必做）**：
   ```bash
   python scripts/compare_with_dump.py <项目dump.sql> <生成SQL>.sql --table equipment_point_config
   ```
   退出码 0=通过 1=有差异。比对 id 外全部字段；新增行（库中无）正常。差异按三类归因修正映射表后重建：description 命名（规则2）、show 集合（规则4）、信号默认（词表 start/end）。山东258 基线：M160102、M160114、M160116、M1613 存量 39 行全字段一致（M160116 状态信号 2/0/1）。
3. 交付清单 + 比对结果汇报给用户。

## 项目配置 projects/<项目>.yaml

```yaml
project: 山东258            # 文件名后缀
exporter: 金旺智能           # R2 导出人
lines:                      # 产线 → factory_module_id → 设备编号前缀
  - name: 灌装线
    factory_module_id: "2111295160195661825"
    device_prefixes: ["M1601", "M1613"]
defaults: {port: "502"}
plc_type_by_port: {"102": "S7", "502": "MODBUSTCP", "503": "MODBUSTCP"}
db: {}                      # 预留：技能集成进项目后直查 factory_module 等真源
```

新项目：复制模板 yaml，向用户确认产线树 factory_module_id（或从项目 SQL dump 的 factory_module 表查）与设备编号段。

## 反模式（禁止）

- 禁止照抄历史 Excel 副本的状态信号（ADR-0001）。
- 禁止机械给所有设备点位去设备前缀——机器人/网关类设备 description 保留完整语义名（阶段4库证据）。
- 禁止凭同族推断把检测设备加入 show_all_eqp——M160102 整表 show 而 M160116 时间类 NULL 是真源事实。
- 禁止在映射未经用户确认前生成最终 SQL。
- 禁止发明字典外点位类型；禁止给单位/阀门列编造内容。
- 禁止把【写】点位混入 is_write_value='0' 的业务表（写点位后续需求另议）。
- 禁止 pyyaml / 修改 parse_input 对标准格式的列顺序假设而不更新 SKILL.md。
