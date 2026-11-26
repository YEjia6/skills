# -*- coding: utf-8 -*-
"""
parse_input.py — 解析 PLC 人员提供的数采点位 Excel（标准《设备PLC》格式）→ points.json

标准输入格式（5列，第1行为表头，设备组用合并单元格）:
  设备编号 | 设备名称/IP | 点位名称 | PLC地址 | Modbus地址/备注

用法:
  python parse_input.py <input.xlsx> [-s 工作表名] [-o out.json]

输出 points.json 结构:
  {
    "source_file": ..., "sheet": ...,
    "devices": [
      {"code":"M160116","name":"瓶检重秤","ip":"192.168.1.76","port":"502","raw_code":"M160116",
       "points":[
         {"raw_name":"【读】状态（0-待机 1-故障 2-运行）","name":"状态","direction":"读",
          "state_map":{"0":"待机","1":"故障","2":"运行"},"state_map_raw":"0-待机 1-故障 2-运行",
          "plc_addr":"%MD1000","modbus_remark":"data=CDAB;S=1;42001",
          "modbus_addr":"42001","span":1,"dataformat":"CDAB","slave":"1",
          "direction_note":"","unit_note":"","is_write":false}
       ]}
    ]
  }
约定: 设备编号为 “—” 或空 → 该组为产线联动信号，code=None（不进入业务配置表）。
"""
import argparse, json, re, sys, os
from openpyxl import load_workbook

HEADER_KEYS = ["设备编号", "点位名称", "PLC地址"]


def fill_merged(ws):
    """把合并单元格左上值铺满整个区域，返回新二维数组。"""
    grid = [[ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
            for r in range(1, ws.max_row + 1)]
    for m in ws.merged_cells.ranges:
        v = ws.cell(m.min_row, m.min_col).value
        for r in range(m.min_row, m.max_row + 1):
            for c in range(m.min_col, m.max_col + 1):
                if r - 1 < len(grid) and c - 1 < len(grid[r - 1]):
                    grid[r - 1][c - 1] = v
    return grid


def find_header_row(grid):
    for r, row in enumerate(grid):
        vals = [str(v).strip() if v is not None else "" for v in row]
        hits = sum(1 for k in HEADER_KEYS if k in vals)
        if hits >= 3:
            return r, vals
    raise SystemExit("未找到表头行（需同时包含: %s）" % ",".join(HEADER_KEYS))


IP_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})(?::(\d+))?")
STATE_WORD = {"待机": "待机", "空闲": "待机", "standby": "待机",
              "运行": "运行", "run": "运行", "runing": "运行", "running": "运行",
              "故障": "故障", "fault": "故障", "报警": "故障", "告警": "故障",
              "alarm": "故障", "error": "故障",
              "停止": "停止", "stop": "停止",
              "no": "运行", "on": "运行", "off": "待机"}


def parse_point_name(raw):
    """拆出方向标记、中文点位名、状态注释映射。"""
    name = str(raw) if raw is not None else ""
    direction = "读"
    m = re.search(r"【(读|写)】", name)
    if m:
        direction = m.group(1)
        name = name.replace(m.group(0), "")
    is_write = direction == "写"
    state_map_raw = ""
    state_map = {}
    # 状态注释: 括号内的 N-词 序列（0-待机 1-故障 2-运行 / 1=NO;0=OFF）
    anno = re.search(r"[（(]([^（）()]*)[)）]", name)
    if anno:
        state_map_raw = anno.group(1).strip()
        body = state_map_raw.replace("=", "-").replace("；", ";")
        for tok in re.split(r"[\s;；]+", body):
            mm = re.match(r"^(\d+)\s*[-–—]\s*(.+)$", tok)
            if mm:
                word = STATE_WORD.get(mm.group(2).strip().lower(), mm.group(2).strip())
                state_map[mm.group(1)] = word
        name = name.replace(anno.group(0), "")
    clean = re.sub(r"\s+", " ", name).strip()
    return clean, direction, is_write, state_map, state_map_raw


