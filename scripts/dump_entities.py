#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段3：从 DXF/DWG 抽出所有线段，写成 entities.json。

策略
  1. 给 .dxf → ezdxf 直读，不依赖 AutoCAD
  2. 给 .dwg → 若装了 AutoCAD 则用 win32com 另存为 DXF 再读；否则报错让用户先转格式

输出结构
  {"source": ..., "lines": [{"s":[x,y], "e":[x,y], "layer":...}], "bbox": [x0,y0,x1,y1]}

用法
  python dump_entities.py --file 平面图.dwg --out temp/entities.json
  python dump_entities.py --file 平面图.dxf --out temp/entities.json --layers WALL,PUB_WALL
"""
import argparse
import json
import math
import os
import sys


def dwg_to_dxf(path, outdir):
    try:
        import win32com.client as wc
    except ImportError:
        sys.exit("读 DWG 需要 pywin32 + 本机 AutoCAD。请先手动另存为 DXF，或用 --file 传 .dxf。")
    out = os.path.join(outdir, os.path.splitext(os.path.basename(path))[0] + "_convert.dxf")
    app = wc.Dispatch("AutoCAD.Application")
    app.Visible = False
    doc = app.Documents.Open(os.path.abspath(path))
    doc.SaveAs(os.path.abspath(out), 61)  # 61 = ac2013_dxf
    doc.Close(False)
    print("dwg -> dxf:", out)
    return out


def lw_points(lw):
    try:
        return [(p[0], p[1]) for p in lw.get_points("xy")]
    except TypeError:
        return [(p[0], p[1]) for p in lw.get_points()]


def collect(dxf_path, layers=None):
    import ezdxf
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    want = {s.strip().upper() for s in layers.split(",")} if layers else None
    lines = []

    def keep(e):
        return want is None or e.dxf.layer.upper() in want

    def push(a, b, layer):
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 0.5:
            return
        lines.append({"s": [float(a[0]), float(a[1])],
                      "e": [float(b[0]), float(b[1])], "layer": layer})

    for e in msp:
        t = e.dxftype()
        if not keep(e):
            continue
        if t == "LINE":
            push(e.dxf.start, e.dxf.end, e.dxf.layer)
        elif t == "LWPOLYLINE":
            pts = lw_points(e)
            for a, b in zip(pts, pts[1:]):
                push(a, b, e.dxf.layer)
            if e.closed and len(pts) > 2:
                push(pts[-1], pts[0], e.dxf.layer)
        elif t == "POLYLINE":
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            for a, b in zip(pts, pts[1:]):
                push(a, b, e.dxf.layer)
        elif t == "INSERT":
            try:
                for sub in e.virtual_entities():
                    if sub.dxftype() == "LINE":
                        push(sub.dxf.start, sub.dxf.end, e.dxf.layer)
                    elif sub.dxftype() == "LWPOLYLINE":
                        pts = lw_points(sub)
                        for a, b in zip(pts, pts[1:]):
                            push(a, b, e.dxf.layer)
            except Exception:
                pass
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--layers", default="", help="只取这些图层，逗号分隔；不填取全部")
    args = ap.parse_args()

    path = os.path.abspath(args.file)
    outdir = os.path.dirname(os.path.abspath(args.out)) or "."
    os.makedirs(outdir, exist_ok=True)

    dxf = path
    if path.lower().endswith(".dwg"):
        dxf = dwg_to_dxf(path, outdir)

    lines = collect(dxf, args.layers)
    xs = [p for l in lines for p in (l["s"][0], l["e"][0])]
    ys = [p for l in lines for p in (l["s"][1], l["e"][1])]
    bbox = [min(xs), min(ys), max(xs), max(ys)] if lines else [0, 0, 0, 0]

    json.dump({"source": path, "bbox": bbox, "lines": lines},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print("线段 %d 条 -> %s" % (len(lines), args.out))
    print("包围盒 X %.0f..%.0f (宽%.0f)  Y %.0f..%.0f (高%.0f)" % (
        bbox[0], bbox[2], bbox[2] - bbox[0], bbox[1], bbox[3], bbox[3] - bbox[1]))


if __name__ == "__main__":
    main()
