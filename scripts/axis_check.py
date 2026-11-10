

import argparse
import itertools
import json
import math
import os

KEY_TOL = 12.0
GAP_TOL = 400.0
PT_TOL = 6.0
PAIR_MAX = 300.0
PAIR_MIN = 20.0
OVERLAP = 0.75
THICKS = (50, 60, 80, 100, 120, 125, 150, 160, 180, 200, 220, 240, 250, 300)


def close_to(v, pool, rel=0.15, abs_tol=15):
    return any(abs(v - t) <= max(abs_tol, t * rel) for t in pool)


def load_segments(entities_path):
    data = json.load(open(entities_path, encoding="utf-8"))
    H, V = [], []
    for ln in data.get("lines", []):
        (x1, y1), (x2, y2) = ln["s"], ln["e"]
        if math.hypot(x2 - x1, y2 - y1) < 1:
            continue
        if abs(y1 - y2) < abs(x1 - x2):
            H.append((min(x1, x2), max(x1, x2), (y1 + y2) / 2.0))
        else:
            V.append((min(y1, y2), max(y1, y2), (x1 + x2) / 2.0))
    return data, H, V


def merge_wall_pairs(segs):
    segs = sorted(segs, key=lambda s: s[2])
    used = [False] * len(segs)
    out = []
    for i, s in enumerate(segs):
        if used[i]:
            continue
        matched = False
        for j in range(i + 1, len(segs)):
            if used[j]:
                continue
            t = segs[j]
            dk = t[2] - s[2]
            if dk < PAIR_MIN:
                continue
            if dk > PAIR_MAX:
                break
            lo = min(s[1] - s[0], t[1] - t[0])
            ov = min(s[1], t[1]) - max(s[0], t[0])
            if lo > 0 and ov / lo >= OVERLAP:
                used[i] = used[j] = True
                out.append((min(s[0], t[0]), max(s[1], t[1]), (s[2] + t[2]) / 2.0))
                matched = True
                break
        if not matched:
            used[i] = True
            out.append(s)
    return out


def build_axes(segs):
    segs = sorted(segs, key=lambda s: s[2])
    groups = []
    for s in segs:
        if groups and abs(s[2] - groups[-1][-1][2]) <= KEY_TOL:
            groups[-1].append(s)
        else:
            groups.append([s])
    axes = []
    for g in groups:
        key = sum(x[2] for x in g) / len(g)
        ss = sorted(g, key=lambda s: s[0])
        run = [ss[0]]
        for s in ss[1:]:
            if s[0] - run[-1][1] <= GAP_TOL:
                run.append(s)
            else:
                axes.append({"key": key, "segs": run})
                run = [s]
        axes.append({"key": key, "segs": run})
    return axes


def axis_points(ax):
    pts = []
    for a, b, _ in ax["segs"]:
        pts.extend([a, b])
    pts.sort()
    merged = []
    for p in pts:
        if merged and p - merged[-1] <= PT_TOL:
            continue
        merged.append(p)
    return merged


def axis_distances(ax):
    pts = axis_points(ax)
    out = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            out.append({"len": pts[j] - pts[i], "from": pts[i],
                        "to": pts[j], "axis": ax["key"], "dir": ax["dir"], "kind": "段内"})
    return out


def axis_cross_distances(axes):
    out = []


    for ad, sd in (("H", "V"), ("V", "H")):
        keys = sorted({round(a["key"], 1) for a in axes if a["dir"] == ad})
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                out.append({"len": keys[j] - keys[i], "from": keys[i],
                            "to": keys[j], "axis": None, "dir": sd, "kind": "轴距"})
    return out


def spec_annotations(spec):
    R = []
    for w, d in (("walls_x", "H"), ("walls_y", "V")):
        xs = sorted(float(v) for v in spec.get(w, []))
        for a, b in zip(xs, xs[1:]):
            R.append((round(b - a), d))
        if len(xs) > 1:
            R.append((round(xs[-1] - xs[0]), d))
    for o in spec.get("openings", []):
        R.append((round(float(o["to"]) - float(o["from"])), ""))
    return [(float(v), d) for v, d in R if v >= 100]


