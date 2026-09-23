"""
display/web_preview.py - watch QUBE live in any web browser.

Runs a tiny web server (Python standard library only). Open the printed address on
a laptop or phone on the same network and you'll see all four faces drawn as LED
dots, the band levels, and buttons to change mode. Works on the Pi with the real
USB mic, or on a computer with --fake-audio.
"""
import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import colors
from display import to_uint8

# The band meters on the page are drawn in each band's loud colour from colors.py.
BAND_COLORS = {"bass": colors.BASS_LOUD, "bassMid": colors.BASS_MID_LOUD, "mid": colors.MID_LOUD,
               "midHigh": colors.MID_HIGH_LOUD, "high": colors.HIGH_LOUD, "highTop": colors.HIGH_TOP_LOUD}


class PreviewServer(ThreadingHTTPServer):
    # On Windows, address reuse lets a second copy of the program silently share the
    # port with the first one. Turn it off there, so the second copy reports an error.
    allow_reuse_address = os.name != "nt"

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>QUBE Preview</title>
<style>
  body { margin: 0; background: #0b0b0f; color: #ccc; font: 14px system-ui, sans-serif; }
  header { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; padding: 12px 16px; }
  #mode { font-weight: 600; color: #fff; min-width: 140px; }
  button { background: #1d1d24; color: #eee; border: 1px solid #444; border-radius: 6px; padding: 6px 12px; cursor: pointer; }
  .meter { display: inline-block; width: 80px; height: 10px; background: #222; border-radius: 5px; overflow: hidden; vertical-align: middle; }
  .meter div { height: 100%; width: 0; }
  #beat { display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #333; vertical-align: middle; }
  .tabs { display: flex; gap: 6px; padding: 0 16px; }
  .tab.active, .face.active { background: #38506b; border-color: #6c9bc8; }
  .view { display: none; }
  .view.active { display: block; }
  canvas { display: block; margin: 8px auto; max-width: 98%; image-rendering: pixelated; }
  #panel-view canvas { width: min(400px, 92vw); height: min(400px, 92vw); background: #000; }
  .faces { display: flex; justify-content: center; gap: 6px; margin: 12px 0 4px; }
</style></head><body>
<header>
  <span id="mode">connecting...</span>
  <button onclick="send('prev')">&#9664; Prev</button>
  <button onclick="send('next')">Next &#9654;</button>
  <button onclick="send('leds')">LEDs on/off</button>
  <button onclick="send('qr')">QR code</button>
  <button onclick="send('restart')">Restart</button>
  <span>bass <span class="meter"><div id="bass" style="background:__bass__"></div></span></span>
  <span>bassMid <span class="meter"><div id="bassMid" style="background:__bassMid__"></div></span></span>
  <span>mid <span class="meter"><div id="mid" style="background:__mid__"></div></span></span>
  <span>midHigh <span class="meter"><div id="midHigh" style="background:__midHigh__"></div></span></span>
  <span>high <span class="meter"><div id="high" style="background:__high__"></div></span></span>
  <span>highTop <span class="meter"><div id="highTop" style="background:__highTop__"></div></span></span>
  <span>beat <span id="beat"></span></span>
  <span id="stats"></span>
</header>
<nav class="tabs" aria-label="Preview view">
  <button class="tab active" data-view="qube-view">QUBE</button>
  <button class="tab" data-view="panel-view">Panel 40x40</button>
</nav>
<section id="qube-view" class="view active">
  <canvas id="view"></canvas>
</section>
<section id="panel-view" class="view">
  <div class="faces" aria-label="Panel selector">
    <button class="face active" data-face="0">Face 1</button>
    <button class="face" data-face="1">Face 2</button>
    <button class="face" data-face="2">Face 3</button>
    <button class="face" data-face="3">Face 4</button>
  </div>
  <canvas id="panel"></canvas>
</section>
<script>
const FPS = __FPS__, SCALE = 6, GAP = 10;
const canvas = document.getElementById('view'), ctx = canvas.getContext('2d');
const panelCanvas = document.getElementById('panel'), panelCtx = panelCanvas.getContext('2d');
let image = null, dot = null, panelFace = 0, latest = null;

for (const tab of document.querySelectorAll('.tab')) {
  tab.onclick = () => {
    for (const button of document.querySelectorAll('.tab')) button.classList.remove('active');
    for (const view of document.querySelectorAll('.view')) view.classList.remove('active');
    tab.classList.add('active');
    document.getElementById(tab.dataset.view).classList.add('active');
  };
}
for (const face of document.querySelectorAll('.face')) {
  face.onclick = () => {
    for (const button of document.querySelectorAll('.face')) button.classList.remove('active');
    face.classList.add('active');
    panelFace = +face.dataset.face;
    if (latest) drawPanel(latest.rgb, latest.width, latest.height);
  };
}

function send(cmd) { fetch('/cmd/' + cmd); }

function makeDot() {                       // round LED shape inside a SCALE x SCALE cell
  const d = new Uint8Array(SCALE * SCALE), c = (SCALE - 1) / 2;
  for (let y = 0; y < SCALE; y++)
    for (let x = 0; x < SCALE; x++)
      d[y * SCALE + x] = ((x - c) ** 2 + (y - c) ** 2 <= (SCALE * 0.45) ** 2) ? 1 : 0;
  return d;
}

function draw(rgb, w, h, face) {
  const faces = Math.round(w / face), cw = w * SCALE + GAP * (faces - 1), ch = h * SCALE;
  if (!image || image.width !== cw || image.height !== ch) {
    canvas.width = cw; canvas.height = ch;
    image = ctx.createImageData(cw, ch); dot = makeDot();
  }
  const out = image.data;
  for (let i = 0; i < out.length; i += 4) { out[i] = out[i + 1] = out[i + 2] = 0; out[i + 3] = 255; }
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const s = (y * w + x) * 3;
      let r = rgb[s], g = rgb[s + 1], b = rgb[s + 2];
      if (r + g + b === 0) { r = g = b = 22; }          // unlit LEDs look dark gray
      const ox = x * SCALE + Math.floor(x / face) * GAP, oy = y * SCALE;
      for (let dy = 0; dy < SCALE; dy++) {
        let o = ((oy + dy) * cw + ox) * 4;
        for (let dx = 0; dx < SCALE; dx++, o += 4) {
          if (dot[dy * SCALE + dx]) { out[o] = r; out[o + 1] = g; out[o + 2] = b; }
        }
      }
    }
  }
  ctx.putImageData(image, 0, 0);
}

function drawPanel(rgb, w, h) {
  const size = h * 10;
  if (panelCanvas.width !== size || panelCanvas.height !== size) {
    panelCanvas.width = size; panelCanvas.height = size;
  }
  const image = panelCtx.createImageData(size, size), out = image.data;
  const left = panelFace * h;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < h; x++) {
      const source = (y * w + left + x) * 3;
      let r = rgb[source], g = rgb[source + 1], b = rgb[source + 2];
      if (r + g + b === 0) r = g = b = 22;
      for (let dy = 0; dy < 10; dy++) {
        for (let dx = 0; dx < 10; dx++) {
          const distance = (dx - 4.5) ** 2 + (dy - 4.5) ** 2;
          if (distance <= 4.5 ** 2) {
            const target = ((y * 10 + dy) * size + x * 10 + dx) * 4;
            out[target] = r; out[target + 1] = g; out[target + 2] = b; out[target + 3] = 255;
          }
        }
      }
    }
  }
  panelCtx.putImageData(image, 0, 0);
}

