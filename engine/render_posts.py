#!/usr/bin/env python3
"""Render Instagram flight deal posts (1080x1350) from a deals JSON file.

Usage: python3 render_posts.py deals.json out_dir [YYYY-MM-DD]

Each deal: {origin, city, country, code, airport, price, trip ("One way"|"Return"),
            departs (ISO local), returns (ISO local or null), airline, link}
"""
import json, math, os, sys, datetime
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

S = 2
W, H = 1080, 1350

F = {
    'black': '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf',
    'xbold': '/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf',
    'bold': '/usr/share/fonts/opentype/inter/Inter-Bold.otf',
    'semi': '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf',
    'med': '/usr/share/fonts/opentype/inter/Inter-Medium.otf',
    'serif_i': '/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf',
}

def font(key, size):
    return ImageFont.truetype(F[key], int(size * S))

PALETTES = [
    ('#0B2A4A', '#1E6FB8', '#FFD166'),  # ocean
    ('#7A1E48', '#E2557A', '#FFE3A3'),  # rose sunset
    ('#0F4C45', '#1FA187', '#FFE082'),  # emerald
    ('#24124F', '#6D45E8', '#FFC6E5'),  # violet
    ('#082F49', '#0E7490', '#FDE68A'),  # deep teal
    ('#4A1942', '#B83280', '#FFE4A3'),  # plum
    ('#14342B', '#2D6A4F', '#F9C74F'),  # forest
    ('#3A0CA3', '#D61F75', '#FFF1A8'),  # electric
    ('#023E8A', '#0096C7', '#FFE66D'),  # sky
    ('#5C2A0E', '#D9622B', '#FFE8C2'),  # terracotta
]

SQ_DAYS = ['e hënë', 'e martë', 'e mërkurë', 'e enjte', 'e premte', 'e shtunë', 'e diel']
SQ_MONTHS = ['janar', 'shkurt', 'mars', 'prill', 'maj', 'qershor', 'korrik', 'gusht',
             'shtator', 'tetor', 'nëntor', 'dhjetor']
SQ_CITY = {'Rome': 'Romë', 'Milan': 'Milano', 'Naples': 'Napoli', 'Venice': 'Venecia', 'Turin': 'Torino',
           'Florence': 'Firence', 'Bologna': 'Bolonjë', 'Vienna': 'Vjenë', 'Prague': 'Pragë',
           'Brussels': 'Bruksel', 'London': 'Londër', 'Warsaw': 'Varshavë', 'Kraków': 'Krakov',
           'Bucharest': 'Bukuresht', 'Cologne': 'Këln', 'Munich': 'Mynih', 'Athens': 'Athinë',
           'Stockholm': 'Stokholm', 'Malta': 'Maltë', 'Edinburgh': 'Edinburg', 'Düsseldorf': 'Dyseldorf',
           'Genoa': 'Gjenova', 'Pescara': 'Peskara', 'Catania': 'Katania', 'Tirana': 'Tirana',
           'Gdańsk': 'Gdansk', 'Wrocław': 'Vroclav', 'Lamezia Terme': 'Lamezia Terme', 'Trieste': 'Trieste'}
SQ_COUNTRY = {'Italy': 'Itali', 'Hungary': 'Hungari', 'Poland': 'Poloni', 'United Kingdom': 'Britani e Madhe',
              'Austria': 'Austri', 'France': 'Francë', 'Germany': 'Gjermani', 'Spain': 'Spanjë',
              'Belgium': 'Belgjikë', 'Netherlands': 'Holandë', 'Czechia': 'Çeki', 'Slovakia': 'Sllovaki',
              'Romania': 'Rumani', 'Malta': 'Maltë', 'Sweden': 'Suedi', 'Ireland': 'Irlandë',
              'Greece': 'Greqi', 'Switzerland': 'Zvicër', 'Denmark': 'Danimarkë', 'Croatia': 'Kroaci'}
