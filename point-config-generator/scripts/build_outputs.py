# -*- coding: utf-8 -*-
"""
build_outputs.py — 由 points.json + 语义映射表(mapping.csv) + 项目配置(project.yaml)
生成规范的设备数采点位交付物。

模式:
  --skeleton   生成「点位语义映射表」骨架 mapping.csv（AI/人工在此表上确认修正）
  (默认)       按确认后的 mapping.csv 生成最终交付物

输出（默认全量，位于 -o 目录，文件名含项目名）:
  设备点位配置表_<项目>.xlsx          复刻16列业务配置表格式（R1标题/R2导出人/R3表头）
  设备点位配置SQL_<项目>.sql          equipment_point_config 幂等导入脚本
  设备点位配置SQL_<项目>_rollback.sql 回滚脚本
选项:
  --excel-only        只要 Excel，不生成 SQL
  --with-collection   追加采集层 equipment_plc / equipment_plc_point 的 INSERT
  --sql-excel         追加 SQL语句清单_<项目>.xlsx

规则要点（与 ADR-0001 / 共识一致）:
  * 状态编码以 PLC 注释为唯一依据（skeleton 阶段自动从 state_map 推导）
  * 【写】点位默认排除；设备编号"—"（产线联动）排除；单位/阀门列占位不填
  * 点位类型以 assets/point-type-dict.csv 为字典，字典外→校验报告警告
  * 语义映射以 assets/semantic-vocab.csv 为词表，未匹配→include=否 请人工判断
"""
import argparse, csv, json, os, re, sys, time
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
DICT_CSV = os.path.join(SKILL, "assets", "point-type-dict.csv")
VOCAB_CSV = os.path.join(SKILL, "assets", "semantic-vocab.csv")
DDL_SQL = os.path.join(SKILL, "assets", "ddl.sql")

MAPPING_COLS = ["设备编号", "设备名称", "源点位名称", "是否纳入", "数采点位", "点位名称",
                "点位类型", "采集分类", "启动信号", "结束信号", "故障信号", "备注"]

TARGET_HEADERS = ["设备编号", "数采点位", "单位", "关联设备编号", "产线", "点位名称",
                  "采集分类", "点位类型", "最小值", "最大值", "启动信号", "结束信号",
                  "故障信号", "阀门设备点位", "阀门点位", "是否支持写值"]

STATE_TYPES = {"device_status", "run_status", "fault_status", "standby_status"}


# ---------------------------------------------------------------- minimal YAML
def load_yaml_min(text):
    """解析本技能约定的 project.yaml 子集: 标量键 / 嵌套列表(list of dict) / 行内数组。"""
    root, last_key, cur_item = {}, None, None
    for raw in text.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if indent == 0:
            k, _, v = s.partition(":")
            last_key, cur_item = k.strip(), None
            if v.strip():
                root[last_key] = _scalar(v.strip())
            else:
                root[last_key] = []  # 复合键预置为列表；纯标量键在本约定中必带值
        elif s.startswith("- "):
            body = s[2:]
            k, _, v = body.partition(":")
            cur_item = {}
            if last_key and isinstance(root.get(last_key), list):
                root[last_key].append(cur_item)
            if v.strip():
                cur_item[k.strip()] = _scalar(v.strip())
        else:
            if cur_item is not None:
                k, _, v = s.partition(":")
                cur_item[k.strip()] = _scalar(v.strip())
    return root


