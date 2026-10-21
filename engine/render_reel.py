#!/usr/bin/env python3
"""Render a 9:16 Instagram reel (MP4, H.264 + AAC) of short getaways.

Usage: python3 render_reel.py deals.json out.mp4 [max_deals] [total_deals_today] [seed]

Deals use the same format as build_kit.py. Return trips are shown as getaways
(dates out and back, nights, weekend badge). The look changes every day: the
seed (default: today's date) picks one of several colour themes, opening hooks,
deal layouts and endings, so consecutive reels never start with the same frame.
The soundtrack is a calm lo-fi jazz loop generated here from scratch (Rhodes
chords, upright bass, brushed drums, vinyl crackle), so it is free to use.
"""
import datetime, json, math, os, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
FONT = {
    'black': '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf',
    'xbold': '/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf',
    'bold': '/usr/share/fonts/opentype/inter/Inter-Bold.otf',
    'semi': '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf',
    'serif_i': '/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf',
    'retro': os.path.join(HERE, 'fonts', 'Righteous.ttf'),
    'dmserif': os.path.join(HERE, 'fonts', 'DMSerifDisplay.ttf'),
    'dmserif_i': os.path.join(HERE, 'fonts', 'DMSerifDisplay-Italic.ttf'),
    'script': os.path.join(HERE, 'fonts', 'Pacifico.ttf'),
}
_fc, _cmap = {}, {}


def font(k, size):
    if not os.path.exists(FONT.get(k, '')):
        k = 'black'
    key = (k, int(size))
    if key not in _fc:
        _fc[key] = ImageFont.truetype(FONT[k], max(4, int(size)))
    return _fc[key]


def has_glyphs(k, text):
    """Display fonts only cover basic Latin; fall back to Inter for names like Wrocław."""
    if k not in _cmap:
        try:
            from fontTools.ttLib import TTFont
            _cmap[k] = set(TTFont(FONT[k])['cmap'].getBestCmap().keys())
        except Exception:
            _cmap[k] = None
    cm = _cmap[k]
    return cm is None or all(ord(c) in cm or c == ' ' for c in text)


def dfont(k, size, text, fallback='black'):
    return font(k if has_glyphs(k, text) else fallback, size)


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


# ---------- themes (90s travel poster feel) ----------
THEMES = [
    dict(name='sunset', bg=[(43, 22, 74), (176, 58, 92), (247, 137, 72)], ink=(255, 244, 226), accent=(255, 205, 96),
         card=(255, 244, 226), card_ink=(43, 22, 74), sun=True, stars=False, light=False),
    dict(name='lagoon', bg=[(8, 48, 66), (18, 110, 120), (64, 168, 150)], ink=(250, 242, 222), accent=(242, 190, 72),
         card=(242, 190, 72), card_ink=(10, 40, 54), sun=False, stars=False, light=False),
    dict(name='postcard', bg=[(246, 236, 214), (240, 222, 190), (232, 206, 168)], ink=(36, 44, 74), accent=(206, 84, 52),
         card=(36, 44, 74), card_ink=(246, 236, 214), sun=False, stars=False, light=True),
    dict(name='midnight', bg=[(12, 14, 40), (34, 30, 86), (88, 46, 120)], ink=(244, 240, 255), accent=(255, 128, 170),
         card=(255, 128, 170), card_ink=(18, 16, 48), sun=False, stars=True, light=False),
    dict(name='riviera', bg=[(214, 80, 62), (238, 132, 86), (250, 196, 128)], ink=(255, 250, 238), accent=(22, 70, 110),
         card=(255, 250, 238), card_ink=(22, 70, 110), sun=True, stars=False, light=False),
    dict(name='olive', bg=[(36, 52, 38), (82, 104, 64), (170, 160, 104)], ink=(250, 244, 226), accent=(240, 160, 80),
         card=(250, 244, 226), card_ink=(36, 52, 38), sun=False, stars=False, light=False),
]

_bg = {}


def background(th, variant=0, deco=False):
    """deco=True adds the theme's big decoration (striped horizon sun); used on hooks and endings only."""
    key = (th['name'], variant, deco)
    if key in _bg:
        return _bg[key].copy()
    c = th['bg']
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    t = np.clip(y * 0.9 + x * 0.1 + (0.06 * variant), 0, 1)
    arr = np.zeros((H, W, 3), np.float32)
    for i in range(3):
        a = np.where(t < 0.5, c[0][i] + (c[1][i] - c[0][i]) * (t / 0.5), c[1][i] + (c[2][i] - c[1][i]) * ((t - 0.5) / 0.5))
        arr[..., i] = a
    rng = np.random.default_rng(11 + variant)
    arr += rng.normal(0, 5.5, (H, W, 1))  # film grain
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img, 'RGBA')
    if th['sun'] and deco:  # striped retro sun rising on the horizon, bottom of the frame
        cx, cy, r = W / 2, H + 60, 360
        sun = Image.new('RGBA', (2 * r, 2 * r), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sun)
        sd.ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=th['accent'] + (225,))
        for k in range(9):
            yy = 70 + k * 36
            sd.rectangle([0, yy, 2 * r, yy + 4 + k * 3], fill=(0, 0, 0, 0))
        img.paste(sun, (int(cx - r), int(cy - r)), sun)
    if th['stars']:
        for _ in range(140):
            sx, sy = rng.uniform(0, W), rng.uniform(0, H * 0.75)
            s = rng.uniform(1, 3.2)
            d.ellipse([sx - s, sy - s, sx + s, sy + s], fill=(255, 255, 255, int(rng.uniform(60, 200))))
    if th['light']:  # postcard border
        d.rectangle([34, 34, W - 34, H - 34], outline=th['accent'] + (255,), width=6)
        d.rectangle([50, 50, W - 50, H - 50], outline=th['ink'] + (90,), width=2)
    _bg[key] = img
    return img.copy()


