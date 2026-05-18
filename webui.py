"""
E-Topic 2025 — WebUI 调参面板
独立线程运行 HTTP 服务, 手机/电脑浏览器访问 http://<maixcam-ip>:8080/
"""

# Python 标准库, MaixPy 内置, 无需额外安装
import threading     # daemon 线程, 不阻塞主循环
import json          # GET/POST API 序列化
import time as _time
from http.server import HTTPServer, BaseHTTPRequestHandler  # 零依赖 HTTP 服务

# ============================================================
# HTML 单文件前端 (内嵌, 零外部资源)
# ============================================================

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<title>E-Topic Config</title>
<style>
/* === 全局 === */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
    background:#fafafa;color:#1a1a1a;max-width:480px;margin:0 auto;padding:16px 20px 40px;
    -webkit-tap-highlight-color:transparent;
}
h1{font-size:20px;font-weight:600;letter-spacing:-0.3px;margin-bottom:4px}
.subtitle{font-size:12px;color:#999;margin-bottom:24px}
/* === 卡片区块 === */
.section{
    background:#fff;border-radius:12px;padding:16px 18px;margin-bottom:14px;
    box-shadow:0 1px 3px rgba(0,0,0,0.04);
}
.section-title{
    font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;
    color:#aaa;margin-bottom:14px;
}
/* === 行: 标签 + 控件 === */
.row{display:flex;align-items:center;margin-bottom:12px}
.row:last-child{margin-bottom:0}
.label{flex:0 0 56px;font-size:13px;font-weight:500;color:#555}
.label.wide{flex:0 0 90px}
/* === 滑块 === */
.slider-wrap{flex:1;display:flex;align-items:center;gap:10px}
input[type=range]{
    flex:1;-webkit-appearance:none;height:4px;background:#e8e8e8;border-radius:2px;outline:none;
}
input[type=range]::-webkit-slider-thumb{
    -webkit-appearance:none;width:20px;height:20px;border-radius:50%;
    background:#1a1a1a;cursor:pointer;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.15);
}
/* === 数值显示 === */
.val{
    flex:0 0 44px;text-align:right;font-size:13px;font-variant-numeric:tabular-nums;
    font-family:"SF Mono","Cascadia Code",Consolas,monospace;color:#333;
}
/* === 数字微调框 === */
.spinbox{
    display:flex;align-items:center;gap:0;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;
}
.spinbox button{
    width:32px;height:32px;border:none;background:#f5f5f5;font-size:16px;cursor:pointer;color:#555;
    display:flex;align-items:center;justify-content:center;
}
.spinbox button:active{background:#e8e8e8}
.spinbox input{
    width:48px;height:32px;border:none;border-left:1px solid #e0e0e0;border-right:1px solid #e0e0e0;
    text-align:center;font-size:14px;font-family:"SF Mono","Cascadia Code",Consolas,monospace;
    outline:none;
}
/* === 下拉菜单 === */
select{
    flex:1;padding:8px 10px;border:1px solid #e0e0e0;border-radius:8px;
    font-size:13px;background:#fff;outline:none;appearance:none;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M6 8L1 3h10z' fill='%23999'/%3E%3C/svg%3E");
    background-repeat:no-repeat;background-position:right 10px center;padding-right:28px;
}
/* === 状态提示条 === */
.status{
    text-align:center;font-size:11px;color:#bbb;margin-top:8px;
    transition:color 0.3s;
}
.status.ok{color:#4caf50}
.status.err{color:#f44336}
/* === 底部按钮 === */
.footer{
    text-align:center;margin-top:20px;
}
.footer button{
    padding:8px 24px;border:1px solid #ddd;border-radius:8px;background:#fff;
    font-size:13px;cursor:pointer;color:#555;
}
.footer button:active{background:#f0f0f0}
.footer button.primary{background:#1a1a1a;color:#fff;border-color:#1a1a1a;margin-right:8px}
/* === 分段选择器 === */
.segmented{display:flex;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;flex:1}
.segmented label{flex:1;text-align:center;padding:8px 0;font-size:12px;color:#888;cursor:pointer;
    border-right:1px solid #eee;background:#fafafa;transition:all .15s}
.segmented label:last-child{border-right:none}
.segmented label.active{background:#1a1a1a;color:#fff;font-weight:600}
.segmented input{position:absolute;opacity:0;pointer-events:none}
/* === 开关 === */
.toggle-wrap{display:flex;align-items:center;justify-content:space-between}
.toggle-wrap .toggle-label{font-size:13px;font-weight:500;color:#555}
.toggle{position:relative;width:48px;height:28px}
.toggle input{opacity:0;width:0;height:0}
.toggle .slider{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;
    background:#ddd;border-radius:28px;transition:background .25s}
.toggle .slider::before{content:'';position:absolute;height:22px;width:22px;
    left:3px;bottom:3px;background:#fff;border-radius:50%;transition:transform .25s}
.toggle input:checked+.slider{background:#1a1a1a}
.toggle input:checked+.slider::before{transform:translateX(20px)}
/* === 实时状态 === */
.stats-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 16px;font-size:12px}
.stats-grid .sk{color:#999}.stats-grid .sv{font-family:"SF Mono","Cascadia Code",Consolas,monospace;color:#333;text-align:right}
.stats-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;vertical-align:middle}
.stats-dot.on{background:#4caf50}.stats-dot.off{background:#ccc}
</style>
</head>
<body>

<h1>E-Topic Config</h1>
<div class="subtitle">2025 电赛E题 · 视觉参数调校</div>

<!-- 调参模式总开关 -->
<div class="section">
    <div class="toggle-wrap">
        <span class="toggle-label">Tuning Mode</span>
        <label class="toggle">
            <input type="checkbox" id="tuning_mode" checked onchange="onTuningToggle(this.checked)">
            <span class="slider"></span>
        </label>
    </div>
</div>

<!-- 白平衡 -->
<div class="section">
    <div class="section-title">White Balance</div>
    <div class="row">
        <span class="label">R</span>
        <div class="slider-wrap">
            <input type="range" id="awb_r" min="0" max="0.50" step="0.01" value="0.13">
            <span class="val" id="awb_r_v">0.13</span>
        </div>
    </div>
    <div class="row">
        <span class="label">G</span>
        <div class="slider-wrap">
            <input type="range" id="awb_g" min="0" max="0.50" step="0.01" value="0.06">
            <span class="val" id="awb_g_v">0.06</span>
        </div>
    </div>
    <div class="row">
        <span class="label">B</span>
        <div class="slider-wrap">
            <input type="range" id="awb_b" min="0" max="0.50" step="0.01" value="0.11">
            <span class="val" id="awb_b_v">0.11</span>
        </div>
    </div>
</div>

<!-- 图像处理 -->
<div class="section">
    <div class="section-title">Image Processing</div>
    <div class="row">
        <span class="label">Contrast</span>
        <div class="slider-wrap">
            <input type="range" id="contrast" min="0" max="100" step="1" value="80">
            <span class="val" id="contrast_v">80</span>
        </div>
    </div>
    <div class="row">
        <span class="label wide">Adp Block</span>
        <div class="spinbox">
            <button onclick="spin('adp_block',-2)">−</button>
            <input type="text" id="adp_block" value="27" inputmode="numeric" pattern="[0-9]*">
            <button onclick="spin('adp_block',2)">+</button>
        </div>
    </div>
    <div class="row">
        <span class="label wide">Adp C</span>
        <div class="slider-wrap">
            <input type="range" id="adp_c" min="0" max="50" step="1" value="31">
            <span class="val" id="adp_c_v">31</span>
        </div>
    </div>
</div>

<!-- 卡尔曼滤波 (已注释,参数预留) -->
<div class="section">
    <div class="section-title">Kalman Filter</div>
    <div class="row">
        <span class="label wide">Predict DT</span>
        <div class="slider-wrap">
            <input type="range" id="kf_dt" min="0" max="0.20" step="0.01" value="0.05">
            <span class="val" id="kf_dt_v">0.05</span>
        </div>
    </div>
    <div class="row">
        <span class="label wide">Proc Noise</span>
        <select id="kf_q">
            <option value="10">10</option>
            <option value="100">100</option>
            <option value="1000">1 000</option>
            <option value="10000">10 000</option>
            <option value="100000" selected>100 000</option>
        </select>
    </div>
</div>

<!-- 瞄准偏移 -->
<div class="section">
    <div class="section-title">Aiming Offset</div>
    <div class="row">
        <span class="label">X</span>
        <div class="slider-wrap">
            <input type="range" id="ofs_x" min="-50" max="50" step="1" value="0">
            <span class="val" id="ofs_x_v">0</span>
        </div>
    </div>
    <div class="row">
        <span class="label">Y</span>
        <div class="slider-wrap">
            <input type="range" id="ofs_y" min="-50" max="50" step="1" value="0">
            <span class="val" id="ofs_y_v">0</span>
        </div>
    </div>
</div>

<!-- 目标圈号 (分段选择器) -->
<div class="section">
    <div class="section-title">Target Ring</div>
    <div class="segmented" id="circle_ring_group">
        <label><input type="radio" name="circle_ring" value="0">bulleye</label>
        <label><input type="radio" name="circle_ring" value="1">R1</label>
        <label><input type="radio" name="circle_ring" value="2">R2</label>
        <label class="active"><input type="radio" name="circle_ring" value="3" checked>R3</label>
        <label><input type="radio" name="circle_ring" value="4">R4</label>
    </div>
</div>

<!-- YOLO 置信度阈值 -->
<div class="section">
    <div class="section-title">YOLO Confidence</div>
    <div class="row">
        <span class="label wide">Conf Th</span>
        <div class="slider-wrap">
            <input type="range" id="conf_th" min="0.10" max="0.90" step="0.05" value="0.50">
            <span class="val" id="conf_th_v">0.50</span>
        </div>
    </div>
</div>

<!-- 相机曝光 (0=自动, >0=手动μs) -->
<div class="section">
    <div class="section-title">Camera Exposure</div>
    <div class="row">
        <span class="label wide">Exposure</span>
        <div class="slider-wrap">
            <input type="range" id="exposure" min="0" max="10000" step="100" value="0">
            <span class="val" id="exposure_v">auto</span>
        </div>
    </div>
</div>

<!-- 最小矩形边长 (过滤噪点) -->
<div class="section">
    <div class="section-title">Min Rect Limit</div>
    <div class="row">
        <span class="label wide">Rect Min</span>
        <div class="spinbox">
            <button onclick="spin('rect_min',-2)">−</button>
            <input type="text" id="rect_min" value="12" inputmode="numeric" pattern="[0-9]*">
            <button onclick="spin('rect_min',2)">+</button>
        </div>
    </div>
</div>

<!-- 一阶低通平滑系数 -->
<div class="section">
    <div class="section-title">LPF Smoothing</div>
    <div class="row">
        <span class="label wide">LPF Alpha</span>
        <div class="slider-wrap">
            <input type="range" id="lpf_alpha" min="0" max="1.00" step="0.05" value="0.30">
            <span class="val" id="lpf_alpha_v">0.30</span>
        </div>
    </div>
</div>

<!-- 实时运行状态 -->
<div class="section" id="live_stats">
    <div class="section-title">Live Status</div>
    <div class="stats-grid">
        <span class="sk">FPS</span><span class="sv" id="st_fps">--</span>
        <span class="sk">Detection</span><span class="sv"><span class="stats-dot off" id="st_dot"></span><span id="st_det">--</span></span>
        <span class="sk">err X</span><span class="sv" id="st_ex">--</span>
        <span class="sk">err Y</span><span class="sv" id="st_ey">--</span>
        <span class="sk">center X</span><span class="sv" id="st_cx">--</span>
        <span class="sk">center Y</span><span class="sv" id="st_cy">--</span>
    </div>
</div>

<div class="status" id="status">ready</div>

<script>
/* === API 端点 === */
const API = '/api/config';

/* === 控件格式化映射: id → 数值显示格式 === */
const SLIDERS = {
    awb_r:   {fmt:v=>parseFloat(v).toFixed(2)},
    awb_g:   {fmt:v=>parseFloat(v).toFixed(2)},
    awb_b:   {fmt:v=>parseFloat(v).toFixed(2)},
    contrast:{fmt:v=>parseInt(v)},
    exposure:{fmt:v=>v==0?'auto':Math.round(v)+'us'},
    adp_c:   {fmt:v=>parseInt(v)},
    conf_th: {fmt:v=>parseFloat(v).toFixed(2)},
    lpf_alpha:{fmt:v=>parseFloat(v).toFixed(2)},
    kf_dt:   {fmt:v=>parseFloat(v).toFixed(2)},
    ofs_x:   {fmt:v=>parseInt(v)},
    ofs_y:   {fmt:v=>parseInt(v)},
};

/* === 底部状态条 === */
function status(msg, ok){
    const el = document.getElementById('status');
    el.textContent = msg;
    el.className = 'status ' + (ok === true ? 'ok' : ok === false ? 'err' : '');
}

/* === 分段选择器: 点选切换高亮 → POST ring 值 === */
document.querySelectorAll('.segmented input').forEach(radio=>{
    radio.addEventListener('change', function(){
        const group = this.closest('.segmented');
        group.querySelectorAll('label').forEach(l=>l.classList.remove('active'));
        this.parentElement.classList.add('active');
        send(this.name, parseInt(this.value));
    });
});

/* === 页面加载: GET 全部配置 → 回填所有控件 === */
fetch(API).then(r=>r.json()).then(cfg=>{
    for(const [k,v] of Object.entries(cfg)){
        const el = document.getElementById(k);
        if(k === 'adp_block'){
            if(el) el.value = v;
        } else if(k === 'rect_min'){
            if(el) el.value = v;
        } else if(k === 'kf_q'){
            if(el) el.value = String(v);
        } else if(k === 'circle_ring' || k === 'conf_th' || k === 'lpf_alpha' || k === 'exposure'){
            if(k === 'circle_ring'){
                // 分段选择器: 匹配值并点亮对应标签
                document.querySelectorAll('.segmented input').forEach(r=>{
                    if(parseInt(r.value)===v) r.checked=true;
                    r.parentElement.classList.toggle('active', parseInt(r.value)===v);
                });
            }
        }
        if(!el) continue;
        el.value = v;
        const disp = document.getElementById(k+'_v');
        const s = SLIDERS[k];
        if(disp && s) disp.textContent = s.fmt(v);
    }
}).catch(e=>status('load failed',false));

/* === 滑块 & 下拉菜单: 拖动/选择 → 实时更新数值显示 → POST 到后端 === */
document.querySelectorAll('input[type=range], select').forEach(el=>{
    el.addEventListener('input', function(){
        const id = this.id;
        const disp = document.getElementById(id+'_v');
        const s = SLIDERS[id];
        if(disp && s) disp.textContent = s.fmt(this.value);
        send(id, this.id==='kf_q' ? parseInt(this.value) : parseFloat(this.value));
    });
});

/* === 数字微调框: ±按钮 + 手动输入 === */
function spin(id, delta){
    const el = document.getElementById(id);
    let v = parseInt(el.value) || 27;
    v += delta;
    if(id==='adp_block'){
        v = Math.max(11, Math.min(99, v));
        if(v % 2 === 0) v += delta > 0 ? 1 : -1;  // 强制奇数
    }
    el.value = v;
    send(id, v);
}
document.getElementById('adp_block').addEventListener('change', function(){
    let v = parseInt(this.value) || 27;
    v = Math.max(11, Math.min(99, v));
    if(v % 2 === 0) v += 1;
    this.value = v;
    send('adp_block', v);
});

/* === 防抖发送: 150ms 内连续操作只发最后一次 POST === */
let _timer = null;
function send(key, value){
    status('...');
    clearTimeout(_timer);
    _timer = setTimeout(()=>{
        fetch(API, {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({[key]:value})
        }).then(r=>r.json()).then(r=>{
            if(r.ok) status('saved', true);
            else status('fail', false);
        }).catch(e=>status('offline', false));
    }, 150);
}

/* === 调参模式总开关 === */
function onTuningToggle(on){
    send('tuning_mode', on ? 1 : 0);
    const sections = document.querySelectorAll('.section');
    sections.forEach((s,i)=>{
        if(i===0) return;
        s.style.display = on ? '' : 'none';
    });
    document.getElementById('live_stats').style.display = '';
}

/* === 实时状态轮询 (500ms) === */
setInterval(()=>{
    fetch('/api/stats').then(r=>r.json()).then(s=>{
        document.getElementById('st_fps').textContent = s.fps.toFixed(1);
        const ok = s.updated;
        document.getElementById('st_det').textContent = ok ? 'YES' : 'NO';
        const dot = document.getElementById('st_dot');
        dot.className = 'stats-dot ' + (ok ? 'on' : 'off');
        document.getElementById('st_ex').textContent = s.err_x;
        document.getElementById('st_ey').textContent = s.err_y;
        document.getElementById('st_cx').textContent = s.center_x;
        document.getElementById('st_cy').textContent = s.center_y;
    }).catch(()=>{});
}, 500);
</script>
<!-- 页面结束: 所有交互走 AJAX, 零整页刷新 -->
</body>
</html>"""

# ============================================================
# HTTP Handler & Server — 后台线程处理浏览器请求
# ============================================================

# 运行时配置存储 (模块级全局 dict, WebUI 前端和 project.py 管线共享)
# 前端 POST 写 → dict 更新 → 管线 webui.get() 读, 零拷贝
_runtime_config = {
    'tuning_mode': True,                                     # 调参模式开关
    'awb_r': 0.134, 'awb_g': 0.0625, 'awb_b': 0.1139,     # 白平衡 [R, G, G, B]
    'contrast': 80,                                         # 对比度 0-100
    'exposure': 0,                                          # 曝光 0=自动, >0=手动(μs)
    'adp_block': 27, 'adp_c': 31,                          # 自适应二值化参数
    'conf_th': 0.5,                                         # YOLO 置信度阈值
    'rect_min': 12,                                         # 最小矩形边长(过滤噪点)
    'circle_ring': 3,                                       # 目标圈号 0=靶心, 3=6cm
    'lpf_alpha': 0.3,                                       # 一阶低通平滑系数
    'kf_dt': 0.05, 'kf_q': 100000,                         # 卡尔曼滤波参数(预留)
    'ofs_x': 0, 'ofs_y': 0,                                # 瞄准偏移(像素)
}

# 运行时统计 (project.py 每帧调用 update_stats, 前端轮询 /api/stats)
_runtime_stats = {
    'fps': 0.0, 'updated': False,
    'err_x': 0, 'err_y': 0,
    'center_x': 0, 'center_y': 0,
    'tuning': True,
}

# ISP 回调: WebUI 修改 awb/contrast/exposure 时触发, 由 project.py 注册
_isp_callback = None  # callable(key, value)


class _ConfigHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器: GET 返回页面/配置, POST 写入配置"""

    def log_message(self, format, *args):
        pass  # 静默日志, 避免刷屏

    def do_GET(self):
        """GET / → HTML页面  GET /api/config → JSON配置"""
        if self.path == '/' or self.path == '/index.html':
            self._respond(200, 'text/html; charset=utf-8', HTML_PAGE.encode())
        elif self.path == '/api/config':
            self._respond(200, 'application/json',
                          json.dumps(_runtime_config).encode())
        elif self.path == '/api/stats':
            self._respond(200, 'application/json',
                          json.dumps(_runtime_stats).encode())
        else:
            self._respond(404, 'text/plain', b'Not Found')

    def do_POST(self):
        """POST /api/config → 写配置 + 触发 ISP 回调"""
        if self.path == '/api/config':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                updates = json.loads(body)                       # 解析前端传来的 {key: value}
                for key, value in updates.items():
                    if key in _runtime_config:
                        _runtime_config[key] = value             # 写入全局 dict
                        if _isp_callback:
                            try:
                                _isp_callback(key, value)        # 通知 project.py (如更新摄像头)
                            except Exception:
                                pass
                self._respond(200, 'application/json',
                              json.dumps({'ok': True}).encode())
            except Exception as e:
                self._respond(400, 'application/json',
                              json.dumps({'ok': False, 'error': str(e)}).encode())
        else:
            self._respond(404, 'text/plain', b'Not Found')

    def _respond(self, code, content_type, data):
        """统一 HTTP 响应"""
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')    # 允许任意域名跨域
        self.end_headers()
        self.wfile.write(data)


class WebUI:
    """轻量级 HTTP 配置面板: HTTPServer + daemon 线程, 不阻塞主循环"""

    def __init__(self, host='0.0.0.0', port=8080):
        self._server = HTTPServer((host, port), _ConfigHandler)
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        daemon=True, name='webui')  # daemon: 主线程退出自动消亡

    def start(self):
        """启动后台 HTTP 线程"""
        self._thread.start()

    def stop(self):
        """关闭 HTTP 服务"""
        self._server.shutdown()


# ============================================================
# 便捷 API — 供 project.py 帧循环调用
# ============================================================

def get_config():
    """返回全部配置 dict (调试用)"""
    return _runtime_config

def get(key, default=None):
    """读取单个配置值 (帧循环高频调用, O(1) dict lookup)"""
    return _runtime_config.get(key, default)

def set_isp_callback(cb):
    """注册 ISP 参数变更回调: WebUI 改 awb/contrast/exposure → 重写摄像头寄存器"""
    global _isp_callback
    _isp_callback = cb

def apply_awb_gain():
    """根据 awb_r/g/b 构建 AWB_GAIN 列表 [R, G, G, B] (GR/GB 统一用 G)"""
    c = _runtime_config
    return [c['awb_r'], c['awb_g'], c['awb_g'], c['awb_b']]

def update_stats(fps=0.0, updated=False, err_x=0, err_y=0, center_x=0, center_y=0):
    """project.py 每帧调用, 更新运行时统计供 WebUI 前端轮询"""
    s = _runtime_stats
    s['fps'] = round(fps, 1)
    s['updated'] = updated
    s['err_x'] = int(err_x)
    s['err_y'] = int(err_y)
    s['center_x'] = int(center_x)
    s['center_y'] = int(center_y)
    s['tuning'] = _runtime_config.get('tuning_mode', True)