def _scalar(v):
    v = v.strip()
    if v == "{}":
        return {}
    if v.startswith("[") and v.endswith("]"):
        return [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
    if v.startswith("{") and v.endswith("}"):
        out = {}
        for part in v[1:-1].split(","):
            k, _, val = part.partition(":")
            if k.strip():
                out[k.strip()] = _scalar(val.strip())
        return out
    return v.strip("\"'")


# ---------------------------------------------------------------- vocab / dict
def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def detect_prefix(dev_name, point_name):
    """码垛/机器人类设备: 左→left_ 右→right_ 其余→main_；普通设备无前缀。"""
    if not dev_name or not any(k in (dev_name or "") for k in ("码垛", "机器人", "机械手")):
        return ""
    if point_name.startswith("右") or "右码垛" in point_name:
        return "right_"
    if point_name.startswith("左") or "左码垛" in point_name:
        return "left_"
    return "main_"


def vocab_match(vocab, name):
    for v in vocab:
        if v["match"] and v["match"] in name:
            return v
    return None


def derive_variable(v, prefix):
    """由词表行+实体前缀 → (variable, point_type, point_class)"""
    english, ptype, pclass = v["english"], v["point_type"], v["point_class"]
    if ptype == "LR_OUTPUT":  # 左/右垛板产量: 类型随前缀
        ptype = {"left_": "left_output", "right_": "right_output"}.get(prefix, "total_output")
        english = "output"
    if ptype == "RUN_STATUS":  # run_status: 分类仅主实体 show，左右子实体留空
        ptype = "run_status"
        pclass = "" if prefix in ("left_", "right_") else "show"
    if ptype == "SHOW_NONLR":
        pclass = "" if prefix in ("left_", "right_") else "show"
    variable = "var_" + prefix + english if english else ""
    return variable, ptype, pclass


def signals_from_state_map(state_map):
    """状态注释映射 → (start,end,fault)。运行=启动，待机=结束，故障=故障。"""
    start = end = fault = ""
    for k, w in state_map.items():
        if w == "运行" and not start:
            start = k
        elif w == "待机" and not end:
            end = k
        elif w == "故障" and not fault:
            fault = k
    return start, end, fault


# ---------------------------------------------------------------- skeleton
def build_skeleton(points, vocab, out_csv):
    rows = []
    for dev in points["devices"]:
        for p in dev["points"]:
            note_parts = []
            include = "是"
            if dev["is_line_level"] or not dev["code"]:
                include = "否"
                note_parts.append("产线联动信号，不进业务配置表")
            if p["is_write"]:
                include = "否"
                note_parts.append("写点位默认排除")
            prefix = detect_prefix(dev["name"], p["name"])
            v = vocab_match(vocab, p["name"])
            variable = ptype = pclass = ""
            start = end = fault = ""
            if v:
                variable, ptype, pclass = derive_variable(v, prefix)
                start, end, fault = signals_from_state_map(p["state_map"])
                if not start and v["start"]:
                    start = v["start"]
                if not end and v["end"]:
                    end = v["end"]
                if ptype in STATE_TYPES and not p["state_map"]:
                    start, end, fault = "1", "0", ""
                    note_parts.append("无状态注释，按默认1/0，请核对")
                if v["note"]:
                    note_parts.append(v["note"])
            else:
                note_parts.append("词表未匹配，请人工判断")
            rows.append({
                "设备编号": dev["code"], "设备名称": dev["name"],
                "源点位名称": p["name"], "是否纳入": include,
                "数采点位": variable, "点位名称": p["name"],
                "点位类型": ptype, "采集分类": pclass,
                "启动信号": start, "结束信号": end, "故障信号": fault,
                "备注": "；".join(note_parts),
            })
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MAPPING_COLS)
        w.writeheader()
        w.writerows(rows)
    inc = sum(1 for r in rows if r["是否纳入"] == "是")
    print("映射骨架已生成: %d 行(纳入%d/排除%d) → %s" % (len(rows), inc, len(rows) - inc, out_csv))
    unmatched = [r for r in rows if r["是否纳入"] == "是" and not r["数采点位"]]
    if unmatched:
        print("⚠ %d 行词表未匹配，需人工补齐数采点位" % len(unmatched))


# ---------------------------------------------------------------- DDL helpers
def ddl_columns(table):
    txt = open(DDL_SQL, encoding="utf-8").read()
    m = re.search(r"CREATE TABLE `%s`.*?\n\)([^;]*);" % table, txt, re.S)
    cols = []
    for line in m.group(0).splitlines():
        lm = re.match(r"\s*`(\w+)`\s", line)
        if lm:
            cols.append(lm.group(1))
    return cols


