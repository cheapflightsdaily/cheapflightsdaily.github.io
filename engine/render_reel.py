#!/usr/bin/env python3
"""Render a 9:16 Instagram reel (MP4, H.264 + AAC) from a list of deals.

Usage: python3 render_reel.py deals.json out.mp4 [max_deals] [total_deals_today]
Deals may mix departure cities (one per city works well); the reel then says "from N cities".
Deals use the same format as build_kit.py (origin, origin_country, origin_code, city, country,
code, price, trip, departs, returns, airline). The first max_deals (default 5) are shown.
The soundtrack is generated here from scratch (no third party music), so it is free to use.
"""
import json, math, os, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
FONT = {
    'black': '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf',
    'xbold': '/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf',
    'bold': '/usr/share/fonts/opentype/inter/Inter-Bold.otf',
    'semi': '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf',
    'serif_i': '/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf',
}
_fc = {}


def font(k, size):
    key = (k, int(size))
    if key not in _fc:
        _fc[key] = ImageFont.truetype(FONT[k], int(size))
    return _fc[key]


CODES = json.load(open(os.path.join(HERE, 'country_codes.json')))
_flag = {}


def flag(country, size):
    code = CODES.get(country)
    if not code:
        return None
    key = (code, size)
    if key not in _flag:
        p = os.path.join(HERE, 'flags', f'{code}.png')
        if not os.path.exists(p):
            _flag[key] = None
        else:
            im = Image.open(p).convert('RGBA').resize((size, size), Image.LANCZOS)
            m = Image.new('L', (size, size), 0)
            ImageDraw.Draw(m).ellipse([0, 0, size - 1, size - 1], fill=255)
            im.putalpha(Image.fromarray(np.minimum(np.array(im.split()[3]), np.array(m))))
            _flag[key] = im
    return _flag[key]


PALETTES = [((10, 38, 84), (24, 104, 176)), ((92, 24, 64), (214, 76, 92)), ((12, 70, 72), (28, 150, 132)),
            ((46, 26, 96), (120, 72, 200)), ((120, 50, 10), (232, 128, 40)), ((14, 52, 110), (30, 111, 184))]
SUN, INK, WHITE = (255, 209, 102), (14, 18, 32), (255, 255, 255)

_bg = {}


def background(pi):
    if pi not in _bg:
        c1, c2 = PALETTES[pi % len(PALETTES)]
        y = np.linspace(0, 1, H)[:, None]
        x = np.linspace(0, 1, W)[None, :]
        t = np.clip(y * 0.85 + x * 0.15, 0, 1)
        arr = np.zeros((H, W, 3), np.float32)
        for i in range(3):
            arr[..., i] = c1[i] + (c2[i] - c1[i]) * t
        # soft glow top right
        g = np.exp(-(((x - 0.85) ** 2) / 0.08 + ((y - 0.18) ** 2) / 0.05))
        arr += g[..., None] * 40
        _bg[pi] = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return _bg[pi].copy()


# easing
def clamp(v):
    return max(0.0, min(1.0, v))


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_back(t):
    t = clamp(t)
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def parse(s):
    import datetime
    return datetime.datetime.fromisoformat(s) if s else None


def pill(d, x, y, text, f, fill, ink, padx=34, h=None):
    tw = d.textlength(text, font=f)
    h = h or int(f.size * 1.75)
    d.rounded_rectangle([x, y, x + tw + 2 * padx, y + h], radius=h // 2, fill=fill)
    d.text((x + padx, y + h / 2), text, font=f, fill=ink, anchor='lm')
    return tw + 2 * padx


def text_center(d, y, text, f, fill, alpha=255):
    d.text((W / 2, y), text, font=f, fill=fill + (int(alpha),), anchor='ms')


def fit_font(d, text, k, start, max_w):
    s = start
    while s > 60 and d.textlength(text, font=font(k, s)) > max_w:
        s -= 6
    return font(k, s)


def origin_capsule(img, d, x, y, origin, country, scale=1.0):
    f1, f2 = font('bold', 30 * scale), font('black', 46 * scale)
    h = int(92 * scale)
    w = int(24 * scale + 64 * scale + 16 * scale + d.textlength('FROM', font=f1) + 14 * scale
            + d.textlength(origin.upper(), font=f2) + 34 * scale)
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=(255, 255, 255, 255))
    fl = flag(country, int(64 * scale))
    if fl:
        img.paste(fl, (int(x + 14 * scale), int(y + (h - fl.size[1]) / 2)), fl)
    tx = x + 14 * scale + 64 * scale + 16 * scale
    d.text((tx, y + h / 2), 'FROM', font=f1, fill=(85, 102, 122, 255), anchor='lm')
    tx += d.textlength('FROM', font=f1) + 14 * scale
    d.text((tx, y + h / 2), origin.upper(), font=f2, fill=INK + (255,), anchor='lm')
    return w


