import numpy as np
import pygame
import sounddevice as sd
import ctypes
import os
from ctypes import Structure, windll, byref, c_long

# ==============================
# デバイス自動選択
# ==============================
def find_input_device():
    devices = sd.query_devices()
    priority_keywords = [
        "stereo mix", "ステレオ ミキサー",
        "vb-audio", "vb-cable", "virtual cable"
    ]
    for key in priority_keywords:
        for d in devices:
            if d['max_input_channels'] > 0 and key.lower() in d['name'].lower():
                print(f"[Input] Selected: {d['name']}")
                return d
    for d in devices:
        if d['max_input_channels'] > 0:
            print(f"[Input] Fallback: {d['name']}")
            return d
    raise RuntimeError("No input device found")

def find_output_device():
    devices = sd.query_devices()
    for d in devices:
        if d['max_output_channels'] > 0:
            print(f"[Output] Selected: {d['name']}")
            return d
    raise RuntimeError("No output device found")

input_device = find_input_device()
find_output_device()

INPUT_DEVICE_INDEX = input_device['index']
SR = int(input_device['default_samplerate'])

# ==============================
# 透過ウィンドウ設定
# ==============================
class RECT(Structure):
    _fields_ = [("left", c_long), ("top", c_long),
                ("right", c_long), ("bottom", c_long)]

class MONITORINFO(Structure):
    _fields_ = [('cbSize', ctypes.c_ulong),
                ('rcMonitor', RECT),
                ('rcWork', RECT),
                ('dwFlags', ctypes.c_ulong)]

def get_monitor_work_area(hwnd):
    monitor = windll.user32.MonitorFromWindow(hwnd, 2)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    windll.user32.GetMonitorInfoW(monitor, byref(info))
    return info.rcWork

pygame.init()
pygame.display.init()

temp = pygame.display.set_mode((100, 100))
hwnd = pygame.display.get_wm_info()["window"]
rc = get_monitor_work_area(hwnd)
pygame.display.quit()

VISUALIZER_HEIGHT = 300
SCREEN_WIDTH = rc.right - rc.left
WINDOW_Y = rc.bottom - VISUALIZER_HEIGHT
os.environ['SDL_VIDEO_WINDOW_POS'] = f'{rc.left},{WINDOW_Y}'

screen = pygame.display.set_mode(
    (SCREEN_WIDTH, VISUALIZER_HEIGHT),
    pygame.NOFRAME | pygame.SRCALPHA
)
pygame.display.set_caption("Visualizer")
hwnd = pygame.display.get_wm_info()["window"]

# ---- Win32 style ----
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008

style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
windll.user32.SetWindowLongW(
    hwnd, GWL_EXSTYLE,
    style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST
)

windll.user32.SetLayeredWindowAttributes(hwnd, 0x000000, 0, 0x1)

HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

# ==============================
# ビジュアライザー設定
# ==============================
BLOCK_SIZE = 2048
N_BARS = 128
BAR_HEIGHT = 250
BAR_WIDTH = screen.get_width() // N_BARS

buffer = np.zeros(BLOCK_SIZE, dtype=np.float32)
prev_bar_heights = np.zeros(N_BARS)
clock = pygame.time.Clock()

visual_peak = 0.15
VISUAL_PEAK_DECAY = 0.985

# ==============================
# オーディオ入力
# ==============================
def audio_callback(indata, frames, time_info, status):
    global buffer
    buffer = indata[:, 0].copy()

stream = sd.InputStream(
    samplerate=SR,
    blocksize=BLOCK_SIZE,
    device=INPUT_DEVICE_INDEX,
    channels=1,
    dtype='float32',
    callback=audio_callback
)
stream.start()

# ==============================
# 周波数ビン
# ==============================
def create_bins(sr, n):
    linear = int(n * 0.4)
    log = n - linear
    return np.concatenate([
        np.linspace(20, 1200, linear, endpoint=False),
        np.logspace(np.log10(1200), np.log10(sr / 2), log)
    ])

log_bins = create_bins(SR, N_BARS)

# ==============================
# スペクトル
# ==============================
def spectrum(audio):
    global prev_bar_heights
    fft = np.abs(np.fft.rfft(audio * np.hanning(len(audio))))
    freqs = np.fft.rfftfreq(len(audio), 1 / SR)

    bars = np.zeros(N_BARS)
    for i in range(N_BARS):
        mask = (freqs >= log_bins[i]) & (
            freqs < (log_bins[i + 1] if i + 1 < len(log_bins) else SR)
        )
        power = np.mean(fft[mask]) if np.any(mask) else 1e-9
        raw = np.clip(np.log10(power + 1e-9) + 5, 0, 1)
        bars[i] = prev_bar_heights[i] * 0.7 + raw * 0.3

    prev_bar_heights[:] = bars
    return bars

# ==============================
# メインループ（安全版）
# ==============================
running = True
while running:
    screen.fill((0, 0, 0))

    # ★ ここが最大の修正点
    try:
        events = pygame.event.get()
    except SystemError:
        pygame.event.clear()
        events = []

    for event in events:
        if event.type == pygame.QUIT:
            running = False

    # ★ 毎フレーム最前面を保証（ACTIVEEVENT不要）
    windll.user32.SetWindowPos(
        hwnd, HWND_TOPMOST,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    )

    bars = spectrum(buffer)
    peak = max(np.max(bars), visual_peak * VISUAL_PEAK_DECAY)
    visual_peak = peak

    for i, v in enumerate(bars / max(peak, 0.1)):
        h = max(1, int(v * BAR_HEIGHT))
        x = i * BAR_WIDTH
        y = screen.get_height() - h
        color = (
            int(173 + v * 80),
            int(216 - v * 70),
            int(230 - v * 100)
        )
        pygame.draw.rect(screen, color, (x, y, BAR_WIDTH - 2, h))

    pygame.display.flip()
    clock.tick(60)

stream.stop()
stream.close()
pygame.quit()