def sq(s):
    if s is None or s == "":
        return "NULL"
    return "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"


# ---------------------------------------------------------------- validation
def validate(mapping_rows, points, project, dict_values):
    warns = []
    dev_map = {d["code"]: d for d in points["devices"] if d["code"]}

    def W(level, check, msg):
        warns.append({"级别": level, "检查项": check, "说明": msg})

    inc = [r for r in mapping_rows if r["是否纳入"] in ("是", "Y", "y", "1", "yes")]
    seen = {}
    for r in inc:
        code = r["设备编号"]
        if not code:
            W("警告", "设备编号缺失", "纳入行缺设备编号: %s" % r["源点位名称"])
        if r["数采点位"]:
            key = (code, r["数采点位"])
            if key in seen:
                W("警告", "数采点位重复", "%s %s 与行「%s」重复" % (code, r["数采点位"], seen[key]))
            seen[key] = r["源点位名称"]
        if r["点位类型"] and r["点位类型"] not in dict_values:
            W("警告", "点位类型不在字典", "%s %s 类型=%s" % (code, r["点位名称"], r["点位类型"]))
        if r["点位类型"] in STATE_TYPES and (not r["启动信号"] or not r["结束信号"]):
            W("警告", "状态信号缺失", "%s %s 启动/结束信号为空(库中惯例需明确)" % (code, r["点位名称"]))
        if not r["数采点位"]:
            W("警告", "数采点位为空", "%s %s" % (code, r["点位名称"]))
        if code and code not in dev_map:
            W("警告", "未知设备", "映射表设备 %s 不在输入文件中" % code)
        if code and not r.get("产线"):
            W("警告", "产线未匹配", "设备 %s 未匹配 project.yaml 中任何 device_prefixes" % code)
    for code, d in dev_map.items():
        if not d["ip"]:
            W("警告", "IP缺失", "%s(%s)" % (code, d["name"]))
        if not d["port"]:
            W("警告", "端口缺失", "%s(%s)" % (code, d["name"]))
        ranges = {}
        for p in d["points"]:
            if p["modbus_addr"]:
                try:
                    a = int(p["modbus_addr"])
                    if not (1 <= a <= 65535):
                        raise ValueError
                    ranges.setdefault((code, d["ip"]), []).append((a, a + max(p["span"], 1) - 1, p["name"]))
                except ValueError:
                    W("警告", "Modbus地址非法", "%s %s 地址=%s" % (code, p["name"], p["modbus_addr"]))
        for key, rs in ranges.items():
            rs_sorted = sorted(rs)
            for i in range(1, len(rs_sorted)):
                if rs_sorted[i][0] <= rs_sorted[i - 1][1]:
                    W("警告", "Modbus地址重叠", "%s: %s[%d-%d] 与 %s[%d-%d] 重叠"
                      % (key[0], rs_sorted[i - 1][2], rs_sorted[i - 1][0], rs_sorted[i - 1][1],
                         rs_sorted[i][2], rs_sorted[i][0], rs_sorted[i][1]))
    return warns, inc


# ---------------------------------------------------------------- line resolve
def resolve_line(project, code):
    for ln in project.get("lines") or []:
        for pref in ln.get("device_prefixes") or []:
            if pref and str(code).startswith(pref):
                return ln
    return None


