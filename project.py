"""
2025电赛E题 视觉处理模块 — MaixCAM Pro
纯视觉管线: 检测A4靶纸 → 靶心误差 → 6cm圆弧轨迹 → UART发给下位机
不包含舵机控制和PID(下位机负责)

API:  https://wiki.sipeed.com/maixpy/api/
"""

from maix import camera, display, image, nn, app, time, touchscreen
from maix.peripheral import uart as uart_mod
import cv2
import numpy as np
import struct
import os
import webui

# ============================================================
# 配置常量
# ============================================================

# 摄像头
CAM_RES             = 448
CAM_BUFF_NUM        = 1         # 1=低延迟, 2=略高fps
HIRES_MODE          = True      # True=摄像头 448x448, resize给AI

# 模型
MODEL_PATH          = "/root/models/model_3356.mud"
MODEL_DUAL_BUFF     = True      # 双缓冲,更高fps

# 检测管线
CONF_TH             = 0.5       # YOLO置信度阈值
IOU_TH              = 0.45      # YOLO IoU阈值
CROP_PADDING        = 12        # bbox外扩像素
RECT_MIN_LIMIT      = 12        # 矩形边最小像素,过滤误检
STD_RES             = [113, 80] # 标准图尺寸(A4比例 29.7:21)
STD_FROM_WHITE_RECT = True      # True=从白纸内侧取角点, False=用整个黑框
APPROX_EPSILON      = 0.02      # approxPolyDP精度(占周长比例)

# 自适应二值化 (WebUI 可动态调整, 以下为默认值)
ADAPTIVE_BLOCK_DEF  = 27        # 块大小(奇数)
ADAPTIVE_C_DEF      = 31        # 减去的常数

# 洪水填充
FLOOD_LO_DIFF       = 5
FLOOD_UP_DIFF       = 5

# 摄像头ISP (WebUI 可动态调整)
AUTO_AWB            = True
AWB_GAIN_DEF        = [0.134, 0.0625, 0.0625, 0.1139]
CONTRAST_DEF        = 80

# 圆参数
CIRCLE3_POINTS      = 50        # 第3圈(6cm)轨迹点数
CIRCLE3_RING        = 3         # 第几圈: 1=2cm, 2=4cm, 3=6cm, 4=8cm, 5=10cm
# A4纸白色内侧: 17.4cm宽, 2cm圆距占比 = 2/17.4 = 0.1149
CIRCLE_DIST_RATIO   = 0.1149425287356322

# UART
UART_PORT           = "/dev/ttyS0"
UART_BAUDRATE       = 115200
UART_TEXT_MODE      = False     # True=CSV文本(调试), False=二进制协议

# # 卡尔曼滤波 (补偿管线延迟)
# KF_ENABLE           = True      # 开启卡尔曼滤波预测
# KF_PREDICT_DT       = 0.05      # 预测超前时间(s), 应匹配管线延迟(~50ms)
# KF_PROCESS_NOISE    = 100000.0  # 过程噪声(像素^2), 越大越信任量测, 越小越平滑
# KF_MEASURE_NOISE    = 0.1       # 量测噪声(像素^2), 越小越信任量测

# 一阶低通 (对 err_center 做 EMA 平滑, 与 KF 可叠加)
LPF_ALPHA           = 0.3       # 0=关闭, 0.15=中度平滑, 0.3=轻度, 1.0=不过滤

# WebUI
WEBUI_PORT          = 8080      # Web配置面板端口

# 显示/调试
ENABLE_DISPLAY      = True      # 生产环境可关
DEBUG_DRAW_RECT     = True      # 画AI检测框
DEBUG_DRAW_ERR_LINE = True      # 画误差线
DEBUG_DRAW_ERR_MSG  = False     # 画FPS/误差文字(~7ms开销)
DEBUG_DRAW_CIRCLE3  = False     # 画circle3轨迹点(慢)
DEBUG_PRINT_TIME    = False     # 打印各阶段耗时
DEBUG_PRINT_ERR     = False     # 打印每帧误差
SHOW_PARAMS         = False     # True=显示参数二级界面(触摸右上角切换)

