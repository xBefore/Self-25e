---
name: maixpy-api-reference
description: MaixPy API quick reference for MaixCAM Pro development — camera, image, nn, uart, pwm, pinmap, display, time
metadata:
  type: reference
---

# MaixPy API Quick Reference (MaixCAM Pro)

Source: https://wiki.sipeed.com/maixpy/api/

---

## maix.camera — Camera

```python
from maix import camera

cam = camera.Camera(width, height, format=image.Format.FMT_RGB888, device=None, fps=-1, buff_num=3, open=True)
img = cam.read(block=True, block_ms=-1)  # → image.Image
cam.clear_buff()       # 清缓冲，下次读到最新帧
cam.skip_frames(n)     # 跳过n帧（刚打开时图像不稳定）
cam.close()

# 属性
cam.width()            # → int
cam.height()           # → int
cam.format()           # → image.Format
cam.fps()              # → float
cam.buff_num()         # → int

# ISP控制
cam.exposure(us)       # -1读取，>0设置(μs)
cam.gain(v)            # -1读，>0设
cam.constrast(v)       # 0~100，-1读
cam.luma(v)            # 0~100，-1读
cam.saturation(v)      # 0~100，-1读
cam.awb_mode(v)        # camera.AwbMode.Auto=0 / Manual=1 / Invalid=-1
cam.set_wb_gain([r, gr, gb, b])  # 0~1.0, MaixCam建议[0.134,0.0625,0.0625,0.1239]
cam.exp_mode(v)        # camera.AeMode.Auto=0 / Manual=1 / Invalid=-1
cam.hmirror(v)         # -1读/0关/1开
cam.vflip(v)           # -1读/0关/1开
cam.set_windowing([x,y,w,h] or [w,h])  # ROI或居中裁切
cam.show_colorbar(True)  # 彩条测试
```

---

## maix.image — Image & Drawing

```python
from maix import image

# 构造函数
img = image.Image(w, h, format=image.Format.FMT_RGB888)
img = image.Image(w, h)  # 空图
image.load(path, format=FMT_RGB888)  # 加载文件
image.image2cv(img, ensure_bgr=True, copy=True)  # → numpy ndarray (HWC)
image.cv2image(arr, bgr=True, copy=True)         # → image.Image

# 格式转换
img.to_format(image.Format.FMT_GRAYSCALE)  # → new Image
img.resize(w, h)     # → new Image (默认FIT_FILL拉伸)
img.crop(x, y, w, h) # → new Image

# 绘制
img.draw_string(x, y, str, scale=1, thickness=1, font='', color=COLOR_RED)
img.draw_line(x1,y1, x2,y2, color, thickness=1)
img.draw_circle(x, y, r, color, thickness=1)    # thickness=-1填充
img.draw_rect(x, y, w, h, color, thickness=1)
img.draw_image(x, y, other_img)
img.draw_keypoints(points_list, color, size, line_thickness=1)  # points = [x,y,x,y,...]

# 信息
image.string_size(str, scale=1, thickness=1, font='')  # → Size [w,h]

# 坐标映射
image.resize_map_pos(w_in,h_in, w_out,h_out, fit, x, y, w=-1, h=-1)  # → [x,y] or [x,y,w,h]
image.resize_map_pos_reverse(w_in,h_in, w_out,h_out, fit, x, y, w=-1, h=-1)

# Format枚举
image.Format.FMT_RGB888 / FMT_BGR888 / FMT_RGBA8888 / FMT_GRAYSCALE / FMT_YUV420SP

# Fit枚举
image.Fit.FIT_NONE / FIT_FILL(拉伸) / FIT_CONTAIN(等比+黑边) / FIT_COVER(等比+裁切)

# 颜色常量
image.COLOR_WHITE / COLOR_BLACK / COLOR_RED  / COLOR_GREEN  / COLOR_BLUE
image.COLOR_YELLOW / COLOR_PURPLE / COLOR_ORANGE / COLOR_GRAY
```

---

## maix.nn — Neural Network

### YOLOv5 (used in project)
```python
from maix import nn

detector = nn.YOLOv5(model="/root/models/model_3356.mud", dual_buff=True)
objs = detector.detect(img, conf_th=0.5, iou_th=0.45, fit=image.Fit.FIT_CONTAIN, sort=0)

# 模型信息
detector.input_width()   # → int (模型输入宽)
detector.input_height()  # → int (模型输入高)
detector.input_format()  # → image.Format (通常FMT_RGB888)
detector.input_size()    # → Size
detector.labels          # → list[str]

# 检测结果对象属性
for obj in objs:
    obj.x, obj.y, obj.w, obj.h   # 边界框
    obj.class_id                 # 类别ID
    obj.score                    # 置信度
```