# ---------------------------------------------------------------- excel
def write_excel(path, rows, warns, project):
    wb = Workbook()
    ws = wb.active
    ws.title = "设备点位配置表"
    ws.merge_cells("A1:P1")
    c = ws["A1"]
    c.value = "设备点位配置表报表"
    c.font = Font(name="Calibri", size=12)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 25
    ws.merge_cells("A2:P2")
    c = ws["A2"]
    c.value = "导出人:%s" % project.get("exporter", "")
    c.font = Font(name="Calibri", size=12)
    c.alignment = Alignment(horizontal="right", vertical="center")
    ws.row_dimensions[2].height = 20
    for i, h in enumerate(TARGET_HEADERS, 1):
        c = ws.cell(3, i, h)
        c.font = Font(name="宋体", size=11)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[3].height = 22.5
    r = 4
    for row in rows:
        vals = [row.get(k, "") for k in TARGET_HEADERS[:-1]] + ["否"]
        for i, v in enumerate(vals, 1):
            c = ws.cell(r, i, v if v != "" else None)
            c.font = Font(name="宋体", size=10)
        ws.row_dimensions[r].height = 25
        r += 1
    for col, wdt in {"A": 15, "B": 34.56, "C": 15, "H": 22.33, "I": 15}.items():
        ws.column_dimensions[col].width = wdt
    # 校验报告
    ws2 = wb.create_sheet("校验报告")
    for i, h in enumerate(["级别", "检查项", "说明"], 1):
        c = ws2.cell(1, i, h)
        c.font = Font(name="宋体", size=11, bold=True)
    if not warns:
        ws2.cell(2, 1, "校验通过，无警告")
    else:
        for i, w in enumerate(warns, 2):
            ws2.cell(i, 1, w["级别"]).font = Font(name="宋体", size=10)
            ws2.cell(i, 2, w["检查项"]).font = Font(name="宋体", size=10)
            ws2.cell(i, 3, w["说明"]).font = Font(name="宋体", size=10)
    for col, wdt in {"A": 10, "B": 18, "C": 80}.items():
        ws2.column_dimensions[col].width = wdt
    wb.save(path)


def write_sql_excel(path, stmts):
    wb = Workbook()
    ws = wb.active
    ws.title = "SQL语句清单"
    heads = ["序号", "目标表", "操作", "设备编号", "SQL语句"]
    for i, h in enumerate(heads, 1):
        c = ws.cell(1, i, h)
        c.font = Font(name="宋体", size=11, bold=True)
    for r, s in enumerate(stmts, 2):
        ws.cell(r, 1, s["序号"]).font = Font(name="宋体", size=10)
        ws.cell(r, 2, s["目标表"]).font = Font(name="宋体", size=10)
        ws.cell(r, 3, s["操作"]).font = Font(name="宋体", size=10)
        ws.cell(r, 4, s["设备编号"]).font = Font(name="宋体", size=10)
        ws.cell(r, 5, s["SQL语句"]).font = Font(name="宋体", size=10)
    for col, wdt in {"A": 8, "B": 26, "C": 10, "D": 14, "E": 120}.items():
        ws.column_dimensions[col].width = wdt
    wb.save(path)


