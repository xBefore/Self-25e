# 2025 电赛 E 题 — 视觉处理模块

基于 **MaixCAM Pro** 的纯视觉管线：检测 A4 靶纸 → 靶心误差 → 6cm 圆弧轨迹 → UART 下发 MSPM0，附带 WiFi WebUI 实时调参。

## 硬件

| 组件 | 说明 |
|---|---|
| 主控 | Sipeed MaixCAM Pro |
| 模型 | `model_3356.mud`（YOLOv5，识别 A4 黑框），需从 [MaixHub](https://maixhub.com/model/zoo/1159) 下载放到 `/root/models/` |
| 摄像头 | 448×448 RGB |
| 串口 | `/dev/ttyS0` @ 115200 → MSPM0 下位机 |

## 快速开始

```bash
# 1. 上传到 MaixCAM Pro
scp project.py webui.py root@<maixcam-ip>:/root/

# 2. 确认模型存在
ls /root/models/model_3356.*

# 3. 运行（开屏调试）
python3 project.py


```

## 视觉管线

```
Camera(448×448)
  → YOLOv5 粗定位黑框
  → ROI 裁剪
  → 自适应二值化 + 洪水填充
  → findContours + approxPolyDP → 4 角点排序
  → 透视变换 → 113×80 标准图（A4 比例）
  → 对角线交点 = 靶心中心
  → 6cm 圆弧轨迹（50 点，逆透视回原图）
  → 一阶低通 EMA 平滑
  → err_center = 预测中心 - 画面中心 + 瞄准偏移
  → UART 二进制打包下发
```

## UART 协议

二进制帧格式（小端序）：

| 偏移 | 字节 | 字段 |
|---|---|---|
| 0 | 2 | 同步头 `0xAA 0x55` |
| 2 | 1 | Flags: bit0=updated, bit1=circle_valid |
| 3 | 1 | 帧序号 (0–255) |
| 4 | 2 | err_x int16 (像素) |
| 6 | 2 | err_y int16 (像素) |
| 8 | 2 | center_x uint16 |
| 10 | 2 | center_y uint16 |
| 12 | 1 | circle3 点数 (0–50) |
| 13 | 1 | checksum (字节 2–12 XOR) |
| 14 | 2 | 保留 |
| 16+ | N×4 | [可选] circle3 点 int16 x, int16 y |

调试文本模式：设置 `UART_TEXT_MODE=True`，输出 CSV 行。

## 配置

所有可调参数在 `project.py` 顶部，部分支持 WebUI 动态修改：

| 参数 | 默认 | 说明 |
|---|---|---|
| `CAM_RES` | 448 | 摄像头分辨率 |
| `CONF_TH` | 0.5 | YOLO 置信度阈值 |
| `ADAPTIVE_BLOCK` | 27 | 自适应二值化窗口（奇数） |
| `ADAPTIVE_C` | 31 | 二值化常数 |
| `LPF_ALPHA` | 0.3 | 一阶低通平滑（0=关） |
| `ENABLE_DISPLAY` | True | 屏幕显示（生产关） |
| `UART_TEXT_MODE` | False | True=CSV 调试 |

## 项目结构

```
project.py          # 主程序：VisualProcessor 类 + 主循环
webui.py            # HTTP 配置面板 + RuntimeConfig
pyrightconfig.json  # Pylance 类型检查配置
.claude/memory/     # MaixPy API 速查参考
```

## 待恢复

- 卡尔曼滤波代码已注释（`# class KalmanFilter2D`），WebUI 中参数已预留。恢复时取消注释 4 处即可。