# ---------- helpers ----------
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
    return datetime.datetime.fromisoformat(s) if s else None


def nights_info(d):
    dep, ret = parse(d['departs']), parse(d.get('returns'))
    if not ret:
        return None, False
    n = (ret.date() - dep.date()).days
    wk = d.get('weekend')
    if wk is None:
        wk = dep.weekday() in (3, 4, 5) and ret.weekday() in (6, 0) and n <= 3
    return n, bool(wk)


def when_text(d):
    dep, ret = parse(d['departs']), parse(d.get('returns'))
    if ret:
        return f"{dep:%a %-d %b}  →  {ret:%a %-d %b}"
    return f"{dep:%a %-d %b}"


def rgba(c, a=255):
    return tuple(c) + (int(max(0, min(255, a))),)


def pill(d, x, y, text, f, fill, ink, padx=34, h=None, right=False):
    tw = d.textlength(text, font=f)
    h = h or int(f.size * 1.8)
    w = tw + 2 * padx
    if right:
        x = x - w
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=fill)
    d.text((x + padx, y + h / 2), text, font=f, fill=ink, anchor='lm')
    return w


def fit(d, text, k, start, max_w, minimum=60):
    s = start
    while s > minimum and d.textlength(text, font=dfont(k, s, text)) > max_w:
        s -= 6
    return dfont(k, s, text)


def plane(d, cx, cy, s, ang, col):
    pts = {'body': [(0, -1), (0.09, -0.85), (0.09, 0.75), (0, 0.95), (-0.09, 0.75), (-0.09, -0.85)],
           'wing': [(0.08, -0.15), (0.95, 0.25), (0.95, 0.38), (0.08, 0.15), (-0.08, 0.15), (-0.95, 0.38), (-0.95, 0.25), (-0.08, -0.15)],
           'tail': [(0.07, 0.62), (0.38, 0.85), (0.38, 0.95), (0.05, 0.85), (-0.05, 0.85), (-0.38, 0.95), (-0.38, 0.85), (-0.07, 0.62)]}
    for k in ('wing', 'tail', 'body'):
        P = [(cx + s * (x * math.cos(ang) - y * math.sin(ang)), cy + s * (x * math.sin(ang) + y * math.cos(ang))) for x, y in pts[k]]
        d.polygon(P, fill=col)


def arc_point(t, x0, y0, x1, y1, lift):
    return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t - math.sin(math.pi * t) * lift


def draw_route(d, th, p, x0, y0, x1, y1, lift, codes=None, dot=5, size=44, two_way=False):
    for k in range(36):
        tt = k / 35
        if tt > p:
            break
        x, y = arc_point(tt, x0, y0, x1, y1, lift)
        d.ellipse([x - dot, y - dot, x + dot, y + dot], fill=rgba(th['ink'], 170))
    px, py = arc_point(max(p, 0.001), x0, y0, x1, y1, lift)
    nx, ny = arc_point(min(1, p + 0.02), x0, y0, x1, y1, lift)
    plane(d, px, py, size, math.atan2(ny - py, nx - px) + math.pi / 2, rgba(th['ink']))
    if codes:
        d.text((x0 - 6, y0 + 56), codes[0], font=font('bold', 40), fill=rgba(th['ink'], 230), anchor='ls')
        d.text((x1 + 30, y1 - 80), codes[1], font=font('bold', 40), fill=rgba(th['ink'], 230 * clamp(p * 1.5 - 0.5)), anchor='rs')
        if two_way and p > 0.95:
            d.text((x1 + 30, y1 - 34), '⇄ return', font=font('semi', 30), fill=rgba(th['ink'], 200), anchor='rs')


def flag_paste(img, country, x, y, size, ring=None, alpha=1.0):
    fl = flag(country, size)
    if not fl:
        return False
    if ring:
        ImageDraw.Draw(img, 'RGBA').ellipse([x - 6, y - 6, x + size + 6, y + size + 6], fill=rgba(ring))
    if alpha < 1:
        fl = fl.copy(); fl.putalpha(Image.fromarray((np.array(fl.split()[3]) * alpha).astype(np.uint8)))
    img.paste(fl, (int(x), int(y)), fl)
    return True


