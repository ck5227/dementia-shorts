#!/usr/bin/env python3
"""Render a bilingual vertical Short (1080x1920) from an episode JSON.

Usage: python3 make_video.py episodes/2026-10-27.json out/2026-10-27.mp4
Background music is synthesized here (no copyrighted audio).
"""
import json, math, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
TC = 1  # face index: Noto Sans CJK TC in the .ttc collection? resolved below

BG_TOP = (14, 32, 54)
BG_BOT = (28, 76, 92)
ACCENT = (255, 196, 87)
WHITE = (245, 247, 250)
MUTED = (178, 199, 214)
GREEN = (120, 214, 170)
GREY_BAR = (120, 140, 158)


def font(path, size):
    # Pick the Traditional Chinese face inside the collection.
    for idx in range(10):
        try:
            f = ImageFont.truetype(path, size, index=idx)
        except OSError:
            break
        if "TC" in " ".join(f.getname()):
            return f
    return ImageFont.truetype(path, size)


def gradient():
    t = np.linspace(0, 1, H)[:, None]
    top, bot = np.array(BG_TOP), np.array(BG_BOT)
    col = (top * (1 - t) + bot * t).astype(np.uint8)
    arr = np.repeat(col[:, None, :], W, axis=1).reshape(H, W, 3)
    img = Image.fromarray(arr, "RGB")
    d = ImageDraw.Draw(img)
    # soft decorative circles
    d.ellipse((-260, -200, 520, 580), outline=(255, 255, 255, 0), width=0)
    return img


def draw_multiline(d, text, y, fnt, fill, spacing=1.35, x_center=True, x=90):
    lines = text.split("\n")
    lh = int(fnt.size * spacing)
    for ln in lines:
        if x_center:
            w = d.textlength(ln, font=fnt)
            d.text(((W - w) / 2, y), ln, font=fnt, fill=fill)
        else:
            d.text((x, y), ln, font=fnt, fill=fill)
        y += lh
    return y


def fit_size(d, text, path, start, max_w):
    size = start
    while size > 24:
        f = font(path, size)
        if max(d.textlength(l, font=f) for l in text.split("\n")) <= max_w:
            return f
        size -= 2
    return font(path, size)


