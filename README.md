# 图注成线 · Cad From Photo

一张平面图照片，一份可编辑的 CAD 线稿。

---

## 它解决什么

图纸上唯一不会说谎的，是人写上去的尺寸数字。

照片有透视，打印有拉伸，像素量出来的墙线永远差一点。所以这里只认标注，不认目测。

共用同一套引擎，两种用法：

| 你手上有什么 | 你拿到什么 |
|:---|:---|
| 平面图照片 + 已有 CAD | 逐条指出哪里画漏了、画错了 |
| 只有一张照片 | 从零生成可编辑的 DXF |

每一条结论都能被图上的数字解释回来。解释不回来的，会被明确标出来——而不是悄悄放过。

## 三条原则

**只信标注。** 像素只能回答"有没有这根线"，不能回答"多长"。长度从数字来。

**回到位置。** 数值相等不等于几何成立。同样的长度可能在别处恰好存在，必须回到那个方向、那个轴段上去确认。

**读不全就说读不全。** 缺失靠图上标注补齐，不靠"这图看着应该是对称的"。

## 快速开始

```bash
git clone https://github.com/MrLing1202/cad-from-photo.git
cd cad-from-photo
pip install ezdxf pillow pywin32
```

> `pywin32` 仅用于 DWG 转 DXF，且需要本机装有 AutoCAD。DXF 输入不需要。

跑一遍自带示例验证引擎：

```bash
python scripts/build_dxf.py --spec examples/spec.json --out demo.dxf
python scripts/dump_entities.py --file demo.dxf --out self.json
python scripts/axis_check.py --entities self.json --from-spec examples/spec.json --outdir .
```

期望结果见 `examples/self_check_report.txt`：**9/9 全中**。

## 怎么用

```bash
# 读图：标注提取与定点复核
python scripts/read_annotations.py --image 平面图.jpg --outdir temp/ann --grid 3x3 --scale 2.0

# 抽线：DWG / DXF 中取出墙体线条
python scripts/dump_entities.py --file 原图.dwg --out temp/entities.json

# 核对：与图上的标注逐条比对，输出报告
python scripts/axis_check.py --entities temp/entities.json --ann "10640:H,8500:V" --outdir temp

# 成线：按轴网生成可编辑 DXF
python scripts/build_dxf.py --spec temp/spec.json --out temp/plan.dxf
```

中间产物是一个 spec 文件，记录轴线坐标、墙厚、洞口与标注集。整条流程以它为准，改动它就能改动结果。

## 判定口径

| 差值 | 判定 | 处理 |
|:---|:---|:---|
| ≤ 10mm | 对 | 忽略 |
| 10–50mm | 存疑 | 人工过一眼，多为取整误差 |
| 接近墙厚量级 | 口径差 | 正常，不判错 |
| 跨轴等值 | 跨轴 | 必须回到位置核实 |
| 其余 | 缺 / 画错 | 硬伤，要改图 |

读报告的顺序：先看"缺"，那是漏画的墙；再看"存疑"，是读数误差；"口径差"可以放过。

## 项目结构

```
cad-from-photo/
├── SKILL.md                   # 完整方法论
├── scripts/
│   ├── read_annotations.py    # 标注提取与复核
│   ├── dump_entities.py       # DWG / DXF 抽线
│   ├── axis_check.py          # 双向对账与判定
│   └── build_dxf.py           # spec → DXF
└── examples/
    ├── spec.json              # 轴网示例
    ├── demo.dxf               # 可直接打开
    └── self_check_report.txt  # 期望自检输出
```

## 边界

这套方法有它做不到的事，写在前面：

- **照片严重透视**：墙线角度失真，几何对账会失效，需要先人工校正
- **同轴墙厚不一**：外墙与隔墙混用时，轴线定位可能偏移，需要核 `axis.json`
- **标注被遮挡**：读不全就说读不全，不要用对称性补数
- **图幅只覆盖局部**：判"缺"之前，先确认那道墙不在图幅之外

## 一次真实核对

某张平面图，62 个去重标注，DWG 145 条线。

57 个标注找到对应。其中 6 个初判为"图上凭空多出的尺寸"，实际是标注相减得来的结果。剩下 1 条判缺——底部那道横墙整个没画，DWG 的范围根本到不了那个位置。

这个案例说明两件事：能靠加减解释的尺寸不算错；在别处恰好能找到等值的，也不算对。

## 开源协议

[MIT](LICENSE)