def plane(d, cx, cy, s, ang, col):
    pts = {'body': [(0, -1), (0.09, -0.85), (0.09, 0.75), (0, 0.95), (-0.09, 0.75), (-0.09, -0.85)],
           'wing': [(0.08, -0.15), (0.95, 0.25), (0.95, 0.38), (0.08, 0.15), (-0.08, 0.15), (-0.95, 0.38), (-0.95, 0.25), (-0.08, -0.15)],
           'tail': [(0.07, 0.62), (0.38, 0.85), (0.38, 0.95), (0.05, 0.85), (-0.05, 0.85), (-0.38, 0.95), (-0.38, 0.85), (-0.07, 0.62)]}
    a = ang
    for k in ('wing', 'tail', 'body'):
        P = [(cx + s * (x * math.cos(a) - y * math.sin(a)), cy + s * (x * math.sin(a) + y * math.cos(a))) for x, y in pts[k]]
        d.polygon(P, fill=col)


def arc_point(t, x0, y0, x1, y1, lift):
    x = x0 + (x1 - x0) * t
    y = y0 + (y1 - y0) * t - math.sin(math.pi * t) * lift
    return x, y


# ---------- scenes ----------
INTRO, PER, OUTRO = 2.6, 2.0, 2.8


def scene_intro(t, deals):
    o = deals[0]
    img = background(5)
    d = ImageDraw.Draw(img, 'RGBA')
    cheapest = min(int(x['price']) for x in deals)
    # flying plane across
    p = ease_out(t / 1.6)
    for i in range(30):
        tt = i / 29
        if tt > p:
            break
        x, y = arc_point(tt, 90, 1720, 990, 1600, 200)
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 255, 255, 150))
    px, py = arc_point(p, 90, 1720, 990, 1600, 200)
    nx, ny = arc_point(min(1, p + 0.02), 90, 1720, 990, 1600, 200)
    plane(d, px, py, 60, math.atan2(ny - py, nx - px) + math.pi / 2, (255, 255, 255, 255))
    # capsule
    a = ease_out((t - 0.1) / 0.5)
    origins = []
    for x in deals:
        if x.get('origin') not in [y.get('origin') for y in origins]:
            origins.append(x)
    multi = len(origins) > 1
    if multi:
        pill(d, 90, int(420 - 30 * (1 - a)), "TODAY'S CHEAPEST FLIGHTS", font('black', 44), (255, 255, 255, int(255 * a)), INK + (int(255 * a),), padx=40, h=92)
    else:
        origin_capsule(img, d, 90, int(420 - 30 * (1 - a)), o.get('origin', 'Tirana'), o.get('origin_country', 'Albania'), 1.2)
    # headline
    a = ease_out((t - 0.3) / 0.5)
    d.text((90, 690 - 40 * (1 - a)), 'Flights from', font=font('black', 112), fill=WHITE + (int(255 * a),), anchor='ls')
    s = ease_back((t - 0.6) / 0.55)
    if s > 0:
        f = font('black', int(250 * max(0.2, s)))
        d.text((80, 940), f'€{cheapest}', font=f, fill=SUN + (255,), anchor='ls')
    a = ease_out((t - 1.1) / 0.5)
    d.text((92, 1040), "Direct flights. Today's best picks.", font=font('semi', 50), fill=WHITE + (int(230 * a),), anchor='ls')
    # flags pop in one by one: departure cities if several, else destinations
    seen, row = set(), []
    for x in deals:
        key = x.get('origin_country') if multi else x.get('country')
        if key not in seen:
            seen.add(key); row.append({'country': key})
    for k, x in enumerate(row[:6]):
        s2 = ease_back((t - 1.2 - 0.12 * k) / 0.35)
        fl = flag(x.get('country', ''), 96)
        if fl and s2 > 0:
            sz = max(4, int(96 * s2))
            f2 = fl.resize((sz, sz), Image.LANCZOS)
            cx = 90 + 48 + k * 120
            d.ellipse([cx - sz / 2 - 6, 1170 - sz / 2 - 6, cx + sz / 2 + 6, 1170 + sz / 2 + 6], fill=(255, 255, 255, 255))
            img.paste(f2, (int(cx - sz / 2), int(1170 - sz / 2)), f2)
    a = ease_out((t - 1.6) / 0.5)
    names = ('From ' + ', '.join(x['origin'] for x in origins)) if multi else (', '.join(x['city'] for x in deals[:4]) + ' and more')
    d.text((92, 1290), names, font=font('semi', 44), fill=WHITE + (int(220 * a),), anchor='ls')
    return img