AIRPORT_SHORT = {'TSF': 'Treviso', 'BGY': 'Bergamo', 'STN': 'Stansted', 'LGW': 'Gatwick', 'BVA': 'Beauvais',
                 'CIA': 'Ciampino', 'FCO': 'Fiumicino', 'WMI': 'Modlin', 'WAW': 'Chopin', 'CRL': 'Charleroi',
                 'NRN': 'Weeze', 'CTA': 'Fontanarossa', 'PSR': 'Abruzzo', 'VRN': 'Villafranca',
                 'VIE': 'Schwechat', 'BUD': 'Liszt Ferenc', 'KRK': 'Balice', 'MXP': 'Malpensa'}


def hexrgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def parse(iso):
    if not iso:
        return None
    return datetime.datetime.fromisoformat(iso)


def en_date(d):
    return d.strftime('%a %-d %b')


def sq_date(d, cap=True):
    s = f"{SQ_DAYS[d.weekday()]}, {d.day} {SQ_MONTHS[d.month - 1]}"
    return s[0].upper() + s[1:] if cap else s


def background(c1, c2, accent, seed, height=None):
    w, h = W * S, (height or H) * S
    a, b = np.array(hexrgb(c1), float), np.array(hexrgb(c2), float)
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(0, 1, w)[None, :]
    t = np.clip(y * 0.78 + x * 0.22, 0, 1)[..., None]
    img = a * (1 - t) + b * t
    base = Image.fromarray(img.astype(np.uint8), 'RGB').convert('RGBA')

    glow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    r = 330 * S
    cx, cy = int(w * 0.86), int(h * 0.17)
    tint = tuple(int(v + (255 - v) * 0.55) for v in hexrgb(c2))
    g.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tint + (90,))
    r2 = 420 * S
    g.ellipse((-r2 // 2, int(h * 0.72) - r2 // 2, r2, int(h * 0.72) + r2), fill=(255, 255, 255, 28))
    glow = glow.filter(ImageFilter.GaussianBlur(150 * S))
    base = Image.alpha_composite(base, glow)

    rng = np.random.default_rng(seed)
    arr = np.array(base).astype(np.int16)
    noise = rng.normal(0, 5, (h, w, 1)).astype(np.int16)
    arr[..., :3] = np.clip(arr[..., :3] + noise, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')


def pill(draw, xy, text, fnt, fill, color, pad=(26, 14), anchor_right=False):
    x, y = xy
    tw = draw.textlength(text, font=fnt)
    asc, desc = fnt.getmetrics()
    th = asc * 0.74
    pw, ph = tw + pad[0] * 2 * S, th + pad[1] * 2 * S
    if anchor_right:
        x = x - pw
    draw.rounded_rectangle((x, y, x + pw, y + ph), radius=ph / 2, fill=fill)
    draw.text((x + pad[0] * S, y + ph / 2), text, font=fnt, fill=color, anchor='lm')
    return pw, ph


def plane(draw, cx, cy, size, angle, fill):
    pts = [(1.0, 0), (0.72, -0.07), (0.2, -0.07), (-0.18, -0.62), (-0.36, -0.62), (-0.14, -0.07),
           (-0.6, -0.07), (-0.76, -0.27), (-0.88, -0.27), (-0.8, 0)]
    pts = pts + [(px, -py) for px, py in reversed(pts[1:])]
    ca, sa = math.cos(angle), math.sin(angle)
    out = [(cx + (px * ca - py * sa) * size, cy + (px * sa + py * ca) * size) for px, py in pts]
    draw.polygon(out, fill=fill)


def fit(draw, text, key, start, max_w, min_size=60):
    size = start
    while size > min_size:
        f = font(key, size)
        if draw.textlength(text, font=f) <= max_w * S:
            return f, size
        size -= 4
    return font(key, min_size), min_size


FLAG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flags')
COUNTRY_CODES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'country_codes.json')))


