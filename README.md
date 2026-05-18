# 2025 电赛 E 题 — 视觉处理模块

**MaixCAM Pro** 纯视觉管线：检测 A4 靶纸 → 靶心误差 → 6cm 圆弧轨迹 → UART 下发 MSPM0。附带 **WiFi WebUI 调参面板** 和 **触摸屏二级参数界面**。

## 硬件

| 组件 | 说明 |
|---|---|
| 主控 | Sipeed MaixCAM Pro |
| 入口 | `main.py`（MaixVision 兼容） |
| 模型 | `model_3356.mud`（YOLOv5，识别 A4 黑框），从 [MaixHub](https://maixhub.com/model/zoo/1159) 下载到 `/root/models/` |
| 摄像头 | 448×448 RGB |
| 串口 | `/dev/ttyS0` @ 115200 → MSPM0 下位机 |
| WiFi | WebUI 通过局域网访问 8080 端口 |

## 快速开始

```bash
# 1. 上传
scp main.py project.py webui.py root@<maixcam-ip>:/root/

# 2. 确认模型
ls /root/models/model_3356.*

# 3. 运行（MaixVision 直接打开 main.py，或命令行）
python3 main.py

# 4. 手机/电脑浏览器打开调参面板
#    http://<maixcam-ip>:8080/

# 5. 触摸屏右上角 → 二级参数界面
```

## 视觉管线

```
Camera(448×448)
  → YOLOv5 粗定位黑框
  → ROI 裁剪 + 自适应二值化 + 洪水填充
  → findContours + approxPolyDP → 4 角点排序
  → 透视变换 → 113×80 标准图（A4 比例）
  → 对角线交点 = 靶心
  → 6cm 圆弧轨迹（50 点，逆透视回原图）
  → 一阶低通 EMA 平滑
  → err_center = (靶心 − 画面中心) + 瞄准偏移
  → UART 二进制打包下发
```

## UART 协议

| 偏移 | 字节 | 字段 |
|---|---|---|
| 0 | 2 | 同步头 `0xAA 0x55` |
| 2 | 1 | Flags: bit0=updated, bit1=circle_valid |
| 3 | 1 | 帧序号 0–255 |
| 4 | 2 | err_x int16 LE（像素） |
| 6 | 2 | err_y int16 LE |
| 8 | 2 | center_x uint16 LE |
| 10 | 2 | center_y uint16 LE |
| 12 | 1 | circle3 点数（0–50） |
| 13 | 1 | checksum（字节 2–12 XOR） |
| 14 | 2 | 保留 |
| 16+ | N×4 | [可选] circle3 点 int16 x LE, int16 y LE |

文本调试模式：`UART_TEXT_MODE=True` 输出 CSV。

## 配置参数

在 `project.py` 顶部修改，部分通过 WebUI 动态调整：

### 静态常量（需重启）

| 参数 | 默认 | 说明 |
|---|---|---|
| `CAM_RES` | 448 | 摄像头分辨率 |
| `CONF_TH` / `IOU_TH` | 0.5 / 0.45 | YOLO 阈值 |
| `CROP_PADDING` | 12 | bbox 外扩像素 |
| `STD_RES` | [113, 80] | 标准图尺寸 |
| `CIRCLE3_POINTS` | 50 | 圆弧轨迹点数 |
| `UART_PORT` | /dev/ttyS0 | 串口设备 |

### WebUI 动态参数（即时生效）

| 参数 | 默认 | 范围 | 控件 |
|---|---|---|---|
| AWB R / G / B | 0.134 / 0.063 / 0.114 | 0.00–0.50 | Slider |
| Contrast | 80 | 0–100 | Slider |
| Adp Block | 27 | 11–99 奇数 | Spinbox |
| Adp C | 31 | 0–50 | Slider |
| LPF Alpha | 0.3 | 0–1 | 常量（可改） |
| KF Pred DT | 0.05 | 0.00–0.20s | Slider |
| KF Proc Noise | 100k | 10/100/1k/10k/100k | Dropdown |
| Offset X / Y | 0 | −50~50 px | Slider |

## WebUI 调参面板

- 纯白极简界面，手机/电脑浏览器访问 `http://<ip>:8080`
- 10 个控件，修改即时生效
- AWB / Contrast 变化实时写摄像头寄存器
- 自适应二值化参数每帧读取，调参立即可视
- 独立 daemon 线程，永不阻塞主循环

## 触摸屏二级界面

- 触摸屏幕任意位置切换：摄像头画面 ↔ 参数总览
- 黑底白字，分组显示 ISP、Threshold、Filter、Offset 所有当前值
- 无检测时也能查看参数

## 滤波链路

```
center_cam → err_raw → [一阶低通 EMA] → err_center → UART
```

- 卡尔曼滤波代码已注释，WebUI 参数已预留，恢复时取消 4 处注释即可

## 文件结构

```
main.py             # MaixVision 入口（代理到 project.main()）
project.py          # 主程序：VisualProcessor + 管线 + 触摸屏界面
webui.py            # HTTP 配置面板 + RuntimeConfig + ISP 回调
pyrightconfig.json  # Pylance 类型检查配置
.gitignore          # 排除 __pycache__ / 本地设置
README.md
.claude/memory/     # MaixPy API 速查参考
```