def origin_capsule(img, d, th, x, y, origin, country, scale=1.0):
    f1, f2 = font('bold', 30 * scale), font('black', 46 * scale)
    h = int(92 * scale)
    bg_c = th['ink'] if not th['light'] else th['ink']
    ink = th['bg'][0] if not th['light'] else th['bg'][0]
    w = int(14 * scale + 64 * scale + 16 * scale + d.textlength('FROM', font=f1) + 14 * scale + d.textlength(origin.upper(), font=f2) + 34 * scale)
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=rgba(bg_c))
    flag_paste(img, country, x + 14 * scale, y + (h - int(64 * scale)) / 2, int(64 * scale))
    tx = x + 14 * scale + 64 * scale + 16 * scale
    d.text((tx, y + h / 2), 'FROM', font=f1, fill=rgba(ink, 170), anchor='lm')
    tx += d.textlength('FROM', font=f1) + 14 * scale
    d.text((tx, y + h / 2), origin.upper(), font=f2, fill=rgba(ink), anchor='lm')
    return w


# ---------- opening hooks ----------
INTRO, PER, OUTRO = 2.8, 2.2, 2.8


def hook_question(t, deals, th, ctx):
    img = background(th, 0, deco=True); d = ImageDraw.Draw(img, 'RGBA')
    _sky_plane(d, th, t)
    a = ease_out((t - 0.1) / 0.5)
    d.text((90, 640 - 40 * (1 - a)), 'Where to', font=font('retro', 150), fill=rgba(th['ink'], 255 * a), anchor='ls')
    a2 = ease_out((t - 0.35) / 0.5)
    d.text((90, 800 - 40 * (1 - a2)), 'this weekend?', font=font('retro', 118), fill=rgba(th['accent'], 255 * a2), anchor='ls')
    a3 = ease_out((t - 0.9) / 0.5)
    d.text((92, 920), f"{len(deals)} getaways, return flights from €{ctx['cheapest']}", font=font('semi', 50), fill=rgba(th['ink'], 235 * a3), anchor='ls')
    _flags_row(img, d, th, t, deals, ctx, 1100)
    return img


def hook_hero(t, deals, th, ctx):
    h = ctx['hero']
    img = background(th, 1, deco=True); d = ImageDraw.Draw(img, 'RGBA')
    _sky_plane(d, th, t)
    a = ease_out((t - 0.1) / 0.45)
    d.text((90, 520), 'a weekend in', font=font('script', 80), fill=rgba(th['accent'], 255 * a), anchor='ls')
    cf = fit(d, h['city'].upper(), 'retro', 230, W - 180)
    a2 = ease_out((t - 0.3) / 0.5)
    d.text((90 - 100 * (1 - a2), 760), h['city'].upper(), font=cf, fill=rgba(th['ink'], 255 * a2), anchor='ls')
    s = ease_back((t - 0.7) / 0.5)
    if s > 0:
        txt = f"€{int(h['price'])}"
        d.text((90, 1000), txt, font=font('black', int(220 * max(0.2, s))), fill=rgba(th['accent']), anchor='ls')
        d.text((100 + d.textlength(txt, font=font('black', 220)), 990), 'return', font=font('serif_i', 64), fill=rgba(th['ink'], 230 * clamp(s)), anchor='ls')
    a3 = ease_out((t - 1.2) / 0.5)
    d.text((92, 1110), f"from {h['origin']}  ·  {when_text(h)}", font=font('semi', 46), fill=rgba(th['ink'], 230 * a3), anchor='ls')
    d.text((92, 1190), f"+ {len(deals) - 1} more getaways inside", font=font('semi', 46), fill=rgba(th['ink'], 200 * a3), anchor='ls')
    return img


def hook_stack(t, deals, th, ctx):
    img = background(th, 2, deco=True); d = ImageDraw.Draw(img, 'RGBA')
    _sky_plane(d, th, t)
    norig = ctx['norig']
    lines = ['3 days.', f'{norig} cities.' if norig > 1 else f'{len(deals)} trips.', f"Under €{ctx['cap']}."]
    for i, ln in enumerate(lines):
        a = ease_out((t - 0.15 - 0.45 * i) / 0.4)
        col = th['accent'] if i == 2 else th['ink']
        d.text((90 + 60 * (1 - a), 620 + i * 190), ln, font=font('retro', 170), fill=rgba(col, 255 * a), anchor='ls')
    a4 = ease_out((t - 1.6) / 0.5)
    d.text((92, 1180), 'Short getaways, return flights included.', font=font('semi', 46), fill=rgba(th['ink'], 230 * a4), anchor='ls')
    return img


def hook_dinner(t, deals, th, ctx):
    img = background(th, 3, deco=True); d = ImageDraw.Draw(img, 'RGBA')
    _sky_plane(d, th, t)
    for i, ln in enumerate(['A weekend away', 'costs less than', 'dinner out.']):
        a = ease_out((t - 0.1 - 0.3 * i) / 0.45)
        d.text((90, 560 + i * 130), ln, font=font('dmserif', 118), fill=rgba(th['ink'] if i < 2 else th['accent'], 255 * a), anchor='ls')
    s = ease_back((t - 1.1) / 0.5)
    if s > 0:
        w = 520 * s; hh = 150 * s
        d.rounded_rectangle([90, 960, 90 + w, 960 + hh], radius=int(hh / 2), fill=rgba(th['card']))
        d.text((90 + w / 2, 960 + hh / 2), f"from €{ctx['cheapest']} return", font=font('black', max(8, int(56 * s))), fill=rgba(th['card_ink']), anchor='mm')
    _flags_row(img, d, th, t, deals, ctx, 1240)
    return img


