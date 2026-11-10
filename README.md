# 图注成线

从平面图照片读取尺寸标注，用来核对已有 CAD 图，或者按读到的轴网直接生成 DXF。

## 来历

这份工具来自一次真实的核对。一张手机拍的平面图，一个别人画好的 DWG，要确认图有没有画错。

第一次比的是墙线的像素坐标。无论怎么调阈值都对不上。照片有透视，打印也有拉伸，墙线量出来的距离不能直接当尺寸用。

换成读图上的标注数字，对账才做得下去。62 个去重标注里，57 个在 DWG 里有对应的墙体距离。一开始有 6 个被判成图上多出来的尺寸，后来发现是其他标注相减得到的值，图纸本身没错。剩下 12400 一个，DWG 里没有这段墙，Y 方向最低只到 -4424，标注落在更下面。

那一轮踩到的坑，现在都写进了脚本。

## 安装

```bash
pip install ezdxf pillow pywin32
```

`pywin32` 只在 DWG 转 DXF 时用到，需要本机装 AutoCAD。DXF 输入用不到它。

## 用法

读图。按 3x3 切分标注，取不准的数字再定点放大复核一遍。

```bash
python scripts/read_annotations.py --image 平面图.jpg --outdir temp/ann --grid 3x3
```

抽线。DWG 走 AutoCAD 转换，DXF 直接读。

```bash
python scripts/dump_entities.py --file 原图.dwg --out temp/entities.json
```

对账。抽出来的线跟标注集逐条比，输出 `report.txt` 和 `axis.json`。

```bash
python scripts/axis_check.py --entities temp/entities.json --ann "10640:H,8500:V" --outdir temp
```

成线。按 spec 生成双线墙体、门窗洞口和尺寸链。

```bash
python scripts/build_dxf.py --spec temp/spec.json --out temp/plan.dxf
```

生成物要能被自己的标注集解释回来再交付。

```bash
python scripts/axis_check.py --entities self.json --from-spec temp/spec.json --outdir temp
```

## 中间产物

整条流程以一份 spec 为准。

```json
{
  "walls_x": [0, 1600, 4400, 7200, 10640],
  "walls_y": [0, 2800, 4950, 8500],
  "thick_x": 200,
  "thick_y": 240,
  "openings": [{"axis": "x", "at": 0, "from": 600, "to": 1500, "type": "门"}],
  "ann_axis": ["10640:H", "8500:V", "3550:V", "2150:V", "1600:H"],
  "ann_line": ["12400:H"]
}
```

`walls_x` 和 `walls_y` 存轴线的绝对坐标，单位 mm，间距由脚本自己算。墙体厚度拿不准时先按 200 和 240 填，对账会报出口径差，那个差值就是实际墙厚。

标注带方向后缀。`10640:H` 量的是横向，`8500:V` 量的是纵向。不标方向的标注会到处命中，同一张图上 10640 和 12400 能在错的方向找到等值。

## 判定口径

| 差值 | 判定 | 处理 |
|:---|:---|:---|
| ≤ 10mm | 对 | 忽略 |
| 10 到 50mm | 存疑 | 多为取整误差，人工过一眼 |
| 接近墙厚量级 | 口径差 | 净空与含墙厚的差别，不判错 |
| 跨轴等值 | 跨轴 | 回到位置核实 |
| 其余 | 缺或画错 | 要改图 |

读报告先看缺，那是漏画的墙。存疑是读数误差。口径差可以放过。

跨轴这一类容易漏判。某个长度在图上别处恰好等值，不代表这个位置真有这根线，要回到那个方向那个轴段上确认。

## 局限

- 照片透视严重时墙线角度失真，几何对账会失效，得先人工校正
- 同一道轴上外墙和隔墙厚度不一时，轴线定位会偏，看 `axis.json` 里的 key 值
- 标注被遮挡或断线，读不全就如实标出，不用对称性补数
- 图幅只覆盖局部时，判缺之前先确认那道墙不在图幅之外

## 协议

MIT