def parse_remark(raw):
    """解析 Modbus地址/备注 列: data=CDAB;S=1;42001 / 42021+42022 / 4x16384 / *100ms / （给PLC）"""
    s = str(raw) if raw is not None else ""
    if s.strip() in ("", "—", "-"):
        s = ""
    out = {"modbus_addr": "", "span": 1, "dataformat": "", "slave": "",
           "direction_note": "", "unit_note": "", "modbus_remark": s}
    m = re.search(r"data\s*=\s*([A-Za-z0-9]+)", s)
    if m:
        out["dataformat"] = m.group(1).upper()
    m = re.search(r"[Ss]\s*=\s*(\d+)", s)
    if m:
        out["slave"] = m.group(1)
    m = re.search(r"[（(]\s*(给PLC|PLC给)\s*[)）]", s)
    if m:
        out["direction_note"] = m.group(1)
    m = re.search(r"\*(\d+ms|\d+s|\d+min)", s)
    if m:
        out["unit_note"] = "*" + m.group(1)
    # 地址: 4x16384 → 16384; 42021+42022 → 42021 span2; 42141-42142 → 42021 span2; 42001 → 42001
    nums = re.findall(r"(?<!\d)(4x)?(\d{4,6})(?!\d)", s.replace(" ", ""))
    addr_pairs = [(int(n), 2 if ("+" in s or "-" in s) and i == 0 else 1)
                  for i, (_x, n) in enumerate(nums)]
    # 精确处理: 优先 A+B / A-B 双寄存器
    m2 = re.search(r"(?<!\d)(\d{4,6})\s*[+\-]\s*(\d{4,6})(?!\d)", s)
    if m2:
        out["modbus_addr"] = m2.group(1)
        out["span"] = 2
    elif nums:
        # 跳过 S= 的小数字（1位不会被 \d{4,6} 匹配到）；取最后一个 4-6 位地址
        out["modbus_addr"] = nums[-1][1]
        out["span"] = 1
    if re.match(r"^4x\d+$", s.strip()):
        out["modbus_addr"] = s.strip()[2:]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="输入 Excel 路径")
    ap.add_argument("-s", "--sheet", default=None, help="工作表名，缺省自动探测")
    ap.add_argument("-o", "--out", default=None, help="输出 points.json 路径")
    args = ap.parse_args()

    wb = load_workbook(args.input, data_only=True)
    sheets = [args.sheet] if args.sheet else wb.sheetnames
    grid = header = None
    used_sheet = None
    for sn in sheets:
        ws = wb[sn]
        try:
            g = fill_merged(ws)
        except Exception:
            continue
        try:
            hr, header = find_header_row(g)
        except SystemExit:
            continue
        grid, used_sheet = (g, hr), sn
        break
    if grid is None:
        raise SystemExit("所有工作表都未找到标准表头行")

    g, hr = grid
    idx = {k: header.index(k) for k in HEADER_KEYS}
    name_ip_idx = header.index("设备名称/IP") if "设备名称/IP" in header else None
    remark_idx = header.index("Modbus地址/备注") if "Modbus地址/备注" in header else None

    def cell(row, i):
        if i is None or i >= len(row) or row[i] is None:
            return ""
        return str(row[i]).strip()

    devices, cur = [], None
    for r in range(hr + 1, len(g)):
        row = g[r]
        code = cell(row, idx["设备编号"])
        name_ip = cell(row, name_ip_idx)
        pname = row[idx["点位名称"]]
        plc = cell(row, idx["PLC地址"])
        remark = cell(row, remark_idx)
        # 空行跳过
        if not code and not name_ip and (pname is None or str(pname).strip() == ""):
            continue
        # 新设备组：code 非空且变化（合并单元格已前向填充；code 为空=沿用当前组）
        if cur is None or (code and code != cur["raw_code"]):
            dev = {"raw_code": code,
                   "code": code if re.match(r"^[A-Za-z0-9_\-]+$", code or "") else "",
                   "is_line_level": code in ("—", ""),
                   "name": "", "ip": "", "port": "", "points": []}
            devices.append(dev)
            cur = dev
        # 设备名称/IP 只在组首行有效
        if name_ip and not cur["name"]:
            lines = [x.strip() for x in name_ip.split("\n") if x.strip()]
            cur["name"] = lines[0] if lines else ""
            nm = IP_RE.search(name_ip)
            if nm:
                cur["ip"] = nm.group(1)
                cur["port"] = nm.group(2) or ""
        clean, direction, is_write, state_map, state_raw = parse_point_name(pname)
        if not clean:
            continue
        p = {"raw_name": str(pname).strip(), "name": clean, "direction": direction,
             "is_write": is_write, "state_map": state_map, "state_map_raw": state_raw,
             "plc_addr": plc}
        p.update(parse_remark(remark))
        cur["points"].append(p)

    result = {"source_file": os.path.abspath(args.input), "sheet": used_sheet, "devices": devices}
    out = args.out or os.path.splitext(args.input)[0] + ".points.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    n_dev = sum(1 for d in devices if d["code"])
    n_pt = sum(len(d["points"]) for d in devices)
    n_w = sum(1 for d in devices for p in d["points"] if p["is_write"])
    print("解析完成: sheet=%s 设备=%d(产线级=%d) 点位=%d(写=%d) → %s"
          % (used_sheet, n_dev, sum(1 for d in devices if d["is_line_level"]), n_pt, n_w, out))


if __name__ == "__main__":
    main()