# # ============================================================
# # 卡尔曼滤波 (常速模型, 4状态: x, y, vx, vy)
# # ============================================================
#
# class KalmanFilter2D:
#     def __init__(self, process_noise=50.0, measurement_noise=10.0):
#         # 状态 [x, y, vx, vy]
#         self.x = np.zeros((4, 1), dtype=np.float32)
#         self.P = np.eye(4, dtype=np.float32) * 1000.0  # 初始协方差(大=不确定)
#         self.Q = np.eye(4, dtype=np.float32) * process_noise
#         self.R = np.eye(2, dtype=np.float32) * measurement_noise
#         self.H = np.array([[1,0,0,0],[0,1,0,0]], dtype=np.float32)
#         self.F = np.eye(4, dtype=np.float32)
#         self._initialized = False
#         self._last_t = None
#
#     def predict(self, dt):
#         """预测 dt 秒后的状态"""
#         self.F[0, 2] = dt
#         self.F[1, 3] = dt
#         # 过程噪声 (离散白噪声加速度模型)
#         dt2 = dt * dt
#         dt3 = dt2 * dt / 2.0
#         dt4 = dt2 * dt2 / 4.0
#         q = self.Q[0, 0]
#         self.Q = np.array([
#             [dt4*q, 0,     dt3*q, 0    ],
#             [0,     dt4*q, 0,     dt3*q],
#             [dt3*q, 0,     dt2*q, 0    ],
#             [0,     dt3*q, 0,     dt2*q],
#         ], dtype=np.float32)
#         self.x = self.F @ self.x
#         self.P = self.F @ self.P @ self.F.T + self.Q
#         return self.x
#
#     def update(self, z, dt):
#         """量测更新 z=[x,y]"""
#         if not self._initialized:
#             self.x[0, 0] = z[0]
#             self.x[1, 0] = z[1]
#             self._initialized = True
#             self._last_t = None
#             return self.x
#         if dt <= 0:
#             # 仅更新位置估计(无速度信息)
#             K = self.P @ self.H.T @ np.linalg.inv(self.H @ self.P @ self.H.T + self.R)
#             self.x = self.x + K @ (np.array([[z[0]],[z[1]]], dtype=np.float32) - self.H @ self.x)
#             self.P = (np.eye(4) - K @ self.H) @ self.P
#             return self.x
#         # 先预测到当前时刻
#         self.predict(dt)
#         # 量测更新
#         z_vec = np.array([[z[0]], [z[1]]], dtype=np.float32)
#         S = self.H @ self.P @ self.H.T + self.R
#         K = self.P @ self.H.T @ np.linalg.inv(S)
#         self.x = self.x + K @ (z_vec - self.H @ self.x)
#         self.P = (np.eye(4) - K @ self.H) @ self.P
#         return self.x
#
#     def predict_ahead(self, dt):
#         """在当前位置预测 dt 秒后(不修改内部状态)"""
#         F_ahead = self.F.copy()
#         F_ahead[0, 2] = dt
#         F_ahead[1, 3] = dt
#         return F_ahead @ self.x
#
#     def reset(self):
#         self._initialized = False
#         self.x = np.zeros((4, 1), dtype=np.float32)
#         self.P = np.eye(4, dtype=np.float32) * 1000.0

# ============================================================
# VisualProcessor
# ============================================================