def hook_countdown(t, deals, th, ctx):
    img = background(th, 4, deco=True); d = ImageDraw.Draw(img, 'RGBA')
    _sky_plane(d, th, t)
    a = ease_out((t - 0.1) / 0.4)
    d.text((90, 470), f"TOP {len(deals)}", font=font('retro', 210), fill=rgba(th['accent'], 255 * a), anchor='ls')
    a2 = ease_out((t - 0.4) / 0.4)
    d.text((90, 640), 'WEEKEND', font=font('retro', 170), fill=rgba(th['ink'], 255 * a2), anchor='ls')
    d.text((90, 800), 'ESCAPES', font=font('retro', 170), fill=rgba(th['ink'], 255 * a2), anchor='ls')
    a3 = ease_out((t - 0.9) / 0.5)
    d.text((92, 900), f"for the coming weekends, from €{ctx['cheapest']} return", font=font('semi', 46), fill=rgba(th['ink'], 230 * a3), anchor='ls')
    _flags_row(img, d, th, t, deals, ctx, 1060)
    return img


def hook_ticket(t, deals, th, ctx):
    img = background(th, 5, deco=True); d = ImageDraw.Draw(img, 'RGBA')
    _sky_plane(d, th, t)
    s = ease_back((t - 0.1) / 0.6)
    x0, y0, w, h = 90, 470, W - 180, 640
    if s > 0:
        hh = h * s
        d.rounded_rectangle([x0, y0 + (h - hh) / 2, x0 + w, y0 + (h + hh) / 2], radius=40, fill=rgba(th['card']))
    if s > 0.9:
        ci = th['card_ink']
        d.text((x0 + 60, y0 + 110), 'BOARDING PASS', font=font('bold', 40), fill=rgba(ci, 170), anchor='ls')
        d.text((x0 + 60, y0 + 260), 'FROM', font=font('bold', 32), fill=rgba(ci, 150), anchor='ls')
        names = ', '.join(o for o in ctx['origins'][:3]) + ('...' if len(ctx['origins']) > 3 else '')
        d.text((x0 + 60, y0 + 330), names, font=fit(d, names, 'black', 64, w - 120), fill=rgba(ci), anchor='ls')
        d.text((x0 + 60, y0 + 430), 'TO', font=font('bold', 32), fill=rgba(ci, 150), anchor='ls')
        a = ease_out((t - 1.0) / 0.5)
        d.text((x0 + 60, y0 + 520), 'Somewhere new' if a < 1 else 'Somewhere new', font=font('dmserif_i', 84), fill=rgba(th['accent'], 255 * a), anchor='ls')
        for k in range(0, w, 34):  # perforation
            d.ellipse([x0 + k + 10, y0 + 170, x0 + k + 20, y0 + 180], fill=rgba(ci, 60))
    a4 = ease_out((t - 1.4) / 0.5)
    d.text((92, 1240), f"{ctx['days_label']} getaways from €{ctx['cheapest']} return", font=font('semi', 50), fill=rgba(th['ink'], 235 * a4), anchor='ls')
    return img


def _sky_plane(d, th, t):
    p = ease_out(t / 2.4)
    draw_route(d, th, p, 60, 1660, 1020, 1540, 120, dot=4, size=52)


def _flags_row(img, d, th, t, deals, ctx, y):
    seen, row = [], []
    multi = ctx['norig'] > 1
    for x in deals:
        key = x.get('origin_country') if multi else x.get('country')
        if key not in seen:
            seen.append(key); row.append(key)
    for k, c in enumerate(row[:6]):
        s2 = ease_back((t - 1.2 - 0.12 * k) / 0.35)
        if s2 > 0:
            sz = max(4, int(96 * s2))
            flag_paste(img, c, 90 + 48 + k * 120 - sz / 2, y - sz / 2, sz, ring=th['ink'])
    a = ease_out((t - 1.6) / 0.5)
    names = ('From ' + ', '.join(ctx['origins'])) if multi else (', '.join(x['city'] for x in deals[:4]) + ' and more')
    d.text((92, y + 120), names, font=fit(d, names, 'semi', 44, W - 180, 30), fill=rgba(th['ink'], 220 * a), anchor='ls')


HOOKS = [hook_question, hook_hero, hook_stack, hook_dinner, hook_countdown, hook_ticket]


