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
    s = unicodedata.normalize('NFD', name.replace('ł', 'l').replace('Ł', 'L').replace('ø', 'o').replace('ß', 'ss'))
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


PRICE_CAP = 70  # max total price for a return trip, in EUR


def getaway_bits(d):
    nights, days, wk = rp.trip_info(d)
    return nights, days, wk


def caption(d):
    """Caption for a single deal post (used when a city has only one deal)."""
    ap = rp.AIRPORT_SHORT.get(d.get('code', ''), '')
    dep = rp.parse(d['departs'])
    ret = rp.parse(d.get('returns'))
    origin = d.get('origin', 'Tirana')
    nights, days, wk = getaway_bits(d)
    lines = [d['hook'], '', f"✈️ {flag_emoji(d.get('origin_country', 'Albania'))}{origin} ⇄ {flag_emoji(d.get('country', ''))}{d['city']}" + (f" ({ap})" if ap else '')]
    if ret:
        lines.append(f"📅 {dep:%a %-d %b} to {ret:%a %-d %b} · {nights} nights" + (' · weekend 🎉' if wk else ''))
        lines.append(f"🛫 Out {dep:%H:%M} · 🛬 Back {ret:%H:%M}")
        lines.append(f"🎫 €{int(d['price'])} for both flights · {d['airline']} · direct")
    else:
        lines.append(f"📅 {dep:%a %-d %b} at {dep:%H:%M}")
        lines.append(f"🎫 One way · {d['airline']} · direct flight")
    lines.append('🎒 Price includes a small personal bag')
    if d.get('note'):
        lines.append(d['note'])
    lines += ['', 'Prices change fast, so grab it while it lasts. Booking link in bio 🔗', '',
              hashtags(origin, d.get('origin_country', 'Albania'), [d])]
    return '\n'.join(lines)


KEYCAPS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
VISIT = {'Italy': '#visititaly', 'Spain': '#visitspain', 'Portugal': '#visitportugal', 'Malta': '#visitmalta',
         'France': '#visitfrance', 'Greece': '#visitgreece', 'Croatia': '#visitcroatia', 'Hungary': '#visitbudapest',
         'Poland': '#visitpoland', 'Albania': '#visitalbania', 'Ireland': '#visitireland', 'United Kingdom': '#visitbritain',
         'Germany': '#visitgermany', 'Austria': '#visitaustria', 'Slovakia': '#visitslovakia', 'Romania': '#visitromania',
         'Bulgaria': '#visitbulgaria', 'Czechia': '#visitczechrepublic', 'Belgium': '#visitbelgium', 'Denmark': '#visitdenmark',
         'Netherlands': '#visitholland', 'Montenegro': '#visitmontenegro', 'Serbia': '#visitserbia'}
# Broad reach tags first, then niche getaway tags, then deal tags; location tags are added per post.
CORE_TAGS = ['#travel', '#travelreels', '#travelhacks', '#traveltips', '#budgettravel', '#cheaptravel', '#travelonabudget',
             '#weekendgetaway', '#weekendtrip', '#citybreak', '#shorttrip', '#europetrip', '#europetravel',
             '#cheapflights', '#flightdeals', '#traveldeals', '#cheapflightsdaily']


def tag_set(origins, destinations, countries, reel=False, limit=28):
    """Hashtags for reach: broad travel tags, getaway niche tags, then origin, destination and country tags."""
    tags = [t for t in CORE_TAGS if reel or t != '#travelreels']
    extra = [f'#{city_tag(o)}' for o in origins] + [f'#{city_tag(d)}' for d in destinations] + \
            [VISIT[c] for c in countries if c in VISIT]
    for t in extra:
        if t not in tags:
            tags.append(t)
    return ' '.join(tags[:limit])


def hashtags(origin='Tirana', country='Albania', deals=None):
    deals = deals or []
    dests = [d['city'] for d in deals]
    ctry = [country] + [d.get('country', '') for d in deals]
    return tag_set([origin], dests, list(dict.fromkeys(ctry)))


HASHTAGS = hashtags()


