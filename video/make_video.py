"""
LIFEGRAPH AI — 3-minute animated explainer video renderer.

Renders a 1920x1080-scaled (1280x720 master) motion-graphics video with
AI-generated narration and a subtle synthesized ambient soundtrack.

Usage:
    python make_video.py            # full render -> LIFEGRAPH_AI_Explainer.mp4
    python make_video.py --frames   # render 10 preview PNG frames only
    python make_video.py --no-audio # skip narration/music generation
"""

import os
import sys
import math
import asyncio
import functools
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from moviepy import (
        VideoClip, AudioFileClip, CompositeAudioClip,
        AudioArrayClip, concatenate_videoclips,
    )
    MOVIEPY_V2 = True
except Exception:
    try:
        from moviepy.editor import (
            VideoClip, AudioFileClip, CompositeAudioClip,
            AudioArrayClip, concatenate_videoclips,
        )
        MOVIEPY_V2 = False
    except Exception:
        VideoClip = AudioFileClip = CompositeAudioClip = None
        AudioArrayClip = concatenate_videoclips = None
        MOVIEPY_V2 = None


# ----------------------------------------------------------------------------
# Global configuration
# ----------------------------------------------------------------------------
W, H = 1280, 720              # logical drawing canvas
OUT_W, OUT_H = 1920, 1080     # delivered resolution
FPS = 30
DURATION = 180.0
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "LIFEGRAPH_AI_Explainer.mp4")
AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
PREVIEW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)

# Client palette (four swatches), plus a few tonal steps derived from them.
DEEP = (10, 25, 41)       # #0A1929  dark navy
TEAL = (26, 110, 122)     # #1A6E7A  deep teal
SKY = (168, 216, 224)     # #A8D8E0  light cyan
PALE = (246, 247, 248)    # #F6F7F8  off-white

# Semantic aliases kept so the scene code stays readable.
CYAN = SKY                # bright accent / text
VIOLET = (95, 160, 170)   # steel teal
GREEN = (140, 200, 200)   # mint
AMBER = (205, 218, 222)   # pale steel
RED = (120, 150, 160)     # slate teal
BLUE = TEAL
WHITE = PALE
MUTED = (158, 180, 190)
DARK = DEEP

# Font discovery
FONT_DIR = "C:/Windows/Fonts"
def _find(names):
    for n in names:
        p = os.path.join(FONT_DIR, n)
        if os.path.exists(p):
            return p
    return None

REG_PATH = _find(["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"])
BOLD_PATH = _find(["segoeuib.ttf", "seguisb.ttf", "arialbd.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf"])


@functools.lru_cache(maxsize=200)
def F(size, bold=False):
    p = (BOLD_PATH if bold and BOLD_PATH else None) or REG_PATH
    if p:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ----------------------------------------------------------------------------
# Small drawing helpers
# ----------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    """Cubic ease-in-out — softer acceleration/deceleration than smoothstep."""
    x = clamp(x)
    return 4 * x * x * x if x < 0.5 else 1 - ((-2 * x + 2) ** 3) / 2


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def pop(x):
    """Slight overshoot for confident, spring-like entrances."""
    x = clamp(x)
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def slide(t, start, dur=0.7, dist=45):
    """Horizontal entrance offset that settles with an ease-out curve."""
    return dist * (1 - ease_out((t - start) / dur))


def appear(t, start, dur=0.55):
    return ease((t - start) / dur)


def fade_window(t, dur, fin=0.5, fout=0.5):
    return min(appear(t, 0, fin), ease((dur - t) / fout))


def A(c, a):
    # Accept either 0..1 (opacity fraction) or 1..255 (alpha byte).
    av = a * 255 if a <= 1.0 else a
    return (c[0], c[1], c[2], int(max(0, min(255, av))))


def mix(a, b, t):
    t = clamp(t)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def txt(d, pos, s, size, color=WHITE, bold=False, anchor="lm", alpha=1.0, shadow=True):
    if alpha <= 0:
        return
    f = F(size, bold)
    col = A(color, alpha)
    if shadow:
        d.text((pos[0] + 2, pos[1] + 3), s, font=f, fill=(0, 0, 0, int(90 * alpha)), anchor=anchor)
    d.text(pos, s, font=f, fill=col, anchor=anchor)


def wrap(d, s, size, maxw, bold=False):
    f = F(size, bold)
    words = s.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=f) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def paragraph(d, xy, s, size, maxw, color=WHITE, bold=False, leading=1.35, alpha=1.0, anchor="la"):
    lines = wrap(d, s, size, maxw, bold)
    x, y = xy
    for i, ln in enumerate(lines):
        txt(d, (x, y + i * size * leading), ln, size, color, bold, anchor=anchor, alpha=alpha)
    return len(lines) * size * leading