# ---------- deal layouts ----------
def deal_classic(t, deal, i, n, th):
    img = background(th, i % 3); d = ImageDraw.Draw(img, 'RGBA')
    nights, wk = nights_info(deal)
    a = ease_out(t / 0.35)
    pill(d, 90, 300, f'{i + 1} / {n}', font('bold', 34), rgba(th['ink'], 40 * a + 10), rgba(th['ink'], 255 * a))
    tag = 'WEEKEND' if wk else (f'{nights + 1} DAYS' if nights else 'ONE WAY')
    pill(d, W - 90, 300, tag, font('black', 34), rgba(th['accent'], 255 * a), rgba(th['card_ink'] if not th['light'] else th['bg'][0], 255 * a), right=True)
    origin_capsule(img, d, th, 90, 420, deal.get('origin', 'Tirana'), deal.get('origin_country', 'Albania'), 0.95)
    d.text((90, 650), 'to', font=font('serif_i', 70), fill=rgba(th['ink'], 220), anchor='ls')
    a = ease_out((t - 0.1) / 0.45)
    cf = fit(d, deal['city'].upper(), 'retro', 200, W - 180)
    d.text((90 - 120 * (1 - a), 850), deal['city'].upper(), font=cf, fill=rgba(th['ink'], 255 * a), anchor='ls')
    a2 = ease_out((t - 0.3) / 0.4)
    flag_paste(img, deal.get('country', ''), 90, 905, 70, alpha=a2)
    d.text((180, 940), f"{deal.get('country', '')}  ·  {deal['airline']}", font=font('semi', 44), fill=rgba(th['ink'], 235 * a2), anchor='lm')
    p = ease_out((t - 0.2) / 1.2)
    draw_route(d, th, p, 110, 1180, 960, 1110, 140, (deal.get('origin_code', ''), deal.get('code', '')), two_way=bool(nights))
    s = ease_back((t - 0.55) / 0.45)
    if s > 0:
        cw, ch = 620 * s, 300 * s
        cx, cy = 90 + 310, 1330 + 150
        d.rounded_rectangle([cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2], radius=int(44 * s), fill=rgba(th['card']))
        lbl = 'return, only' if nights else 'only'
        d.text((cx - cw / 2 + 50 * s, cy - ch / 2 + 78 * s), lbl, font=font('serif_i', max(10, int(54 * s))), fill=rgba(th['card_ink']), anchor='ls')
        d.text((cx - cw / 2 + 40 * s, cy + ch / 2 - 40 * s), f"€{int(deal['price'])}", font=font('black', max(10, int(200 * s))), fill=rgba(th['card_ink']), anchor='ls')
    a = ease_out((t - 0.8) / 0.4)
    d.text((90, 1730 - 20 * (1 - a)), when_text(deal), font=font('bold', 58), fill=rgba(th['ink'], 255 * a), anchor='ls')
    if nights:
        d.text((90, 1800 - 20 * (1 - a)), f"{nights} nights  ·  direct both ways", font=font('semi', 40), fill=rgba(th['accent'] if not th['light'] else th['ink'], 230 * a), anchor='ls')
    return img


def deal_ticket(t, deal, i, n, th):
    img = background(th, i % 3); d = ImageDraw.Draw(img, 'RGBA')
    nights, wk = nights_info(deal)
    a = ease_out(t / 0.35)
    d.text((90, 330), f"Getaway {i + 1} of {n}", font=font('script', 66), fill=rgba(th['accent'], 255 * a), anchor='ls')
    s = ease_back((t - 0.1) / 0.5)
    x0, y0, w, h = 70, 420, W - 140, 1120
    if s > 0:
        hh = h * s
        top = y0 + (h - hh) / 2
        d.rounded_rectangle([x0, top, x0 + w, top + hh], radius=46, fill=rgba(th['card']))
    if s > 0.95:
        ci = th['card_ink']
        d.text((x0 + 60, y0 + 100), 'BOARDING PASS', font=font('bold', 36), fill=rgba(ci, 150), anchor='ls')
        tag = 'WEEKEND' if wk else (f'{nights + 1} DAYS' if nights else 'ONE WAY')
        pill(d, x0 + w - 60, y0 + 50, tag, font('black', 32), rgba(th['accent']), rgba(th['card'] if not th['light'] else (255, 255, 255)), right=True)
        oc, dc = deal.get('origin_code', ''), deal.get('code', '')
        d.text((x0 + 60, y0 + 300), oc, font=font('retro', 190), fill=rgba(ci), anchor='ls')
        d.text((x0 + w - 60, y0 + 300), dc, font=font('retro', 190), fill=rgba(ci), anchor='rs')
        mid = x0 + w / 2
        plane(d, mid, y0 + 225, 44, math.pi / 2, rgba(th['accent']))
        d.text((x0 + 60, y0 + 360), deal.get('origin', '').upper(), font=font('bold', 36), fill=rgba(ci, 170), anchor='ls')
        cityf = fit(d, deal['city'].upper(), 'bold', 36, w / 2 - 60, 22)
        d.text((x0 + w - 60, y0 + 360), deal['city'].upper(), font=cityf, fill=rgba(ci, 170), anchor='rs')
        a2 = ease_out((t - 0.5) / 0.5)
        cf = fit(d, deal['city'], 'dmserif', 150, w - 120)
        d.text((x0 + 60, y0 + 560), deal['city'], font=cf, fill=rgba(ci, 255 * a2), anchor='ls')
        flag_paste(img, deal.get('country', ''), x0 + 60, y0 + 600, 60, alpha=a2)
        d.text((x0 + 140, y0 + 632), f"{deal.get('country', '')}  ·  {deal['airline']}", font=fit(d, f"{deal.get('country', '')}  ·  {deal['airline']}", 'semi', 38, w - 220, 24), fill=rgba(ci, 200 * a2), anchor='lm')
        for k in range(0, int(w) - 40, 34):
            d.ellipse([x0 + 30 + k, y0 + 720, x0 + 40 + k, y0 + 730], fill=rgba(ci, 70))
        dep, ret = parse(deal['departs']), parse(deal.get('returns'))
        a3 = ease_out((t - 0.8) / 0.4)
        d.text((x0 + 60, y0 + 800), 'OUT', font=font('bold', 30), fill=rgba(ci, 140 * a3), anchor='ls')
        d.text((x0 + 60, y0 + 860), f"{dep:%a %-d %b}", font=font('black', 50), fill=rgba(ci, 255 * a3), anchor='ls')
        if ret:
            d.text((x0 + 420, y0 + 800), 'BACK', font=font('bold', 30), fill=rgba(ci, 140 * a3), anchor='ls')
            d.text((x0 + 420, y0 + 860), f"{ret:%a %-d %b}", font=font('black', 50), fill=rgba(ci, 255 * a3), anchor='ls')
        s2 = ease_back((t - 0.9) / 0.45)
        if s2 > 0:
            d.text((x0 + 60, y0 + 1040), f"€{int(deal['price'])}", font=font('black', max(10, int(170 * s2))), fill=rgba(ci), anchor='ls')
            d.text((x0 + w - 60, y0 + 1030), ('return' if ret else 'one way') + (f' · {nights} nights' if nights else ''), font=font('serif_i', 52), fill=rgba(ci, 220 * clamp(s2)), anchor='rs')
    return img