def paste_flag(img, country, x, y, size, ring=True):
    code = COUNTRY_CODES.get(country)
    path = os.path.join(FLAG_DIR, f'{code}.png') if code else None
    if not path or not os.path.exists(path):
        return False
    size = int(size)
    if ring:
        rd = ImageDraw.Draw(img, 'RGBA')
        g = int(4 * S)
        rd.ellipse((x - g, y - g, x + size + g, y + size + g), fill=(255, 255, 255, 255))
    fimg = Image.open(path).convert('RGBA').resize((size, size), Image.LANCZOS)
    img.paste(fimg, (int(x), int(y)), fimg)
    return True


def trip_info(deal):
    """(nights, days, is_weekend) for a return deal; weekend = out Thu/Fri/Sat, back Sun/Mon, 3 nights max."""
    dep, ret = parse(deal['departs']), parse(deal.get('returns'))
    if not ret:
        return None, None, False
    nights = (ret.date() - dep.date()).days
    wk = dep.weekday() in (3, 4, 5) and ret.weekday() in (6, 0) and nights <= 3
    if 'weekend' in deal:
        wk = bool(deal['weekend'])
    return nights, nights + 1, wk


def render(deal, idx, out_path, today):
    c1, c2, accent = PALETTES[idx % len(PALETTES)]
    acc = hexrgb(accent)
    dark = (14, 18, 32)
    img = background(c1, c2, accent, idx + 7).convert('RGB')
    d = ImageDraw.Draw(img, 'RGBA')
    M = 80 * S
    white = (255, 255, 255)

    # Top pills
    nights, days, weekend = trip_info(deal)
    if nights is None:
        pill(d, (M, 80 * S), 'FLIGHT DEAL', font('bold', 26), (255, 255, 255, 46), white)
        trip_label = 'ONE WAY'
    else:
        if weekend:
            pill(d, (M, 80 * S), 'WEEKEND GETAWAY', font('black', 26), (255, 255, 255, 255), dark)
        else:
            pill(d, (M, 80 * S), f'{days}-DAY GETAWAY', font('bold', 26), (255, 255, 255, 46), white)
        trip_label = f'RETURN · {nights} NIGHT' + ('S' if nights != 1 else '')
    pill(d, (W * S - M, 80 * S), trip_label, font('bold', 26), acc + (255,), dark, anchor_right=True)

    # Origin capsule: flag + FROM TIRANA, so the departure city reads at a glance
    origin = deal.get('origin', 'Tirana')
    cap_top, cap_h = 172 * S, 80 * S
    of_small, of_big = font('bold', 24), font('black', 44)
    t1, t2 = 'FROM', origin.upper()
    w1, w2 = d.textlength(t1, font=of_small), d.textlength(t2, font=of_big)
    fl = 56 * S
    cap_w = 12 * S + fl + 18 * S + w1 + 12 * S + w2 + 30 * S
    d.rounded_rectangle((M, cap_top, M + cap_w, cap_top + cap_h), radius=cap_h / 2, fill=(255, 255, 255, 255))
    paste_flag(img, deal.get('origin_country', 'Albania'), M + 12 * S, cap_top + (cap_h - fl) / 2, fl, ring=False)
    tx = M + 12 * S + fl + 18 * S
    d.text((tx, cap_top + cap_h / 2 + 2 * S), t1, font=of_small, fill=(90, 98, 115), anchor='lm')
    d.text((tx + w1 + 12 * S, cap_top + cap_h / 2 + 2 * S), t2, font=of_big, fill=dark, anchor='lm')
    d.text((M + cap_w + 22 * S, cap_top + cap_h / 2 + 4 * S), 'to', font=font('serif_i', 52),
           fill=(255, 255, 255, 230), anchor='lm')

    city = deal['city'].upper()
    cf, csize = fit(d, city, 'black', 196, 920)
    city_base = 300 * S + int(csize * 0.73 * S)
    d.text((M, city_base), city, font=cf, fill=white, anchor='ls')
    cb = (0, 0, 0, city_base)

    # Destination row: flag + country, airport, airline
    country = deal.get('country', '')
    country_show = 'UK' if country == 'United Kingdom' else country
    ap = AIRPORT_SHORT.get(deal.get('code', ''), '')
    bits = [b for b in [country_show, f'{ap} Airport' if ap else '', deal.get('airline', '')] if b]
    sub = '  ·  '.join(bits)
    df_ = 60 * S
    sf, _ = fit(d, sub, 'med', 36, 920 - 80, 24)
    sub_y = cb[3] + 40 * S
    has_flag = paste_flag(img, country, M, sub_y, df_, ring=True)
    sx0 = M + (df_ + 20 * S if has_flag else 0)
    d.text((sx0, sub_y + df_ / 2), sub, font=sf, fill=(255, 255, 255, 230), anchor='lm')

    # Flight arc with airport codes at each end
    y0 = (sub_y + df_) / S + 100
    p0, p1, p2 = (M / S - 10, y0 + 120), (540, y0 - 70), (W - 150, y0 + 10)
    n = 46
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    for x, y in pts[:-3]:
        r = 4.2
        d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=(255, 255, 255, 150))
    ex, ey = pts[-1]
    px, py = pts[-3]
    plane(d, ex * S, ey * S, 46 * S, math.atan2(ey - py, ex - px), white)
    sx, sy = pts[0]
    d.ellipse(((sx - 11) * S, (sy - 11) * S, (sx + 11) * S, (sy + 11) * S), outline=white, width=4 * S)
    codef = font('bold', 26)
    d.text(((sx + 24) * S, (sy + 9) * S), deal.get('origin_code', 'TIA'), font=codef, fill=white, anchor='lm')
    if deal.get('code'):
        d.text((ex * S, (ey - 44) * S), deal['code'], font=codef, fill=white, anchor='ms')

    # Price card
    price = f"€{int(round(deal['price']))}"
    pf = font('black', 220)
    pw = d.textlength(price, font=pf)
    card_top = (y0 + 168) * S
    card_w = max(pw + 120 * S, 470 * S)
    card_h = 300 * S
    d.rounded_rectangle((M, card_top, M + card_w, card_top + card_h), radius=44 * S, fill=acc + (255,))
    label = 'both flights, only' if deal.get('returns') else 'only'
    d.text((M + 52 * S, card_top + 72 * S), label, font=font('serif_i', 48), fill=dark, anchor='ls')
    d.text((M + 46 * S, card_top + card_h - 44 * S), price, font=pf, fill=dark, anchor='ls')

    # Direct stamp
    cx, cy, r = (W - 80 - 118) * S, card_top + card_h / 2, 118 * S
    if M + card_w + 30 * S < cx - r:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 235), width=4 * S)
        d.ellipse((cx - r + 14 * S, cy - r + 14 * S, cx + r - 14 * S, cy + r - 14 * S),
                  outline=(255, 255, 255, 110), width=2 * S)
        d.text((cx, cy - 22 * S), 'DIRECT', font=font('bold', 27), fill=white, anchor='mm')
        d.text((cx, cy + 22 * S), 'FLIGHT', font=font('black', 40), fill=white, anchor='mm')

    # Dates
    dep = parse(deal['departs'])
    ret = parse(deal.get('returns'))
    dy = card_top + card_h + 78 * S
    df = font('semi', 40)
    if ret:
        d.text((M, dy), f"{en_date(dep)}  →  {en_date(ret)}", font=font('bold', 44), fill=white, anchor='ls')
        d.text((M, dy + 58 * S), f"Out {dep:%H:%M}  ·  Back {ret:%H:%M}  ·  direct both ways", font=font('med', 32),
               fill=acc + (255,), anchor='ls')
    else:
        d.text((M, dy), f"{en_date(dep)}  ·  {dep.strftime('%H:%M')}", font=df, fill=white, anchor='ls')
        d.text((M, dy + 58 * S), 'Book fast, prices change every day!', font=font('med', 34),
               fill=acc + (255,), anchor='ls')

    # Footer
    fy = (H - 92) * S
    d.line((M, fy, W * S - M, fy), fill=(255, 255, 255, 70), width=2 * S)
    d.text((M, fy + 50 * S), 'Booking link in bio', font=font('semi', 28), fill=white, anchor='ls')
    d.text((W * S - M, fy + 50 * S), f"Price found {today}", font=font('med', 24),
           fill=(255, 255, 255, 190), anchor='rs')

    out = img.convert('RGB').resize((W, H), Image.LANCZOS)
    out.save(out_path, quality=95)


