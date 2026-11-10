#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段1：把平面图切成适合视觉模型读标注的小块。

产出（全部写入 --outdir）：
  full_small.png      整图缩略，看布局
  zone_r{r}c{c}.png   九宫格，每块放大2倍，用于逐块读数字
  edge_top/bottom/left/right.png  四边缘条，补读被裁掉的总尺寸
  key_*.png           指定关键数字的定点复核块（需 --points）

用法：
  python read_annotations.py --image 90179.jpg --outdir temp
  python read_annotations.py --image 90179.jpg --outdir temp --points "10600:1952:150;12400:1952:2520"
  --points 格式  数字:像素x:像素y[;数字:像素x:像素y...]
"""
import argparse
import os

from PIL import Image


def ensure(d):
    os.makedirs(d, exist_ok=True)
    return d


def up(im, scale):
    return im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="参考图路径")
    ap.add_argument("--outdir", required=True, help="中间产物目录")
    ap.add_argument("--grid", default="3x3", help="分区，默认 3x3")
    ap.add_argument("--scale", type=float, default=2.0, help="分区放大倍数")
    ap.add_argument("--points", default="", help="关键数字定点复核：值:x:y;...")
    args = ap.parse_args()

    out = ensure(args.outdir)
    im = Image.open(args.image).convert("RGB")
    W, H = im.size
    print("image:", args.image, W, "x", H)

    # 整图缩略
    p = os.path.join(out, "full_small.png")
    im.resize((1500, int(H * 1500 / W)), Image.LANCZOS).save(p)
    print("saved", p)

    # 九宫格
    cols, rows = (int(x) for x in args.grid.lower().split("x"))
    for r in range(rows):
        for c in range(cols):
            box = (int(c * W / cols), int(r * H / rows),
                   int((c + 1) * W / cols), int((r + 1) * H / rows))
            crop = up(im.crop(box), args.scale)
            p = os.path.join(out, "zone_r%dc%d.png" % (r, c))
            crop.save(p)
            print("saved", p, box)

    # 四边缘条（补读总尺寸，被九宫格边界切掉的常在这里）
    edge_h = max(180, int(H * 0.10))
    edge_w = max(180, int(W * 0.08))
    bands = {
        "edge_top": (0, 0, W, edge_h),
        "edge_bottom": (0, H - edge_h, W, H),
        "edge_left": (0, 0, edge_w, H),
        "edge_right": (W - edge_w, 0, W, H),
    }
    for name, box in bands.items():
        p = os.path.join(out, name + ".png")
        up(im.crop(box), 1.2).save(p)
        print("saved", p, box)

    # 关键数字定点复核
    for item in filter(None, (s.strip() for s in args.points.split(";"))):
        val, x, y = item.split(":")
        cx, cy = int(float(x)), int(float(y))
        w, h = 600, 500
        box = (max(0, cx - w // 2), max(0, cy - h // 2),
               min(W, cx + w // 2), min(H, cy + h // 2))
        p = os.path.join(out, "key_%s.png" % val)
        up(im.crop(box), 2.5).save(p)
        print("saved", p, box)

    print("\n下一步：把 zone_*.png 分三批交给 analyze_image（每次 3 张），"
          "提示词要求逐张列出「数字 | 九宫格方位 | 横竖」，只出数字不解释。")


if __name__ == "__main__":
    main()
