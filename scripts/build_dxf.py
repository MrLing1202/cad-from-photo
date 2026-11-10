#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段7：由轴网规格生成 DXF 线稿。坐标从标注累加得来，不照抄图片像素。

spec.json
{
  "walls_x": [0, 1600, 4400, 7200],
  "walls_y": [0, 2800, 4950],
  "thickness": 200,
  "wall_thickness": {"x": [240, 200, 200, 240], "y": [240, 200, 240]},
  "openings": [
    {"axis": "x", "at": 1600, "from": 600, "to": 1500, "type": "door"},
    {"axis": "y", "at": 2800, "from": 1200, "to": 2400, "type": "window"}
  ],
  "dim": {"enabled": true, "offset": 1200}
}

用法
  python build_dxf.py --spec temp/spec.json --out output/平面图.dxf
"""
import argparse
import json
import os

import ezdxf
from ezdxf.enums import TextEntityAlignment

DIM_STYLE = "EZDXF"


def thickness_of(spec, axis, idx, n):
    t = spec.get("thickness", 200)
    wt = spec.get("wall_thickness", {}).get(axis)
    if wt:
        if isinstance(wt, (int, float)):
            return float(wt)
        if len(wt) == n:
            return float(wt[idx])
    return float(t)


def split_spans(lo, hi, cuts):
    """在 [lo,hi] 上挖掉 cuts 区间。"""
    spans = [(lo, hi)]
    for c0, c1 in sorted(cuts):
        nxt = []
        for a, b in spans:
            if c1 <= a or c0 >= b:
                nxt.append((a, b))
                continue
            if c0 > a:
                nxt.append((a, c0))
            if c1 < b:
                nxt.append((c1, b))
        spans = nxt
    return [(a, b) for a, b in spans if b - a > 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec = json.load(open(args.spec, encoding="utf-8"))
    wx = [float(v) for v in spec["walls_x"]]
    wy = [float(v) for v in spec["walls_y"]]
    if not wx or not wy:
        raise SystemExit("walls_x / walls_y 不能为空")

    x0, x1 = min(wx), max(wx)
    y0, y1 = min(wy), max(wy)

    doc = ezdxf.new("R2013", setup=True)
    msp = doc.modelspace()
    for name, color in (("WALL", 7), ("OPENING", 4), ("DIM", 3), ("AXIS", 8)):
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    openings = spec.get("openings", [])

    # 外墙外皮：用相邻外墙的厚度外扩，墙线才能在转角处自然闭合
    tx0 = thickness_of(spec, "x", 0, len(wx))
    tx1 = thickness_of(spec, "x", len(wx) - 1, len(wx))
    ty0 = thickness_of(spec, "y", 0, len(wy))
    ty1 = thickness_of(spec, "y", len(wy) - 1, len(wy))
    v_lo, v_hi = y0 - ty0 / 2, y1 + ty1 / 2      # 垂直墙的 Y 范围
    h_lo, h_hi = x0 - tx0 / 2, x1 + tx1 / 2      # 水平墙的 X 范围

    # ---- 垂直墙（X = wx[i]）
    for i, xi in enumerate(wx):
        t = thickness_of(spec, "x", i, len(wx))
        raw = [(float(o["from"]), float(o["to"])) for o in openings
               if o["axis"].lower() == "x" and abs(float(o["at"]) - xi) <= 15]
        for a, b in split_spans(v_lo, v_hi, raw):
            msp.add_line((xi - t / 2, a), (xi - t / 2, b), dxfattribs={"layer": "WALL"})
            msp.add_line((xi + t / 2, a), (xi + t / 2, b), dxfattribs={"layer": "WALL"})

    # ---- 水平墙（Y = wy[j]）
    for j, yj in enumerate(wy):
        t = thickness_of(spec, "y", j, len(wy))
        raw = [(float(o["from"]), float(o["to"])) for o in openings
               if o["axis"].lower() == "y" and abs(float(o["at"]) - yj) <= 15]
        for a, b in split_spans(h_lo, h_hi, raw):
            msp.add_line((a, yj - t / 2), (b, yj - t / 2), dxfattribs={"layer": "WALL"})
            msp.add_line((a, yj + t / 2), (b, yj + t / 2), dxfattribs={"layer": "WALL"})

    # ---- 洞口符号
    for o in openings:
        w = float(o["to"]) - float(o["from"])
        if o["axis"].lower() == "x":
            xi, a = float(o["at"]), float(o["from"])
            b = float(o["to"])
            if o.get("type") == "door":
                msp.add_line((xi, a), (xi, a + min(w, 900)), dxfattribs={"layer": "OPENING"})
                msp.add_arc((xi, a), min(w, 900), 0, 90, dxfattribs={"layer": "OPENING"})
            else:
                for dx in (-60, 60):
                    msp.add_line((xi + dx, a), (xi + dx, b), dxfattribs={"layer": "OPENING"})
        else:
            yj, a, b = float(o["at"]), float(o["from"]), float(o["to"])
            if o.get("type") == "door":
                msp.add_line((a, yj), (a + min(w, 900), yj), dxfattribs={"layer": "OPENING"})
                msp.add_arc((a, yj), min(w, 900), 0, 90, dxfattribs={"layer": "OPENING"})
            else:
                for dy in (-60, 60):
                    msp.add_line((a, yj + dy), (b, yj + dy), dxfattribs={"layer": "OPENING"})

    # ---- 轴网标注
    dimcfg = spec.get("dim", {})
    if dimcfg.get("enabled", True):
        off = float(dimcfg.get("offset", 1200))
        style = DIM_STYLE if DIM_STYLE in doc.dimstyles else "Standard"

        def dim(p1, p2, base, ang):
            msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=ang,
                               dimstyle=style,
                               dxfattribs={"layer": "DIM"}).render()

        yb = y0 - off
        for a, b in zip(wx, wx[1:]):
            dim((a, y0), (b, y0), (a, yb), 0)
        dim((wx[0], y0), (wx[-1], y0), (wx[0], y0 - off * 2.0), 0)

        xb = x1 + off
        for a, b in zip(wy, wy[1:]):
            dim((x1, a), (x1, b), (xb, a), 90)
        dim((x1, wy[0]), (x1, wy[-1]), (x1 + off * 2.0, wy[0]), 90)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    doc.saveas(args.out)
    print("墙轴 X %d 道 / Y %d 道" % (len(wx), len(wy)))
    print("洞口 %d 处" % len(openings))
    print("范围 %.0f x %.0f mm -> %s" % (x1 - x0, y1 - y0, args.out))
    print("下一步：把产出的 DXF 走 dump_entities + axis_check 自检，A向命中率须 100%")


if __name__ == "__main__":
    main()
