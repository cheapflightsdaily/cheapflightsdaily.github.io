#!/usr/bin/env python3
"""Build the daily posting kit: post images + captions page.

Usage: python3 build_kit.py deals.json out_dir YYYY-MM-DD
Writes out_dir/NN-city.png, out_dir/captions.txt and out_dir/kit.html
"""
import base64, io, json, os, sys, unicodedata, html
from PIL import Image
import render_posts as rp

SQ_DATE_LONG = ['E hënë', 'E martë', 'E mërkurë', 'E enjte', 'E premte', 'E shtunë', 'E diel']


def city_tag(name):
    s = unicodedata.normalize('NFD', name)
    return ''.join(c for c in s if c.isalpha() and ord(c) < 128).lower()


CITY_RENAME = {'Palma, Majorca': 'Mallorca', 'Palma de Mallorca': 'Mallorca'}


def load_deals(path):
    deals = json.load(open(path))
    for d in deals:
        d['city'] = CITY_RENAME.get(d['city'], d['city'])
    return deals


CODES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'country_codes.json')))


def flag_emoji(country):
    code = CODES.get(country)
    if not code or code == 'xk':
        return ''
    return ''.join(chr(0x1F1E6 + ord(c) - ord('a')) for c in code) + ' '


def caption(d):
    ap = rp.AIRPORT_SHORT.get(d.get('code', ''), '')
    dep = rp.parse(d['departs'])
    ret = rp.parse(d.get('returns'))
    origin = d.get('origin', 'Tirana')
    lines = [d['hook'], '', f"✈️ {flag_emoji(d.get('origin_country', 'Albania'))}{origin} → {flag_emoji(d.get('country', ''))}{d['city']}" + (f" ({ap})" if ap else '')]
    if ret:
        lines.append(f"📅 Out: {dep:%a %-d %b} at {dep:%H:%M}")
        lines.append(f"📅 Back: {ret:%a %-d %b} at {ret:%H:%M}")
    else:
        lines.append(f"📅 {dep:%a %-d %b} at {dep:%H:%M}")
    trip = 'Return trip, total price' if d['trip'] == 'Return' else 'One way'
    lines.append(f"🎫 {trip} · {d['airline']} · direct flight")
    lines.append('🎒 Price includes a small personal bag')
    if d.get('note'):
        lines.append(d['note'])
    lines += ['', 'Prices change fast, so grab it while it lasts. Booking link in bio 🔗', '',
              hashtags(origin, d.get('origin_country', 'Albania')) + f" #{city_tag(d['city'])}"]
    return '\n'.join(lines)


KEYCAPS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
def hashtags(origin='Tirana', country='Albania'):
    o, c = city_tag(origin), city_tag(country)
    return f'#cheapflights #flightdeals #{o} #{c} #flyfrom{o} #travel #traveldeals #budgettravel #europetravel #cheapflightsdaily'


HASHTAGS = hashtags()


def short_note(d):
    n = d.get('note') or ''
    if 'visa' in n:
        return 'visa needed' if 'UK' not in n else 'UK visa needed'
    if 'Lands at' in n:
        return 'lands at ' + n.split('Lands at ')[1].split(',')[0]
    return ''


def summary_caption(deals, today):
    lines = [f"✈️ Today's cheapest flights from {flag_emoji('Albania')}Tirana · {today}", '']
    for d in deals:
        trip = 'return' if d['trip'] == 'Return' else 'one way'
        lines.append(f"{flag_emoji(d.get('country', ''))}{d['city']}  €{int(d['price'])} {trip}")
    lines += ['', 'Swipe our carousel post for dates and details of every deal 👉',
              'All booking links in bio 🔗', '', HASHTAGS]
    return '\n'.join(lines)


def carousel_caption(deals):
    origin = deals[0].get('origin', 'Tirana') if deals else 'Tirana'
    ocountry = deals[0].get('origin_country', 'Albania') if deals else 'Albania'
    lines = [f"🔥 {len(deals)} flight deals from {flag_emoji(ocountry)}{origin} today. Swipe through 👉", '']
    for i, d in enumerate(deals):
        dep = rp.parse(d['departs'])
        ret = rp.parse(d.get('returns'))
        when = f"{dep:%a %-d %b} to {ret:%a %-d %b}" if ret else f"{dep:%a %-d %b}"
        trip = 'Return' if ret else 'One way'
        extra = short_note(d)
        line = f"{KEYCAPS[i] if i < 10 else str(i + 1) + '.'} {flag_emoji(d.get('country', ''))}{d['city']} €{int(d['price'])} · {trip} · {when} · {d['airline']}"
        if extra:
            line += f" ({extra})"
        lines.append(line)
    lines += ['', '🎒 Prices include a small personal bag. Direct flights only.',
              f'Prices change fast, so grab them while they last. All {origin} booking links in bio 🔗', '', hashtags(origin, ocountry)]
    return '\n'.join(lines)


