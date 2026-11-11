#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尺寸链闭合校验 / 墙厚反算。

对账引擎（axis_check.py）只做单条标注的几何对位，发现不了整条链的错位：
每段标注都能在自己位置上找到等长线段，40mm 的误差照样躲过去。
本脚本补这一刀。

两种模式：

  chain       一条尺寸链各段累加，与总尺寸比对，定位差额可能的落点。
  thickness   总宽、净宽、已知一侧墙厚，反算另一侧，并判定是否为标准厚度。

用法：
    python chain_check.py --mode chain \
        --chain "240+1600+200+3450+790+600+450+200+850+1500+800+200+1800+240" \
        --total 12920 --axis H

    python chain_check.py --mode thickness \
        --total 12920 --net 12400 --known-side left --known-thick 240 --axis H

退出码：0 闭合 / 1 不闭合或有告警
"""

import argparse
import sys

# 国内常见墙体完成面厚度。用减法凑出来的数落在这里，才算能收进结论。
STD_THICK = [60, 80, 90, 100, 120, 150, 180, 200, 240, 300, 370, 490]

# 差额与常见成因的对应，纯粹来自踩过的坑，不是理论
DIFF_HINTS = {
    10: "取整误差，或图上某段标注抄写差一位",
    20: "单面抹灰厚度被漏算（常见 20mm）",
    40: "墙体厚度归属搞错（240 与 280 互串），或净空与轴线之间混用了半墙厚",
    50: "半墙厚 25 被漏算两次，或墙厚 200/240 混用",
    60: "轻质隔墙（60/90）被漏算",
    100: "一道 100 隔墙被漏算",
    120: "一道 120 隔墙被漏算",
    180: "一道 180 隔墙被漏算",
    200: "一道 200 隔墙被漏算",
    240: "一道 240 墙被整个漏算",
}

OK_TOL = 2  # 累加允许的取整误差


def parse_segments(text):
    """把 "240+1600+200" 或 "240,1600,200" 或混合写法切成数字列表。"""
    buf = text
    for ch in ("，", "、", ";", "；", "/", " "):
        buf = buf.replace(ch, ",")
    parts = []
    for chunk in buf.split(","):
        if not chunk:
            continue
        if "+" in chunk:
            parts.extend(chunk.split("+"))
        else:
            parts.append(chunk)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        try:
            out.append(float(p))
        except ValueError:
            raise SystemExit("无法解析的段值：%r" % p)
    return out


def is_std(t, tol=3.0):
    return any(abs(t - s) <= tol for s in STD_THICK)


def nearest_std(t):
    return min(STD_THICK, key=lambda s: abs(t - s))


def fmt(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def run_chain(segs, total, axis):
    acc = sum(segs)
    diff = acc - total
    print("=" * 60)
    print("尺寸链闭合校验  轴向 %s" % axis)
    print("=" * 60)
    print("段数           %d" % len(segs))
    print("各段累加       %s" % fmt(acc))
    print("给定总尺寸     %s" % fmt(total))
    print("差额(累加-总)  %s" % fmt(diff))

    if abs(diff) <= OK_TOL:
        print("\n结论：闭合。累加与总尺寸一致，链上无错位。")
        return 0

    print("\n结论：不闭合。差额 %s mm 藏在链里，不在任何单条标注上。" % fmt(diff))
    ad = abs(diff)

    hint = None
    for k in sorted(DIFF_HINTS):
        if abs(ad - k) <= 3:
            hint = DIFF_HINTS[k]
            break
    if hint:
        print("成因提示：%s" % hint)
    else:
        print("成因提示：差额不属于常见模式，优先核对是否有段值读错一位（如 1600/1660、3450/3480）。")

    # 差额归到哪一段：列出把它吸收之后、结果最像整数的候选
    print("\n若把差额归到某一段（改前 → 改后 → 是否标准厚度）：")
    print("  %-4s %-10s %-10s %-10s %s" % ("段号", "改前", "改后", "偏离标准", "判定"))
    cands = []
    for i, s in enumerate(segs):
        new = s + diff
        if new <= 0:
            continue
        if is_std(new):
            tag = "改后是标准厚度，优先考虑"
        elif is_std(s):
            tag = "改前是标准厚度，改它会破坏标准墙厚"
        else:
            tag = "两端都不是标准厚度"
        cands.append((i + 1, s, new, abs(new - nearest_std(new)), tag))
    cands.sort(key=lambda x: (0 if "优先" in x[4] else 1, x[3]))
    for i, s, new, dev, tag in cands:
        print("  %-4d %-10s %-10s %-10s %s" % (i, fmt(s), fmt(new), fmt(dev), tag))
    print("\n注意：脚本只算数，不判几何。最终归到哪一段，按铁律十用证据密度定：")
    print("  有独立分界点、有第二处标注互证的那一侧锁死；只剩孤证、且孤证与某个大跨度标注")
    print("  直接冲突的，错位就在那一侧。")
    return 1


def run_thickness(total, net, known_side, known_thick, axis):
    unknown = total - net - known_thick
    print("=" * 60)
    print("墙厚反算  轴向 %s" % axis)
    print("=" * 60)
    print("总尺寸            %s" % fmt(total))
    print("净宽              %s" % fmt(net))
    print("已知%s墙厚      %s" % ("左" if known_side == "left" else "右", fmt(known_thick)))
    print("反算另一侧墙厚    %s" % fmt(unknown))

    bad = False
    if unknown <= 0:
        print("\n结论：反算结果非正，说明总尺寸与净宽本身就矛盾（净宽已超过总宽）。")
        print("      先核对总尺寸是否读错，再谈墙厚。")
        return 1

    if is_std(unknown):
        print("\n结论：反算值是标准厚度，可以收进结论。")
        return 0

    bad = True
    print("\n结论：反算值不是标准厚度。按铁律九，这不是墙厚，是信号——")
    print("      链里有一处错位，别把它写进结论，也别四舍五入到相邻标准值了事。")

    # 按相邻标准厚度列解：取哪个标准值，净宽就得怎么改
    print("\n若另一侧取标准厚度，净宽应改为（差额即错位所在）：")
    print("  %-12s %-14s %-10s" % ("另一侧取", "净宽应改为", "与当前净宽之差"))
    # 240 永远是国内最普适的外墙厚度，排在最前，避免"数值最接近"把人带偏
    cands = sorted(STD_THICK, key=lambda s: (0 if s == 240 else 1, abs(s - unknown)))[:3]
    for s in cands:
        n = total - known_thick - s
        print("  %-12s %-14s %-10s" % (fmt(s), fmt(n), fmt(n - net)))

    print("\n反向问法：若净宽 %s 是对的，那%s墙厚只能是 %s。"
          % (fmt(net), "左" if known_side == "right" else "右", fmt(unknown)))
    print("两个数不能同时为真的时候，按铁律十看证据密度，不要看哪个更接近标准值。")
    return 1


def main():
    ap = argparse.ArgumentParser(description="尺寸链闭合校验 / 墙厚反算")
    ap.add_argument("--mode", choices=["chain", "thickness"], default="chain")
    ap.add_argument("--chain", help="chain 模式：各段值，用 + 或逗号分隔")
    ap.add_argument("--total", type=float, required=True, help="总尺寸")
    ap.add_argument("--axis", default="?", help="轴向 H/V，仅用于输出标注")
    ap.add_argument("--net", type=float, help="thickness 模式：净宽")
    ap.add_argument("--known-side", choices=["left", "right"], default="left",
                    help="thickness 模式：已确认的那一侧")
    ap.add_argument("--known-thick", type=float, help="thickness 模式：已确认那侧的墙厚")
    ap.add_argument("--json", help="可选：把结果另存为 JSON")
    args = ap.parse_args()

    if args.mode == "chain":
        if not args.chain:
            raise SystemExit("chain 模式必须给 --chain")
        segs = parse_segments(args.chain)
        rc = run_chain(segs, args.total, args.axis)
        payload = {"mode": "chain", "segments": segs, "sum": sum(segs),
                   "total": args.total, "diff": sum(segs) - args.total, "closed": rc == 0}
    else:
        if args.net is None or args.known_thick is None:
            raise SystemExit("thickness 模式必须给 --net 和 --known-thick")
        rc = run_thickness(args.total, args.net, args.known_side, args.known_thick, args.axis)
        unknown = args.total - args.net - args.known_thick
        payload = {"mode": "thickness", "total": args.total, "net": args.net,
                   "known_side": args.known_side, "known_thick": args.known_thick,
                   "unknown_thick": unknown, "is_standard": is_std(unknown),
                   "nearest_standard": nearest_std(unknown)}

    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("\n已写出 %s" % args.json)

    return rc


if __name__ == "__main__":
    sys.exit(main())
