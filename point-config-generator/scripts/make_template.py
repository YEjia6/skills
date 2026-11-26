# -*- coding: utf-8 -*-
"""生成空白《设备PLC点位采集模板.xlsx》——PLC 人员填写入口。运行一次即可，产物入库 assets/。"""
import os
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "设备PLC点位采集模板.xlsx")

wb = Workbook()
ws = wb.active
ws.title = "设备PLC"
heads = ["设备编号", "设备名称/IP", "点位名称", "PLC地址", "Modbus地址/备注"]
for i, h in enumerate(heads, 1):
    c = ws.cell(1, i, h)
    c.font = Font(name="宋体", size=11, bold=True)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws.row_dimensions[1].height = 22.5
samples = [
    ["M100001", "示例设备A\n192.168.1.10:502", "【读】状态（0-待机 1-故障 2-运行）", "%MD1000", ""],
    ["M100001", "", "【读】产量计数", "%MD1004", "42011+42012"],
    ["M100001", "", "【写】启动命令", "%MW1010", "42201（给PLC）"],
    ["M100002", "示例设备B\n192.168.1.11:503", "【读】满料信号", "%MX6.0", "4x16384"],
]
r = 2
for s in samples:
    for i, v in enumerate(s, 1):
        c = ws.cell(r, i, v)
        c.font = Font(name="宋体", size=10)
    ws.row_dimensions[r].height = 25
    r += 1
for col, wdt in {"A": 14, "B": 30, "C": 40, "D": 16, "E": 30}.items():
    ws.column_dimensions[col].width = wdt
# 删除示例行留给真实数据？保留示例但标注
ws.cell(r + 1, 1, "↑ 示例行仅供格式参考，填写时请删除").font = Font(name="宋体", size=9, italic=True, color="FF808080")

ws2 = wb.create_sheet("填写说明")
notes = [
    "《设备PLC点位采集表》填写规范",
    "",
    "1. 设备编号：系统设备编码（如 M160116），同组可合并单元格；产线联动信号组填“—”。",
    "2. 设备名称/IP：两行，第一行设备名称，第二行 IP:端口（端口 102=西门子S7，502/503=ModbusTCP）。",
    "   示例：灌装机\\n192.168.1.70:502",
    "3. 点位名称：开头用【读】或【写】标记方向；状态类点位在名称后附括号状态注释，",
    "   如：状态（0-待机 1-故障 2-运行）——运行值将成为启动信号、待机值=结束信号、故障值=故障信号。",
    "4. PLC地址：PLC 原始地址（如 %MD1000、%MX4400.0、MW50）；纯 Modbus 设备可留空。",
    "5. Modbus地址/备注：Modbus 寄存器地址及说明，支持以下写法：",
    "   42011+42012   双寄存器(2个字)",
    "   4x16384       线圈/离散量地址",
    "   data=CDAB;S=1;42001   字节序+从站号+地址",
    "   42141-42142（PLC给）/ 42201（给PLC）  方向备注",
    "   *100ms / 件/min  量程或单位备注",
    "6. 状态注释必须使用标准词：待机/运行/故障（报警、告警视同故障）。",
    "7. 同一设备的 Modbus 地址不得重叠。",
]
for i, t in enumerate(notes, 1):
    c = ws2.cell(i, 1, t)
    c.font = Font(name="宋体", size=11, bold=(i == 1))
ws2.column_dimensions["A"].width = 100
wb.save(OUT)
print("模板已生成:", os.path.abspath(OUT))
