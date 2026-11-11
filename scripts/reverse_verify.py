#!/usr/bin/env python3
"""强推倒算验证：每一条线都必须能被标注真值唯一推出，否则判定不通过。

这条门禁和前面对账脚本的分工：

  axis_check.py   回答「标注在图上找不找得到」（A 向）和「图上长度像不像标注」（B 向）
  reverse_verify  回答「这条线凭什么是这个位置、这个长度」

两个问题的区别就是上一轮翻车的根源。当时的图 A 向 100% 命中、B 向也能解释大半，
照样有 14 处断头，因为对账只检查数值，不检查一根线是怎么被推出来的。

判定三态：

  PROVEN    坐标或长度直接落在标注真值上，或落在有旁证的墙皮偏移上
  DERIVED   本身无标注，但两端都接在已证明的线上，位置由闭合约束唯一确定
  UNPROVEN  推不出来。有一条就不通过。

用法：

    python reverse_verify.py --entities temp/self.json --spec temp/spec.json --outdir temp

退出码：0 通过（UNPROVEN 为 0）；1 不通过；2 参数或数据缺失。
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

TOL = 0.6


def load_lines(path):
    d = json.load(open(path, encoding="utf-8"))
    rs = d["lines"] if isinstance(d, dict) else d
    out = []
    for x in rs:
        s, e = x["s"], x["e"]
        o = "H" if abs(s[1] - e[1]) <= TOL else ("V" if abs(s[0] - e[0]) <= TOL else "D")
        out.append({
            "s": (float(s[0]), float(s[1])),
            "e": (float(e[0]), float(e[1])),
            "layer": x.get("layer", ""),
            "o": o,
            "len": abs(e[0] - s[0]) + abs(e[1] - s[1]),
        })
    return d, out


def anchors(spec):
    """从 spec 取已确认的坐标网格。walls_x/walls_y 是绝对坐标，不是间距。"""
    gx = sorted(float(v) for v in spec.get("walls_x", []))
    gy = sorted(float(v) for v in spec.get("walls_y", []))
    return gx, gy


def offsets(spec, lines):
    """允许的墙皮偏移，必须成对出现才算数。

    单独一条偏移线可以随便画，成对出现才说明那是一道有厚度的墙。
    不给旁证就放行，等于把 +40 私移那类错误洗成合法。
    """
    base = [float(v) for v in spec.get("face_offsets", [])]
    cnt = Counter()
    gx, gy = anchors(spec)
    for x in lines:
        if x["o"] == "V":
            pool = gx
            v = x["s"][0]
        elif x["o"] == "H":
            pool = gy
            v = x["s"][1]
        else:
            continue
        for a in pool:
            d = round(abs(v - a), 2)
            if 0 < d <= 300:
                cnt[d] += 1
    ok = set()
    for d in base:
        for k in cnt:
            if abs(k - d) <= TOL and cnt[k] >= 2:
                ok.add(k)
    return ok, cnt


def on_seg(p, x):
    x1, y1 = x["s"]
    x2, y2 = x["e"]
    if abs(x1 - x2) <= TOL:
        return abs(p[0] - x1) <= TOL and min(y1, y2) - TOL <= p[1] <= max(y1, y2) + TOL
    if abs(y1 - y2) <= TOL:
        return abs(p[1] - y1) <= TOL and min(x1, x2) - TOL <= p[0] <= max(x1, x2) + TOL
    return False


def endpoints(x):
    return [x["s"], x["e"]]


def prove_coord(v, pool, offs):
    """坐标能否由网格坐标直接解释。"""
    for a in pool:
        if abs(v - a) <= TOL:
            return ("轴位", round(a, 2), 0.0)
    for a in pool:
        for d in offs:
            for sgn in (1, -1):
                if abs(v - (a + sgn * d)) <= TOL:
                    return ("墙皮偏移", round(a, 2), sgn * d)
    return None


def prove_len(L, vals, thick):
    for v in vals:
        if abs(L - v) <= max(TOL, 1.0):
            return ("标注值", v)
    for a in vals:
        for b in vals:
            if abs(L - (a + b)) <= max(TOL, 1.0):
                return ("标注和", a + b)
            if abs(L - abs(a - b)) <= max(TOL, 1.0):
                return ("标注差", abs(a - b))
    for t in thick:
        for v in vals:
            if abs(L - (v - t)) <= max(TOL, 1.0):
                return ("标注扣墙厚%d" % t, v - t)
    return None


def anchor_check(spec, tol):
    """双端锚定：链从左端累加、从右端累加，两组坐标必须逐点吻合。

    只从一头加，中间段一旦不是同向排布，整段就整体错位，而链仍然闭合。
    实测案例：1500 那段其实含一道 100 隔墙，拆成 710 + 790 才对齐，
    只从左边累加会把隔墙算到别处，图上那道墙就变成没有标注支撑的悬空线。
    """
    rs = []
    for key, name in (("chain_x", "H"), ("chain_y", "V")):
        c = spec.get(key)
        if not c:
            continue
        segs = [float(v) for v in c]
        total = sum(segs)
        left = [0.0]
        for s in segs:
            left.append(round(left[-1] + s, 2))
        right = [total]
        for s in reversed(segs):
            right.append(round(right[-1] - s, 2))
        right = list(reversed(right))
        bad = [(i, a, b) for i, (a, b) in enumerate(zip(left, right)) if abs(a - b) > tol]
        rs.append({
            "axis": name,
            "segs": len(segs),
            "total": round(total, 2),
            "从右锚定": len(bad) == 0,
            "分歧点": [{"第几段": i, "左推": a, "右推": b, "差": round(a - b, 2)} for i, a, b in bad],
        })
    return rs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entities", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--tol", type=float, default=TOL)
    a = ap.parse_args()
    for p in (a.entities, a.spec):
        if not os.path.exists(p):
            print("找不到文件：%s" % p)
            sys.exit(2)

    _, lines = load_lines(a.entities)
    spec = json.load(open(a.spec, encoding="utf-8"))
    gx, gy = anchors(spec)
    offs, offcnt = offsets(spec, lines)
    thick = [int(v) for v in spec.get("wall_thick_list", [100, 120, 200, 240, 370])]

    vals = []
    for t in spec.get("ann_axis", []):
        vals.append(float(str(t).split(":")[0]))
    for t in spec.get("ann_line", []):
        vals.append(float(str(t).split(":")[0]))
    for w in ("walls_x", "walls_y"):
        xs = sorted(float(v) for v in spec.get(w, []))
        for p, q in zip(xs, xs[1:]):
            vals.append(round(q - p, 2))
    vals = sorted(set(round(v, 2) for v in vals if v >= 100))

    # 先判坐标，再判长度，最后判是否接在已证线上
    rows = []
    for x in lines:
        if x["o"] == "D":
            rows.append({"line": x, "state": "UNPROVEN", "why": "非正交线，方法不覆盖"})
            continue
        v = x["s"][0] if x["o"] == "V" else x["s"][1]
        pool = gx if x["o"] == "V" else gy
        c = prove_coord(v, pool, offs)
        L = prove_len(x["len"], vals, thick)
        if c and L:
            why = "坐标=%s%.2f%+.0f 长度=%s%.0f" % (c[0], c[1], c[2], L[0], L[1])
            rows.append({"line": x, "state": "PROVEN", "why": why})
        elif c:
            rows.append({"line": x, "state": "PROVEN", "why": "坐标=%s%.2f%+.0f 长度待补" % (c[0], c[1], c[2])})
        elif L:
            rows.append({"line": x, "state": "UNPROVEN", "why": "长度可解释但坐标无处落（%s）" % L[0]})
        else:
            rows.append({"line": x, "state": "UNPROVEN", "why": "坐标与长度均无标注支撑"})

    # DERIVED：两端点都接在 PROVEN 线上则继承
    proven = [r for r in rows if r["state"] == "PROVEN"]
    for r in rows:
        if r["state"] != "UNPROVEN":
            continue
        x = r["line"]
        hits = []
        for p in endpoints(x):
            for q in proven:
                if q["line"] is x:
                    continue
                if any(abs(p[0] - t[0]) <= a.tol and abs(p[1] - t[1]) <= a.tol for t in endpoints(q["line"])) or on_seg(p, q["line"]):
                    hits.append(q)
                    break
        if len(hits) >= 2:
            r["state"] = "DERIVED"
            r["why"] = "两端接于已证线，位置由闭合约束继承"

    # 断头
    dangling = []
    for i, x in enumerate(lines):
        for p in endpoints(x):
            ok = False
            for j, q in enumerate(lines):
                if i == j:
                    continue
                if any(abs(p[0] - t[0]) <= a.tol and abs(p[1] - t[1]) <= a.tol for t in endpoints(q)) or on_seg(p, q):
                    ok = True
                    break
            if not ok:
                dangling.append({"端点": [round(p[0], 2), round(p[1], 2)], "图层": x["layer"]})

    anc = anchor_check(spec, a.tol)
    cnt = Counter(r["state"] for r in rows)
    total = len(rows)
    want = total
    passed = cnt["PROVEN"] + cnt["DERIVED"]
    ok = (cnt["UNPROVEN"] == 0) and (not dangling) and all(z["从右锚定"] for z in anc)

    os.makedirs(a.outdir, exist_ok=True)
    out = os.path.join(a.outdir, "reverse_verify.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("强推倒算验证\n\n")
        f.write("线段 %d 条\n" % total)
        f.write("  直接可证 PROVEN  %d\n" % cnt["PROVEN"])
        f.write("  闭合可推 DERIVED %d\n" % cnt["DERIVED"])
        f.write("  推不出来 UNPROVEN %d\n" % cnt["UNPROVEN"])
        f.write("  覆盖率 %.1f%%（要求 100%%）\n\n" % (100.0 * passed / total if total else 0))
        f.write("=== 双端锚定\n")
        for z in anc:
            f.write("  %s 向 %d 段 合计 %.2f  双端吻合=%s\n" % (z["axis"], z["segs"], z["total"], "是" if z["从右锚定"] else "否"))
            for b in z["分歧点"][:6]:
                f.write("    第%d段 左推%.2f 右推%.2f 差%.2f\n" % (b["第几段"], b["左推"], b["右推"], b["差"]))
        f.write("\n=== 断头 %d 处\n" % len(dangling))
        for d in dangling:
            f.write("  (%.2f, %.2f) %s\n" % (d["端点"][0], d["端点"][1], d["图层"]))
        f.write("\n=== 推不出来的线 %d 条\n" % cnt["UNPROVEN"])
        for r in rows:
            if r["state"] == "UNPROVEN":
                x = r["line"]
                f.write("  %-9s %s %s  (%0.2f,%0.2f)-(%0.2f,%0.2f) 长%.2f  %s\n" % (
                    x["layer"], x["o"], "", x["s"][0], x["s"][1], x["e"][0], x["e"][1], x["len"], r["why"]))
        f.write("\n=== 墙皮偏移旁证\n")
        for d in sorted(offcnt):
            f.write("  %s mm 出现 %d 次%s\n" % (d, offcnt[d], "（成对，可用）" if d in offs else ""))
        f.write("\n结论：%s\n" % ("通过（100% 倒算可证）" if ok else "不通过"))
    print(open(out, encoding="utf-8").read())
    print("已写入 %s" % out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