def scene_deal(t, deal, i, n):
    img = background(i)
    d = ImageDraw.Draw(img, 'RGBA')
    # counter + trip pill
    a = ease_out(t / 0.35)
    pill(d, 90, 300, f'DEAL {i + 1} OF {n}', font('bold', 34), (255, 255, 255, int(46 * a + 10)), WHITE + (int(255 * a),))
    trip = 'RETURN TRIP' if deal.get('returns') else 'ONE WAY'
    tw = d.textlength(trip, font=font('bold', 34)) + 68
    pill(d, W - 90 - tw, 300, trip, font('bold', 34), SUN + (int(255 * a),), INK + (int(255 * a),))
    # origin capsule small + "to"
    origin_capsule(img, d, 90, 420, deal.get('origin', 'Tirana'), deal.get('origin_country', 'Albania'), 0.9)
    d.text((90, 640), 'to', font=font('serif_i', 70), fill=WHITE + (220,), anchor='ls')
    # city slides in
    a = ease_out((t - 0.1) / 0.45)
    cf = fit_font(d, deal['city'].upper(), 'black', 200, W - 180)
    d.text((90 - 120 * (1 - a), 840), deal['city'].upper(), font=cf, fill=WHITE + (int(255 * a),), anchor='ls')
    # country row
    fl = flag(deal.get('country', ''), 70)
    a2 = ease_out((t - 0.3) / 0.4)
    if fl and a2 > 0:
        fa = fl.copy(); fa.putalpha(Image.fromarray((np.array(fl.split()[3]) * a2).astype(np.uint8)))
        img.paste(fa, (90, 900), fa)
    d.text((180, 935), f"{deal.get('country', '')}  ·  {deal['airline']}", font=font('semi', 46), fill=WHITE + (int(235 * a2),), anchor='lm')
    # route arc with plane
    p = ease_out((t - 0.2) / 1.2)
    x0, y0, x1, y1 = 110, 1180, 960, 1110
    for k in range(34):
        tt = k / 33
        if tt > p:
            break
        x, y = arc_point(tt, x0, y0, x1, y1, 140)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 255, 255, 170))
    px, py = arc_point(max(p, 0.001), x0, y0, x1, y1, 140)
    nx, ny = arc_point(min(1, p + 0.02), x0, y0, x1, y1, 140)
    plane(d, px, py, 44, math.atan2(ny - py, nx - px) + math.pi / 2, (255, 255, 255, 255))
    d.text((x0 - 10, y0 + 56), deal.get('origin_code', ''), font=font('bold', 40), fill=WHITE + (230,), anchor='ls')
    d.text((x1 + 30, y1 - 80), deal.get('code', ''), font=font('bold', 40), fill=WHITE + (int(230 * clamp(p * 1.5 - 0.5)),), anchor='rs')
    # price card bounce
    s = ease_back((t - 0.55) / 0.45)
    if s > 0:
        cw, ch = 600 * s, 300 * s
        cx, cy = 90 + 300, 1330 + 150
        d.rounded_rectangle([cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2], radius=int(44 * s), fill=SUN + (255,))
        lbl = 'return, only' if deal.get('returns') else 'only'
        d.text((cx - cw / 2 + 50 * s, cy - ch / 2 + 78 * s), lbl, font=font('serif_i', max(10, int(54 * s))), fill=INK + (255,), anchor='ls')
        d.text((cx - cw / 2 + 40 * s, cy + ch / 2 - 40 * s), f"€{int(deal['price'])}", font=font('black', max(10, int(200 * s))), fill=INK + (255,), anchor='ls')
    # date
    a = ease_out((t - 0.8) / 0.4)
    dep, ret = parse(deal['departs']), parse(deal.get('returns'))
    when = f"{dep:%a %-d %b}" + (f"  to  {ret:%a %-d %b}" if ret else "")
    d.text((90, 1745 - 20 * (1 - a)), when, font=font('bold', 58), fill=WHITE + (int(255 * a),), anchor='ls')
    return img