def radial(color, size, strength=1.0):
    """Precomputed soft radial glow sprite (RGBA)."""
    arr = np.linspace(-1, 1, size, dtype=np.float32)
    xx, yy = np.meshgrid(arr, arr)
    r = np.sqrt(xx * xx + yy * yy)
    a = np.clip(1.0 - r, 0, 1) ** 2.2
    a = (a * 150 * strength).astype(np.uint8)
    out = np.zeros((size, size, 4), dtype=np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = color
    out[..., 3] = a
    return Image.fromarray(out, "RGBA")


_CYAN_GLOW = radial(TEAL, 512, 1.0)
_VIOLET_GLOW = radial(VIOLET, 512, 0.9)
_GREEN_GLOW = radial(SKY, 256, 0.6)


@functools.lru_cache(maxsize=64)
def glow_at(color, size):
    src = {CYAN: _CYAN_GLOW, VIOLET: _VIOLET_GLOW, GREEN: _GREEN_GLOW}.get(color)
    if src is None:
        src = radial(color, 256, 0.7)
    return src.resize((int(size), int(size)))


@functools.lru_cache(maxsize=1)
def vignette_layer():
    yy = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
    r = np.sqrt(xx * xx + yy * yy)
    a = (np.clip((r - 0.52) / 0.78, 0, 1) ** 1.4 * 105).astype(np.uint8)
    arr = np.zeros((H, W, 4), dtype=np.uint8)
    arr[..., 3] = a
    return Image.fromarray(arr, "RGBA")


_AMBIENT = []
for _i in range(46):
    _r = np.random.RandomState(100 + _i)
    _AMBIENT.append((int(_r.randint(0, W)), int(_r.randint(0, H)),
                     float(0.25 + _r.rand() * 0.75), float(4 + _r.rand() * 13)))


def draw_ambient(img, t):
    """Slow drifting depth particles shared by every scene."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay, "RGBA")
    for x0, y0, depth, speed in _AMBIENT:
        y = (y0 - t * speed * depth) % (H + 40) - 20
        x = x0 + 6 * math.sin(t * 0.4 * depth + y0)
        r = 1 + depth * 1.4
        d.ellipse((x - r, y - r, x + r, y + r), fill=A(SKY, 14 + 26 * depth))
    img.alpha_composite(lay)


def panel(img, box, fill=(12, 28, 50, 205), outline=(90, 150, 190, 120),
          radius=18, width=2, glow=None, gloww=5):
    x0, y0, x1, y1 = [int(v) for v in box]
    m = 26
    bx0, by0 = max(0, x0 - m), max(0, y0 - m)
    bx1, by1 = min(W, x1 + m), min(H, y1 + m)
    if glow:
        gl = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gl)
        gd.rounded_rectangle((x0 - bx0, y0 - by0, x1 - bx0, y1 - by0),
                             radius=radius, outline=A(glow, 170), width=gloww)
        img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(14)), (bx0, by0))
    lay = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=radius,
                        fill=fill, outline=outline, width=width)
    img.alpha_composite(lay, (x0, y0))
    return d


def line(d, pts, color, width=2):
    d.line(pts, fill=color, width=width, joint="curve")


def arrow(d, p1, p2, color, width=3, head=10):
    line(d, [p1, p2], color, width)
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    for off in (2.6, -2.6):
        q = (p2[0] - head * math.cos(ang + off), p2[1] - head * math.sin(ang + off))
        line(d, [p2, q], color, width)


def icon(d, kind, cx, cy, s, color, w=3):
    """Simple geometric icon glyph set."""
    c = A(color, 1.0)
    if kind == "calendar":
        d.rounded_rectangle((cx - s, cy - s * .8, cx + s, cy + s * .8), radius=4, outline=c, width=w)
        line(d, [(cx - s, cy - s * .3), (cx + s, cy - s * .3)], c, w)
        for dx in (-s * .45, s * .45):
            d.ellipse((cx + dx - 2, cy - s * 1.15, cx + dx + 2, cy - s * .85), fill=c)
    elif kind == "mail":
        d.rectangle((cx - s, cy - s * .7, cx + s, cy + s * .7), outline=c, width=w)
        line(d, [(cx - s, cy - s * .7), (cx, cy + s * .05), (cx + s, cy - s * .7)], c, w)
    elif kind == "tasks":
        for i, dy in enumerate((-s * .65, 0, s * .65)):
            d.rounded_rectangle((cx - s, cy + dy - s * .22, cx - s * .45, cy + dy + s * .22), radius=2, outline=c, width=2)
            line(d, [(cx - s * .82, cy + dy), (cx - s * .62, cy + dy + s * .12), (cx - s * .35, cy + dy - s * .16)], c, 2)
            line(d, [(cx - s * .2, cy + dy), (cx + s, cy + dy)], A(color, .55), 2)
    elif kind == "wallet":
        d.rounded_rectangle((cx - s, cy - s * .7, cx + s, cy + s * .7), radius=5, outline=c, width=w)
        d.ellipse((cx + s * .45, cy - s * .22, cx + s * .85, cy + s * .22), outline=c, width=2)
    elif kind == "phone":
        d.rounded_rectangle((cx - s * .55, cy - s, cx + s * .55, cy + s), radius=6, outline=c, width=w)
        d.ellipse((cx - 3, cy + s * .72, cx + 3, cy + s * .78), fill=c)
    elif kind == "weather":
        d.ellipse((cx - s * .45, cy - s * .45, cx + s * .45, cy + s * .45), outline=c, width=w)
        for k in range(8):
            a = k * math.pi / 4
            line(d, [(cx + math.cos(a) * s * .65, cy + math.sin(a) * s * .65),
                     (cx + math.cos(a) * s * .95, cy + math.sin(a) * s * .95)], c, 2)
    elif kind == "people":
        d.ellipse((cx - s * .85, cy - s * .75, cx - s * .15, cy - s * .05), outline=c, width=w)
        d.ellipse((cx + s * .15, cy - s * .75, cx + s * .85, cy - s * .05), outline=c, width=w)
        d.arc((cx - s, cy - s * .1, cx - s * .05, cy + s), 190, 350, fill=c, width=w)
        d.arc((cx + s * .05, cy - s * .1, cx + s, cy + s), 190, 350, fill=c, width=w)
    elif kind == "book":
        line(d, [(cx, cy - s * .8), (cx - s, cy - s * .95), (cx - s, cy + s * .8), (cx, cy + s * .6)], c, w)
        line(d, [(cx, cy - s * .8), (cx + s, cy - s * .95), (cx + s, cy + s * .8), (cx, cy + s * .6)], c, w)
        line(d, [(cx, cy - s * .8), (cx, cy + s * .6)], c, w)
    elif kind == "clock":
        d.ellipse((cx - s, cy - s, cx + s, cy + s), outline=c, width=w)
        line(d, [(cx, cy), (cx, cy - s * .65)], c, w)
        line(d, [(cx, cy), (cx + s * .5, cy + s * .2)], c, w)
    elif kind == "bars":
        for i, h in enumerate((.45, .8, .6, 1.0)):
            x = cx - s + i * (2 * s / 4) + s / 5
            d.rounded_rectangle((x, cy + s * .7 - h * s * 1.5, x + s / 3.2, cy + s * .7), radius=2, fill=c)
    elif kind == "lock":
        d.arc((cx - s * .55, cy - s * .9, cx + s * .55, cy + s * .2), 180, 360, fill=c, width=w)
        d.rounded_rectangle((cx - s * .8, cy - s * .1, cx + s * .8, cy + s * .85), radius=4, outline=c, width=w)
        d.ellipse((cx - 4, cy + s * .25, cx + 4, cy + s * .45), fill=c)
    elif kind == "spark":
        pts = []
        for k in range(12):
            a = k * math.pi / 6 - math.pi / 2
            r = s if k % 2 == 0 else s * .4
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        d.polygon(pts, outline=c)
    elif kind == "brain":
        for dx, dy in ((-.5, -.4), (0, -.6), (.5, -.35), (-.55, .2), (0, .15), (.55, .25), (-.2, .65), (.3, .65)):
            d.ellipse((cx + dx * s - 4, cy + dy * s - 4, cx + dx * s + 4, cy + dy * s + 4), fill=c)
        for p1, p2 in (((-.5, -.4), (0, -.6)), ((0, -.6), (.5, -.35)), ((-.5, -.4), (-.55, .2)),
                       ((0, -.6), (0, .15)), ((.5, -.35), (.55, .25)), ((-.55, .2), (-.2, .65)),
                       ((0, .15), (.3, .65)), ((-.2, .65), (.3, .65))):
            line(d, [(cx + p1[0] * s, cy + p1[1] * s), (cx + p2[0] * s, cy + p2[1] * s)], A(color, .6), 2)
    elif kind == "heart":
        d.ellipse((cx - s * .9, cy - s * .6, cx, cy + s * .15), outline=c, width=w)
        d.ellipse((cx, cy - s * .6, cx + s * .9, cy + s * .15), outline=c, width=w)
        d.polygon([(cx - s * .85, cy - s * .1), (cx + s * .85, cy - s * .1), (cx, cy + s)], outline=c)


def pill(d, xy, text, color, size=16, alpha=1.0, pad=10, fill_alpha=40):
    f = F(size, True)
    tw = d.textlength(text, font=f)
    x, y = xy
    box = (x, y - size * .75 - pad * .3, x + tw + pad * 2, y + size * .75 + pad * .3)
    d.rounded_rectangle(box, radius=(box[3] - box[1]) / 2, fill=A(color, fill_alpha * alpha), outline=A(color, 200 * alpha), width=1)
    txt(d, (x + pad, y), text, size, color, True, "lm", alpha)
    return box


# ----------------------------------------------------------------------------
# 3D helpers: real rotation + perspective projection (no external 3D library)
# ----------------------------------------------------------------------------
def rot3(p, ax=0.0, ay=0.0):
    x, y, z = p
    cy_, sy = math.cos(ay), math.sin(ay)
    x, z = x * cy_ + z * sy, -x * sy + z * cy_
    cx_, sx = math.cos(ax), math.sin(ax)
    y, z = y * cx_ - z * sx, y * sx + z * cx_
    return (x, y, z)


def project(p, cx=640, cy=360, focal=760, camz=900):
    x, y, z = p
    depth = max(60.0, camz - z)
    f = focal / depth
    return (cx + x * f, cy + y * f, f)


def poly3(d, pts_world, ax, ay, cx, cy, color, width=2, focal=760, camz=900, closed=False):
    proj = [project(rot3(p, ax, ay), cx, cy, focal, camz) for p in pts_world]
    seq = proj + ([proj[0]] if closed else [])
    for a, b in zip(seq, seq[1:]):
        zavg = (a[2] + b[2]) * 0.5
        alpha = clamp(0.30 + zavg * 0.75)
        line(d, [(a[0], a[1]), (b[0], b[1])], A(color, alpha * 190), width)


def draw_globe(img, t, cx, cy, radius, nodes, ax=-0.35, ay=0.0, spin=0.45, focal=760):
    """Rotating wireframe sphere with orbiting, labeled life-domain nodes."""
    d = ImageDraw.Draw(img, "RGBA")
    ay += t * spin
    ax += 0.10 * math.sin(t * 0.4)
    for lat in (-60, -30, 0, 30, 60):
        r = radius * math.cos(math.radians(lat))
        y = radius * math.sin(math.radians(lat))
        pts = [(r * math.cos(k * math.pi / 24), y, r * math.sin(k * math.pi / 24)) for k in range(49)]
        poly3(d, pts, ax, ay, cx, cy, TEAL, 2, focal)
    for k in range(12):
        lon = k * math.pi / 6
        pts = [(radius * math.cos(math.radians(a)) * math.cos(lon),
                radius * math.sin(math.radians(a)),
                radius * math.cos(math.radians(a)) * math.sin(lon)) for a in range(-90, 91, 6)]
        poly3(d, pts, ax, ay, cx, cy, SKY, 1, focal)
    # connect nodes with glowing arcs
    pts = []
    for label, lat, lon in nodes:
        la, lo = math.radians(lat), math.radians(lon + t * spin * 8)
        p = (radius * math.cos(la) * math.cos(lo),
             radius * math.sin(la),
             radius * math.cos(la) * math.sin(lo))
        q = rot3(p, ax, ay)
        s = project(q, cx, cy, focal=focal)
        pts.append((s, q[2], label))
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            a, b = pts[i], pts[j]
            al = clamp(0.20 + (a[1] + b[1]) / 2 / radius * 0.4)
            line(d, [(a[0][0], a[0][1]), (b[0][0], b[0][1])], A(SKY, 45 * al), 1)
    for s, z, label in pts:
        r = 4 + 4 * clamp((z + radius) / (2 * radius))
        pulse = 0.7 + 0.3 * math.sin(t * 3 + len(label))
        d.ellipse((s[0] - r * 2, s[1] - r * 2, s[0] + r * 2, s[1] + r * 2), fill=A(SKY, 28 * pulse))
        d.ellipse((s[0] - r, s[1] - r, s[0] + r, s[1] + r), fill=A(SKY, 220), outline=A(PALE, 200), width=1)
        txt(d, (s[0], s[1] - r - 12), label, 11, SKY, True, "mm")


def iso_card(img, x, y, w, h, depth, col, alpha=1.0, radius=10):
    """Extruded card that reads as a 3D slab floating above the background."""
    d = ImageDraw.Draw(img, "RGBA")
    off = int(4 + depth * 9)
    d.rounded_rectangle((x + off, y - off // 2, x + w + off, y + h - off // 2),
                        radius=radius, fill=A(col, 55 * alpha), outline=A(col, 95 * alpha), width=1)
    for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        line(d, [(px, py), (px + off, py - off // 2)], A(col, 80 * alpha), 1)
    panel(img, (x, y, x + w, y + h), fill=(9, 24, 38, int(225 * alpha)),
          outline=A(col, 130 * alpha), radius=radius)
    return ImageDraw.Draw(img, "RGBA")


# ----------------------------------------------------------------------------
# Background builder
# ----------------------------------------------------------------------------
def build_base(variant=0):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    g = np.clip(0.55 * yy + 0.45 * xx, 0, 1)
    arr = np.zeros((H, W, 4), dtype=np.uint8)
    arr[..., 0] = (6 + 8 * g).astype(np.uint8)
    arr[..., 1] = (16 + 16 * g).astype(np.uint8)
    arr[..., 2] = (29 + 24 * g).astype(np.uint8)
    arr[..., 3] = 255
    img = Image.fromarray(arr, "RGBA")
    d = ImageDraw.Draw(img)
    for x in range(0, W, 64):
        d.line([(x, 0), (x, H)], fill=(168, 216, 224, 8))
    for y in range(0, H, 64):
        d.line([(0, y), (W, y)], fill=(168, 216, 224, 8))
    # horizon accent
    d.line([(0, H - 4), (W, H - 4)], fill=A(SKY, 40), width=3)
    img.alpha_composite(_CYAN_GLOW, (-190, -190))
    img.alpha_composite(_VIOLET_GLOW, (W - 320, H - 360))
    if variant in (1, 3):
        img.alpha_composite(_GREEN_GLOW.resize((420, 420)), (W - 460, -120))
    return img


BASES = {}


def get_base(idx):
    if idx not in BASES:
        BASES[idx] = build_base(idx % 4)
    return BASES[idx]


# ----------------------------------------------------------------------------
# Scene definitions
# ----------------------------------------------------------------------------
SCENES = [
    {"start": 0.0,   "dur": 12.0, "name": "Intro"},
    {"start": 12.0,  "dur": 18.0, "name": "Problem"},
    {"start": 30.0,  "dur": 18.0, "name": "Cycle"},
    {"start": 48.0,  "dur": 17.0, "name": "Assistant"},
    {"start": 65.0,  "dur": 28.0, "name": "Domains"},
    {"start": 93.0,  "dur": 19.0, "name": "Schedule"},
    {"start": 112.0, "dur": 19.0, "name": "Tasks"},
    {"start": 131.0, "dur": 18.0, "name": "CrossDomain"},
    {"start": 149.0, "dur": 17.0, "name": "Control"},
    {"start": 166.0, "dur": 14.0, "name": "Closing"},
]

NARRATION = {
    0: "Meet LIFEGRAPH AI. One personal AI that understands your whole life and helps you decide what to do next. Your life. Your intelligence. Your AI.",
    1: "Here is the real problem. Your timetable is in one app, deadlines in your email, tasks in another, spending in your bank app, screen time on your phone, and social plans somewhere else. You waste energy just deciding what matters now. LIFEGRAPH AI brings it all together.",
    2: "So LIFEGRAPH AI does it for you. Observe. Understand. Analyze. Predict. Recommend. Execute. It learns from your authorized data and turns scattered information into clarity. Zero-input intelligence, with you in control.",
    3: "At the center is your AI assistant. Ask anything, by voice or text. What should I do today? What is my next deadline? How much did I spend this month? Your assistant answers using your real context, not generic advice.",
    4: "Six intelligence domains work together. Academic tracks assignments, deadlines and study patterns. Productivity finds your peak hours and spots deadline risk. Financial follows expenses, budgets and savings goals. Digital understands screen time and distraction. Environmental uses weather, air quality and commute data. Social keeps your calendar and relationships in balance.",
    5: "The Smart Schedule Manager maps your real day: college, travel, meals, rest and focus hours. Then the Free-Time Optimizer finds the gaps and tells you what to do with them. A forty-five minute assignment, a short break, practice, personal time. Realistic, flexible, and always yours to accept or change.",
    6: "Tasks go far beyond a checklist. Upload an assignment PDF and the AI extracts the questions, instructions and workload. It checks your calendar and email first, then asks only for what is truly missing. A task is created with priority, an estimate and a proposed plan.",
    7: "Where it becomes powerful is connection. Does screen time rise when study time falls? Do late nights affect preparation? The Cross-Domain Engine maps these relationships with evidence and confidence, never confusing correlation with causation. In the What-If Lab, simulate a decision before you make it.",
    8: "Your AI learns what you love and what you avoid, and you can edit or delete any of it. Three modes keep you in charge: observe, recommend, execute. Sensitive actions always need your approval. Weekly reports turn everything into clear, useful insight.",
    9: "LIFEGRAPH A.I. One intelligent system for your whole life. Let your personal A.I. understand it, organize it, and help you make better decisions. Your life. Your intelligence. Your A.I.",
}


def header(d, kicker, title, alpha=1.0):
    txt(d, (64, 52), kicker, 15, CYAN, True, "la", alpha * .95)
    txt(d, (64, 84), title, 38, WHITE, True, "la", alpha)
    d.line([(64, 132), (300, 132)], fill=A(CYAN, 150 * alpha), width=3)


def draw_particles(d, t, seed=0, n=26, color=CYAN, alpha=.35):
    rnd = np.random.RandomState(seed)
    for i in range(n):
        x = rnd.randint(60, W - 60)
        y = rnd.randint(60, H - 60)
        dy = (y + t * (6 + (i % 5) * 2)) % (H - 40) + 20
        r = 1 + (i % 3)
        d.ellipse((x - r, dy - r, x + r, dy + r), fill=A(color, alpha * (0.4 + 0.6 * math.sin(t + i) ** 2)))


GLOBE_NODES = [
    ("SCHEDULE", 35, -40), ("TASKS", -10, 30), ("PREFERENCES", 40, 130),
    ("GOALS", -35, 150), ("FINANCE", 5, -110), ("HABITS", -50, 70),
]


def scene_intro(img, t, dur):
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = 905, 350
    img.alpha_composite(glow_at(TEAL, 700), (cx - 350, cy - 380))
    draw_globe(img, t, cx, cy, 172, GLOBE_NODES, ax=-0.32, ay=0.3, spin=0.5)
    d = ImageDraw.Draw(img, "RGBA")
    a1 = appear(t, 0.3, .8)
    txt(d, (88 - slide(t, 0.3, 1.0, 30), 70), "LIFEGRAPH AI  ·  TRACK 3", 15, CYAN, True, "la", a1 * .9)
    txt(d, (86 - slide(t, 0.8, 1.0, 70), 202), "ONE AI.", 66, WHITE, True, "la", appear(t, 0.8, .8))
    txt(d, (86 - slide(t, 1.4, 1.0, 70), 272), "YOUR WHOLE", 54, WHITE, True, "la", appear(t, 1.4, .8))
    txt(d, (86 - slide(t, 1.9, 1.0, 70), 330), "LIFE.", 54, CYAN, True, "la", appear(t, 1.9, .8))
    ln = 300 * ease_out((t - 2.3) / .9)
    x0 = 88 - slide(t, 2.3, 1.0, 40)
    d.line([(x0, 392), (x0 + ln, 392)], fill=A(SKY, 170), width=3)
    body = "Understands your schedule, tasks, preferences\nand goals — then helps you decide what to do next."
    for i, s in enumerate(body.split("\n")):
        txt(d, (88 - slide(t, 2.8 + i * .35, 1.0, 35), 444 + i * 32), s, 19, MUTED, False, "la", appear(t, 2.8 + i * .35, .7))
    txt(d, (88 - slide(t, 4.2, 1.0, 30), 586), "Your Life. Your Intelligence. Your AI.", 22, SKY, True, "la", appear(t, 4.2, .9))
    txt(d, (88 - slide(t, 5.0, 1.0, 25), 640), "IDEATHON 2026 — KNOW THYSELF", 13, MUTED, True, "la", appear(t, 5.0, .8))
    draw_particles(d, t, 1, color=SKY, alpha=.25)


def scene_problem(img, t, dur):
    d = ImageDraw.Draw(img, "RGBA")
    header(d, "THE REAL-WORLD PROBLEM", "Your life is scattered across apps.")
    cards = [
        ("calendar", "TIMETABLE", 145, 205, SKY),
        ("mail", "EMAIL DEADLINES", 420, 172, VIOLET),
        ("tasks", "TASKS", 720, 208, GREEN),
        ("wallet", "SPENDING", 1000, 180, AMBER),
        ("phone", "SCREEN TIME", 245, 425, RED),
        ("weather", "WEATHER", 555, 458, BLUE),
        ("people", "SOCIAL PLANS", 885, 430, VIOLET),
    ]
    gather = ease((t - 12.0) / 4.0)
    for i, (kind, name, x, y, col) in enumerate(cards):
        a = appear(t, 0.4 + i * 0.32, .55)
        if a <= 0:
            continue
        tx = 640 + (x - 640) * (1 - gather * 0.12)
        ty = 385 + (y - 385) * (1 - gather * 0.12)
        tx += 4 * math.sin(t * 2.3 + i) * (1 - gather)
        ty += 3 * math.cos(t * 1.9 + i) * (1 - gather)
        d2 = iso_card(img, int(tx - 110), int(ty - 38), 220, 76, .35 + (i % 3) * .22, col, a)
        icon(d2, kind, int(tx - 72), int(ty), 15, A(col, a), 2)
        txt(d2, (int(tx - 38), int(ty)), name, 14, WHITE, True, "lm", a)
    d = ImageDraw.Draw(img, "RGBA")
    if gather < .85:
        for i in range(len(cards) - 1):
            p1 = (cards[i][2], cards[i][3])
            p2 = (cards[i + 1][2], cards[i + 1][3])
            al = .30 * (1 - gather)
            for k in range(0, 10, 2):
                q1 = (p1[0] + (p2[0] - p1[0]) * k / 10, p1[1] + (p2[1] - p1[1]) * k / 10)
                q2 = (p1[0] + (p2[0] - p1[0]) * (k + 1) / 10, p1[1] + (p2[1] - p1[1]) * (k + 1) / 10)
                line(d, [q1, q2], A(MUTED, al), 2)
    txt(d, (640, 578), "You waste energy deciding what matters now.", 24, WHITE, True, "mm", appear(t, 5.5, 1.0))
    if t > 11.0:
        txt(d, (640, 628), "LIFEGRAPH AI brings it all into one connected picture.", 18, SKY, True, "mm", appear(t, 11.0, 1.0))


def scene_cycle(img, t, dur):
    d = ImageDraw.Draw(img, "RGBA")
    header(d, "THE CORE CYCLE", "From raw data to real action")
    steps = ["OBSERVE", "UNDERSTAND", "ANALYZE", "PREDICT", "RECOMMEND", "EXECUTE"]
    cols = [SKY, (150, 200, 210), (185, 215, 220), PALE, (140, 195, 200), SKY]
    cx, cy, r = 640, 385, 215
    # 3D tilted ring: six steps orbit in depth, closer ones appear larger
    ax, ay = -0.62 + 0.08 * math.sin(t * 0.5), t * 0.42
    proj = []
    for i in range(6):
        ang = i * math.pi / 3
        q = rot3((r * math.cos(ang), 0, r * math.sin(ang)), ax, ay)
        sx, sy, _ = project(q, cx, cy, focal=900, camz=1100)
        proj.append(((sx, sy), q[2]))
    pts = [p[0] for p in proj]
    for i in range(6):
        a = appear(t, i * 0.22, 0.5)
        p1, p2 = pts[i], pts[(i + 1) % 6]
        arrow(d, p1, p2, A(cols[i], 85 * a), 2, 8)
    active = int((t / 1.6)) % 6
    for i, ((x, y), z) in enumerate(proj):
        name, col = steps[i], cols[i]
        a = appear(t, i * 0.22, 0.5)
        rad = 17 + 9 * clamp((z + r) / (2 * r))
        is_on = i == active and t > 2.0
        if is_on:
            img.alpha_composite(glow_at(col, 150), (int(x - 75), int(y - 75)))
            d = ImageDraw.Draw(img, "RGBA")
        d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=A(col, (120 if is_on else 60) * a), outline=A(col, (255 if is_on else 210) * a), width=3 if is_on else 2)
        ox = -46 if x < cx - 50 else (46 if x > cx + 50 else 0)
        oy = -34 if y < cy - 40 else (34 if y > cy + 40 else 0)
        txt(d, (x + ox, y + oy), name, 13, col if is_on else MUTED, is_on, "mm", a)
    txt(d, (cx, cy - 16), "ZERO-INPUT", 30, WHITE, True, "mm", appear(t, 2.2, .8))
    txt(d, (cx, cy + 20), "INTELLIGENCE", 30, CYAN, True, "mm", appear(t, 2.6, .8))
    txt(d, (cx, cy + 60), "with you in control", 15, MUTED, False, "mm", appear(t, 3.6, .8))
    txt(d, (640, 676), "Authorized data in. Clarity and action out.", 16, MUTED, False, "mm", appear(t, 5.0, 1.0))


def scene_assistant(img, t, dur):
    d = ImageDraw.Draw(img, "RGBA")
    header(d, "CENTRAL AI ASSISTANT", "Your assistant understands your context")
    panel(img, (150, 160, 1130, 630), fill=(8, 20, 38, 225), outline=A(CYAN, 90), radius=20)
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((150, 160, 1130, 214), radius=20, fill=A(CYAN, 22))
    d.rectangle((150, 196, 1130, 214), fill=A(CYAN, 22))
    dot = 0.5 + 0.5 * math.sin(t * 4)
    d.ellipse((178, 182 - 5, 190, 182 + 7), fill=A(GREEN, 160 + 95 * dot))
    txt(d, (204, 187), "AI ASSISTANT", 17, WHITE, True, "lm")
    txt(d, (280, 187), "ONLINE  ·  VOICE + TEXT", 13, MUTED, True, "lm")
    msgs = [
        ("user", "What should I do today?", 1.0, 250),
        ("ai", "You have a free 90-minute slot this evening.", 3.0, 320),
        ("ai", "DBMS assignment due Friday. Study 6:00-6:45, take a break, then practice.", 6.0, 392),
        ("user", "Schedule it.", 10.5, 492),
    ]
    for who, text, st, y in msgs:
        a = appear(t, st, 0.7)
        if a <= 0:
            continue
        f = F(17)
        tw = d.textlength(text, font=f)
        bw = min(tw + 42, 760)
        offx = slide(t, st, 0.85, 60)
        if who == "user":
            box = (1110 - bw + offx, y, 1110 + offx, y + 50)
            col = VIOLET
        else:
            box = (170 - offx, y, 170 + bw - offx, y + 50)
            col = CYAN
        d.rounded_rectangle(box, radius=14, fill=A(col, 34 * a), outline=A(col, 110 * a))
        # typing reveal
        shown = text[: max(1, int(len(text) * clamp((t - st) / 0.9)))] if t - st < 0.9 else text
        txt(d, (box[0] + 20, box[1] + 25), shown, 17, WHITE, False, "lm", a)
    if t > 12.0:
        pill(d, (170, 562), "APPROVED  ·  3 EVENTS CREATED", GREEN, 14, appear(t, 12.0, .6))
    # waveform
    base = 600
    for i in range(46):
        x = 470 + i * 8
        h = 3 + 14 * abs(math.sin(t * 5 + i * .6)) * (0.4 + 0.6 * math.sin(i * .3 + t) ** 2)
        d.rounded_rectangle((x, base - h, x + 4, base + h), radius=2, fill=A(CYAN, 90 + 100 * abs(math.sin(t * 4 + i))))


DOMAIN_DATA = [
    ("ACADEMIC", "book", CYAN, ["Assignments & deadlines", "Study patterns"]),
    ("PRODUCTIVITY", "clock", GREEN, ["Peak hours", "Deadline risk"]),
    ("FINANCIAL", "wallet", AMBER, ["Expenses & budgets", "Savings goals"]),
    ("DIGITAL", "phone", RED, ["Screen-time habits", "Distraction signals"]),
    ("ENVIRONMENTAL", "weather", BLUE, ["Weather & air quality", "Commute conditions"]),
    ("SOCIAL", "people", VIOLET, ["Event conflicts", "Work-life balance"]),
]


def scene_domains(img, t, dur):
    d = ImageDraw.Draw(img, "RGBA")
    header(d, "ONE LIFE · SIX LENSES", "Six intelligence domains")
    for i, (name, kind, col, bullets) in enumerate(DOMAIN_DATA):
        a = appear(t, 1.0 + i * 1.1, 0.7)
        if a <= 0:
            continue
        cx = 60 + (i % 3) * 400
        cy = int(170 + (i // 3) * 248 + 26 * (1 - ease_out((t - (1.0 + i * 1.1)) / 0.9)))
        img.alpha_composite(glow_at(col, 220), (cx + 20, cy + 30))
        panel(img, (cx, cy, cx + 370, cy + 218), fill=(9, 22, 42, int(220 * a)), outline=A(col, 110 * a), glow=col, radius=16)
        d = ImageDraw.Draw(img, "RGBA")
        d.ellipse((cx + 20, cy + 22, cx + 66, cy + 68), fill=A(col, 40 * a), outline=A(col, 170 * a), width=2)
        icon(d, kind, cx + 43, cy + 45, 15, A(col, a), 2)
        txt(d, (cx + 82, cy + 45), name, 19, WHITE, True, "lm", a)
        d.line([(cx + 22, cy + 88), (cx + 348, cy + 88)], fill=A(col, 70 * a))
        for j, b in enumerate(bullets):
            d.ellipse((cx + 24, cy + 116 + j * 38 - 3, cx + 30, cy + 116 + j * 38 + 3), fill=A(col, 200 * a))
            txt(d, (cx + 44, cy + 116 + j * 38), b, 15, MUTED, False, "lm", a)
    txt(d, (640, 686), "Connected domains reveal patterns no single app can see.", 16, CYAN, False, "mm", appear(t, 9.5, 1.2))


SEGMENTS = [
    ("COLLEGE", 9, 16, BLUE), ("TRAVEL", 16, 17, VIOLET), ("REST", 17, 18, AMBER),
    ("FREE", 18, 20, CYAN), ("DINNER", 20, 21, VIOLET), ("FOCUS", 21, 22, GREEN),
]


def scene_schedule(img, t, dur):
    d = ImageDraw.Draw(img, "RGBA")
    header(d, "FOUNDATION MODULE", "Smart schedule + free-time optimizer")
    x0, x1, y0, y1 = 90, 1190, 210, 268
    d.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=(9, 22, 42, 220), outline=A(MUTED, 90))
    d = ImageDraw.Draw(img, "RGBA")
    for k in range(9, 23):
        x = x0 + (x1 - x0) * (k - 9) / 14
        d.line([(x, y0), (x, y1)], fill=A(MUTED, 55), width=1)
        if k % 3 == 0:
            txt(d, (x, y0 - 16), f"{k}:00", 12, MUTED, False, "mm")
    for name, a_h, b_h, col in SEGMENTS:
        ax = x0 + (x1 - x0) * (a_h - 9) / 14
        bx = x0 + (x1 - x0) * (b_h - 9) / 14
        is_free = name == "FREE"
        pulse = .65 + .35 * math.sin(t * 4)
        d.rounded_rectangle((ax + 2, y0 + 4, bx - 2, y1 - 4), radius=6,
                            fill=A(col, (55 + 55 * pulse) if is_free else 45),
                            outline=A(col, 210 if is_free else 120), width=2 if is_free else 1)
        txt(d, ((ax + bx) / 2, (y0 + y1) / 2), name, 12, WHITE, is_free, "mm")
    fx0 = x0 + (x1 - x0) * 9 / 14
    fx1 = x0 + (x1 - x0) * 11 / 14
    pill(d, ((fx0 + fx1) / 2, 168), "2 HOURS AVAILABLE", CYAN, 14, appear(t, 1.2, .8))

    plans = [
        ("18:00 - 18:45", "DBMS assignment", "45 MIN  ·  HIGH", CYAN),
        ("18:45 - 19:00", "Break", "RECOVERY", AMBER),
        ("19:00 - 19:30", "Programming practice", "30 MIN  ·  MEDIUM", GREEN),
        ("19:30 - 20:00", "Personal time", "FLEXIBLE", VIOLET),
    ]
    for i, (time_s, title, tag, col) in enumerate(plans):
        a = appear(t, 3.0 + i * 1.5, .7)
        if a <= 0:
            continue
        x = 90 + i * 280
        yoff = 30 * (1 - ease_out((t - (3.0 + i * 1.5)) / 0.9))
        panel(img, (x, 330 + yoff, x + 260, 500 + yoff), fill=(9, 22, 42, int(220 * a)), outline=A(col, 110 * a), radius=14)
        d = ImageDraw.Draw(img, "RGBA")
        txt(d, (x + 18, 362 + yoff), time_s, 14, col, True, "lm", a)
        txt(d, (x + 18, 402 + yoff), title, 17, WHITE, True, "lm", a)
        txt(d, (x + 18, 438 + yoff), tag, 12, MUTED, False, "lm", a)
        bw = 224 * ease_out((t - (3.4 + i * 1.5)) / 1.1)
        d.rounded_rectangle((x + 18, 470 + yoff, x + 18 + bw, 476 + yoff), radius=3, fill=A(col, 200 * a))
    txt(d, (640, 560), "Accept  ·  Reject  ·  Modify", 22, WHITE, True, "mm", appear(t, 9.0, 1.0))
    txt(d, (640, 606), "The system never fills every minute with work.", 16, MUTED, False, "mm", appear(t, 10.5, 1.0))


def scene_tasks(img, t, dur):
    d = ImageDraw.Draw(img, "RGBA")
    header(d, "INTELLIGENT TO-DO MANAGER", "From a PDF to a plan")
    a = appear(t, 0.3, .8)
    panel(img, (80, 165, 520, 580), fill=(10, 24, 44, int(220 * a)), outline=A(CYAN, 90 * a), radius=16)
    d = ImageDraw.Draw(img, "RGBA")
    txt(d, (108, 200), "assignment.pdf", 16, CYAN, True, "lm", a)
    d.line([(108, 226), (492, 226)], fill=A(CYAN, 60))
    lines = ["DBMS Unit 3 assignment", "Answer all 10 questions", "Submit as a single PDF", "Deadline: Friday, 11:59 PM"]
    for i, s in enumerate(lines):
        aa = appear(t, 1.0 + i * 0.9, .6)
        d.rounded_rectangle((108, 262 + i * 46, 496, 292 + i * 46), radius=5, fill=A(CYAN, 12))
        txt(d, (122, 277 + i * 46), s, 14, MUTED if i > 1 else WHITE, False, "lm", aa)
    if t > 4.4:
        pill(d, (400, 200), "EXTRACTED", GREEN, 12, appear(t, 4.4, .5))

    arrow(d, (535, 370), (620, 370), A(CYAN, 200 * appear(t, 5.0, .6)), 3, 12)
    b = appear(t, 5.2, .8)
    panel(img, (640, 180, 1200, 520), fill=(10, 24, 44, int(225 * b)), outline=A(GREEN, 110 * b), glow=GREEN, radius=16)
    d = ImageDraw.Draw(img, "RGBA")
    txt(d, (672, 218), "DBMS Assignment", 26, WHITE, True, "lm", b)
    pill(d, (672, 258), "HIGH PRIORITY", AMBER, 13, b)
    pill(d, (822, 258), "45 MIN ESTIMATE", CYAN, 13, b)
    d.line([(672, 296), (1168, 296)], fill=A(MUTED, 60))
    rows = [("Subject", "DBMS · Unit 3"), ("Deadline", "Friday, 11:59 PM"), ("Subtasks", "10 questions created"), ("Next session", "Today, 6:00 PM")]
    for i, (k, v) in enumerate(rows):
        aa = appear(t, 6.0 + i * 0.8, .6)
        txt(d, (672, 336 + i * 42), k, 14, MUTED, False, "lm", aa)
        txt(d, (1168, 336 + i * 42), v, 15, WHITE, True, "rm", aa)
    c = appear(t, 10.0, .8)
    d.rounded_rectangle((640, 544, 1200, 606), radius=14, fill=A(VIOLET, 28 * c), outline=A(VIOLET, 110 * c))
    txt(d, (664, 566), "The AI asks only what's missing:", 14, VIOLET, True, "lm", c)
    txt(d, (664, 590), "\"How much have you already started?\"", 16, WHITE, False, "lm", c)


NODE_POS = {
    "STUDY": (250, 250), "SCREEN": (470, 190), "SLEEP": (250, 440),
    "SOCIAL": (480, 500), "WORK": (80, 350), "SPEND": (350, 350),
}
EDGES = [("SCREEN", "STUDY"), ("SLEEP", "STUDY"), ("SPEND", "SOCIAL"), ("WORK", "STUDY"), ("SCREEN", "SLEEP")]


def scene_cross(img, t, dur):
    d = ImageDraw.Draw(img, "RGBA")
    header(d, "DEEPER INTELLIGENCE", "Cross-domain insight + what-if simulation")
    d.line([(625, 160), (625, 640)], fill=A(MUTED, 55), width=1)
    txt(d, (110, 168), "PERSONAL RELATIONSHIP GRAPH", 13, CYAN, True, "lm")
    for i, (a, b) in enumerate(EDGES):
        aa = appear(t, 0.8 + i * .5, .6)
        p1, p2 = NODE_POS[a], NODE_POS[b]
        col = RED if (a, b) == ("SCREEN", "STUDY") else MUTED
        line(d, [p1, p2], A(col, (150 if col == RED else 60) * aa), 2 if col == RED else 1)
        if col == RED and t > 4:
            q = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            k = (t * 40) % 1
            d.ellipse((p1[0] + (p2[0] - p1[0]) * k - 4, p1[1] + (p2[1] - p1[1]) * k - 4,
                       p1[0] + (p2[0] - p1[0]) * k + 4, p1[1] + (p2[1] - p1[1]) * k + 4), fill=A(RED, 220))
    for i, (name, pos) in enumerate(NODE_POS.items()):
        aa = appear(t, .4 + i * .3, .5)
        x, y = pos
        col = RED if name in ("SCREEN", "STUDY") else BLUE
        d.ellipse((x - 32, y - 32, x + 32, y + 32), fill=A(col, 45 * aa), outline=A(col, 190 * aa), width=2)
        txt(d, (x, y), name, 11, WHITE, True, "mm", aa)
    txt(d, (110, 580), "Screen time ↑   ↔   Study time ↓", 16, RED, True, "lm", appear(t, 5.0, .8))
    txt(d, (110, 612), "Association 0.72  ·  medium confidence", 13, MUTED, False, "lm", appear(t, 6.0, .8))
    txt(d, (110, 642), "Correlation, not causation.", 13, AMBER, True, "lm", appear(t, 7.0, .8))

    txt(d, (670, 168), "WHAT-IF LAB", 13, VIOLET, True, "lm")
    txt(d, (670, 206), "What if I study 2 extra hours daily?", 18, WHITE, True, "lm", appear(t, 1.0, .8))
    sliders = [("Study hours", .72), ("Sleep", .42), ("Free time", .30)]
    for i, (lab, val) in enumerate(sliders):
        y = 270 + i * 66
        txt(d, (670, y), lab, 14, MUTED, False, "lm")
        d.rounded_rectangle((850, y - 7, 1160, y + 7), radius=7, fill=A(MUTED, 45))
        v = val * ease((t - (2.0 + i * .8)) / 1.4)
        d.rounded_rectangle((850, y - 7, 850 + 310 * v, y + 7), radius=7, fill=A(VIOLET, 210))
        d.ellipse((850 + 310 * v - 9, y - 9, 850 + 310 * v + 9, y + 9), fill=A(WHITE, 230))
    chart_x, chart_y = 670, 520
    txt(d, (chart_x, 474), "PROJECTED OUTCOME", 13, MUTED, True, "lm")
    vals = [.38, .62, .5, .82]
    for i, v in enumerate(vals):
        h = 90 * v * ease((t - (6.0 + i * .5)) / 1.0)
        col = GREEN if i % 2 == 0 else CYAN
        d.rounded_rectangle((chart_x + i * 58, chart_y + 80 - h, chart_x + i * 58 + 36, chart_y + 80), radius=4, fill=A(col, 200))
    txt(d, (960, 560), "Assignments", 14, GREEN, True, "lm", appear(t, 8.0, .8))
    txt(d, (960, 590), "12% earlier", 13, MUTED, False, "lm", appear(t, 8.4, .8))
    txt(d, (960, 620), "Sleep −20 min", 13, AMBER, False, "lm", appear(t, 9.0, .8))


def scene_control(img, t, dur):
    d = ImageDraw.Draw(img, "RGBA")
    header(d, "PRIVACY BY DESIGN", "You are always in control")
    prefs = [("Quiet places", True, GREEN), ("Programming", True, GREEN),
             ("Crowded places", False, RED), ("Late nights", False, RED), ("Live music", True, GREEN)]
    txt(d, (80, 172), "LEARNED PREFERENCES", 13, CYAN, True, "lm")
    for i, (name, liked, col) in enumerate(prefs):
        a = appear(t, .6 + i * .5, .6)
        x = 80 + (i % 3) * 210
        y = 210 + (i // 3) * 62
        d.rounded_rectangle((x, y, x + 190, y + 44), radius=22, fill=A(col, 28 * a), outline=A(col, 120 * a))
        if liked:
            line(d, [(x + 16, y + 22), (x + 22, y + 28), (x + 34, y + 14)], A(col, 230 * a), 3)
        else:
            line(d, [(x + 16, y + 16), (x + 32, y + 28)], A(col, 230 * a), 3)
            line(d, [(x + 32, y + 16), (x + 16, y + 28)], A(col, 230 * a), 3)
        txt(d, (x + 50, y + 22), name, 14, WHITE, False, "lm", a)
    txt(d, (80, 366), "User-controlled memory — inspect, edit or delete anytime.", 13, MUTED, False, "lm")

    levels = [("LEVEL 1", "OBSERVE", BLUE), ("LEVEL 2", "RECOMMEND", VIOLET), ("LEVEL 3", "EXECUTE", GREEN)]
    txt(d, (80, 428), "AUTONOMY MODES", 13, CYAN, True, "lm")
    for i, (lv, name, col) in enumerate(levels):
        a = appear(t, 4.0 + i * 1.1, .7)
        x = 80 + i * 205
        panel(img, (x, 462, x + 190, 570), fill=(9, 22, 42, int(220 * a)), outline=A(col, 110 * a), radius=12)
        d = ImageDraw.Draw(img, "RGBA")
        txt(d, (x + 95, 492), lv, 12, col, True, "mm", a)
        txt(d, (x + 95, 526), name, 16, WHITE, True, "mm", a)
    icon(d, "lock", 700, 516, 18, A(AMBER, appear(t, 8.0, .7)), 3)
    txt(d, (740, 516), "Sensitive actions need approval", 14, AMBER, True, "lm", appear(t, 8.0, .7))

    panel(img, (760, 165, 1200, 400), fill=(9, 22, 42, 220), outline=A(GREEN, 100), radius=14)
    d = ImageDraw.Draw(img, "RGBA")
    txt(d, (788, 196), "WEEKLY LIFE REPORT", 14, GREEN, True, "lm", appear(t, 6.0, .6))
    pts = []
    for i in range(14):
        xx = 790 + i * 28
        yy = 340 - 55 * (0.35 + 0.5 * math.sin(i * .8 + 1) ** 2) * ease((t - (7 + i * .15)) / .5)
        pts.append((xx, yy))
    line(d, pts, A(GREEN, 220 * appear(t, 7.0, 1.0)), 3)
    rows = [("Tasks completed", "18 / 21"), ("Study time", "9.5 hrs"), ("Spend vs budget", "82%")]
    for i, (k, v) in enumerate(rows):
        txt(d, (788, 372 + i * 0 * 1), "", 1, WHITE)
    txt(d, (788, 372), "Tasks 18/21   ·   Study 9.5h   ·   Budget 82%", 12, MUTED, False, "lm", appear(t, 9.0, .8))


def scene_closing(img, t, dur):
    d = ImageDraw.Draw(img, "RGBA")
    img.alpha_composite(glow_at(CYAN, 900), (190, -140))
    d = ImageDraw.Draw(img, "RGBA")
    a = appear(t, 0.2, 1.0)
    txt(d, (640, 200), "LIFEGRAPH AI", 66, WHITE, True, "mm", a)
    txt(d, (640, 264), "One intelligent system for your whole life.", 24, CYAN, False, "mm", appear(t, 1.0, .8))
    para = "Don't manage your life through multiple applications. Let your personal AI understand it, organize it, and help you make better decisions."
    lines = wrap(d, para, 19, 880)
    for i, ln in enumerate(lines):
        txt(d, (640, 360 + i * 30), ln, 19, WHITE, False, "mm", appear(t, 2.2 + i * .35, .8))
    d.line([(440, 500), (840, 500)], fill=A(CYAN, 150 * appear(t, 4.0, .8)), width=2)
    txt(d, (640, 560), "Your Life. Your Intelligence. Your AI.", 26, WHITE, True, "mm", appear(t, 4.2, .9))
    txt(d, (640, 636), "OBSERVE  →  UNDERSTAND  →  ANALYZE  →  PREDICT  →  RECOMMEND  →  EXECUTE", 13, MUTED, True, "mm", appear(t, 5.0, 1.0))
    draw_particles(d, t, 9)


SCENE_FNS = [scene_intro, scene_problem, scene_cycle, scene_assistant, scene_domains,
             scene_schedule, scene_tasks, scene_cross, scene_control, scene_closing]


def scene_index_at(t):
    for i, s in enumerate(SCENES):
        if s["start"] <= t < s["start"] + s["dur"]:
            return i
    return len(SCENES) - 1


def scene_frame_rgb(i, lt):
    img = get_base(i).copy()
    SCENE_FNS[i](img, lt, SCENES[i]["dur"])
    draw_ambient(img, lt + i * 3.0)
    # slow parallax light sweep across every scene (own layer, then blended)
    sweep = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sweep, "RGBA")
    sx = ((lt * 74 + i * 160) % (W + 460)) - 230
    d.polygon([(sx, 0), (sx + 70, 0), (sx + 210, H), (sx + 140, H)], fill=A(SKY, 9))
    img.alpha_composite(sweep)
    img.alpha_composite(vignette_layer())
    # PIL's ImageDraw writes raw RGBA; blend the assembled frame over black
    # so translucent accents render at their intended brightness.
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    rgb = Image.alpha_composite(bg, img).convert("RGB")
    # gentle cinematic camera drift + push-in, then upscale to delivery size
    zoom = 1.0 + 0.030 * (0.5 + 0.5 * math.sin(lt * 0.42 + i * 0.7))
    cw, ch = max(1, int(W / zoom)), max(1, int(H / zoom))
    x0 = int(clamp((W - cw) // 2 + 7 * math.sin(lt * 0.33 + i), 0, W - cw))
    y0 = int(clamp((H - ch) // 2 + 5 * math.cos(lt * 0.29 + i), 0, H - ch))
    return rgb.crop((x0, y0, x0 + cw, y0 + ch)).resize((OUT_W, OUT_H), Image.Resampling.LANCZOS)


def global_frame(t):
    i = scene_index_at(t)
    s = SCENES[i]
    lt = clamp(t - s["start"], 0, s["dur"])
    im = scene_frame_rgb(i, lt)
    # cinematic crossfade between adjacent scenes
    fade = 0.7
    if lt < fade and i > 0:
        prev = scene_frame_rgb(i - 1, SCENES[i - 1]["dur"] - (fade - lt))
        im = Image.blend(prev, im, ease(lt / fade))
    elif lt > s["dur"] - fade and i < len(SCENES) - 1:
        nxt = scene_frame_rgb(i + 1, fade - (s["dur"] - lt))
        im = Image.blend(im, nxt, ease((lt - (s["dur"] - fade)) / fade))
    # whole-video fade in/out
    fo = fade_window(t, DURATION, 0.9, 1.1)
    if fo < 1:
        im = Image.blend(Image.new("RGB", (OUT_W, OUT_H), (0, 0, 0)), im, fo)
    # subtle progress indicator along the bottom edge
    pd = ImageDraw.Draw(im)
    pd.rectangle((0, OUT_H - 4, int(OUT_W * t / DURATION), OUT_H), fill=TEAL)
    return np.asarray(im)


# ----------------------------------------------------------------------------
# Audio
# ----------------------------------------------------------------------------
VOICES = ["en-GB-RyanNeural", "en-US-GuyNeural", "en-US-JennyNeural"]


async def _edge_tts(text, path, voice, rate_pct=8):
    import edge_tts
    c = edge_tts.Communicate(text, voice, rate=f"+{int(rate_pct)}%")
    await c.save(path)


def synth_one(idx, text, target):
    """Synthesize narration that comfortably fits inside its scene."""
    path = os.path.join(AUDIO_DIR, f"scene_{idx:02d}.mp3")
    rate = 8
    last = None
    for attempt in range(3):
        for voice in VOICES:
            try:
                asyncio.run(_edge_tts(text, path, voice, rate))
                if os.path.exists(path) and os.path.getsize(path) > 2000:
                    break
            except Exception as e:
                last = e
        try:
            dur = AudioFileClip(path).duration
        except Exception:
            dur = 1e9
        if dur <= target:
            print(f"  [tts] scene {idx}: {dur:.1f}s @ +{rate}%")
            return path
        # re-synthesize faster: duration scales inversely with the rate factor
        rate = min(75, int(round(((1 + rate / 100) * (dur / target) - 1) * 100)) + 2)
    if os.path.exists(path) and os.path.getsize(path) > 2000:
        print(f"  [tts] scene {idx}: using fastest available rate (+{rate}%)")
        return path
    # offline fallback 1: native Windows SAPI (no extra package needed)
    try:
        wav = os.path.join(AUDIO_DIR, f"scene_{idx:02d}.wav")
        txtfile = os.path.join(AUDIO_DIR, f"scene_{idx:02d}.txt")
        with open(txtfile, "w", encoding="utf-8") as fh:
            fh.write(text)
        ps = (
            '$v = New-Object -ComObject SAPI.SpVoice; '
            '$s = New-Object -ComObject SAPI.SpFileStream; '
            f'$s.Open("{wav}", 3); '
            '$v.AudioOutputStream = $s; '
            '$v.Rate = 1; '
            f'$t = Get-Content -Raw "{txtfile}"; '
            '$v.Speak($t); '
            '$s.Close()'
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=180)
        if os.path.exists(wav) and os.path.getsize(wav) > 2000:
            print(f"  [tts] scene {idx} via Windows SAPI")
            return wav
    except Exception as e:
        last = e
    # offline fallback 2: pyttsx3
    try:
        import pyttsx3
        wav = os.path.join(AUDIO_DIR, f"scene_{idx:02d}.wav")
        eng = pyttsx3.init()
        eng.setProperty("rate", 152)
        eng.save_to_file(text, wav)
        eng.runAndWait()
        if os.path.exists(wav) and os.path.getsize(wav) > 2000:
            print(f"  [tts] scene {idx} via local SAPI")
            return wav
    except Exception as e:
        last = e
    print(f"  [tts] WARNING scene {idx} failed: {last}")
    return None


def make_music():
    sr = 22050
    n = int(DURATION * sr)
    t = np.linspace(0, DURATION, n, dtype=np.float32)
    # gentle ambient pad: stacked sines with slow beating
    sig = np.zeros(n, dtype=np.float32)
    for freq, amp, lfo in [(55, .45, .07), (82.4, .3, .11), (110, .22, .05), (164.8, .12, .09)]:
        sig += amp * np.sin(2 * np.pi * freq * t) * (0.6 + 0.4 * np.sin(2 * np.pi * lfo * t))
    sig += .10 * np.sin(2 * np.pi * 220 * t) * np.exp(-((t % 4) / 1.2) ** 2)
    # fade edges
    env = np.minimum(1, t / 3) * np.minimum(1, (DURATION - t) / 3)
    sig = sig * env * 0.055
    arr = np.stack([sig, sig], axis=1).astype(np.float32) * 0.9
    return arr, sr


def build_audio():
    tracks = []
    for i, s in enumerate(SCENES):
        target = s["dur"] - 0.7
        p = synth_one(i, NARRATION[i], target)
        if not p:
            continue
        try:
            a = AudioFileClip(p)
            if a.duration > target:
                # last-resort guard; normal path is re-synthesizing at a faster rate
                a = a.subclipped(0, target)
            # gentle in/out ramps so no sentence is chopped off abruptly
            if afx is not None:
                a = a.with_effects([afx.AudioFadeIn(0.12), afx.AudioFadeOut(0.30)])
            a = a.with_start(s["start"] + 0.15).with_volume_scaled(1.0)
            tracks.append(a)
        except Exception as e:
            print(f"  [audio] skip scene {i}: {e}")
    music, sr = make_music()
    music_clip = AudioArrayClip(music, fps=sr)
    tracks.insert(0, music_clip)
    comp = CompositeAudioClip(tracks).with_duration(DURATION)
    return comp


# Need afx import for TimeStretch
try:
    from moviepy import afx
except Exception:
    try:
        from moviepy.editor import afx
    except Exception:
        afx = None


def render_preview():
    print("Rendering preview frames...")
    for i, s in enumerate(SCENES):
        frame = global_frame(s["start"] + s["dur"] * 0.7)
        Image.fromarray(frame).save(os.path.join(PREVIEW_DIR, f"scene_{i:02d}_{s['name']}.png"))
    print(f"Previews written to {PREVIEW_DIR}")


def main():
    args = sys.argv[1:]
    if "--frames" in args:
        render_preview()
        return
    audio = None
    if "--no-audio" not in args:
        print("Generating narration and soundtrack...")
        audio = build_audio()
    print(f"Rendering video: {W}x{H} @ {FPS}fps, {DURATION:.0f}s ({int(DURATION * FPS)} frames)")
    clip = VideoClip(global_frame, duration=DURATION).with_fps(FPS)
    if audio is not None:
        clip = clip.with_audio(audio)
    clip.write_videofile(
        os.path.abspath(OUT),
        codec="libx264",
        audio_codec="aac" if audio is not None else None,
        preset="medium",
        fps=FPS,
        threads=4,
        logger="bar",
    )
    print("DONE:", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