def deal_postcard(t, deal, i, n, th):
    img = background(th, i % 3); d = ImageDraw.Draw(img, 'RGBA')
    nights, wk = nights_info(deal)
    a = ease_out(t / 0.4)
    d.text((W / 2, 330), 'Greetings from' if wk else 'A few days in', font=font('script', 84), fill=rgba(th['accent'], 255 * a), anchor='ms')
    a2 = ease_out((t - 0.15) / 0.5)
    cf = fit(d, deal['city'].upper(), 'retro', 240, W - 160)
    d.text((W / 2, 560 + 40 * (1 - a2)), deal['city'].upper(), font=cf, fill=rgba(th['ink'], 255 * a2), anchor='ms')
    flag_paste(img, deal.get('country', ''), W / 2 - 50, 620, 100, ring=th['ink'], alpha=a2)
    p = ease_out((t - 0.3) / 1.1)
    draw_route(d, th, p, 150, 1020, 930, 1020, 160, (deal.get('origin_code', ''), deal.get('code', '')), size=50)
    d.text((W / 2, 1110), f"from {deal.get('origin', '')}  ·  {deal['airline']}", font=font('semi', 44), fill=rgba(th['ink'], 220 * a2), anchor='ms')
    s = ease_back((t - 0.7) / 0.5)
    if s > 0:  # stamp
        r = 230 * s
        cx, cy = W / 2, 1420
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgba(th['card']))
        d.ellipse([cx - r + 16 * s, cy - r + 16 * s, cx + r - 16 * s, cy + r - 16 * s], outline=rgba(th['card_ink'], 140), width=max(1, int(4 * s)))
        d.text((cx, cy + 40 * s), f"€{int(deal['price'])}", font=font('black', max(10, int(150 * s))), fill=rgba(th['card_ink']), anchor='ms')
        d.text((cx, cy + 110 * s), 'return' if nights else 'one way', font=font('serif_i', max(10, int(48 * s))), fill=rgba(th['card_ink'], 220), anchor='ms')
        d.text((cx, cy - 110 * s), 'WEEKEND' if wk else (f'{nights + 1} DAYS' if nights else ''), font=font('black', max(8, int(40 * s))), fill=rgba(th['card_ink'], 200), anchor='ms')
    a3 = ease_out((t - 0.9) / 0.4)
    d.text((W / 2, 1780), when_text(deal), font=font('bold', 56), fill=rgba(th['ink'], 255 * a3), anchor='ms')
    return img


LAYOUTS = [deal_classic, deal_ticket, deal_postcard]


# ---------- endings ----------
def outro(t, deals, total, th, ctx, variant):
    img = background(th, 0, deco=True); d = ImageDraw.Draw(img, 'RGBA')
    a = ease_out(t / 0.5)
    if variant == 0:
        d.text((W / 2, 640 - 40 * (1 - a)), f"{total} getaways today", font=font('retro', 104), fill=rgba(th['ink'], 255 * a), anchor='ms')
        sub = f"from {ctx['norig']} cities, all under €{ctx['cap']} return" if ctx['norig'] > 1 else f"all under €{ctx['cap']} return"
        d.text((W / 2, 740 - 40 * (1 - a)), sub, font=font('semi', 52), fill=rgba(th['accent'], 255 * a), anchor='ms')
    elif variant == 1:
        d.text((W / 2, 600 - 40 * (1 - a)), 'Pack light.', font=font('dmserif', 130), fill=rgba(th['ink'], 255 * a), anchor='ms')
        d.text((W / 2, 740 - 40 * (1 - a)), 'Go this weekend.', font=font('dmserif_i', 110), fill=rgba(th['accent'], 255 * a), anchor='ms')
    else:
        d.text((W / 2, 600 - 40 * (1 - a)), 'Save this', font=font('retro', 130), fill=rgba(th['ink'], 255 * a), anchor='ms')
        d.text((W / 2, 740 - 40 * (1 - a)), 'for your next trip 📌'.replace(' 📌', ''), font=font('semi', 66), fill=rgba(th['accent'], 255 * a), anchor='ms')
    s = ease_back((t - 0.4) / 0.5)
    if s > 0:
        f = font('black', max(10, int(84 * s)))
        tw = d.textlength('Link in bio', font=f)
        bw, bh = tw + 140 * s, 170 * s
        d.rounded_rectangle([W / 2 - bw / 2, 960 - bh / 2, W / 2 + bw / 2, 960 + bh / 2], radius=int(bh / 2), fill=rgba(th['card']))
        d.text((W / 2, 960), 'Link in bio', font=f, fill=rgba(th['card_ink']), anchor='mm')
    a = ease_out((t - 0.8) / 0.5)
    msg = 'Pick your city, book in a minute' if ctx['norig'] > 1 else 'New getaways every morning'
    d.text((W / 2, 1180), msg, font=font('semi', 52), fill=rgba(th['ink'], 235 * a), anchor='ms')
    d.text((W / 2, 1270), '@cheapflights.daily', font=font('bold', 60), fill=rgba(th['accent'], 255 * a), anchor='ms')
    if t > 1.0:
        yy = 1380 + 14 * math.sin((t - 1.0) * 6)
        d.polygon([(W / 2 - 40, yy), (W / 2 + 40, yy), (W / 2, yy + 46)], fill=rgba(th['ink'], 200))
    return img