def slide_layer(s, ep):
    """Static text layer (RGBA) for a slide; bars are drawn per-frame."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    maxw = W - 160
    if s["kind"] == "hook":
        d.text((90, 300), s["kicker"], font=font(FONT_BOLD, 50), fill=ACCENT)
        fz = fit_size(d, s["zh"], FONT_BOLD, 124, maxw)
        y = draw_multiline(d, s["zh"], 600, fz, WHITE, 1.3)
        fe = fit_size(d, s["en"], FONT_REG, 46, maxw)
        draw_multiline(d, s["en"], y + 70, fe, MUTED, 1.4)
        return layer
    # label pill
    lf = font(FONT_BOLD, 50)
    lw = d.textlength(s["label"], font=lf)
    d.rounded_rectangle((90, 255, 90 + lw + 64, 345), radius=45, fill=ACCENT)
    d.text((122, 265), s["label"], font=lf, fill=BG_TOP)
    top = 480
    if s.get("answer"):
        af = fit_size(d, s["answer"], FONT_BOLD, 96, maxw)
        draw_multiline(d, s["answer"], 400, af, ACCENT, 1.3)
        top = 600
    if s.get("bars_title"):
        tf = fit_size(d, s["bars_title"], FONT_BOLD, 50, maxw)
        draw_multiline(d, s["bars_title"], 550, tf, WHITE, 1.3)
    if s["kind"] == "result" and s.get("bars"):
        top = 1340
    elif s.get("bars_title"):
        top = 760  # title only (no bars): keep text below the title
    fz = fit_size(d, s["zh"], FONT_BOLD, 92 if s["kind"] != "caveat" else 80, maxw)
    left = s["kind"] == "caveat"
    y = draw_multiline(d, s["zh"], top, fz, WHITE, 1.45, x_center=not left)
    fe = fit_size(d, s["en"], FONT_REG, 42, maxw)
    y = draw_multiline(d, s["en"], y + 50, fe, MUTED, 1.4, x_center=not left)
    if s.get("stars"):
        draw_stars(d, int(s["stars"]), y + 70)
    if s.get("source"):
        sf = font(FONT_REG, 32)
        draw_multiline(d, "Source: " + s["source"], H - 330, sf, MUTED, 1.3)
    if s["kind"] == "takeaway":
        df = font(FONT_REG, 30)
        draw_multiline(d, "衛教資訊，不取代醫療建議 · For education, not medical advice",
                       H - 270, df, MUTED, 1.3)
    return layer


def star_poly(cx, cy, r):
    pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.42
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return pts


def draw_stars(d, n, y):
    """Evidence rating: n filled of 5 stars, centered, with a plain-language caption."""
    n = max(1, min(5, n))
    r, gap = 58, 140
    x0 = (W - gap * 4) / 2
    for k in range(5):
        cx = x0 + k * gap
        if k < n:
            d.polygon(star_poly(cx, y + r, r), fill=ACCENT)
        else:
            d.polygon(star_poly(cx, y + r, r), outline=MUTED, width=4)
    words = {5: "很可靠 Very solid", 4: "可靠 Solid", 3: "還算可靠 Fair",
             2: "參考就好 Early signal", 1: "還很初步 Very early"}[n]
    cf = font(FONT_BOLD, 52)
    draw_multiline(d, "可信度：" + words, y + 2 * r + 40, cf, WHITE, 1.3)


def draw_bars(img, s, progress):
    d = ImageDraw.Draw(img)
    bars = s["bars"]
    if s.get("unit") == "人":
        vmax = max(b["value"] for b in bars) * 1.25  # small counts: scale to largest bar
    else:
        vmax = max(60.0, max(b["value"] for b in bars) * 1.15)
    base_y, max_h = 1180, 470
    bw = 260
    gap = (W - 2 * bw) // 3
    nf = font(FONT_BOLD, 40)
    vf = font(FONT_BOLD, 92)
    for i, b in enumerate(bars):
        x0 = gap + i * (bw + gap)
        h = int(max_h * b["value"] / vmax * min(1, progress))
        col = GREEN if i == 0 else GREY_BAR
        d.rounded_rectangle((x0, base_y - h, x0 + bw, base_y), radius=24, fill=col)
        if progress > 0.15:
            unit = s.get("unit", "%")
            v = f"{round(b['value'] * min(1, progress))}{unit}"
            vw = d.textlength(v, font=vf)
            d.text((x0 + (bw - vw) / 2, base_y - h - 115), v, font=vf, fill=WHITE)
        y = base_y + 20
        for ln in b["name"].split("\n"):
            lw = d.textlength(ln, font=nf)
            d.text((x0 + (bw - lw) / 2, y), ln, font=nf, fill=MUTED)
            y += 54


def make_music(path, secs, sr=44100):
    """Soft ambient pad: slow chord cycle with gentle arpeggio."""
    t = np.arange(int(secs * sr)) / sr
    chords = [[220.0, 277.18, 329.63], [196.0, 246.94, 293.66],
              [174.61, 220.0, 261.63], [196.0, 246.94, 329.63]]  # A, G, F, G(sus-ish)
    seg = 4.0
    out = np.zeros_like(t)
    for k, ch in enumerate(chords * int(secs // (seg * 4) + 2)):
        s0 = k * seg
        if s0 > secs:
            break
        m = (t >= s0) & (t < s0 + seg + 1.0)
        tt = t[m] - s0
        env = np.clip(tt / 1.2, 0, 1) * np.clip((seg + 1.0 - tt) / 1.5, 0, 1)
        for f in ch:
            out[m] += env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2 * tt)) / 6
        # arpeggio plucks
        for j, f in enumerate(ch + [ch[0] * 2]):
            p0 = j * 1.0
            pm = (tt >= p0) & (tt < p0 + 1.0)
            pt = tt[pm] - p0
            out[np.where(m)[0][pm]] += 0.12 * np.exp(-pt * 4) * np.sin(2 * np.pi * f * 2 * pt)
    fade = np.clip(t / 1.5, 0, 1) * np.clip((secs - t) / 2.0, 0, 1)
    out = out * fade
    out = out / (np.abs(out).max() + 1e-9) * 0.35
    data = (out * 32767).astype(np.int16)
    stereo = np.stack([data, data], axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(stereo.tobytes())


def main(ep_path, out_path):
    ep = json.load(open(ep_path, encoding="utf-8"))
    bg = gradient()
    slides = ep["slides"]
    layers = [slide_layer(s, ep) for s in slides]
    total = sum(s["secs"] for s in slides)
    music = out_path.replace(".mp4", "_music.wav")
    make_music(music, total)

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", music,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    wm = font(FONT_BOLD, 36)
    elapsed = 0.0
    for i, s in enumerate(slides):
        n = int(s["secs"] * FPS)
        for f in range(n):
            ts = f / FPS
            fin = min(1, ts / 0.6)
            fout = min(1, (s["secs"] - ts) / 0.4) if i < len(slides) - 1 else 1
            a = max(0, min(fin, fout))
            frame = bg.copy()
            if s["kind"] == "result" and s.get("bars"):
                draw_bars(frame, s, (ts - 0.3) / 2.0 * a if ts > 0.3 else 0)
            # slide-up text with fade
            off = int((1 - fin) * 40)
            lay = layers[i]
            if a < 1:
                al = lay.getchannel("A").point(lambda v: int(v * a))
                lay = lay.copy(); lay.putalpha(al)
            frame.paste(lay, (0, off), lay)
            d = ImageDraw.Draw(frame)
            # progress bar + watermark
            prog = (elapsed + ts) / total
            d.rectangle((0, H - 14, int(W * prog), H), fill=ACCENT)
            d.text((90, 150), "顧好大腦 · 每日一分鐘", font=wm, fill=MUTED)
            p.stdin.write(frame.tobytes())
        elapsed += s["secs"]
    p.stdin.close()
    p.wait()
    if p.returncode:
        sys.exit("ffmpeg failed")
    print(out_path, f"{total}s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
