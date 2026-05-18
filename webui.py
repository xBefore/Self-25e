"""
E-Topic 2025 — WebUI 调参面板
独立线程运行 HTTP 服务, 手机/电脑浏览器访问 http://<maixcam-ip>:8080/
"""

import threading
import json
import time as _time
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================
# HTML 单文件前端
# ============================================================

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<title>E-Topic Config</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
    background:#fafafa;color:#1a1a1a;max-width:480px;margin:0 auto;padding:16px 20px 40px;
    -webkit-tap-highlight-color:transparent;
}
h1{font-size:20px;font-weight:600;letter-spacing:-0.3px;margin-bottom:4px}
.subtitle{font-size:12px;color:#999;margin-bottom:24px}
.section{
    background:#fff;border-radius:12px;padding:16px 18px;margin-bottom:14px;
    box-shadow:0 1px 3px rgba(0,0,0,0.04);
}
.section-title{
    font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;
    color:#aaa;margin-bottom:14px;
}
.row{display:flex;align-items:center;margin-bottom:12px}
.row:last-child{margin-bottom:0}
.label{flex:0 0 56px;font-size:13px;font-weight:500;color:#555}
.label.wide{flex:0 0 90px}
.slider-wrap{flex:1;display:flex;align-items:center;gap:10px}
input[type=range]{
    flex:1;-webkit-appearance:none;height:4px;background:#e8e8e8;border-radius:2px;outline:none;
}
input[type=range]::-webkit-slider-thumb{
    -webkit-appearance:none;width:20px;height:20px;border-radius:50%;
    background:#1a1a1a;cursor:pointer;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.15);
}
.val{
    flex:0 0 44px;text-align:right;font-size:13px;font-variant-numeric:tabular-nums;
    font-family:"SF Mono","Cascadia Code",Consolas,monospace;color:#333;
}
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
select{
    flex:1;padding:8px 10px;border:1px solid #e0e0e0;border-radius:8px;
    font-size:13px;background:#fff;outline:none;appearance:none;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M6 8L1 3h10z' fill='%23999'/%3E%3C/svg%3E");
    background-repeat:no-repeat;background-position:right 10px center;padding-right:28px;
}
.status{
    text-align:center;font-size:11px;color:#bbb;margin-top:8px;
    transition:color 0.3s;
}
.status.ok{color:#4caf50}
.status.err{color:#f44336}
.footer{
    text-align:center;margin-top:20px;
}
.footer button{
    padding:8px 24px;border:1px solid #ddd;border-radius:8px;background:#fff;
    font-size:13px;cursor:pointer;color:#555;
}
.footer button:active{background:#f0f0f0}
.footer button.primary{background:#1a1a1a;color:#fff;border-color:#1a1a1a;margin-right:8px}
</style>
</head>
<body>

<h1>E-Topic Config</h1>
<div class="subtitle">2025 电赛E题 · 视觉参数调校</div>

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

<div class="status" id="status">ready</div>

<script>
const API = '/api/config';
const SLIDERS = {
    awb_r:   {fmt:v=>parseFloat(v).toFixed(2)},
    awb_g:   {fmt:v=>parseFloat(v).toFixed(2)},
    awb_b:   {fmt:v=>parseFloat(v).toFixed(2)},
    contrast:{fmt:v=>parseInt(v)},
    adp_c:   {fmt:v=>parseInt(v)},
    kf_dt:   {fmt:v=>parseFloat(v).toFixed(2)},
    ofs_x:   {fmt:v=>parseInt(v)},
    ofs_y:   {fmt:v=>parseInt(v)},
};

function status(msg, ok){
    const el = document.getElementById('status');
    el.textContent = msg;
    el.className = 'status ' + (ok === true ? 'ok' : ok === false ? 'err' : '');
}

// Fetch current config
fetch(API).then(r=>r.json()).then(cfg=>{
    for(const [k,v] of Object.entries(cfg)){
        const el = document.getElementById(k);
        if(!el) continue;
        if(k === 'adp_block'){
            el.value = v;
        } else if(k === 'kf_q'){
            el.value = String(v);
        } else {
            el.value = v;
            const disp = document.getElementById(k+'_v');
            const s = SLIDERS[k];
            if(disp) disp.textContent = s ? s.fmt(v) : v;
        }
    }
}).catch(e=>status('load failed',false));

// Slider & select change → POST
document.querySelectorAll('input[type=range], select').forEach(el=>{
    el.addEventListener('input', function(){
        const id = this.id;
        const disp = document.getElementById(id+'_v');
        const s = SLIDERS[id];
        if(disp && s) disp.textContent = s.fmt(this.value);
        send(id, this.id==='kf_q' ? parseInt(this.value) : parseFloat(this.value));
    });
});

// Spinbox
function spin(id, delta){
    const el = document.getElementById(id);
    let v = parseInt(el.value) || 27;
    v += delta;
    if(id==='adp_block'){
        v = Math.max(11, Math.min(99, v));
        if(v % 2 === 0) v += delta > 0 ? 1 : -1;
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
</script>
</body>
</html>"""

# ============================================================
# HTTP Handler & Server
# ============================================================

# 运行时配置存储 (模块级, WebUI 和 pipeline 共享)
_runtime_config = {
    'awb_r': 0.134, 'awb_g': 0.0625, 'awb_b': 0.1139,  # AWB GAIN [R, G, G, B]
    'contrast': 80,
    'adp_block': 27, 'adp_c': 31,                        # adaptive threshold
    'kf_dt': 0.05, 'kf_q': 100000,                        # kalman
    'ofs_x': 0, 'ofs_y': 0,                               # aiming offset
}

# 可选回调: 当 ISP 相关参数变化时调用
_isp_callback = None  # callable(key, value)


class _ConfigHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默 HTTP 日志

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._respond(200, 'text/html; charset=utf-8', HTML_PAGE.encode())
        elif self.path == '/api/config':
            self._respond(200, 'application/json',
                          json.dumps(_runtime_config).encode())
        else:
            self._respond(404, 'text/plain', b'Not Found')

    def do_POST(self):
        if self.path == '/api/config':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                updates = json.loads(body)
                for key, value in updates.items():
                    if key in _runtime_config:
                        _runtime_config[key] = value
                        if _isp_callback:
                            try:
                                _isp_callback(key, value)
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
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)


class WebUI:
    """轻量级 HTTP 配置面板, 运行在后台 daemon 线程"""
    def __init__(self, host='0.0.0.0', port=8080):
        self._server = HTTPServer((host, port), _ConfigHandler)
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        daemon=True, name='webui')

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()


# ============================================================
# 便捷 API (供 project.py 调用)
# ============================================================

def get_config():
    """返回当前配置 dict (性能敏感, 帧循环中谨慎使用)"""
    return _runtime_config

def get(key, default=None):
    """读取单个配置值"""
    return _runtime_config.get(key, default)

def set_isp_callback(cb):
    """设置 ISP 参数变更回调 (WebUI 修改 awb/contrast 时触发)"""
    global _isp_callback
    _isp_callback = cb

def apply_awb_gain():
    """根据当前 awb_r/g/b 构建 AWB_GAIN 列表"""
    c = _runtime_config
    return [c['awb_r'], c['awb_g'], c['awb_g'], c['awb_b']]