def fade(a, b, k):
    return Image.blend(a, b, clamp(k))


# ---------- soundtrack: calm lo-fi jazz, generated ----------
def soundtrack(seconds, path, seed=0, cuts=()):
    from scipy.signal import butter, lfilter
    sr = 44100
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    out = np.zeros(n)
    bpm = float(rng.choice([74, 78, 82, 86]))
    beat = 60 / bpm
    swing = 0.64
    key = int(rng.integers(-4, 4))  # transpose around C
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)

    def add(sig, start, buf=out):
        i = int(start * sr)
        if i >= n or i < 0:
            return
        j = min(n, i + len(sig))
        buf[i:j] += sig[:j - i]

    # chord vocabulary (rootless, jazz voicings, relative to chord root)
    V = {'maj9': [4, 7, 11, 14], 'm9': [3, 7, 10, 14], '13': [4, 10, 14, 21], 'm7': [3, 7, 10, 15],
         '7b9': [4, 10, 13, 19], 'maj7': [4, 7, 11, 16], '6/9': [4, 9, 14, 19]}
    PROGS = [
        [(2, 'm9'), (7, '13'), (0, 'maj9'), (9, '7b9')],   # ii V I VI
        [(5, 'maj7'), (4, 'm7'), (2, 'm9'), (0, 'maj9')],   # IV iii ii I
        [(0, 'maj9'), (9, 'm9'), (2, 'm9'), (7, '13')],     # I vi ii V
        [(0, '6/9'), (5, 'maj9'), (0, '6/9'), (5, 'maj9')], # two-chord vamp
        [(9, 'm9'), (2, 'm9'), (7, '13'), (0, 'maj9')],     # vi ii V I
    ]
    prog = PROGS[int(rng.integers(0, len(PROGS)))]
    base = 48 + key  # C3 area

    def rhodes(f, dur, vel=0.5):
        t = np.arange(int(dur * sr)) / sr
        idx = 1.6 * np.exp(-t * 6) + 0.25
        mod = np.sin(2 * np.pi * f * t) * idx
        car = np.sin(2 * np.pi * f * t + mod) + 0.25 * np.sin(2 * np.pi * f * 2.001 * t) * np.exp(-t * 3)
        env = np.minimum(1, t / 0.008) * np.exp(-t * 1.1)
        trem = 1 + 0.12 * np.sin(2 * np.pi * 4.2 * t)
        return car * env * trem * vel

    def bass(f, dur, vel=0.6):
        t = np.arange(int(dur * sr)) / sr
        s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
        env = np.minimum(1, t / 0.01) * np.exp(-t * 3.2)
        return s * env * vel

    def noise(dur):
        return rng.standard_normal(int(dur * sr))

    b_hp = butter(2, 5000 / (sr / 2), 'high')
    b_bp = butter(2, [900 / (sr / 2), 5000 / (sr / 2)], 'band')
    bar = beat * 4
    nbars = int(math.ceil(seconds / bar)) + 1
    keys_buf, bass_buf, drum_buf, mel_buf = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    for b in range(nbars):
        root, q = prog[b % len(prog)]
        nxt = prog[(b + 1) % len(prog)][0]
        t0 = b * bar
        notes = [base + root + iv for iv in V[q]]
        # comping: beat 1 and the swung "and" of 2
        for off, vel in ((0, 0.42), (beat + beat * swing, 0.3)):
            if rng.random() < (1.0 if off == 0 else 0.7):
                for k, m in enumerate(notes):
                    add(rhodes(hz(m), bar * 0.9, vel / len(notes) * 2.2), t0 + off + k * 0.012, keys_buf)
        # walking bass, one note per beat
        r = base - 12 + root
        walk = [r, r + (3 if q.startswith('m') else 4), r + 7, base - 12 + nxt + rng.choice([-1, 1])]
        for k, m in enumerate(walk):
            add(bass(hz(m), beat * 0.95, 0.55), t0 + k * beat, bass_buf)
        # drums: soft kick, brushed snare on 2 and 4, swung hats
        for k in range(4):
            bt = t0 + k * beat
            if k in (0, 2) or (k == 3 and rng.random() < 0.4):
                tt = np.arange(int(0.3 * sr)) / sr
                kick = np.sin(2 * np.pi * (48 + 50 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 10) * 0.55
                add(kick, bt + (beat * swing if k == 3 else 0), drum_buf)
            if k in (1, 3):
                sn = lfilter(*b_bp, noise(0.35)) * np.exp(-np.arange(int(0.35 * sr)) / sr * 9) * 0.22
                add(sn, bt, drum_buf)
            for sub, v in ((0, 0.06), (beat * swing, 0.045)):
                hh = lfilter(*b_hp, noise(0.06)) * np.exp(-np.arange(int(0.06 * sr)) / sr * 60) * v
                add(hh, bt + sub, drum_buf)
        # sparse melody (vibes-like), chord tones an octave up
        for k in range(8):
            if rng.random() < 0.28:
                m = notes[int(rng.integers(0, len(notes)))] + 12
                tt = t0 + (k // 2) * beat + (beat * swing if k % 2 else 0)
                add(rhodes(hz(m), beat * 1.6, 0.16), tt, mel_buf)
    lp = butter(2, 3200 / (sr / 2), 'low')
    mix = lfilter(*lp, keys_buf * 0.9 + mel_buf * 0.8) + lfilter(*butter(2, 900 / (sr / 2), 'low'), bass_buf) * 1.1 + drum_buf * 0.8
    # vinyl: hiss + crackle
    hiss = lfilter(*butter(1, 6000 / (sr / 2), 'low'), rng.standard_normal(n)) * 0.012
    crack = np.zeros(n)
    for pos in rng.integers(0, n, int(seconds * 7)):
        crack[pos] = rng.uniform(-1, 1) * rng.uniform(0.05, 0.25)
    crack = lfilter(*butter(1, 2500 / (sr / 2), 'high'), crack)
    mix = mix + hiss + crack
    # gentle tape wobble: tiny slow amplitude drift, then soft clip and fades
    tt = np.arange(n) / sr
    mix *= 1 + 0.03 * np.sin(2 * np.pi * 0.35 * tt)
    mix = np.tanh(mix * 1.3)
    mix *= np.minimum(1, tt / 1.0) * np.minimum(1, (seconds - tt) / 1.5)
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.8
    pcm = (mix * 32767).astype(np.int16)
    st = np.stack([pcm, pcm], 1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(st.tobytes())


def main():
    deals = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    maxn = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    total = int(sys.argv[4]) if len(sys.argv) > 4 else len(deals)
    today = datetime.date.today()
    seed = int(sys.argv[5]) if len(sys.argv) > 5 else today.toordinal()
    show = deals[:maxn]
    n = len(show)
    th = THEMES[seed % len(THEMES)]
    hook = HOOKS[(seed * 5 + 1) % len(HOOKS)]
    layout = LAYOUTS[(seed + seed // 3) % len(LAYOUTS)]
    ov = seed % 3
    origins = []
    for x in show:
        if x.get('origin') not in origins:
            origins.append(x.get('origin'))
    nights = [nights_info(x)[0] for x in show if nights_info(x)[0]]
    ctx = dict(cheapest=min(int(x['price']) for x in show), cap=70, norig=len(origins), origins=origins,
               hero=min(show, key=lambda x: x['price']), today=today,
               days_label=(f"{min(nights) + 1} to {max(nights) + 1} day" if nights and min(nights) != max(nights) else (f"{nights[0] + 1}-day" if nights else 'Short')))
    dur = INTRO + PER * n + OUTRO
    xf = 0.22
    tmp = tempfile.mkdtemp()
    frames = int(dur * FPS)
    cuts = [INTRO + PER * i for i in range(n + 1)]

    def frame_at(T):
        if T < INTRO:
            return hook(T, show, th, ctx)
        if T < INTRO + PER * n:
            i = int((T - INTRO) // PER)
            return layout(T - INTRO - PER * i, show[i], i, n, th)
        return outro(T - INTRO - PER * n, show, total, th, ctx, ov)

    soundtrack(dur, os.path.join(tmp, 'a.wav'), seed=seed, cuts=cuts)
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-i', os.path.join(tmp, 'a.wav'),
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
                           '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-shortest', '-movflags', '+faststart', out],
                          stdin=subprocess.PIPE)
    for f in range(frames):
        T = f / FPS
        img = frame_at(T)
        for c in cuts:
            if c <= T < c + xf:
                img = fade(frame_at(c - 0.001), img, (T - c) / xf)
        ff.stdin.write(img.convert('RGB').tobytes())
    ff.stdin.close()
    ff.wait()
    hook(INTRO - 0.01, show, th, ctx).convert('RGB').save(os.path.splitext(out)[0] + '-cover.jpg', quality=92)
    print('reel', out, f'{dur:.1f}s', n, 'deals', 'theme', th['name'], 'hook', hook.__name__, 'layout', layout.__name__)


if __name__ == '__main__':
    main()