def explain_by_ann(L, R, tol):
    for r in R:
        if abs(r - L) <= tol:
            return ("单值", r, abs(r - L))
    for t in (240, 200, 220, 120, 100):
        for r in R:
            if abs(r - (L - t)) <= tol:
                return ("扣墙厚%d" % t, r, abs(r - (L - t)))
    for r1, r2 in itertools.combinations_with_replacement(R, 2):
        if r1 == r2:
            continue
        if abs(r1 + r2 - L) <= tol:
            return ("和", (r1, r2), abs(r1 + r2 - L))
        if abs(abs(r1 - r2) - L) <= tol:
            return ("差", (r1, r2), abs(abs(r1 - r2) - L))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entities", required=True)
    ap.add_argument("--ann", default="", help="轴距类标注（尺寸链/开间进深/总尺寸），逗号分隔")
    ap.add_argument("--ann-line", default="", help="单根线长度类标注，必须同轴段内命中才算对")
    ap.add_argument("--ann-file", default="", help="标注值文件")
    ap.add_argument("--from-spec", default="", help="从 spec.json 自动取标注集（自检用）")
    ap.add_argument("--tol", type=float, default=25.0)
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--dim-line", type=float, default=2000.0, help="只详列不小于此值的标注")
    ap.add_argument("--no-merge", action="store_true", help="关闭墙皮双线合并")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    data, H, V = load_segments(args.entities)
    n_raw = len(H) + len(V)
    if not args.no_merge:
        H, V = merge_wall_pairs(H), merge_wall_pairs(V)

    axes = build_axes(H)
    for a in axes:
        a["dir"] = "H"
    vaxes = build_axes(V)
    for a in vaxes:
        a["dir"] = "V"
    axes += vaxes

    dists = axis_cross_distances(axes)
    for ax in axes:
        dists.extend(axis_distances(ax))

    json.dump({"axes": [{"dir": a["dir"], "key": a["key"],
                         "points": axis_points(a), "nseg": len(a["segs"])} for a in axes],
               "distances": dists},
              open(os.path.join(args.outdir, "axis.json"), "w", encoding="utf-8"),
              ensure_ascii=False)


    ann = []
    for src, kind in ((args.ann, "axis"), (args.ann_line, "line")):
        raw = src.replace("，", ",")
        for t in raw.split(","):
            t = t.strip()
            if not t:
                continue
            d = ""
            if ":" in t:
                t, d = t.split(":", 1)
                d = d.strip().upper()[:1]
            try:
                ann.append((float(t), d if d in ("H", "V") else "", kind))
            except ValueError:
                pass
    auto = False
    if args.from_spec and os.path.exists(args.from_spec):
        ann += [(v, d, "axis") for v, d in
                spec_annotations(json.load(open(args.from_spec, encoding="utf-8")))]
        auto = True
    dedup = {}
    for v, d, k in ann:
        dedup.setdefault(v, [set(), set()])
        dedup[v][0].add(d)
        dedup[v][1].add(k)
    R = sorted(dedup, reverse=True)
    dirs = {v: (set() if "" in ds else ds) for v, (ds, _) in dedup.items()}
    kinds = {v: ("line" if "line" in ks else "axis") for v, (_, ks) in dedup.items()}
    Rdir = [v for v in R if dirs[v]]
    Rfree = [v for v in R if not dirs[v]]

    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    emit("线段 %d 条 → 墙轴 %d 道（水平%d / 垂直%d）  端点距离候选 %d 个%s" % (
        n_raw, len(axes),
        sum(1 for a in axes if a["dir"] == "H"),
        sum(1 for a in axes if a["dir"] == "V"),
        len(dists), "（已做墙皮双线合并）" if not args.no_merge else "（未合并）"))

    if not R:
        emit("\n未提供标注值，只输出轴网。用 --ann 或 --from-spec 再跑一次做对账。")
        open(os.path.join(args.outdir, "report.txt"), "w", encoding="utf-8").write("\n".join(lines))
        return

    emit("\n=== A 向：标注能否在图上找到等长距离")
    stat = {"对": [], "半对": [], "存疑": [], "口径差": [], "缺": []}
    for r in R:
        ok = [d for d in dists if not dirs[r] or d["dir"] in dirs[r]]
        seg = [d for d in ok if d["kind"] == "段内"]
        axd = [d for d in ok if d["kind"] == "轴距"]
        bs = min(seg, key=lambda d: abs(d["len"] - r)) if seg else None
        ba = min(axd, key=lambda d: abs(d["len"] - r)) if axd else None
        ds = abs(bs["len"] - r) if bs else 1e9
        da = abs(ba["len"] - r) if ba else 1e9

        if kinds[r] == "line" and ds > 10:
            tag, hit, dd, kind = "缺", (bs if bs else ba), ds, ""
            stat["缺"].append(r)
            where = ("%s轴 key=%.0f %.0f→%.0f" % (hit["dir"], hit["axis"], hit["from"], hit["to"])
                     if hit and hit.get("kind") == "段内"
                     else "无同轴等长段")
            emit("  %-4s %-8.0f %s 差 %.0f%s" % (
                tag, r, where, dd,
                "（全图另有 %s向 %.0f→%.0f 恰好等值，属数值偶合）" % (
                    ba["dir"], ba["from"], ba["to"])
                if ba is not None and da <= 10 else ""))
            continue
        if ds <= 10:
            tag, hit, dd, kind = "对", bs, ds, "段内"
        elif da <= 10:

            tag = "对" if kinds[r] == "axis" else "半对"
            hit, dd, kind = ba, da, "轴距"
        elif ds <= 50 or da <= 50:
            tag, hit, dd, kind = "存疑", (bs if ds <= da else ba), min(ds, da), ""
        elif min(ds, da) <= 300 and close_to(min(ds, da), THICKS):
            tag, hit, dd, kind = "口径差", (bs if ds <= da else ba), min(ds, da), ""
        else:
            tag, hit, dd, kind = "缺", (bs if ds <= da else ba), min(ds, da), ""
        stat[tag].append(r)
        if r >= args.dim_line or tag in ("缺", "存疑", "半对"):
            if hit is None:
                emit("  %-4s %-8.0f 该方向找不到任何同向线段" % (tag, r))
                continue
            where = ("%s向轴距 %.0f→%.0f" % (hit["dir"], hit["from"], hit["to"])
                     if hit.get("kind") == "轴距"
                     else "%s轴 key=%.0f  %.0f→%.0f" % (hit["dir"], hit["axis"],
                                                       hit["from"], hit["to"]))
            emit("  %-4s %-8.0f 最近 %.0f（%s）差 %.0f" % (tag, r, hit["len"], where, dd))
    emit("  标注 %d 项（轴距类 %d / 单线类 %d / 带方向 %d） → 对 %d / 跨轴 %d / 存疑 %d / 口径差 %d / 缺 %d" % (
        len(R), sum(1 for v in R if kinds[v] == "axis"),
        sum(1 for v in R if kinds[v] == "line"), len(Rdir),
        len(stat["对"]), len(stat["半对"]),
        len(stat["存疑"]), len(stat["口径差"]), len(stat["缺"])))
    for k in ("半对", "存疑", "口径差", "缺"):
        if stat[k]:
            emit("    %s：%s" % (k, [int(x) for x in stat[k]]))
    if stat["半对"]:
        emit("  [!] 跨轴命中只说明数值在全图别处存在，几何未必成立。")
        emit("      典型反例：某道墙的长度 12400 画漏了，但另两道墙的间距恰好也 12400，")
        emit("      对账会判「有」。这类必须回到位置核对，看该方向、该轴段是否真有这根线。")
    if Rfree:
        emit("  [!] %d 项没标方向（%s），这类命中含假阳性，重要尺寸务必标 H/V。"
             % (len(Rfree), [int(x) for x in Rfree[:8]]))

    emit("\n=== B 向：DWG 长度能否由标注解释（单值/两和/两差）")
    C = sorted({round(math.hypot(l["e"][0] - l["s"][0], l["e"][1] - l["s"][1]), 1)
                for l in data["lines"]}, reverse=True)
    C = [x for x in C if x >= 100]
    bad = [L for L in C if explain_by_ann(L, R, args.tol) is None]
    emit("  DWG 长度去重 %d 种（≥100mm），无法解释 %d 种：%s" % (
        len(C), len(bad), [int(x) for x in bad[:20]]))
    if C and len(bad) / len(C) > 0.3 and not auto:
        emit("  [!] 无法解释比例 %.0f%%，大概率是标注集没收全——回去补读图，"
             "不要据此判定 DWG 有凭空尺寸。" % (100.0 * len(bad) / len(C)))

    emit("\n=== 判定口径")
    emit("  ≤10mm              → 对")
    emit("  ≈墙厚或其半（≤300） → 口径差：净空 vs 含墙厚，属正常，不判错")
    emit("  10–50mm            → 存疑：取整或读数误差，需人工看一眼")
    emit("  其余 / 同轴无对应    → 缺 或 画错")
    emit("  数值对 ≠ 位置对：位置需另做像素→世界坐标换算后复核。")

    p = os.path.join(args.outdir, "report.txt")
    open(p, "w", encoding="utf-8").write("\n".join(lines))
    print("\nreport -> " + p)


if __name__ == "__main__":
    main()