def reel_caption(deals, total=None, cities=None):
    """Caption for the daily reel: one line per deal shown, then hashtags for every departure city."""
    origins = []
    for d in deals:
        if d.get('origin') not in [o[0] for o in origins]:
            origins.append((d.get('origin'), d.get('origin_country')))
    multi = len(origins) > 1
    if multi:
        head = f"✈️ Today's cheapest flights from {len(origins)} cities, all €30 or less!"
    else:
        head = f"✈️ Today's cheapest flights from {flag_emoji(origins[0][1])}{origins[0][0]}, all €30 or less!"
    lines = [head, '']
    for d in deals:
        dep = rp.parse(d['departs'])
        ret = rp.parse(d.get('returns'))
        when = f"{dep:%a %-d %b}" + (f" to {ret:%a %-d %b}, return" if ret else '')
        extra = ' (from Beauvais)' if d.get('origin_code') == 'BVA' else ''
        lines.append(f"{flag_emoji(d.get('origin_country', ''))}{d.get('origin')} → {flag_emoji(d.get('country', ''))}{d['city']} €{int(d['price'])} · {when}{extra}")
    lines += ['', 'Direct flights, small personal bag included. Prices change fast!']
    if total:
        lines.append(f"{total} deals today" + (", pick your city at the link in bio 🔗" if multi else ", all booking links in bio 🔗"))
    else:
        lines.append('All booking links in bio 🔗')
    lines += ['Follow @cheapflights.daily for new deals every morning ☀️', '']
    tags = ['#cheapflights', '#flightdeals', '#traveldeals', '#budgettravel', '#europetravel', '#travelreels', '#cheapflightsdaily']
    for o, c in origins:
        tags += [f'#{city_tag(o)}', f'#flyfrom{city_tag(o)}']
    for d in deals:
        t = f"#{city_tag(d['city'])}"
        if t not in tags:
            tags.append(t)
    lines.append(' '.join(tags[:30]))
    return '\n'.join(lines)


def build_bio(deals, today_label, out_path, groups=None):
    """Bio page. groups: list of deal lists, one per departure city (tabs). Default: one group."""
    flags_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flags')
    cache = {}

    def flag_uri(country):
        code = CODES.get(country)
        if not code:
            return None
        if code not in cache:
            path = os.path.join(flags_dir, f'{code}.png')
            if not os.path.exists(path):
                cache[code] = None
            else:
                im = Image.open(path).convert('RGBA').resize((72, 72), Image.LANCZOS)
                b = io.BytesIO(); im.save(b, 'PNG', optimize=True)
                cache[code] = 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
        return cache[code]

    origins = []
    for grp in (groups if groups is not None else [deals]):
        if not grp:
            continue
        items = []
        for d in grp:
            dep = rp.parse(d['departs'])
            ret = rp.parse(d.get('returns'))
            when = f"{dep:%a %-d %b}, {dep:%H:%M}" + (f" · back {ret:%a %-d %b}" if ret else '')
            note = (d.get('note') or '').replace('ℹ️ ', '').replace('⚠️ ', '')
            items.append({'city': d['city'], 'country': d.get('country', ''), 'flag': flag_uri(d.get('country', '')),
                          'code': d.get('code', ''), 'originCode': d.get('origin_code', 'TIA'),
                          'airport': rp.AIRPORT_SHORT.get(d.get('code', ''), ''), 'price': int(d['price']),
                          'trip': d['trip'], 'when': when, 'airline': d['airline'], 'link': d['link'], 'note': note})
        o = grp[0].get('origin', 'Tirana')
        notes = {i['note'] for i in items}
        shared = notes.pop() if len(notes) == 1 and len(items) > 1 else ''
        if shared:
            for i in items:
                i['note'] = ''
        origins.append({'origin': o, 'slug': city_tag(o), 'originFlag': flag_uri(grp[0].get('origin_country', 'Albania')),
                        'note': shared, 'deals': items})
    page = {'updated': today_label, 'origins': origins}
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bio_template.html')).read()
    open(out_path, 'w').write(tpl.replace('__DATA__', json.dumps(page).replace('</', '<\\/')))


