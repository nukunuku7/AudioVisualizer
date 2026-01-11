# ==============================
# 仮想環境有効かコマンド
# muvenv\Scripts\activate
#
# 使用するプロジェクトを変える際は、仮想環境を無効化してから行うこと
# deactivate
# ==============================

import numpy as np
import pygame
import sounddevice as sd
import ctypes
import os
import time
from ctypes import Structure, windll, byref, c_long

# ==============================
# デバイス自動選択
# ==============================

def find_input_device():
    devices = sd.query_devices()
    priority_keywords = [
        "stereo mix",
        "ステレオ ミキサー",
        "vb-audio",
        "vb-cable",
        "virtual cable"
    ]

    for key in priority_keywords:
        for d in devices:
            if d["max_input_channels"] > 0 and key.lower() in d["name"].lower():
                print(f"[Input] Selected: {d['name']}")
                return d

    # fallback
    for d in devices:
        if d["max_input_channels"] > 0:
            print(f"[Input] Fallback: {d['name']}")
            return d

    raise RuntimeError("No input device found")


def find_output_device():
    devices = sd.query_devices()
    wired_keywords = ["speaker", "headphone", "line"]
    bt_keywords = ["bluetooth", "bt"]

    for key in wired_keywords:
        for d in devices:
            if d["max_output_channels"] > 0 and key.lower() in d["name"].lower():
                print(f"[Output] Selected (wired): {d['name']}")
                return d

    for key in bt_keywords:
        for d in devices:
            if d["max_output_channels"] > 0 and key.lower() in d["name"].lower():
                print(f"[Output] Selected (BT): {d['name']}")
                return d

    for d in devices:
        if d["max_output_channels"] > 0:
            print(f"[Output] Fallback: {d['name']}")
            return d

    raise RuntimeError("No output device found")


input_device = find_input_device()
output_device = find_output_device()

INPUT_DEVICE_INDEX = input_device["index"]
SR = int(input_device["default_samplerate"])

# ==============================
# 透過ウィンドウ設定
# ==============================

class RECT(Structure):
    _fields_ = [
        ("left", c_long),
        ("top", c_long),
        ("right", c_long),
        ("bottom", c_long)
    ]


class MONITORINFO(Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_ulong)
    ]


def get_monitor_work_area(hwnd):
    monitor = windll.user32.MonitorFromWindow(hwnd, 2)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    windll.user32.GetMonitorInfoW(monitor, byref(info))
    return info.rcWork


pygame.init()
pygame.display.init()

# ダミーウィンドウで作業領域取得
temp = pygame.display.set_mode((100, 100))
hwnd = pygame.display.get_wm_info()["window"]
rc = get_monitor_work_area(hwnd)
pygame.display.quit()

VISUALIZER_HEIGHT = 300
SCREEN_WIDTH = rc.right - rc.left
WINDOW_Y = rc.bottom - VISUALIZER_HEIGHT

os.environ["SDL_VIDEO_WINDOW_POS"] = f"{rc.left},{WINDOW_Y}"

screen = pygame.display.set_mode(
    (SCREEN_WIDTH, VISUALIZER_HEIGHT),
    pygame.NOFRAME | pygame.SRCALPHA
)

pygame.display.set_caption("Visualizer")
hwnd = pygame.display.get_wm_info()["window"]

# ==== 透過・最前面設定 ====
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008

ex_style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
windll.user32.SetWindowLongW(
    hwnd,
    GWL_EXSTYLE,
    ex_style | WS_EX_LAYERED | WS_EX_TOPMOST
)

# 黒を透過色に
LWA_COLORKEY = 0x00000001
windll.user32.SetLayeredWindowAttributes(hwnd, 0x000000, 0, LWA_COLORKEY)

HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

windll.user32.SetWindowPos(
    hwnd,
    HWND_TOPMOST,
    0, 0, 0, 0,
    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
)

# クリック透過は最後に追加
ex_style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
windll.user32.SetWindowLongW(
    hwnd,
    GWL_EXSTYLE,
    ex_style | WS_EX_TRANSPARENT
)

# ==============================
# ビジュアライザー設定
# ==============================