def scene_outro(t, deals, total):
    img = background(5)
    d = ImageDraw.Draw(img, 'RGBA')
    o = deals[0]
    a = ease_out(t / 0.5)
    norig = len({x.get('origin') for x in deals})
    if norig > 1:
        text_center(d, 640 - 40 * (1 - a), f'{total} deals today', font('black', 104), WHITE, 255 * a)
        text_center(d, 760 - 40 * (1 - a), f'from {norig} cities, all €30 or less', font('black', 70), SUN, 255 * a)
    else:
        text_center(d, 640 - 40 * (1 - a), f'{total} deals from {o.get("origin", "Tirana")}', font('black', 96), WHITE, 255 * a)
        text_center(d, 760 - 40 * (1 - a), 'today, all €30 or less', font('black', 96), SUN, 255 * a)
    s = ease_back((t - 0.4) / 0.5)
    if s > 0:
        f = font('black', max(10, int(84 * s)))
        tw = d.textlength('Link in bio', font=f)
        bw, bh = tw + 140 * s, 170 * s
        d.rounded_rectangle([W / 2 - bw / 2, 960 - bh / 2, W / 2 + bw / 2, 960 + bh / 2], radius=int(bh / 2), fill=WHITE + (255,))
        d.text((W / 2, 960), 'Link in bio', font=f, fill=INK + (255,), anchor='mm')
    a = ease_out((t - 0.8) / 0.5)
    text_center(d, 1180, 'Pick your city in the bio link' if norig > 1 else 'Follow for new deals every morning', font('semi', 52), WHITE, 235 * a)
    text_center(d, 1270, '@cheapflights.daily', font('bold', 60), SUN, 255 * a)
    # gentle pulse on the arrow
    if t > 1.0:
        yy = 1380 + 14 * math.sin((t - 1.0) * 7)
        d.polygon([(W / 2 - 40, yy), (W / 2 + 40, yy), (W / 2, yy + 46)], fill=WHITE + (200,))
    return img


def fade(a, b, k):
    return Image.blend(a, b, clamp(k))