SITE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Cheap Flights Daily</title>
<meta name="description" content="Today's cheapest direct flights, updated every morning.">
<link rel="icon" href="icon.png">
<link rel="apple-touch-icon" href="icon.png">
<meta property="og:title" content="Cheap Flights Daily">
<meta property="og:description" content="Today's cheapest direct flights, updated every morning.">
<meta property="og:image" content="icon.png">
"""


def build_site(bio_path, out_path):
    """Standalone website version of the bio page (for GitHub Pages), with no Claude markup."""
    src = open(bio_path).read()
    src = src.replace('<title>Tirana Flight Deals</title>\n', '').replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '')
    src = src.replace('<div class="wrap">', '</head>\n<body>\n<div class="wrap">', 1)
    open(out_path, 'w').write(SITE_HEAD + src + '\n</body>\n</html>\n')


def site_main():
    """python3 build_kit.py site OUT_DIR YYYY-MM-DD deals_city1.json deals_city2.json ...
    Writes OUT_DIR/bio.html and OUT_DIR/index.html with one tab per departure city (in the order given)."""
    out, today = sys.argv[2], sys.argv[3]
    import datetime
    y, m, dd = today.split('-')
    label = datetime.date(int(y), int(m), int(dd)).strftime('%-d %b %Y')
    groups = [load_deals(p) for p in sys.argv[4:]]
    os.makedirs(out, exist_ok=True)
    build_bio(None, label, os.path.join(out, 'bio.html'), groups=groups)
    build_site(os.path.join(out, 'bio.html'), os.path.join(out, 'index.html'))
    print('site built with', [g[0]['origin'] for g in groups if g])


def main():
    if sys.argv[1] == 'site':
        return site_main()
    deals = load_deals(sys.argv[1])
    out = sys.argv[2]
    today = sys.argv[3]
    y, m, dd = today.split('-')
    import datetime
    today_sq = datetime.date(int(y), int(m), int(dd)).strftime('%-d %b %Y')
    os.makedirs(out, exist_ok=True)

    cards, txt = [], []
    for i, d in enumerate(deals):
        name = f"{i + 1:02d}-{city_tag(d['city'])}.png"
        path = os.path.join(out, name)
        rp.render(d, i, path, today_sq)
        buf = io.BytesIO()
        Image.open(path).convert('RGB').save(buf, 'JPEG', quality=88, optimize=True)
        uri = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
        cap = caption(d)
        city_sq = d['city']
        trip = 'Return' if d['trip'] == 'Return' else 'One way'
        txt.append(f"POST {i + 1} · {d.get('time', '')} · {city_sq} €{int(d['price'])} ({trip})\n"
                   f"Booking link: {d['link']}\n\n{cap}\n\n" + '=' * 40 + '\n')
        cards.append({'n': i + 1, 'time': d.get('time', ''), 'city': city_sq, 'price': int(d['price']),
                      'trip': trip, 'img': uri, 'caption': cap, 'link': d['link'], 'file': name})

    open(os.path.join(out, 'captions.txt'), 'w').write('\n'.join(txt))
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kit_template.html')).read()
    page = (tpl.replace('__DATE__', html.escape(today_sq))
               .replace('__COUNT__', str(len(cards)))
               .replace('__DATA__', json.dumps(cards).replace('</', '<\\/')))
    open(os.path.join(out, 'kit.html'), 'w').write(page)
    rp.render_summary(deals, os.path.join(out, 'summary.png'), today_sq)
    build_bio(deals, today_sq, os.path.join(out, 'bio.html'))
    build_site(os.path.join(out, 'bio.html'), os.path.join(out, 'index.html'))
    json.dump({'summary_caption': summary_caption(deals, today_sq), 'carousel_caption': carousel_caption(deals)},
              open(os.path.join(out, 'captions.json'), 'w'), ensure_ascii=False, indent=1)
    print('built', len(cards), 'posts + summary + bio')


if __name__ == '__main__':
    main()