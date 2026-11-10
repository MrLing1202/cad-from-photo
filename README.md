# cad-from-photo

从一张平面图的照片出发，读出图上的尺寸标注，核对已有 DWG 画得对不对，或者直接按标注生成 DXF 线稿。

不用 OCR，不靠像素量墙线。核心只有一句：**图纸上唯一可信的是人写上去的尺寸数字。**

## 它解决什么

| 场景 | 你会得到 |
|---|---|
| 手上有个 DWG，怀疑画漏了 | 逐条列出哪几个标注对不上、差多少、差在哪个方向 |
| 只有一张图，要从零画 | 一份可直接打开的 DXF，含双线墙体、门窗洞口、尺寸标注链 |
| 想验证自己的对账结论 | 一套自检闭环，生成物必须能被自己的标注集解释回来 |

## 为什么不能直接比长度

两个坑，踩了结论就是错的。

**墙画的是双线，标注量的是轴线。** 直接拿线段长度和标注比，会系统性地差一个墙厚。所以先做墙皮合并。

**数值相等不等于几何成立。** 实测踩过：图底部一道墙标长 12400，DWG 里根本没画这根线，但另外两道墙的间距恰好也是 12400，对账会欢快地报"有"。这类只能回到位置核对。

## 快速开始

```bash
# 1 读图：九宫格切分，逐块读标注
python scripts/read_annotations.py --image 平面图.jpg --outdir temp/ann

# 2 抽线：把 DWG 的线段倒出来
python scripts/dump_entities.py --file 原图.dwg --out temp/entities.json

# 3 对账
python scripts/axis_check.py --entities temp/entities.json \
  --ann "10640:H,8500:H,2800:V" --ann-line "12400:H" --outdir temp

# 4 成线
python scripts/build_dxf.py --spec temp/spec.json --out temp/plan.dxf

# 5 自检，A 向必须 100% 命中
python scripts/dump_entities.py --file temp/plan.dxf --out temp/self.json
python scripts/axis_check.py --entities temp/self.json --from-spec temp/spec.json --outdir temp
```

标注格式 `10640:H` 里的 H/V 是方向，不标方向会到处乱命中。

## 依赖

Python 3.8+，`ezdxf` 用于生成 DXF，`Pillow` 用于切图。核对 DWG 需要本机装 AutoCAD 做 DXF 转换，DXF 可以直接读。

```bash
pip install ezdxf pillow
```

## 一个真实结果

图上有 62 个去重标注，DWG 有 145 条线。对账结果：57 个找到对应，其中 6 个一开始被误判成"图上凭空多出来的尺寸"，实际是标注相加相减得来的（8740 = 10640 − 1900）。剩下 12400 判缺——底部那道横向墙整个没画。

加减组合能解释的不要当错，数值恰好能在别处找到等值的也不能当对。这两句话值这份脚本的全部。

## 在 Marvis 里用

把整个目录放进 `skills/custom/cad-from-photo/`，重启客户端即可作为技能加载，SKILL.md 会被识别。

## License

MIT