# ---------- soundtrack (original, generated) ----------
def soundtrack(seconds, path, bpm=112, cuts=()):
    sr = 44100
    n = int(seconds * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    beat = 60 / bpm
    rng = np.random.default_rng(7)

    def env(length, attack=0.005, decay=0.2):
        tt = np.arange(int(length * sr)) / sr
        return np.minimum(1, tt / attack) * np.exp(-tt / decay)

    def add(sig, start):
        i = int(start * sr)
        if i >= n:
            return
        j = min(n, i + len(sig))
        out[i:j] += sig[:j - i]

    # kick on every beat
    kl = 0.35
    kt = np.arange(int(kl * sr)) / sr
    kick = np.sin(2 * np.pi * (50 + 90 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 9)
    # hat on off beats
    hat = rng.standard_normal(int(0.06 * sr)) * env(0.06, 0.001, 0.015)
    hat = np.diff(hat, prepend=0)
    # clap on 2 and 4
    clap = rng.standard_normal(int(0.2 * sr)) * env(0.2, 0.002, 0.05)
    # chords (I V vi IV in A major), bass
    roots = [57, 64, 66, 62]  # A, E, F#, D (midi)
    chords = [[57, 61, 64], [64, 68, 71], [66, 69, 73], [62, 66, 69]]
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    bar = beat * 4
    k = 0
    while k * beat < seconds:
        s = k * beat
        add(kick * 0.9, s)
        add(hat * 0.25, s + beat / 2)
        if k % 2 == 1:
            add(clap * 0.25, s)
        k += 1
    b = 0
    while b * bar < seconds:
        ch = chords[b % 4]
        L = bar
        tt = np.arange(int(L * sr)) / sr
        pad = sum(np.sin(2 * np.pi * hz(m) * tt) + 0.3 * np.sin(2 * np.pi * hz(m) * 2 * tt) for m in ch)
        pad *= np.minimum(1, tt / 0.08) * np.minimum(1, (L - tt) / 0.1) * 0.06
        add(pad, b * bar)
        for e in range(8):  # eighth note bass
            bl = beat / 2
            bt = np.arange(int(bl * sr)) / sr
            f0 = hz(roots[b % 4] - 24 + (12 if e % 4 == 3 else 0))
            bass = np.sign(np.sin(2 * np.pi * f0 * bt)) * 0.5 + np.sin(2 * np.pi * f0 * bt) * 0.5
            add(bass * np.exp(-bt * 6) * 0.16, b * bar + e * bl)
        # simple arpeggio lead
        for e in range(8):
            bl = beat / 2
            bt = np.arange(int(bl * sr)) / sr
            m = ch[[0, 1, 2, 1, 0, 2, 1, 2][e]] + 12
            lead = np.sin(2 * np.pi * hz(m) * bt) * np.exp(-bt * 8) * 0.08
            add(lead, b * bar + e * bl)
        b += 1
    # whoosh on scene cuts
    for c in cuts:
        L = 0.45
        wn = rng.standard_normal(int(L * sr))
        tt = np.arange(len(wn)) / sr
        wn = np.convolve(wn, np.ones(30) / 30, mode='same') * np.sin(np.pi * tt / L) ** 2 * 0.5
        add(wn, max(0, c - L / 2))
    # fade in/out, normalise
    out *= np.minimum(1, t / 0.3) * np.minimum(1, (seconds - t) / 0.8)
    out = out / (np.max(np.abs(out)) + 1e-9) * 0.85
    pcm = (out * 32767).astype(np.int16)
    st = np.stack([pcm, pcm], 1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(st.tobytes())


def main():
    deals = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    maxn = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    total = int(sys.argv[4]) if len(sys.argv) > 4 else len(deals)  # total deals found today (for the ending)
    show = deals[:maxn]
    n = len(show)
    dur = INTRO + PER * n + OUTRO
    xf = 0.18  # crossfade seconds
    tmp = tempfile.mkdtemp()
    frames = int(dur * FPS)
    cuts = [INTRO + PER * i for i in range(n + 1)]

    def frame_at(T):
        if T < INTRO:
            return scene_intro(T, show)
        if T < INTRO + PER * n:
            i = int((T - INTRO) // PER)
            return scene_deal(T - INTRO - PER * i, show[i], i, n)
        return scene_outro(T - INTRO - PER * n, show, total)

    soundtrack(dur, os.path.join(tmp, 'a.wav'), cuts=cuts)
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-i', os.path.join(tmp, 'a.wav'),
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
                           '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-shortest', '-movflags', '+faststart', out],
                          stdin=subprocess.PIPE)
    for f in range(frames):
        T = f / FPS
        img = frame_at(T)
        for c in cuts:  # short crossfade into each new scene
            if c <= T < c + xf:
                img = fade(frame_at(c - 0.001), img, (T - c) / xf)
        ff.stdin.write(img.convert('RGB').tobytes())
    ff.stdin.close()
    ff.wait()
    # cover image: the intro's final state
    scene_intro(INTRO - 0.01, show).convert('RGB').save(os.path.splitext(out)[0] + '-cover.jpg', quality=92)
    print('reel', out, f'{dur:.1f}s', n, 'deals')


if __name__ == '__main__':
    main()
