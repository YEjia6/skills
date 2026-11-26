# 数采点位配置（金旺智能数采服务）

围绕"PLC人员点位表 → 规范设备点位配置表 + 可执行SQL"转换技能的领域语言。目标库为金旺智能数采服务（JeecgBoot + MySQL），核心表 `equipment_point_config`。

## Language

**数采点位（Variable）**:
业务层点位唯一变量名，`var_` 前缀蛇形命名（如 `var_device_status`、`var_left_run_status`），可带 `main_/left_/right_` 实体前缀。
_Avoid_: 点位编码、tag、变量号

**点位名称（Description）**:
点位中文语义名，写入 `equipment_point_config.description`（Excel 列「点位名称」）。标准六点使用去设备前缀的通用名。
_Avoid_: 与「数采点位」混称

**设备编号（Equipment Code）**:
产线内设备唯一编码，如 `M160102`、`M1613`，对应 `eqp_code`。
_Avoid_: 设备号、机器号

**点位类型（Point Type）**:
来自 `plc_point_type_map` 字典的枚举值：`device_status`、`run_status`、`run_time`、`fault_time`、`standby_time`、`total_output`、`realtime_output`、`speed`、`cumulative_quantity`、`qualified_quantity`、`unqualified_quantity`、`stop_signal`、`warn`、`1`（开关点位）等。
_Avoid_: 与「数据类型」混称

**数据类型（Datatype）**:
采集层 `equipment_plc_point.datatype` 的存储格式代码（如 `0`/`3`），与点位类型无关。
_Avoid_: 归入点位类型

**采集分类（Point Class）**:
采集分层枚举：`show`（展示）、`signal`（信号）、`state`（状态）、`warn`（报警）。业务配置表中仅 `show` 常用；主实体状态/产量/产能/统计数默认 `show`，左右子实体、时间类、监控类、位信号默认空。
_Avoid_: 分类编码

**启动/结束/故障信号**:
设备状态点的三态值。唯一依据是 PLC 注释（如 `0-待机 1-故障 2-运行`）解析：启动=运行值、结束=待机值、故障=故障值。历史 Excel 副本曾出现与注释矛盾的人工错误（M160116 写 1/0/2，库中实为 2/0/1）。

**标准六点**:
设备状态、运行时间、故障时间、待机时间、产量、产能的惯称，点位名称去设备前缀（如「瓶检重秤设备状态」→「设备状态」）。

**业务配置表（equipment_point_config）**:
技能生成的 SQL 的默认唯一目标表；列与《设备点位配置表》16 列一一对应，另有 `factory_module_id`、19 位雪花风格 `id`、`is_write_value`。
_Avoid_: 称作「点位配置表」（口语可用，文档中用全称）

**采集层（equipment_plc / equipment_plc_point）**:
设备连接配置与采集点位注册表。山东258 项目设备不在其中（走网关），故默认不生成，仅 `--with-collection` 开关时生成。

**产线（Factory Module）**:
`factory_module` 树节点（如 山东新华→生产车间→灌装线），业务配置经 `factory_module_id` 关联；Excel「产线」列显示其 `full_name`。

**网关变量表（…Variable.xlsx）**:
数采网关导出的变量清单（文件名前缀为网关 SN），属输入侧参考资料，非生成目标。

**点位语义映射表**:
两阶段流程的中间产物：原点位名称 → 数采点位/点位类型/采集分类/启动结束故障信号 的对照清单，经人工确认后才产出最终 Excel 与 SQL。