class VisualProcessor:
    def __init__(self, enable_display=ENABLE_DISPLAY):
        self._t = time.ticks_ms()

        # --- 显示 ---
        self._disp = None
        if enable_display:
            self._disp = display.Display()

        # --- 模型 ---
        model_path = MODEL_PATH
        if not os.path.exists(model_path):
            model_path = "model/model_3356.mud"
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model not found. Download from https://maixhub.com/model/zoo/1159 "
                f"to /root/models/model_3356.mud"
            )
        self._detector = nn.YOLOv5(model_path, dual_buff=MODEL_DUAL_BUFF)

        # --- 摄像头 ---
        if HIRES_MODE:
            cam_w, cam_h = CAM_RES, CAM_RES
        else:
            cam_w = self._detector.input_width()
            cam_h = self._detector.input_height()
        fmt = self._detector.input_format()
        self._cam = camera.Camera(cam_w, cam_h, fmt, buff_num=CAM_BUFF_NUM)
        # ISP 设置 (初始值从 WebUI 读取, 后续可通过 WebUI 动态调整)
        if not AUTO_AWB:
            self._cam.awb_mode(camera.AwbMode.Manual)
            self._cam.set_wb_gain(webui.apply_awb_gain())
        self._cam.constrast(webui.get('contrast', CONTRAST_DEF))

        # 注册 ISP 回调: WebUI 改变 awb/contrast/exposure 时重新应用到摄像头
        def _on_isp_change(key, value):
            if key in ('awb_r', 'awb_g', 'awb_b'):
                if not AUTO_AWB:
                    self._cam.set_wb_gain(webui.apply_awb_gain())
            elif key == 'contrast':
                self._cam.constrast(value)
            elif key == 'exposure':
                if value > 0:
                    self._cam.exp_mode(camera.AeMode.Manual)
                    self._cam.exposure(int(value))
                else:
                    self._cam.exp_mode(camera.AeMode.Auto)

        webui.set_isp_callback(_on_isp_change)

        # --- 坐标映射参数 ---
        self._cam_w = cam_w
        self._cam_h = cam_h
        self._ai_w = self._detector.input_width()
        self._ai_h = self._detector.input_height()
        # AI输入图相对于摄像头的缩放比例
        self._ai_scale_x = cam_w / self._ai_w
        self._ai_scale_y = cam_h / self._ai_h
        self._screen_center = [cam_w // 2, cam_h // 2]
        self._screen_center_small = [self._ai_w // 2, self._ai_h // 2]

        # --- 状态 ---
        self.err_center   = [0, 0]
        self.last_center  = None
        self.last_circle3 = []
        self.updated      = False

        # --- Search/Track 状态机 ---
        self.track_state  = 'SEARCH'   # 'SEARCH' | 'TRACK'
        self.last_bbox    = None       # [x, y, w, h] 缓存的 ROI (AI 坐标系)
        self.miss_count   = 0
        self.ROI_MARGIN   = 20         # Track 模式下 ROI 外扩像素
        self.MAX_MISS     = 2          # 连续丢失帧数阈值, 超则降级 SEARCH

        # --- UART ---
        self._uart = None
        try:
            self._uart = uart_mod.UART(UART_PORT, UART_BAUDRATE)
        except Exception as e:
            print(f"[WARN] UART init failed: {e}")

        # --- 帧序号 ---
        self._seq = 0

        # # --- 卡尔曼滤波 ---
        # self._kf = KalmanFilter2D(KF_PROCESS_NOISE, KF_MEASURE_NOISE) if KF_ENABLE else None
        # self._kf_t = None  # 上次更新时间戳

        # --- 一阶低通 ---
        self._lpf_err = None  # [err_x, err_y] 滤波后的误差

        # --- 二级参数界面 ---
        self._show_params = SHOW_PARAMS
        self._ts = touchscreen.TouchScreen() if ENABLE_DISPLAY else None
        self._ts_touched = False

    def __del__(self):
        if self._uart and self._uart.is_open():
            self._uart.close()
        if hasattr(self, '_cam'):
            self._cam.close()
        if hasattr(self, '_disp') and self._disp:
            self._disp.close()

    # ============================================================
    # 主循环
    # ============================================================

    def run(self):
        """
        Search/Track 状态机:
          SEARCH → 每帧 YOLO, 检测到目标后切 TRACK
          TRACK  → 跳过 YOLO, 用缓存 ROI+margin 做局部传统CV追踪
                   连续 miss >= MAX_MISS → 降级回 SEARCH
        """
        self.updated = False
        self._debug_time("start")

        # 0. 触摸检测
        self._check_touch()

        # 1. 读帧
        img = self._cam.read()
        if img is None:
            return self._no_result()
        self._debug_time("cam_read")

        # 准备 AI 尺寸小图 (两种状态都需要, TRACK 用于裁剪, SEARCH 用于 YOLO)
        img_ai = img.resize(self._ai_w, self._ai_h) if HIRES_MODE else img

        # ============================================================
        # 分支A: SEARCH — 全帧 YOLO 检测
        # ============================================================
        if self.track_state == 'SEARCH':
            found, bbox, _ = self._detect_border(img)
            if not found or bbox is None:
                self._display(img)
                return self._no_result()
            self._debug_time("ai_detect")
            self.last_bbox = [bbox[0], bbox[1], bbox[2], bbox[3]]
            self.miss_count = 0
            self.track_state = 'TRACK'

        # ============================================================
        # 分支B: TRACK — 跳过 YOLO, 缓存 ROI + margin
        # ============================================================
        else:  # self.track_state == 'TRACK'
            self._debug_time("ai_detect(skip)")

        # 两种状态的共用 bbox (SEARCH 刚写入, TRACK 复用缓存)
        bbox = self.last_bbox

        # 3. 裁剪 ROI + 二值化 (SEARCH: YOLO bbox, TRACK: 缓存 bbox + margin)
        crop_ai, crop_ai_rect = self._crop(img_ai, bbox)
        binary = self._threshold(crop_ai)
        if binary is None:
            self._display(img)
            self._track_miss()
            return self._no_result()
        self._debug_time("threshold")

        # 4. 找四角点
        corners_ai = self._find_corners(binary)
        if corners_ai is None:
            self._display(img)
            self._track_miss()
            return self._no_result()
        self._debug_time("find_corners")

        # TRACK 模式下角点找到: 更新缓存 bbox (在 AI 坐标系)
        if self.track_state == 'TRACK':
            corners_ai_global = corners_ai.copy()
            corners_ai_global[:, 0] += crop_ai_rect[0]
            corners_ai_global[:, 1] += crop_ai_rect[1]
            self.last_bbox = self._corners_to_bbox(corners_ai_global)
            self.miss_count = 0

        # 5. 角点映射到摄像头坐标系
        corners_cam = self._map_to_camera(corners_ai, crop_ai_rect)
        self._debug_time("map_corners")

        # 6. 透视变换到标准图
        img_cv = image.image2cv(img, ensure_bgr=True, copy=False)
        M, M_inv, img_std_cv = self._perspective(corners_cam, img_cv)
        if M is None or img_std_cv is None:
            self._display(img)
            self._track_miss()
            return self._no_result()
        self._debug_time("perspective")

        # 7. 计算中心和circle3(标准图空间)
        std_h = img_std_cv.shape[0]
        circle_dist = int(std_h * CIRCLE_DIST_RATIO)
        center_std = (STD_RES[0] // 2, STD_RES[1] // 2)
        circle3_std = self._gen_circle3(center_std, circle_dist)
        self._debug_time("compute_center")

        # 8. 逆变换回原图
        center_cam = self._inverse_point(center_std, M_inv)
        circle3_cam = self._inverse_points(circle3_std, M_inv)
        self._debug_time("inverse")

        # 9. 卡尔曼滤波: 量测更新 → 预测 T+Δt (已禁用)
        center_for_err = center_cam

        # 10. 计算误差
        err_x = center_for_err[0] - self._screen_center[0] + webui.get('ofs_x', 0)
        err_y = center_for_err[1] - self._screen_center[1] + webui.get('ofs_y', 0)
        self.err_center  = self._lpf_apply([err_x, err_y])
        self.last_center = list(center_for_err)
        self.last_circle3 = circle3_cam
        self.updated = True
        self._debug_time("error")

        # 11. 触摸检测 + 显示
        self._check_touch()
        if webui.get('tuning_mode', True):
            if not self._show_params:
                img = self._draw_debug(img, img_ai, bbox, corners_cam,
                                        center_cam, center_for_err, circle3_cam)
        self._display(img)

        # 12. WebUI 实时状态
        webui.update_stats(
            fps=time.fps(),
            updated=self.updated,
            err_x=self.err_center[0], err_y=self.err_center[1],
            center_x=self.last_center[0] if self.last_center else 0,
            center_y=self.last_center[1] if self.last_center else 0,
        )

        return {
            "err_center":      self.err_center,
            "center_pos":      self.last_center,
            "screen_center":   self._screen_center,
            "circle3_points":  self.last_circle3,
            "updated":         True,
        }

    def send_uart(self, result):
        """将结果打包通过 UART 发送"""
        if self._uart is None or not self._uart.is_open():
            return
        try:
            if UART_TEXT_MODE:
                data = self._encode_text(result)
            else:
                data = self._encode_binary(result)
            self._uart.write(data)
        except Exception as e:
            if DEBUG_PRINT_ERR:
                print(f"[WARN] UART send failed: {e}")

    # ============================================================
    # 管线子步骤
    # ============================================================

    def _detect_border(self, img):
        """YOLOv5检测黑框,返回(found, bbox, img_ai)"""
        img_ai = img.resize(self._ai_w, self._ai_h) if HIRES_MODE else img
        objs = self._detector.detect(img_ai, conf_th=webui.get('conf_th', CONF_TH),
                                     iou_th=IOU_TH, fit=image.Fit.FIT_CONTAIN)
        if not objs:
            return False, None, img_ai
        best = max(objs, key=lambda o: o.w * o.h)
        return True, (best.x, best.y, best.w, best.h), img_ai

    def _crop(self, img_ai, bbox):
        """裁剪AI检测框区域,返回(crop_image, crop_rect_ai)"""
        x, y, w, h = bbox
        x1 = max(0, x - CROP_PADDING)
        y1 = max(0, y - CROP_PADDING)
        x2 = min(self._ai_w, x + w + CROP_PADDING)
        y2 = min(self._ai_h, y + h + CROP_PADDING)
        # 偶数化
        w_crop = x2 - x1
        h_crop = y2 - y1
        if w_crop % 2 != 0:
            x2 = max(x1 + 1, x2 - 1)
            w_crop = x2 - x1
        if h_crop % 2 != 0:
            y2 = max(y1 + 1, y2 - 1)
            h_crop = y2 - y1
        crop = img_ai.crop(x1, y1, w_crop, h_crop)
        return crop, [x1, y1, w_crop, h_crop]

    def _threshold(self, crop_ai):
        """大津法全局二值化 + 洪水填充,返回numpy二值图 (比自适应快~3x)"""
        gray = crop_ai.to_format(image.Format.FMT_GRAYSCALE)
        gray_cv = image.image2cv(gray, ensure_bgr=False, copy=False)

        # 大津法 (OTSU): 自动计算全局最优阈值, 无需手动调参
        _, binary = cv2.threshold(gray_cv, 0, 255,
                                   cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        if binary is None or binary.size == 0:
            return None

        if STD_FROM_WHITE_RECT:
            # 洪水填充: 从四周清掉背景噪声
            h, w = binary.shape
            mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
            cv2.floodFill(binary, mask, (2, 2), 255,
                          loDiff=FLOOD_LO_DIFF, upDiff=FLOOD_UP_DIFF, flags=4)
            cv2.floodFill(binary, mask, (w - 3, h - 3), 255,
                          loDiff=FLOOD_LO_DIFF, upDiff=FLOOD_UP_DIFF, flags=4)
            # 反转: 白纸区域变255, 黑框变0
            binary = cv2.bitwise_not(binary)

        return binary

    def _find_corners(self, binary):
        """找最大轮廓 → 多边形逼近 → 4角点排序"""
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, APPROX_EPSILON * peri, True)

        if len(approx) != 4:
            return None

        # 重塑并排序: [TL, TR, BR, BL]
        rect = approx.reshape(4, 2).astype(np.float32)
        s = rect.sum(axis=1)   # x+y
        d = np.diff(rect, axis=1)  # y-x

        ordered = np.zeros((4, 2), dtype=np.float32)
        ordered[0] = rect[np.argmin(s)]   # TL: 最小和
        ordered[2] = rect[np.argmax(s)]   # BR: 最大和
        ordered[3] = rect[np.argmax(d)]   # BL: 最大差(y-x)
        ordered[1] = rect[np.argmin(d)]   # TR: 最小差(y-x)

        # 验证最小边长
        min_w = np.linalg.norm(ordered[1] - ordered[0])
        min_h = np.linalg.norm(ordered[3] - ordered[0])
        rlim = webui.get('rect_min', RECT_MIN_LIMIT)
        if min_w < rlim or min_h < rlim:
            return None

        return ordered

    def _track_miss(self):
        """TRACK 模式丢失目标: 累加计数器, 超阈值切回 SEARCH"""
        if self.track_state != 'TRACK':
            return
        self.miss_count += 1
        if self.miss_count >= self.MAX_MISS:
            self.track_state = 'SEARCH'
            self.miss_count = 0

    def _corners_to_bbox(self, corners):
        """从 4 角点反算外接矩形 (用于 Track 模式更新缓存 ROI)"""
        x_min = int(np.min(corners[:, 0]))
        y_min = int(np.min(corners[:, 1]))
        w = int(np.max(corners[:, 0])) - x_min
        h = int(np.max(corners[:, 1])) - y_min
        return [x_min, y_min, max(w, 1), max(h, 1)]

    def _map_to_camera(self, corners_ai, crop_rect):
        """角点从AI裁剪图坐标 → 摄像头坐标"""
        cx, cy, cw, ch = crop_rect
        corners = corners_ai.copy()
        corners[:, 0] += cx
        corners[:, 1] += cy
        corners[:, 0] *= self._ai_scale_x
        corners[:, 1] *= self._ai_scale_y
        return corners

    def _perspective(self, corners_cam, img_cv):
        """透视变换到标准图 113x80"""
        dst = np.array([
            [0, 0],
            [STD_RES[0] - 1, 0],
            [STD_RES[0] - 1, STD_RES[1] - 1],
            [0, STD_RES[1] - 1],
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(corners_cam, dst)
        try:
            M_inv = np.linalg.inv(M)
        except np.linalg.LinAlgError:
            return None, None, None

        img_std_cv = cv2.warpPerspective(img_cv, M, tuple(STD_RES))
        return M, M_inv, img_std_cv

    def _gen_circle3(self, center_std, circle_dist):
        """在标准图空间生成第3圈(r=6cm)的轨迹点"""
        radius = circle_dist * webui.get('circle_ring', CIRCLE3_RING)
        angles = np.linspace(0, 2 * np.pi, CIRCLE3_POINTS, endpoint=False)
        pts = np.zeros((1, CIRCLE3_POINTS, 2), dtype=np.float32)
        pts[0, :, 0] = center_std[0] + radius * np.cos(angles)
        pts[0, :, 1] = center_std[1] + radius * np.sin(angles)
        return pts

    def _inverse_point(self, pt_std, M_inv):
        """单点逆透视变换"""
        src = np.array([[[pt_std[0], pt_std[1]]]], dtype=np.float32)
        dst = cv2.perspectiveTransform(src, M_inv)
        return dst[0][0]

    def _inverse_points(self, pts_std, M_inv):
        """多点逆透视变换"""
        dst = cv2.perspectiveTransform(pts_std, M_inv)
        return dst[0]  # (N, 2)

    # ============================================================
    # UART编码
    # ============================================================

    def _encode_binary(self, result):
        """二进制协议打包"""
        updated = 1 if result["updated"] else 0
        has_circle = 1 if (updated and len(result.get("circle3_points", [])) > 0) else 0
        flags = updated | (has_circle << 1)

        err_x = int(result["err_center"][0])
        err_y = int(result["err_center"][1])
        cx = int(result["center_pos"][0]) if result["center_pos"] else 0
        cy = int(result["center_pos"][1]) if result["center_pos"] else 0

        circle3 = result.get("circle3_points", [])
        count = len(circle3) if (has_circle and isinstance(circle3, np.ndarray)) else 0

        seq = self._seq
        self._seq = (self._seq + 1) & 0xFF

        # 固定头(字节2-12用于校验)
        header = struct.pack(
            "<BBhhHHBBH",
            flags, seq,
            err_x, err_y,
            cx, cy,
            min(count, 255),
            0,   # checksum placeholder
            0,   # reserved
        )
        # 计算校验和
        cksum = 0
        for b in header[:-3]:  # 跳过checksum位和保留位
            cksum ^= b
        header = struct.pack(
            "<BBhhHHBBH",
            flags, seq,
            err_x, err_y,
            cx, cy,
            min(count, 255),
            cksum & 0xFF,
            0,
        )

        # 拼接: 同步头 + 固定头 + circle3数据
        packet = b"\xAA\x55" + header

        if has_circle and count > 0:
            pts = circle3.astype(np.int16)
            packet += pts.tobytes()

        return packet

    def _encode_text(self, result):
        """CSV文本编码(调试用)"""
        parts = [
            str(int(result["err_center"][0])),
            str(int(result["err_center"][1])),
            "1" if result["updated"] else "0",
            str(int(result["center_pos"][0])) if result["center_pos"] else "0",
            str(int(result["center_pos"][1])) if result["center_pos"] else "0",
        ]
        circle3 = result.get("circle3_points", [])
        if isinstance(circle3, np.ndarray) and len(circle3) > 0:
            parts.append(str(len(circle3)))
            for pt in circle3:
                parts.append(str(int(pt[0])))
                parts.append(str(int(pt[1])))
        else:
            parts.append("0")
        return (",".join(parts) + "\n").encode()

    # ============================================================
    # 调试显示
    # ============================================================

    def _draw_debug(self, img, img_ai, bbox, corners_cam, center_meas, center_pred, circle3_cam):
        """绘制调试信息, center_meas=量测中心, center_pred=预测中心(KF)"""
        if self._disp is None:
            return img

        use_small = not DEBUG_DRAW_ERR_LINE and not DEBUG_DRAW_CIRCLE3
        if use_small:
            canvas = img_ai
            scale_x = 1.0 / self._ai_scale_x
            scale_y = 1.0 / self._ai_scale_y
            sc_x = self._screen_center_small[0]
            sc_y = self._screen_center_small[1]
        else:
            canvas = img
            scale_x = 1.0
            scale_y = 1.0
            sc_x = self._screen_center[0]
            sc_y = self._screen_center[1]

        # AI检测框 (bbox在AI图坐标系,画到大图需缩放)
        if DEBUG_DRAW_RECT and bbox:
            x, y, w, h = bbox
            if not use_small:
                x = int(x * self._ai_scale_x)
                y = int(y * self._ai_scale_y)
                w = int(w * self._ai_scale_x)
                h = int(h * self._ai_scale_y)
            color = image.COLOR_RED if self.updated else image.COLOR_YELLOW
            canvas.draw_rect(x, y, w, h, color, thickness=2)

        # 四角点
        if self.updated and corners_cam is not None:
            pts = []
            for c in corners_cam:
                pts.extend([int(c[0]*scale_x), int(c[1]*scale_y)])
            canvas.draw_keypoints(pts, image.COLOR_GREEN, size=4, line_thickness=1)

        # 量测中心(小空心圆)
        if self.updated and center_meas is not None:
            mx = int(center_meas[0] * scale_x)
            my = int(center_meas[1] * scale_y)
            canvas.draw_circle(mx, my, 5, image.COLOR_RED, thickness=1)

        # 预测中心(KF, 实心红=量测更新过, 实心绿=纯预测)
        if center_pred is not None:
            px = int(center_pred[0] * scale_x)
            py = int(center_pred[1] * scale_y)
            kf_color = image.COLOR_RED if self.updated else image.COLOR_GREEN
            canvas.draw_circle(px, py, 4, kf_color, thickness=-1)

        # 误差线: 预测中心 → 画面中心
        if DEBUG_DRAW_ERR_LINE and center_pred is not None:
            px = int(center_pred[0] * scale_x)
            py = int(center_pred[1] * scale_y)
            canvas.draw_line(px, py, sc_x, sc_y, image.COLOR_YELLOW, thickness=1)
            canvas.draw_circle(sc_x, sc_y, 3, image.COLOR_BLUE, thickness=1)

        # Circle3轨迹点
        if DEBUG_DRAW_CIRCLE3 and self.updated and len(circle3_cam) > 0:
            pts = []
            for pt in circle3_cam:
                pts.extend([int(pt[0]*scale_x), int(pt[1]*scale_y)])
            canvas.draw_keypoints(pts, image.COLOR_GREEN, size=1, line_thickness=0)

        # 文字: FPS + 误差
        if DEBUG_DRAW_ERR_MSG:
            fps = time.fps()
            msg = f"FPS:{fps:.1f}"
            if self.updated:
                msg += f" err:{self.err_center[0]:.0f},{self.err_center[1]:.0f}"
            canvas.draw_string(5, 5, msg, scale=1.2, thickness=1,
                              color=image.COLOR_GREEN)

        return canvas

    def _draw_params_screen(self, img):
        """二级界面: 黑底白字显示当前所有参数值"""
        w, h = img.width(), img.height()

        # 直接填充黑色背景 (不用RGBA叠加,避免格式不匹配)
        img.draw_rect(0, 0, w, h, image.COLOR_BLACK, thickness=-1)

        y = 12
        left_x = 14
        val_x = 170
        row_h = 19
        c_head  = image.COLOR_YELLOW
        c_label = image.COLOR_WHITE
        c_value = image.Color(120, 255, 0)   # 亮绿
        c_dim   = image.Color(130, 130, 130) # 灰色

        def row(label, value, unit=''):
            nonlocal y
            img.draw_string(left_x, y, label, scale=1.0, color=c_label)
            txt = f'{value}{unit}'
            tw = image.string_size(txt, scale=1.0)[0]
            img.draw_string(val_x - tw, y, txt, scale=1.0, color=c_value)
            y += row_h

        # ISP
        img.draw_string(left_x, y, '-- ISP --', scale=1.0, color=c_head)
        y += row_h + 2
        awb = webui.apply_awb_gain()
        row('  R',  f'{awb[0]:.3f}')
        row('  G',  f'{awb[1]:.3f}')
        row('  B',  f'{awb[3]:.3f}')
        row('  Contrast', webui.get('contrast', 80))
        exp = webui.get('exposure', 0)
        row('  Exposure', 'auto' if exp==0 else str(int(exp))+'us')
        onoff = 'ON' if AUTO_AWB else 'OFF'
        img.draw_string(left_x, y - row_h - 4, f'  Auto AWB: {onoff}', scale=0.8, color=c_dim)

        # Detection
        y += 4
        img.draw_string(left_x, y, '-- Detection --', scale=1.0, color=c_head)
        y += row_h + 2
        row('  YOLO conf', f'{webui.get("conf_th", 0.5):.2f}')
        row('  Rect min', webui.get('rect_min', 12))
        ring = webui.get('circle_ring', 3)
        ring_names = {0:'Bullseye', 1:'R1(2cm)', 2:'R2(4cm)', 3:'R3(6cm)', 4:'R4(8cm)'}
        row('  Ring', ring_names.get(ring, f'R{ring}'))

        # Threshold
        y += 4
        img.draw_string(left_x, y, '-- Threshold --', scale=1.0, color=c_head)
        y += row_h + 2
        row('  Block', webui.get('adp_block', 27))
        row('  C', webui.get('adp_c', 31))

        # Filter
        y += 4
        img.draw_string(left_x, y, '-- Filter --', scale=1.0, color=c_head)
        y += row_h + 2
        row('  LPF alpha', f'{webui.get("lpf_alpha", LPF_ALPHA):.2f}')
        row('  KF pred dt', f'{webui.get("kf_dt", 0.05):.2f}', 's')
        kf_q = webui.get('kf_q', 100000)
        row('  KF Q', f'{kf_q:.0f}' if kf_q < 1000 else f'{kf_q/1000:.0f}k')

        # Offset
        y += 4
        img.draw_string(left_x, y, '-- Offset --', scale=1.0, color=c_head)
        y += row_h + 2
        row('  X', webui.get('ofs_x', 0), 'px')
        row('  Y', webui.get('ofs_y', 0), 'px')

        # 帧率 + 提示
        fps = time.fps()
        img.draw_string(left_x, h - 22, f'FPS:{fps:.0f}', scale=1.0, color=c_dim)
        tip = 'tap to toggle'
        tw = image.string_size(tip, scale=0.7)[0]
        img.draw_string(w - tw - 8, h - 18, tip, scale=0.7, color=c_dim)

    def _check_touch(self):
        """检测触摸, 切换参数界面。非调参模式下跳过"""
        if not webui.get('tuning_mode', True):
            return
        if self._ts is None:
            return
        try:
            if self._ts.available():
                state = self._ts.read()       # → [x, y, pressed]
                pressed = state[2] if state else 0
                if pressed:
                    if not self._ts_touched:
                        self._ts_touched = True
                        self._show_params = not self._show_params
                else:
                    self._ts_touched = False
        except Exception:
            pass

    def _display(self, img):
        """统一的显示入口。调参模式=画面+调试, 竞赛模式=跳过(零开销)"""
        if self._disp is None:
            return
        if not webui.get('tuning_mode', True):
            return  # 不推帧 → 显示控制器复用帧缓冲, CPU 零开销
        if self._show_params:
            self._draw_params_screen(img)
        self._disp.show(img, fit=image.Fit.FIT_CONTAIN)

    def _show(self, img):
        if self._disp is not None:
            self._disp.show(img, fit=image.Fit.FIT_CONTAIN)

    # ============================================================
    # 辅助
    # ============================================================

    def _no_result(self):
        # # 卡尔曼滤波: 无观测时纯预测 (已禁用)
        # if self._kf is not None and self._kf_t is not None:
        #     now = time.ticks_ms()
        #     dt = (now - self._kf_t) / 1000.0
        #     if 0 < dt < 0.5:
        #         self._kf.predict(dt)
        #         predicted = self._kf.predict_ahead(KF_PREDICT_DT)
        #         px, py = predicted[0, 0], predicted[1, 0]
        #         self._kf_t = now
        #         err_x = px - self._screen_center[0]
        #         err_y = py - self._screen_center[1]
        #         return {
        #             "err_center":      self._lpf_apply([err_x, err_y]),
        #             "center_pos":      [px, py],
        #             "screen_center":   self._screen_center,
        #             "circle3_points":  [],
        #             "updated":         False,
        #         }
        return {
            "err_center":      [0, 0],
            "center_pos":      None,
            "screen_center":   self._screen_center,
            "circle3_points":  [],
            "updated":         False,
        }

    def _lpf_apply(self, err):
        """一阶低通 EMA: y = α*x + (1-α)*y_prev"""
        alpha = webui.get('lpf_alpha', LPF_ALPHA)
        if alpha <= 0 or alpha >= 1:
            return err
        if self._lpf_err is None:
            self._lpf_err = err
            return err
        a = alpha
        self._lpf_err = [a * err[0] + (1 - a) * self._lpf_err[0],
                         a * err[1] + (1 - a) * self._lpf_err[1]]
        return self._lpf_err

    def _debug_time(self, stage):
        if DEBUG_PRINT_TIME:
            now = time.ticks_ms()
            print(f"  [{stage}] {now - self._t}ms")
            self._t = now

    @property
    def camera_size(self):
        return [self._cam_w, self._cam_h]

    @property
    def ai_size(self):
        return [self._ai_w, self._ai_h]


# ============================================================
# 主入口
# ============================================================

def main():
    processor = None
    try:
        processor = VisualProcessor(enable_display=ENABLE_DISPLAY)
        print(f"Camera: {processor.camera_size}")
        print(f"AI input: {processor.ai_size}")
        print(f"UART: {'text' if UART_TEXT_MODE else 'binary'} @ {UART_PORT}:{UART_BAUDRATE}")

        # 启动 WebUI (后台线程)
        ui = webui.WebUI(port=WEBUI_PORT)
        ui.start()
        print(f"WebUI: http://<maixcam-ip>:{WEBUI_PORT}/")
        print("Running...")

        while not app.need_exit():
            try:
                result = processor.run()
                if result is not None:
                    processor.send_uart(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                time.sleep_ms(10)

    except Exception as e:
        import traceback
        print(f"Init failed:\n{traceback.format_exc()}")
        # 尝试在屏幕显示错误
        try:
            err_disp = display.Display()
            err_img = image.Image(err_disp.width(), err_disp.height())
            err_img.draw_string(5, 5, f"Error: {e}", scale=1.5,
                               color=image.COLOR_RED)
            err_disp.show(err_img)
            time.sleep(5)
        except:
            pass
    finally:
        if processor:
            del processor
        print("Done.")


if __name__ == "__main__":
    main()