SH = 1920  # story height


def render_story(deal, idx, out_path, today, n=None, total=None):
    """9:16 story: the feed design centred on a taller canvas, with a story header and CTA."""
    c1, c2, accent = PALETTES[idx % len(PALETTES)]
    acc = hexrgb(accent)
    dark = (14, 18, 32)
    tmp = out_path + '.tmp.png'
    render(deal, idx, tmp, today)
    post = Image.open(tmp).convert('RGB').resize((W * S, H * S), Image.LANCZOS)
    os.remove(tmp)
    bg = background(c1, c2, accent, idx + 31, height=SH).convert('RGB')
    oy = 250 * S
    # feather the pasted post into the taller background
    mask = Image.new('L', post.size, 255)
    md = ImageDraw.Draw(mask)
    fe = 140 * S
    for i in range(fe):
        a = int(255 * i / fe)
        md.line((0, i, post.size[0], i), fill=a)
        md.line((0, post.size[1] - 1 - i, post.size[0], post.size[1] - 1 - i), fill=a)
    bg.paste(post, (0, oy), mask)
    d = ImageDraw.Draw(bg, 'RGBA')
    M = 80 * S
    white = (255, 255, 255)
    label = "TODAY'S FLIGHT DEALS" + (f"  ·  {n}/{total}" if n and total else '')
    d.text((W * S / 2, 150 * S), label, font=font('bold', 32), fill=white, anchor='mm')
    d.line((W * S / 2 - 60 * S, 190 * S, W * S / 2 + 60 * S, 190 * S), fill=acc + (255,), width=4 * S)
    # call to action, leaving room above for a link sticker
    cy = (250 + H + 120) * S
    cta = 'Tap the link to book'
    f = font('black', 46)
    tw = d.textlength(cta, font=f)
    ph = 104 * S
    d.rounded_rectangle((W * S / 2 - tw / 2 - 48 * S, cy, W * S / 2 + tw / 2 + 48 * S, cy + ph), radius=ph / 2,
                        fill=acc + (255,))
    d.text((W * S / 2, cy + ph / 2 + 2 * S), cta, font=f, fill=dark, anchor='mm')
    d.text((W * S / 2, cy + ph + 60 * S), 'All of today’s deals are in our bio', font=font('med', 32),
           fill=(255, 255, 255, 220), anchor='mm')
    bg.resize((W, SH), Image.LANCZOS).save(out_path, quality=95)