# ---------------------------------------------------------------- sql build
def build_sql(mapping_inc, points, project, outdir, base, with_collection, stmts_out):
    cfg_cols = ddl_columns("equipment_point_config")
    lines_txt = []
    stmts = []
    seq = [0]
    dev_map = {d["code"]: d for d in points["devices"] if d["code"]}

    def nid():
        seq[0] += 1
        return str(int(time.time() * 1000)) + ("%06d" % seq[0])

    codes = []
    for r in mapping_inc:
        if r["设备编号"] not in codes:
            codes.append(r["设备编号"])
    codes = [c for c in codes if c]

    lines_txt.append("-- 设备点位配置导入SQL  项目:%s  生成:%s  数据源:%s"
                     % (project.get("project", ""), time.strftime("%Y-%m-%d %H:%M"), base))
    lines_txt.append("-- 目标表: equipment_point_config（业务配置表） 幂等: 按 eqp_code 先删后插")
    lines_txt.append("-- 导入前建议备份:")
    lines_txt.append("--   SELECT * FROM equipment_point_config WHERE eqp_code IN (%s);"
                     % ",".join(sq(c) for c in codes))
    lines_txt.append("")
    lines_txt.append("START TRANSACTION;")
    all_ids = []
    for code in codes:
        rows = [r for r in mapping_inc if r["设备编号"] == code]
        ln = resolve_line(project, code)
        fid = ln.get("factory_module_id") if ln else None
        if ln is None:
            stmts.append({"序号": len(stmts) + 1, "目标表": "⚠", "操作": "产线未匹配", "设备编号": code,
                          "SQL语句": "设备 %s 未匹配产线(factory_module_id 将为 NULL)" % code})
        vals = []
        ids = []
        for r in rows:
            i = nid()
            ids.append(i)
            v = {"id": i, "eqp_code": code, "variable": r["数采点位"],
                 "description": r["点位名称"], "type": r["点位类型"] or None,
                 "start_signal": r["启动信号"] or None, "end_signal": r["结束信号"] or None,
                 "fault_signal": r["故障信号"] or None, "relevance_eqp_code": code,
                 "pointclass": r["采集分类"] or None, "factory_module_id": fid,
                 "is_write_value": "0"}
            row_vals = ", ".join(sq(v.get(c)) for c in cfg_cols)
            vals.append("(%s)" % row_vals)
        all_ids.extend(ids)
        lines_txt.append("")
        lines_txt.append("-- %s %s (%d 点)" % (code, dev_map.get(code, {}).get("name", ""), len(rows)))
        lines_txt.append("DELETE FROM equipment_point_config WHERE eqp_code = %s;" % sq(code))
        lines_txt.append("INSERT INTO `equipment_point_config` (%s) VALUES"
                         % ", ".join("`%s`" % c for c in cfg_cols))
        lines_txt.append(",\n".join(vals) + ";")
        stmts.append({"序号": len(stmts) + 1, "目标表": "equipment_point_config", "操作": "DELETE",
                      "设备编号": code, "SQL语句": lines_txt[-2]})
        stmts.append({"序号": len(stmts) + 1, "目标表": "equipment_point_config", "操作": "INSERT",
                      "设备编号": code, "SQL语句": "INSERT INTO `equipment_point_config` ... VALUES(...%d行)" % len(rows)})
    lines_txt.append("")
    lines_txt.append("COMMIT;")

    if with_collection:
        plc_cols = ddl_columns("equipment_plc")
        plp_cols = ddl_columns("equipment_plc_point")
        port_map = project.get("plc_type_by_port") or {}
        defaults = project.get("defaults") or {}
        lines_txt.append("")
        lines_txt.append("-- ============ 采集层(--with-collection) ============")
        for code in codes:
            d = dev_map.get(code)
            if not d:
                continue
            port = d["port"] or defaults.get("port", "")
            i = nid()
            v = {"id": i, "eqp_code": code, "eqp_name": d["name"],
                 "plc_type": port_map.get(str(port), None), "plc_ip": d["ip"],
                 "plc_port": port or None, "iscollection": "1"}
            lines_txt.append("INSERT INTO `equipment_plc` (%s) VALUES (%s);"
                             % (", ".join("`%s`" % c for c in plc_cols),
                                ", ".join(sq(v.get(c)) for c in plc_cols)))
            stmts.append({"序号": len(stmts) + 1, "目标表": "equipment_plc", "操作": "INSERT",
                          "设备编号": code, "SQL语句": "INSERT INTO `equipment_plc` ... (%s)" % code})
            for r in [x for x in mapping_inc if x["设备编号"] == code]:
                p = next((pp for pp in d["points"] if pp["name"] == r["源点位名称"]), {})
                i2 = nid()
                v2 = {"id": i2, "eqp_code": code, "variable": r["数采点位"],
                      "description": r["点位名称"], "pointclass": r["采集分类"] or None,
                      "mbaddress": (p.get("modbus_addr") or p.get("plc_addr") or None),
                      "vlength": str(p.get("span") or 1), "ratio": "1"}
                lines_txt.append("INSERT INTO `equipment_plc_point` (%s) VALUES (%s);"
                                 % (", ".join("`%s`" % c for c in plp_cols),
                                    ", ".join(sq(v2.get(c)) for c in plp_cols)))
            stmts.append({"序号": len(stmts) + 1, "目标表": "equipment_plc_point", "操作": "INSERT",
                          "设备编号": code, "SQL语句": "INSERT INTO `equipment_plc_point` ... (%s, %d点)"
                          % (code, len([x for x in mapping_inc if x["设备编号"] == code]))})

    sql_path = os.path.join(outdir, "设备点位配置SQL_%s.sql" % project.get("project", ""))
    with open(sql_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines_txt) + "\n")
    rb = ["-- 回滚脚本: 撤销本次导入插入的配置行", "-- 注意: 若导入前库中已存在这些设备的旧配置（本次 DELETE 已移除），",
          "-- 请改用导入前备份恢复，或执行上一次生成的 rollback。",
          "START TRANSACTION;"]
    for i in range(0, len(all_ids), 500):
        rb.append("DELETE FROM equipment_point_config WHERE id IN (%s);"
                  % ",".join(sq(x) for x in all_ids[i:i + 500]))
    rb.append("COMMIT;")
    rb_path = os.path.join(outdir, "设备点位配置SQL_%s_rollback.sql" % project.get("project", ""))
    with open(rb_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rb) + "\n")
    return sql_path, rb_path, stmts


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("points_json", help="parse_input.py 产出的 points.json")
    ap.add_argument("--mapping", default=None, help="点位语义映射表 mapping.csv")
    ap.add_argument("--project", default=None, help="项目配置 project.yaml")
    ap.add_argument("-o", "--outdir", default=None)
    ap.add_argument("--skeleton", action="store_true", help="生成映射表骨架")
    ap.add_argument("--excel-only", action="store_true")
    ap.add_argument("--with-collection", action="store_true")
    ap.add_argument("--sql-excel", action="store_true")
    args = ap.parse_args()

    with open(args.points_json, encoding="utf-8") as f:
        points = json.load(f)
    vocab = load_csv(VOCAB_CSV)
    dict_values = {r["点位类型值"] for r in load_csv(DICT_CSV) if r["点位类型值"]}
    project = {}
    if args.project:
        project = load_yaml_min(open(args.project, encoding="utf-8").read())

    outdir = args.outdir or os.path.dirname(os.path.abspath(args.points_json))
    os.makedirs(outdir, exist_ok=True)
    proj_name = (project.get("project") or
                 os.path.splitext(os.path.basename(args.points_json))[0]).strip()
    base = os.path.basename(args.points_json)

    if args.skeleton:
        out_csv = args.mapping or os.path.join(outdir, "点位语义映射表_%s.csv" % proj_name)
        build_skeleton(points, vocab, out_csv)
        return

    if not args.mapping:
        raise SystemExit("缺少 --mapping 映射表（先用 --skeleton 生成，确认后传入）")
    mapping_rows = load_csv(args.mapping)
    show_all = set(project.get("show_all_eqp") or [])
    for r in mapping_rows:
        r["产线"] = (resolve_line(project, r["设备编号"]) or {}).get("name", "")
        if r["设备编号"] in show_all:
            r["采集分类"] = "show"  # 项目级: 整机所有点位均展示（库真源惯例，如单机展示设备）

    warns, inc = validate(mapping_rows, points, project, dict_values)

    xlsx_path = os.path.join(outdir, "设备点位配置表_%s.xlsx" % proj_name)
    write_excel(xlsx_path, inc, warns, project)
    print("Excel: %s (%d 行)" % (xlsx_path, len(inc)))

    if not args.excel_only:
        sql_path, rb_path, stmts = build_sql(inc, points, project, outdir, base,
                                             args.with_collection, None)
        print("SQL:   %s" % sql_path)
        print("回滚:  %s" % rb_path)
        if args.sql_excel:
            se = os.path.join(outdir, "SQL语句清单_%s.xlsx" % proj_name)
            write_sql_excel(se, stmts)
            print("SQL清单: %s" % se)

    print("校验: %d 条警告" % len(warns))
    for w in warns:
        print("  [%s] %s: %s" % (w["级别"], w["检查项"], w["说明"]))


if __name__ == "__main__":
    main()