BLOCK_SIZE = 2048
N_BARS = 128
BAR_HEIGHT = 250
BAR_WIDTH = SCREEN_WIDTH // N_BARS

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
    if indata is not None and len(indata) > 0:
        buffer = indata[:, 0].copy()


stream = sd.InputStream(
    samplerate=SR,
    blocksize=BLOCK_SIZE,
    device=INPUT_DEVICE_INDEX,
    channels=1,
    dtype="float32",
    callback=audio_callback
)

stream.start()

# ==============================
# 周波数ビン
# ==============================

def create_custom_log_bins(sr, n_bars, linear_cutoff=1200, linear_ratio=0.4, min_freq=20):
    linear_bins = int(n_bars * linear_ratio)
    log_bins = n_bars - linear_bins
    linear_edges = np.linspace(min_freq, linear_cutoff, linear_bins + 1)
    log_edges = np.logspace(np.log10(linear_cutoff), np.log10(sr / 2), log_bins + 1)
    return np.concatenate((linear_edges[:-1], log_edges))


log_bins = create_custom_log_bins(SR, N_BARS)

# ==============================
# スペクトル
# ==============================

def get_freq_spectrum(audio, log_bins):
    global prev_bar_heights

    if audio is None or len(audio) == 0:
        return prev_bar_heights

    windowed = audio * np.hanning(len(audio))
    fft = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(len(audio), 1 / SR)

    bar_heights = np.zeros(N_BARS)

    NOISE_FLOOR_DB = -65
    GATE_MARGIN_DB = 8

    SMOOTH_LOW = 0.30
    SMOOTH_HIGH = 0.03

    EXP_LOW = 1.6
    EXP_HIGH = 3.2

    GAIN_LOW = 1.0
    GAIN_HIGH = 2.2

    for i in range(N_BARS):
        mask = (freqs >= log_bins[i]) & (freqs < log_bins[i + 1])
        power = np.mean(fft[mask]) if np.any(mask) else 1e-9

        db = 20 * np.log10(power + 1e-9)
        effective_db = db - NOISE_FLOOR_DB

        if effective_db <= GATE_MARGIN_DB:
            raw = 0.0
        else:
            norm = np.clip(effective_db / abs(NOISE_FLOOR_DB), 0, 1)
            base = np.log1p(norm * 8) / np.log1p(8)
            t = i / (N_BARS - 1)
            exp = EXP_LOW * (1 - t) + EXP_HIGH * t
            shaped = base ** exp
            gain = GAIN_LOW * (1 - t) + GAIN_HIGH * t
            raw = shaped * gain

        t = i / (N_BARS - 1)
        smooth = SMOOTH_LOW * (1 - t) + SMOOTH_HIGH * t
        bar_heights[i] = prev_bar_heights[i] * (1 - smooth) + raw * smooth

    prev_bar_heights[:] = bar_heights
    return bar_heights

# ==============================
# メインループ
# ==============================

pygame.event.clear()  # ★ 初期イベント破棄（KeyError対策）

running = True
while running:
    screen.fill((0, 0, 0))

    try:
        events = pygame.event.get()
    except Exception:
        continue

    for event in events:
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.ACTIVEEVENT:
            try:
                if event.state == 2 and event.gain == 0:
                    windll.user32.SetWindowPos(
                        hwnd,
                        HWND_TOPMOST,
                        0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                    )
            except Exception:
                pass

    bar_heights = get_freq_spectrum(buffer, log_bins)

    current_peak = np.max(bar_heights)
    visual_peak = max(current_peak, visual_peak * VISUAL_PEAK_DECAY)

    display_heights = np.clip(bar_heights / max(visual_peak, 0.1), 0, 1)

    for i, mag in enumerate(display_heights):
        h = max(1, int(mag * BAR_HEIGHT))
        x = i * BAR_WIDTH
        y = VISUALIZER_HEIGHT - h

        start = np.array([173, 216, 230])
        end = np.array([255, 140, 160])

        COLOR_GAMMA = 3.0
        c = mag ** COLOR_GAMMA
        color = start * (1 - c) + end * c

        pygame.draw.rect(
            screen,
            tuple(color.astype(int)),
            (x, y, BAR_WIDTH - 2, h)
        )

    pygame.display.flip()
    clock.tick(60)

# ==============================
# 終了
# ==============================

stream.stop()
stream.close()
pygame.quit()