def short_note(d):
    n = d.get('note') or ''
    if 'visa' in n:
        return 'visa needed' if 'UK' not in n else 'UK visa needed'
    if 'Lands at' in n:
        return 'lands at ' + n.split('Lands at ')[1].split(',')[0]
    if 'Back from' in n:
        return 'back from ' + n.split('Back from ')[1].split(',')[0].rstrip('.')
    if 'Out to' in n:
        return n.replace('ℹ️ ', '').rstrip('.').lower()
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
    cheapest = min(int(d['price']) for d in deals) if deals else 0
    nwk = sum(1 for d in deals if getaway_bits(d)[2])
    head = f"🧳 {len(deals)} short getaways from {flag_emoji(ocountry)}{origin}, return flights from €{cheapest}. Swipe through 👉"
    lines = [head]
    if nwk:
        lines.append(f"🎉 {nwk} of them are weekend trips")
    lines.append('')
    for i, d in enumerate(deals):
        dep = rp.parse(d['departs'])
        ret = rp.parse(d.get('returns'))
        nights, days, wk = getaway_bits(d)
        if ret:
            when = f"{dep:%a %-d %b} to {ret:%a %-d %b}" if dep.month != ret.month else f"{dep:%a %-d} to {ret:%a %-d %b}"
            info = f"€{int(d['price'])} return · {when} · {nights} nights" + (' · weekend' if wk else '')
        else:
            info = f"€{int(d['price'])} one way · {dep:%a %-d %b}"
        extra = short_note(d)
        line = f"{KEYCAPS[i] if i < 10 else str(i + 1) + '.'} {flag_emoji(d.get('country', ''))}{d['city']} {info}"
        if extra:
            line += f" ({extra})"
        lines.append(line)
    lines += ['', '✈️ Prices are for both flights, direct, with a small personal bag.',
              f'Prices change fast, so grab them while they last. All {origin} booking links in bio 🔗',
              'Save this for your next weekend 📌', '', hashtags(origin, ocountry, deals)]
    return '\n'.join(lines)


def reel_caption(deals, total=None, cities=None):
    """Caption for the daily reel: one line per getaway shown, then hashtags for every departure city."""
    origins = []
    for d in deals:
        if d.get('origin') not in [o[0] for o in origins]:
            origins.append((d.get('origin'), d.get('origin_country')))
    multi = len(origins) > 1
    cheapest = min(int(d['price']) for d in deals)
    if multi:
        head = f"🧳 Short getaways from {len(origins)} cities, return flights from €{cheapest}!"
    else:
        head = f"🧳 Short getaways from {flag_emoji(origins[0][1])}{origins[0][0]}, return flights from €{cheapest}!"
    lines = [head, '']
    for d in deals:
        dep = rp.parse(d['departs'])
        ret = rp.parse(d.get('returns'))
        nights, days, wk = getaway_bits(d)
        when = (f"{dep:%a %-d %b} to {ret:%a %-d %b}" + (' 🎉' if wk else '')) if ret else f"{dep:%a %-d %b}"
        extra = ' (from Beauvais)' if d.get('origin_code') == 'BVA' else ''
        lines.append(f"{flag_emoji(d.get('origin_country', ''))}{d.get('origin')} ⇄ {flag_emoji(d.get('country', ''))}{d['city']} €{int(d['price'])} · {when}{extra}")
    lines += ['', 'Direct flights both ways, small personal bag included. Prices change fast!']
    if total:
        lines.append(f"{total} getaways today" + (", pick your city at the link in bio 🔗" if multi else ", all booking links in bio 🔗"))
    else:
        lines.append('All booking links in bio 🔗')
    lines += ['Follow @cheapflights.daily for new getaways every morning ☀️', '']
    countries = list(dict.fromkeys([d.get('country', '') for d in deals]))
    lines.append(tag_set([o for o, c in origins], [d['city'] for d in deals], countries, reel=True, limit=30))
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
            when = (f"{dep:%a %-d %b} → {ret:%a %-d %b}") if ret else f"{dep:%a %-d %b}, {dep:%H:%M}"
            note = (d.get('note') or '').replace('ℹ️ ', '').replace('⚠️ ', '')
            nights, days, wk = getaway_bits(d)
            items.append({'nights': nights, 'weekend': wk,
                          'city': d['city'], 'country': d.get('country', ''), 'flag': flag_uri(d.get('country', '')),
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
    import datetime as _dt
    page = {'updated': today_label, 'origins': origins, 'cap': PRICE_CAP, 'stamp': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bio_template.html')).read()
    open(out_path, 'w').write(tpl.replace('__DATA__', json.dumps(page).replace('</', '<\\/')))
    # same data as a JSON file: uploaded to Cloudinary each morning, the live site reads it
    json.dump(page, open(os.path.join(os.path.dirname(out_path) or '.', 'latest.json'), 'w'), ensure_ascii=False)


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
    print('site built with', [g[0]['origin'] for g in groups if g], '+ latest.json')


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