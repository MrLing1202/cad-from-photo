# 图注成线 · Cad From Photo

把一张平面图照片，变成一份可编辑的 CAD 线稿。

## 只信标注

图纸上唯一精确的东西，是人写上去的尺寸数字。

照片有透视，打印有拉伸，像素量出来的墙线永远差一点。所以这里不比像素，只核数字。

| 手上有什么 | 拿到什么 |
|:---|:---|
| 照片 + 已有 CAD | 逐条指出哪里画漏了、画错了 |
| 只有一张照片 | 从零生成可编辑的 DXF |

一套引擎，两个入口。每条结论都能被图上的数字解释回来；解释不回来的，单独列出。

## 快速开始

```bash
git clone https://github.com/MrLing1202/cad-from-photo.git
cd cad-from-photo
pip install ezdxf pillow pywin32
```

`pywin32` 仅用于 DWG 转 DXF，需本机装有 AutoCAD。DXF 输入不需要。

验证引擎是否正常：

```bash
python scripts/build_dxf.py --spec examples/spec.json --out demo.dxf
python scripts/dump_entities.py --file demo.dxf --out self.json
python scripts/axis_check.py --entities self.json --from-spec examples/spec.json --outdir .
```

期望输出见 `examples/self_check_report.txt`，九项全中。

## 完整流程

```bash
python scripts/read_annotations.py --image 平面图.jpg --outdir temp/ann --grid 3x3
python scripts/dump_entities.py --file 原图.dwg --out temp/entities.json
python scripts/axis_check.py --entities temp/entities.json --ann "10640:H,8500:V" --outdir temp
python scripts/build_dxf.py --spec temp/spec.json --out temp/plan.dxf
```

读图、抽线、对账、成线。中间产物是一份 spec，记轴线坐标、墙厚、洞口、标注集。改它，结果就改。

## 报告怎么读

| 差值 | 判定 | 处理 |
|:---|:---|:---|
| ≤ 10mm | 对 | 忽略 |
| 10–50mm | 存疑 | 多为取整误差 |
| 接近墙厚量级 | 口径差 | 正常，不判错 |
| 跨轴等值 | 跨轴 | 回到位置核实 |
| 其余 | 缺 / 画错 | 要改图 |

先看「缺」，那是漏画的墙；再看「存疑」，是读数误差；「口径差」可以放过。

「跨轴」最容易被放过。同样的长度在别处恰好存在，不代表这根线画了。

## 结构

```
cad-from-photo/
├── SKILL.md                   # 方法与纪律
├── scripts/
│   ├── read_annotations.py    # 标注提取与复核
│   ├── dump_entities.py       # DWG / DXF 抽线
│   ├── axis_check.py          # 对账与判定
│   └── build_dxf.py           # spec → DXF
└── examples/
    ├── spec.json              # 轴网示例
    ├── demo.dxf               # 可直接打开
    └── self_check_report.txt  # 期望自检输出
```

## 它做不到什么

- **照片严重透视**：墙线角度失真，几何对账失效，需先人工校正
- **同轴墙厚不一**：外墙与隔墙混用，轴线可能偏移，核 `axis.json`
- **标注被遮挡**：读不全就是读不全，不用对称性补数
- **图幅只覆盖局部**：判「缺」之前，先确认那道墙不在图幅之外

## 一次真实核对

某张平面图，62 个去重标注，DWG 145 条线。

57 个标注找到对应。其中 6 个初判为「图上凭空多出的尺寸」，实际是标注相减得来的。剩下 1 条判缺：底部那道横墙整个没画，DWG 的范围根本到不了那个位置。

能靠加减解释的尺寸不算错；在别处恰好找到等值的，也不算对。

## 协议

MIT

---

图纸不会骗人，像素会。