function showInfo(info) {
  document.getElementById('mode').textContent = info.mode;
  for (const k of ['bass', 'bassMid', 'mid', 'midHigh', 'high', 'highTop'])
    document.getElementById(k).style.width = Math.round(info[k] * 100) + '%';
  document.getElementById('beat').style.background = info.beat > 0.2 ? '#ff5020' : '#333';
  document.getElementById('stats').textContent =
    info.fps.toFixed(0) + ' fps | mic ' + info.volume_db.toFixed(0) + ' dB' + (info.silent ? ' | silent' : '') +
    (info.leds === false ? ' | LEDs OFF' : '');
}

async function tick() {
  try {
    const res = await fetch('/frame', { cache: 'no-store' });
    const rgb = new Uint8Array(await res.arrayBuffer());
    const width = +res.headers.get('X-Width'), height = +res.headers.get('X-Height');
    draw(rgb, width, height, +res.headers.get('X-Face'));
    latest = { rgb, width, height };
    drawPanel(rgb, width, height);
    showInfo(JSON.parse(res.headers.get('X-Info')));
  } catch (e) {
    document.getElementById('mode').textContent = 'waiting for QUBE...';
  }
  setTimeout(tick, 1000 / FPS);
}
tick();
</script></body></html>
"""


class WebPreview:
    wants_brightness = False    # show full brightness so colors are easy to judge on a screen

    def __init__(self, layout, cfg):
        self.layout = layout
        self.interval = 1.0 / max(cfg.WEB_PREVIEW_FPS, 1)
        self.lock = threading.Lock()
        self.frame_bytes = bytes(layout.width * layout.height * 3)
        self.info_json = json.dumps({"mode": "starting", "bass": 0, "bassMid": 0,
                                     "mid": 0, "midHigh": 0, "high": 0, "highTop": 0,
                                     "beat": 0, "fps": 0, "volume_db": -120, "silent": True})
        self.last_update = 0.0
        self.commands = []
        page = PAGE.replace("__FPS__", str(cfg.WEB_PREVIEW_FPS))
        for band, color in BAND_COLORS.items():
            page = page.replace(f"__{band}__", "#%02x%02x%02x" % tuple(
                round(255 * min(max(c, 0.0), 1.0)) for c in color))
        page = page.encode("utf-8")
        preview = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    self.reply(200, "text/html; charset=utf-8", page)
                elif self.path.startswith("/frame"):
                    with preview.lock:
                        body, info = preview.frame_bytes, preview.info_json
                    self.reply(200, "application/octet-stream", body,
                               {"X-Width": layout.width, "X-Height": layout.height,
                                "X-Face": layout.face, "X-Info": info})
                elif self.path.startswith("/cmd/"):
                    with preview.lock:
                        preview.commands.append(self.path[len("/cmd/"):])
                    self.reply(204, "text/plain", b"")
                else:
                    self.reply(404, "text/plain", b"not found")

            def reply(self, code, content_type, body, headers=None):
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                for key, value in (headers or {}).items():
                    self.send_header(key, str(value))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def log_message(self, *args):
                pass     # keep the terminal quiet

        port = cfg.WEB_PREVIEW_PORT
        try:
            self.server = PreviewServer(("0.0.0.0", port), Handler)
        except OSError as error:
            raise RuntimeError(f"Web preview can't use port {port} ({error}). "
                               "Change WEB_PREVIEW_PORT in config.py.") from error
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print("Web preview running. Open one of these in a browser:")
        print(f"    http://localhost:{port}            (on this computer)")
        print(f"    http://{local_ip()}:{port}   (from another device on the same network)")

    def show(self, frame, info):
        now = time.monotonic()
        if now - self.last_update < self.interval:
            return                   # the browser only needs WEB_PREVIEW_FPS frames per second
        self.last_update = now
        data = to_uint8(frame).tobytes()
        text = json.dumps(info)
        with self.lock:
            self.frame_bytes, self.info_json = data, text

    def poll_commands(self):
        with self.lock:
            commands, self.commands = self.commands, []
        return commands

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def local_ip():
    """Best guess at this computer's address on the local network."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))     # no packet is actually sent
            return s.getsockname()[0]
    except OSError:
        return socket.gethostname() + ".local"