def render_summary(deals, out_path, today, origin='Tirana', origin_country='Albania'):
    """Feed post listing all of today's deals."""
    c1, c2, accent = ('#0B2A4A', '#1E6FB8', '#FFD166')
    acc = hexrgb(accent)
    dark = (14, 18, 32)
    img = background(c1, c2, accent, 99).convert('RGB')
    d = ImageDraw.Draw(img, 'RGBA')
    M = 72 * S
    white = (255, 255, 255)
    pill(d, (M, 64 * S), 'FLIGHT DEALS', font('bold', 26), (255, 255, 255, 46), white)
    pill(d, (W * S - M, 64 * S), today.upper(), font('bold', 26), acc + (255,), dark, anchor_right=True)
    # origin capsule
    cap_top, cap_h, fl = 140 * S, 76 * S, 52 * S
    t1, t2 = 'FROM', origin.upper()
    f1, f2 = font('bold', 22), font('black', 40)
    w1, w2 = d.textlength(t1, font=f1), d.textlength(t2, font=f2)
    cap_w = 12 * S + fl + 16 * S + w1 + 10 * S + w2 + 28 * S
    d.rounded_rectangle((M, cap_top, M + cap_w, cap_top + cap_h), radius=cap_h / 2, fill=white + (255,))
    paste_flag(img, origin_country, M + 12 * S, cap_top + (cap_h - fl) / 2, fl, ring=False)
    tx = M + 12 * S + fl + 16 * S
    d.text((tx, cap_top + cap_h / 2 + 2 * S), t1, font=f1, fill=(90, 98, 115), anchor='lm')
    d.text((tx + w1 + 10 * S, cap_top + cap_h / 2 + 2 * S), t2, font=f2, fill=dark, anchor='lm')
    d.text((M, 318 * S), "Today's cheapest flights", font=font('black', 76), fill=white, anchor='ls')
    rows = deals[:10]
    top, rh = 352 * S, 84 * S
    for i, r in enumerate(rows):
        y = top + i * rh
        if i % 2 == 0:
            d.rounded_rectangle((M - 16 * S, y, W * S - M + 16 * S, y + rh - 6 * S), radius=22 * S,
                                fill=(255, 255, 255, 22))
        fsz = 52 * S
        paste_flag(img, r.get('country', ''), M, y + (rh - 6 * S - fsz) / 2, fsz, ring=True)
        cx = M + fsz + 24 * S
        d.text((cx, y + 36 * S), r['city'], font=font('bold', 36), fill=white, anchor='ls')
        dep = parse(r['departs'])
        ret = parse(r.get('returns'))
        sub = (f"Return  ·  {en_date(dep)} to {en_date(ret)}" if ret else f"One way  ·  {en_date(dep)}")
        sub += f"  ·  {r.get('airline', '')}"
        d.text((cx, y + 68 * S), sub, font=font('med', 24), fill=(255, 255, 255, 200), anchor='ls')
        price = f"€{int(round(r['price']))}"
        pf = font('black', 40)
        pw = d.textlength(price, font=pf)
        px1 = W * S - M
        px0 = px1 - pw - 40 * S
        d.rounded_rectangle((px0, y + 12 * S, px1, y + rh - 18 * S), radius=(rh - 30 * S) / 2, fill=acc + (255,))
        d.text(((px0 + px1) / 2, y + (rh - 6 * S) / 2 + 2 * S), price, font=pf, fill=dark, anchor='mm')
    fy = (H - 88) * S
    d.line((M, fy, W * S - M, fy), fill=(255, 255, 255, 70), width=2 * S)
    d.text((M, fy + 48 * S), 'All booking links in bio', font=font('semi', 28), fill=white, anchor='ls')
    d.text((W * S - M, fy + 48 * S), 'Direct flights  ·  small bag included', font=font('med', 24),
           fill=(255, 255, 255, 190), anchor='rs')
    img.resize((W, H), Image.LANCZOS).save(out_path, quality=95)


def main():
    deals = json.load(open(sys.argv[1]))
    out_dir = sys.argv[2]
    today = sys.argv[3] if len(sys.argv) > 3 else datetime.date.today().isoformat()
    y, m, dd = today.split('-')
    today_sq = datetime.date(int(y), int(m), int(dd)).strftime('%-d %b %Y')
    os.makedirs(out_dir, exist_ok=True)
    for i, deal in enumerate(deals):
        name = f"{i + 1:02d}-{deal['city'].lower().replace(' ', '-')}.png"
        render(deal, i, os.path.join(out_dir, name), today_sq)
        print(name)


if __name__ == '__main__':
    main()
