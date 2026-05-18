# 2025 电赛 E 题 — 视觉处理模块

**MaixCAM Pro** 纯视觉管线：检测 A4 靶纸 → 靶心误差 → 6cm 圆弧轨迹 → UART 下发 MSPM0。附带 **WiFi WebUI 调参面板**、**调参/竞赛双模式** 和 **触摸屏参数界面**。

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

# 3. 运行
python3 main.py

# 4. 手机/电脑浏览器打开调参面板
#    http://<maixcam-ip>:8080/

# 5. 触摸屏幕任意位置 → 二级参数界面
```

## 视觉管线

```
Camera(448×448)
  ┌─ SEARCH: YOLOv5 全帧检测 ──→ 切到 TRACK
  └─ TRACK:  跳过 YOLO, 缓存 ROI + margin → 传统 CV 追踪
  → ROI 裁剪 + 大津法全局二值化 + 洪水填充
  → findContours + approxPolyDP → 4 角点排序
  → 透视变换 → 113×80 标准图（A4 比例）
  → 对角线交点 = 靶心
  → Circle3 轨迹（50 点，逆透视回原图）
  → 一阶低通 EMA 平滑
  → err_center = (靶心 − 画面中心) + 瞄准偏移
  → UART 二进制打包下发
```

### Search/Track 状态机

| 状态 | 检测方式 | 触发条件 |
|---|---|---|
| **SEARCH** | YOLOv5 全帧推理 | 启动 / 连续丢失 2 帧 |
| **TRACK** | 跳过 YOLO，缓存 ROI + 传统 CV | YOLO 找到目标后自动切换 |

TRACK 模式下省掉 YOLO（~15-20ms），连续丢失后自动降级回 SEARCH。

### 二值化

大津法（OTSU）全局阈值 `cv2.THRESH_OTSU`，自动计算最优阈值，比自适应逐块计算快约 3×。

## 调参模式 / 竞赛模式

WebUI 顶部 **Tuning Mode** 开关控制：

| 模式 | 屏幕 | 调试绘制 | 触摸 | YOLO | UART | 性能 |
|---|---|---|---|---|---|---|
| **Tuning ON** | 开 | 开 | 开 | SEARCH/TRACK | 正常 | 正常 |
| **Tuning OFF** | 关 | 关 | 关 | SEARCH/TRACK | 正常 | **全力处理** |

竞赛模式下 `_display()` 直接跳过，屏幕不推帧，零开销。

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

`UART_TEXT_MODE=True` 输出 CSV 调试文本。

## WebUI 调参面板

纯白极简界面，手机/电脑浏览器访问 `http://<ip>:8080`。独立 daemon 线程，不阻塞主循环。

### 控件列表（共 16 项）

| 控件 | 绑定变量 | 类型 | 范围 | 即时生效 |
|---|---|---|---|---|
| **Tuning Mode** | `tuning_mode` | Toggle | ON/OFF | 全系统 |
| **AWB R / G / B** | `awb_r/g/b` | Slider | 0.00–0.50 | 写摄像头寄存器 |
| **Contrast** | `contrast` | Slider | 0–100 | 写摄像头寄存器 |
| **Exposure** | `exposure` | Slider | 0(auto)–10000μs | 切换 AE 模式 |
| **Target Ring** | `circle_ring` | Segmented | 0(靶心)~4(8cm) | 每帧轨迹半径 |
| **YOLO Conf** | `conf_th` | Slider | 0.10–0.90 | 每帧推理 |
| **Min Rect** | `rect_min` | Spinbox | 5–50 | 每帧过滤 |
| **Adp Block** | `adp_block` | Spinbox | 11–99 奇数 | 已降级为 OTSU，预留 |
| **Adp C** | `adp_c` | Slider | 0–50 | 已降级为 OTSU，预留 |
| **LPF Alpha** | `lpf_alpha` | Slider | 0.00–1.00 | 每帧平滑 |
| **KF Pred DT** | `kf_dt` | Slider | 0.00–0.20s | KF 预留 |
| **KF Noise** | `kf_q` | Dropdown | 10–100k | KF 预留 |
| **Offset X / Y** | `ofs_x/y` | Slider | −50~50 px | 每帧 err_center |

### Live Status 面板

页面底部 500ms 轮询实时显示：FPS、Detection 状态、err_center、靶心坐标。

## 触摸屏二级界面

- 触摸屏幕任意位置切换：摄像头画面 ↔ 参数总览
- 黑底白字，分组显示 ISP / Detection / Threshold / Filter / Offset 所有当前值
- 无检测时也能查看

## 滤波链路

```
center_cam → err_raw → [一阶低通 EMA, α 可 WebUI 调整] → err_center → UART
```

- 卡尔曼滤波代码已注释，WebUI 参数已预留

## 文件结构

```
main.py             # MaixVision 入口（代理到 project.main()）
project.py          # 主程序：VisualProcessor + 状态机 + 触摸屏
webui.py            # HTTP 配置面板 + RuntimeConfig + API + LiveStats
pyrightconfig.json  # Pylance 类型检查
.gitignore          # 排除 __pycache__ / 本地设置
README.md
.claude/memory/     # MaixPy API 参考
```
