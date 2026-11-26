# -*- coding: utf-8 -*-
"""阶段4验收工具: 将生成的设备点位配置SQL与 mysqldump 真源逐字段比对。

用法:
  python compare_with_dump.py <dump.sql> <生成.sql> [--table equipment_point_config]
                              [--eqp M160102,M1613] [--out 报告.txt]

规则:
  - 按生成SQL中出现的 eqp_code 过滤真源行；生成侧多出的行标"新增(库中无)"。
  - id 不参与比对（生成时新分配19位）；其余列必须完全一致。
  - 支持 mysqldump 单行扩展INSERT 与 生成的多行带列清单INSERT 两种格式。
退出码: 0=通过 1=存在差异。
"""
import re, sys, argparse

COLS = ["id","eqp_id","eqp_code","point_code","point_name","variable","description","type",
        "min_value","max_value","start_signal","end_signal","fault_signal","relevance_eqp_code",
        "point_class","pointclass","factory_module_id","converter_rule_id","valve_eqp_code",
        "valve_variable","data_type","order_num","unit","related_point_id","value_type",
        "tenant_id","is_write_value"]
SKIP = {"id"}


def tokenize_values(s):
    rows, cur, buf, i, inq, depth = [], [], "", 0, False, 0
    while i < len(s):
        c = s[i]
        if inq:
            if c == "'":
                if i + 1 < len(s) and s[i + 1] == "'":
                    buf += "'"; i += 2; continue
                inq = False; i += 1; continue
            buf += c; i += 1; continue
        if c == "'":
            inq = True; i += 1; continue
        if c == "(":
            depth += 1
            if depth == 1:
                cur, buf = [], ""; i += 1; continue
        if c == ")":
            depth -= 1
            if depth == 0:
                cur.append(buf.strip() or None); rows.append(cur); i += 1; continue
        if c == "," and depth == 1:
            cur.append(buf.strip() or None); buf = ""; i += 1; continue
        buf += c; i += 1
    return rows


def norm(v):
    return None if (v is None or v == "NULL" or v == "") else v


def extract(path, table, eqp_filter=None):
    rows = []
    text = open(path, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r"INSERT INTO `%s`[^;]*?VALUES([^;]*);" % table, text, re.S):
        for r in tokenize_values(m.group(1)):
            r = [norm(x) for x in r]
            if eqp_filter is None or (len(r) > 2 and r[2] in eqp_filter):
                rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump_sql", help="mysqldump 真源文件")
    ap.add_argument("gen_sql", help="生成的SQL文件")
    ap.add_argument("--table", default="equipment_point_config")
    ap.add_argument("--eqp", default=None, help="逗号分隔设备编号; 默认取生成SQL中出现的全部")
    ap.add_argument("--out", default=None, help="报告输出路径(可选)")
    args = ap.parse_args()

    if args.eqp:
        targets = {x.strip() for x in args.eqp.split(",") if x.strip()}
    else:
        text = open(args.gen_sql, encoding="utf-8", errors="replace").read()
        targets = set(re.findall(r"'([A-Za-z][\w-]*)'", text))
        # 收窄: 只保留形如设备编号的值(出现于 eqp_code 位), 再由比对本身兜底
        targets = set()
        for r in extract(args.gen_sql, args.table):
            if len(r) > 2 and r[2]:
                targets.add(r[2])

    db_rows = extract(args.dump_sql, args.table, targets)
    gen_rows = extract(args.gen_sql, args.table)
    lines = ["真源行: %d, 生成行: %d, 比对设备: %s" % (len(db_rows), len(gen_rows),
             ",".join(sorted(targets)) or "(无)")]
    db_map, gen_map = {}, {}
    for r in db_rows:
        db_map.setdefault((r[2], r[5]), []).append(r)
    for r in gen_rows:
        gen_map[(r[2], r[5])] = r
    diffs = 0
    for key in sorted(set(db_map) | set(gen_map)):
        d, g = db_map.get(key), gen_map.get(key)
        if d and not g:
            lines.append("✗ 仅在真源: %s %s (%s)" % (key[0], key[1], d[0][6]))
            diffs += 1
            continue
        if g and not d:
            lines.append("✓ 新增(库中无): %s %s %s" % (key[0], key[1], g[6]))
            continue
        d = d[0]
        for ci, col in enumerate(COLS):
            if col in SKIP or ci >= len(d) or ci >= len(g):
                continue
            if (d[ci] or None) != (g[ci] or None):
                lines.append("✗ %s %s [%s] DB=%r != GEN=%r" % (key[0], key[1], col, d[ci], g[ci]))
                diffs += 1
    if diffs == 0:
        lines.append("")
        lines.append("✅ 验收通过: 全部可比字段一致 (id 为新生成19位)")
    else:
        lines.append("")
        lines.append("❌ %d 处差异，需修正映射表后重建" % diffs)
    report = "\n".join(lines)
    print(report)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(report + "\n")
    sys.exit(0 if diffs == 0 else 1)


if __name__ == "__main__":
    main()