### YOLO11
```python
detector = nn.YOLO11(model, dual_buff=True)
# detect()多了 keypoint_th=0.5 参数; 另有 draw_pose(), draw_seg_mask()
```

### Other models
- `nn.FaceDetector`, `nn.Retinaface` — 人脸检测
- `nn.FaceRecognizer` — 人脸识别（检测+特征）
- `nn.Classifier` — 分类
- `nn.SelfLearnClassifier` — 自学习分类
- `nn.HandLandmarks` — 手部关键点
- `nn.PP_OCR` — OCR文字识别
- `nn.DepthAnything` — 深度估计
- `nn.YOLOWorld` — 开放词汇检测
- `nn.MixFormerV2` — 目标跟踪
- `nn.Whisper` — 语音转文字

---

## maix.peripheral.uart — 串口（与下位机通信）

```python
from maix.peripheral import uart

# 查可用端口
uart.list_devices()  # → list[str]

# 构造(可一步打开)
ser = uart.UART(port="/dev/ttyS0", baudrate=115200,
                databits=uart.BITS_8, parity=uart.PARITY_NONE,
                stopbits=uart.STOP_1, flow_ctrl=uart.FLOW_CTRL_NONE)

# 或分步
ser = uart.UART()
ser.set_port("/dev/ttyS0")
ser.set_baudrate(115200)
ser.open()

# 发送
ser.write_str("hello\n")           # 发字符串,返回发送字节数
ser.write(b"hello\n")              # 发bytes
ser.write("hello\n".encode())      # str→bytes

# 接收
n = ser.available(timeout=0)       # 可用字节; timeout:0立即/-1阻塞/>0ms
data = ser.read(len=-1, timeout=0) # -1=读全部; 返回bytes
line = ser.readline(timeout=-1)    # 读一行直到\n; 返回bytes

# 回调
def on_data(uart_obj, data_bytes):
    pass
ser.set_received_callback(on_data)

ser.is_open()  # → bool
ser.close()
```

---

## maix.peripheral.pwm — PWM（舵机控制）

```python
from maix.peripheral import pwm

p = pwm.PWM(id=6, freq=50, duty=50, enable=True)
p.duty(75)          # 0~100 百分比
p.duty()            # -1 读取当前值
p.freq(100)         # 设置频率
p.freq()            # -1 读取
p.duty_val(val)     # 直接设duty值(不换算)
p.enable() / p.disable()
p.is_enabled()      # → bool
```

---

## maix.peripheral.pinmap — 引脚映射

```python
from maix.peripheral import pinmap

pinmap.get_pins()                        # → list[str] 所有引脚
pinmap.get_pin_functions("A18")          # → list[str] 某引脚所有功能
pinmap.set_pin_function("A18", "PWM6")   # 设置引脚功能
pinmap.get_pin_function("A18")           # → str 当前功能
```

---

## maix.display — 显示

```python
from maix import display

disp = display.Display(width=-1, height=-1, format=image.Format.FMT_RGBA8888, open=True)
disp.show(img, fit=image.Fit.FIT_CONTAIN)
disp.width()      # → int
disp.height()     # → int
disp.size()       # → [w, h]
disp.set_backlight(50)  # 0~100
disp.close()
```

---

## maix.time — 时间

```python
from maix import time

time.ticks_ms()     # → int 自启动以来毫秒
time.ticks_us()     # → int 微秒
time.ticks_s()      # → float 秒
time.sleep_ms(100)  # 休眠ms
time.sleep_us(50)   # 休眠μs
time.sleep(0.1)     # 休眠秒
time.fps()          # → float 调用间隔FPS(默认20帧平均)
time.time()         # → float 当前时间戳(秒)
```

---

## maix.app — 应用生命周期

```python
from maix import app

app.need_exit()  # → bool 是否收到退出信号(主循环条件)
while not app.need_exit():
    # main loop
    pass
```

---

## 本项目典型模式

```python
# 1. Camera + AI检测 + 串口输出 (find_circle.py + UART)
from maix import camera, display, image, nn, app, time
from maix.peripheral import uart

cam = camera.Camera(448, 448, nn_det.input_format(), buff_num=1)
detector = nn.YOLOv5(model="/root/models/model_3356.mud", dual_buff=True)
ser = uart.UART("/dev/ttyS0", 115200)

while not app.need_exit():
    img = cam.read()
    objs = detector.detect(img)
    # ... find_circle logic ...
    # 发送: err_x, err_y, updated, [circle3_points...]
    ser.write_str(f"{err_x},{err_y},{updated}\n")
```

```python
# 2. PWM舵机控制
from maix.peripheral import pwm, pinmap
pinmap.set_pin_function("A18", "PWM6")
servo = pwm.PWM(6, freq=50, duty=50)  # 50Hz, 初始50%占空比
```
