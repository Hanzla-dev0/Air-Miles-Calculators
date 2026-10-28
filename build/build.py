#!/usr/bin/env python3
"""Static site generator for Air Miles Calculators.

Run:  python3 build/build.py
Output: ./site  (upload this folder to any static host)
"""
import html
import json
import math
import os
import re
import shutil

from airports_data import AIRPORTS, ROUTES

# ----------------------------------------------------------------- config
BASE = "https://airmilescalculators.com"
SITE = "Air Miles Calculators"
MAIN_KW = "Air Miles Calculator"
CONTACT_EMAIL = "contact@airmilescalculators.com"
TODAY = "2026-10-27"
YEAR = "2026"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "site")

R_MILES = 3958.8
KM_PER_MILE = 1.609344
NM_PER_MILE = 0.868976
EARTH_CIRC_MI = 24901.0

esc = html.escape

# ----------------------------------------------------------------- data
AP = {a[0]: a for a in AIRPORTS}
assert len(AP) == len(AIRPORTS), "duplicate IATA codes"


def city(c):
    return AP[c][2]


def mi_between(a, b):
    A, B = AP[a], AP[b]
    p1, p2 = math.radians(A[4]), math.radians(B[4])
    dp = p2 - p1
    dl = math.radians(B[5] - A[5])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_MILES * math.asin(min(1, math.sqrt(h)))


def bearing(a, b):
    A, B = AP[a], AP[b]
    p1, p2 = math.radians(A[4]), math.radians(B[4])
    dl = math.radians(B[5] - A[5])
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def compass(deg):
    names = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
    return names[int((deg + 22.5) // 45) % 8]


def midpoint(a, b):
    A, B = AP[a], AP[b]
    p1, l1 = math.radians(A[4]), math.radians(A[5])
    p2, l2 = math.radians(B[4]), math.radians(B[5])
    bx = math.cos(p2) * math.cos(l2 - l1)
    by = math.cos(p2) * math.sin(l2 - l1)
    pm = math.atan2(math.sin(p1) + math.sin(p2), math.sqrt((math.cos(p1) + bx) ** 2 + by ** 2))
    lm = l1 + math.atan2(by, math.cos(p1) + bx)
    lm = (math.degrees(lm) + 540) % 360 - 180
    return math.degrees(pm), lm


def coords(lat, lon):
    return "%.2f° %s, %.2f° %s" % (abs(lat), "N" if lat >= 0 else "S", abs(lon), "E" if lon >= 0 else "W")


def n(x):
    return "{:,}".format(int(round(x)))


def ftime(mi, speed=500.0):
    hours = mi / speed + 0.5
    h = int(hours)
    m = int(round((hours - h) * 60))
    if m == 60:
        h, m = h + 1, 0
    return "%d h %02d min" % (h, m)


def haul(mi):
    if mi < 1000:
        return "short-haul"
    if mi < 3000:
        return "medium-haul"
    if mi < 5500:
        return "long-haul"
    return "ultra-long-haul"


def slug(a, b):
    return "%s-to-%s" % (a.lower(), b.lower())


# canonical routes (one page per airport pair, regardless of direction)
CANON = []
_seen = set()
for a, b in ROUTES:
    assert a in AP and b in AP, (a, b)
    if a == b or frozenset((a, b)) in _seen:
        continue
    _seen.add(frozenset((a, b)))
    CANON.append((a, b))
ROUTE_SLUG = {}
for a, b in CANON:
    ROUTE_SLUG["%s-%s" % (a.lower(), b.lower())] = slug(a, b)
    ROUTE_SLUG["%s-%s" % (b.lower(), a.lower())] = slug(a, b)


def route_url(a, b):
    k = "%s-%s" % (a.lower(), b.lower())
    return "/distance/%s/" % ROUTE_SLUG[k] if k in ROUTE_SLUG else None


# ----------------------------------------------------------------- html helpers
LOGO = (
    '<svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="15" fill="#1d7fd6"/>'
    '<path d="M6 19.5l8.2-2.1 5.6-8.4c.5-.7 1.5-.9 2.1-.4.5.4.6 1 .3 1.6l-2.6 7 5.3-1.4c.8-.2 1.5.3 1.7 1 .2.8-.3 1.5-1.1 1.7l-7.6 2-5.8 5.3c-.6.5-1.5.5-2-.1-.4-.5-.4-1.2 0-1.7l3.4-4.1-5.3 1.4c-.8.2-1.6-.2-1.8-1-.1-.7.3-1.4 1.1-1.6z" fill="#fff"/></svg>'
)

NAV = [
    ("/", "Air Miles Calculator"),
    ("/distance/", "Popular Routes"),
    ("/airports/", "Airports"),
    ("/air-miles-calculator-guide/", "Guide"),
]


def jsonld(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return '<script type="application/ld+json">%s</script>' % s.replace("</", "<\\/")


def faq_ld(faqs):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs
        ],
    }


def crumbs_ld(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": BASE + path}
            for i, (name, path) in enumerate(items)
        ],
    }


def crumbs_html(items):
    parts = []
    for i, (name, path) in enumerate(items):
        if i == len(items) - 1:
            parts.append("<span aria-current=\"page\" style=\"margin:0;opacity:1\">%s</span>" % esc(name))
        else:
            parts.append('<a href="%s">%s</a>' % (path, esc(name)))
    return '<nav class="crumbs" aria-label="Breadcrumb">%s</nav>' % "<span>›</span>".join(parts)


def faq_html(faqs):
    return "".join("<details><summary>%s</summary><p>%s</p></details>" % (esc(q), esc(a)) for q, a in faqs)


def calc_html(frm=None, to=None):
    attrs = ""
    if frm:
        attrs += ' data-from="%s"' % frm
    if to:
        attrs += ' data-to="%s"' % to
    return f"""
<div class="calc" id="calculator">
  <form id="calc-form" novalidate{attrs} aria-label="{MAIN_KW}">
    <div class="field">
      <label for="from">From airport</label>
      <input id="from" type="text" placeholder="City, airport or code (e.g. JFK)" autocomplete="off" role="combobox" aria-autocomplete="list" aria-controls="from-list" aria-expanded="false">
      <ul class="suggest" id="from-list" role="listbox" hidden></ul>
    </div>
    <button class="btn swap" id="swap" type="button" aria-label="Swap airports" title="Swap airports">⇄</button>
    <div class="field">
      <label for="to">To airport</label>
      <input id="to" type="text" placeholder="City, airport or code (e.g. LHR)" autocomplete="off" role="combobox" aria-autocomplete="list" aria-controls="to-list" aria-expanded="false">
      <ul class="suggest" id="to-list" role="listbox" hidden></ul>
    </div>
    <button class="btn" type="submit">Calculate air miles</button>
  </form>
  <p class="error" id="calc-error" role="alert"></p>
  <div class="result" id="result" hidden aria-live="polite"></div>
</div>"""


def head(title, desc, path, og_type="website", noindex=False, ld=None):
    url = BASE + path
    robots = "noindex, follow" if noindex else "index, follow, max-image-preview:large, max-snippet:-1"
    canon = "" if noindex else '<link rel="canonical" href="%s">' % url
    alt = "" if noindex else '<link rel="alternate" hreflang="en" href="%s"><link rel="alternate" hreflang="x-default" href="%s">' % (url, url)
    scripts = "".join(jsonld(x) for x in (ld or []))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="{robots}">
{canon}
{alt}
<meta name="google-site-verification" content="wTdP7klXRDBCEFBE2lMC_E0DGJUUiSU244CxhgpC8oE">
<meta name="theme-color" content="#0b2545">
<meta property="og:site_name" content="{SITE}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}/assets/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{BASE}/assets/og-image.png">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/style.css">
{scripts}
</head>"""


def header_html():
    links = "".join('<a href="%s">%s</a>' % (p, esc(t)) for p, t in NAV)
    return f"""<header class="site-header"><div class="wrap">
<a class="brand" href="/" aria-label="{SITE} home">{LOGO}<span>{SITE}</span></a>
<nav class="nav" aria-label="Main">{links}</nav>
</div></header>"""


def footer_html():
    pop = "".join(
        '<li><a href="/distance/%s/">%s to %s distance</a></li>' % (slug(a, b), esc(city(a)), esc(city(b)))
        for a, b in CANON[:6]
    )
    return f"""<footer class="site-footer"><div class="wrap">
<div class="foot-grid">
<div><h4>{SITE}</h4><p>A free {MAIN_KW.lower()} for measuring the distance between airports in air miles, kilometres and nautical miles, with estimated flight times.</p></div>
<div><h4>Explore</h4><ul>
<li><a href="/">{MAIN_KW}</a></li><li><a href="/distance/">Popular routes</a></li><li><a href="/airports/">Airports</a></li><li><a href="/air-miles-calculator-guide/">How air miles are calculated</a></li>
</ul></div>
<div><h4>Popular routes</h4><ul>{pop}</ul></div>
</div>
<div class="copy">© {YEAR} {SITE}. <a href="/about/">About</a> · <a href="/contact/">Contact</a> · <a href="/privacy-policy/">Privacy Policy</a> · <a href="/terms/">Terms</a> · Distances are great-circle estimates for information only and must not be used for navigation.</div>
</div></footer>"""


AIRPORT_JS = None


def page(path, head_html, hero, body, with_calc=None, scripts=True):
    """with_calc: None (no calculator) or (from, to) tuple."""
    calc = calc_html(*with_calc) if with_calc is not None else ""
    js = '<script src="/assets/airports.js" defer></script><script src="/assets/app.js" defer></script>' if with_calc is not None else ""
    doc = f"""{head_html}
<body>
<a href="#main" style="position:absolute;left:-999px" onfocus="this.style.left='8px'">Skip to content</a>
{header_html()}
<div class="hero"><div class="wrap">{hero}</div></div>
<main id="main"><div class="wrap">
{calc}
{body}
</div></main>
{footer_html()}
{js}
</body>
</html>
"""
    write(path, doc)


PAGES = []  # (path, priority, changefreq)


def relativize(path, content):
    """Turn root-relative href/src into relative URLs so the site also works
    when opened from a sub-folder (VS Code Live Server, GitHub Pages project sites)."""
    if path == "/404.html":
        return content  # 404 is served from any depth, keep absolute
    segs = [x for x in path.split("/") if x]
    depth = len(segs) if path.endswith("/") else len(segs) - 1
    prefix = "../" * depth

    def fix(m):
        attr, url = m.group(1), m.group(2)
        out = prefix + url[1:]
        return '%s="%s"' % (attr, out or "./")

    return re.sub(r'\b(href|src)="(/(?!/)[^"]*)"', fix, content)


def write(path, content):
    if path.endswith(".html") or path.endswith("/"):
        content = relativize(path, content)
    if path.endswith("/"):
        fp = os.path.join(OUT, path.strip("/"), "index.html")
    else:
        fp = os.path.join(OUT, path.lstrip("/"))
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)


def register(path, prio="0.6", freq="monthly"):
    PAGES.append((path, prio, freq))


def check_len(label, title, desc):
    if len(title) > 65:
        print("WARN title >65 (%d): %s" % (len(title), label))
    if len(desc) > 160:
        print("WARN description >160 (%d): %s" % (len(desc), label))


ORG_LD = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": SITE,
    "url": BASE + "/",
    "logo": BASE + "/favicon.svg",
}

# ----------------------------------------------------------------- HOME
def build_home():
    path = "/"
    title = "Air Miles Calculator – Distance Between Airports"
    desc = "Free air miles calculator: find the distance between any two airports in air miles, km and nautical miles, plus flight time. Fast, accurate, no sign-up."
    check_len("home", title, desc)
    n_air = len(AIRPORTS)
    faqs = [
        ("What is an air miles calculator?",
         "An air miles calculator measures the shortest distance between two airports along the surface of the Earth (the great-circle distance) and shows it in miles, kilometres and nautical miles. Pick a departure and arrival airport and the result appears instantly."),
        ("How do you calculate air miles between two airports?",
         "Each airport has a latitude and longitude. The calculator applies the haversine formula to those coordinates, which accounts for the curvature of the Earth, and multiplies the result by the Earth's radius of 3,958.8 miles."),
        ("Is this the same as the Air Miles loyalty programme?",
         "No. This tool measures distance between airports. Frequent-flyer and loyalty schemes award points using their own rules, which may depend on the fare class, the airline, the partner and the status of the traveller rather than on distance alone."),
        ("What is the difference between air miles, statute miles and nautical miles?",
         "On this site air miles are shown as statute miles of great-circle distance, where one mile equals 1.609 kilometres. A nautical mile is longer than a statute mile in the other direction: one statute mile is about 0.869 nautical miles. Aviation navigation uses nautical miles, while many travellers and loyalty schemes use statute miles."),
        ("How is the estimated flight time worked out?",
         "Flight time is estimated as the distance divided by an average speed of 500 mph, plus 30 minutes for taxi, take-off, climb and landing. Real schedules vary with the aircraft, winds, air-traffic routing and airline timetable."),
        ("Why is the distance flown longer than the calculator result?",
         "Aircraft follow airways, avoid restricted airspace and weather, and adjust for wind, so the route actually flown is usually a little longer than the straight great-circle line between the airports."),
        ("Which airports does the calculator cover?",
         "It currently covers %d major international airports across North America, South America, Europe, the Middle East, Africa, Asia and Oceania, searchable by city, airport name, country or IATA code." % n_air),
    ]
    ld = [
        ORG_LD,
        {"@context": "https://schema.org", "@type": "WebSite", "name": SITE, "url": BASE + "/", "inLanguage": "en"},
        {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": MAIN_KW,
            "url": BASE + "/",
            "applicationCategory": "UtilitiesApplication",
            "operatingSystem": "Any (web browser)",
            "description": desc,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        },
        faq_ld(faqs),
    ]
    hero = (
        "<h1>Air Miles Calculator</h1>"
        '<p class="lead">Calculate the distance between any two airports in air miles, kilometres and nautical miles, with an estimated flight time. Free, instant and no sign-up.</p>'
    )
    chips = "".join(
        '<li><a href="/distance/%s/">%s to %s</a></li>' % (slug(a, b), esc(city(a)), esc(city(b))) for a, b in CANON[:24]
    )
    hubs = ["LHR", "JFK", "DXB", "SIN", "HKG", "LAX", "CDG", "FRA", "DEL", "SYD", "IST", "NRT"]
    apchips = "".join('<li><a href="/airport/%s/">%s – %s</a></li>' % (c.lower(), c, esc(city(c))) for c in hubs)
    body = f"""
<section class="block prose">
<h2>Free air miles calculator for any flight</h2>
<p>This air miles calculator tells you how far apart two airports are. Type a city, an airport name or a three-letter IATA code such as JFK or LHR, choose your departure and arrival airports, and press <strong>Calculate air miles</strong>. You get the distance in air miles (statute miles), kilometres and nautical miles, along with an estimated flight time.</p>
<p>Use it to plan a trip, compare itineraries, check how many miles a journey covers, estimate the miles you may earn on a frequent-flyer scheme, or settle a geography argument. Every result is a great-circle distance, which is the shortest possible path between two points on the globe.</p>
</section>

<section class="block">
<h2>How to use the air miles calculator</h2>
<div class="cols">
<div class="card"><h3>1. Choose your airports</h3><p>Start typing in the <em>From</em> and <em>To</em> boxes. Suggestions appear as you type and match city names, airport names, countries and IATA codes.</p></div>
<div class="card"><h3>2. Calculate</h3><p>Press the button. The calculator reads the latitude and longitude of both airports and applies the haversine formula to work out the great-circle distance.</p></div>
<div class="card"><h3>3. Read the result</h3><p>See the distance in air miles, kilometres and nautical miles, plus an estimated flight time. Open the route page for more detail.</p></div>
</div>
</section>

<section class="block prose">
<h2>What are air miles?</h2>
<p>In everyday use, “air miles” means the distance between two places measured through the air, as the crow flies. It is the great-circle distance, not the length of any road, rail or sea route. Because the Earth is a sphere, the shortest path between two airports is an arc, which is why flights from North America to Europe often curve north on a flat map.</p>
<p>The phrase is also used for loyalty points earned by flying. Those schemes have their own rules. This air miles calculator measures only the distance, which is a useful starting point when you want to estimate what a trip might earn.</p>
</section>

<section class="block">
<h2>Distance units explained</h2>
<table>
<thead><tr><th>Unit</th><th>Equivalent</th><th>Typically used for</th></tr></thead>
<tbody>
<tr><td>1 air mile (statute mile)</td><td>1.609 km · 0.869 nautical miles</td><td>Travel planning, loyalty schemes in the US and UK</td></tr>
<tr><td>1 kilometre</td><td>0.621 miles · 0.540 nautical miles</td><td>Most countries outside the US and UK</td></tr>
<tr><td>1 nautical mile</td><td>1.852 km · 1.151 miles</td><td>Aviation and maritime navigation</td></tr>
</tbody>
</table>
</section>

<section class="block">
<h2>Popular air miles routes</h2>
<p>Jump straight to the distance, flight time and route details for some of the most searched city pairs.</p>
<ul class="chips">{chips}</ul>
<p style="margin-top:14px"><a href="/distance/">See all popular routes →</a></p>
</section>

<section class="block">
<h2>Major airports</h2>
<ul class="chips">{apchips}</ul>
<p style="margin-top:14px"><a href="/airports/">Browse all airports →</a></p>
</section>

<section class="block prose">
<h2>Air miles calculator FAQ</h2>
{faq_html(faqs)}
<p>Want the maths? Read <a href="/air-miles-calculator-guide/">how air miles are calculated</a>.</p>
</section>
"""
    page(path, head(title, desc, path, ld=ld), hero, body, with_calc=(None, None))
    register(path, "1.0", "weekly")


# ----------------------------------------------------------------- ROUTES
def build_routes():
    for a, b in CANON:
        path = "/distance/%s/" % slug(a, b)
        ca, cb = city(a), city(b)
        mi = mi_between(a, b)
        km, nm = mi * KM_PER_MILE, mi * NM_PER_MILE
        t = ftime(mi)
        brg = bearing(a, b)
        mlat, mlon = midpoint(a, b)
        pct = mi / EARTH_CIRC_MI * 100
        title = "%s to %s Distance – Air Miles (%s to %s)" % (ca, cb, a, b)
        desc = ("%s (%s) to %s (%s): %s air miles (%s km), about %s flying time. Free air miles calculator for any route."
                % (ca, a, cb, b, n(mi), n(km), t))
        check_len(path, title, desc)
        faqs = [
            ("How far is it from %s to %s in air miles?" % (ca, cb),
             "The great-circle distance between %s (%s) and %s (%s) is %s air miles, which is %s kilometres or %s nautical miles."
             % (AP[a][1], a, AP[b][1], b, n(mi), n(km), n(nm))),
            ("How long is the flight from %s to %s?" % (ca, cb),
             "At an average cruise speed of 500 mph plus 30 minutes for take-off and landing, the estimated flight time is %s. Real flight times vary with the aircraft, winds and routing." % t),
            ("Is the distance the same in both directions?",
             "Yes. The distance from %s to %s is the same as from %s to %s: %s air miles. Flight time can differ because of prevailing winds and jet streams."
             % (a, b, b, a, n(mi))),
        ]
        ld = [
            crumbs_ld([("Home", "/"), ("Popular routes", "/distance/"), ("%s to %s" % (ca, cb), path)]),
            faq_ld(faqs),
            {"@context": "https://schema.org", "@type": "WebPage", "name": title, "url": BASE + path, "description": desc,
             "dateModified": TODAY, "isPartOf": {"@type": "WebSite", "name": SITE, "url": BASE + "/"}},
        ]
        hero = crumbs_html([("Home", "/"), ("Popular routes", "/distance/"), ("%s to %s" % (ca, cb), path)]) + (
            "<h1>%s (%s) to %s (%s) Distance</h1>" % (esc(ca), a, esc(cb), b)
            + '<p class="lead">%s air miles · %s km · %s nautical miles · about %s in the air.</p>' % (n(mi), n(km), n(nm), t)
        )
        # related
        from_a = [(x, y) for x, y in CANON if (x == a or y == a) and (x, y) != (a, b)][:8]
        to_b = [(x, y) for x, y in CANON if (x == b or y == b) and (x, y) != (a, b) and (x, y) not in from_a][:8]

        def chip(x, y):
            return '<li><a href="/distance/%s/">%s to %s</a></li>' % (slug(x, y), esc(city(x)), esc(city(y)))

        rel_a = "".join(chip(x, y) for x, y in from_a)
        rel_b = "".join(chip(x, y) for x, y in to_b)
        speed_rows = "".join(
            "<tr><td>%d mph (%s)</td><td>%s</td></tr>" % (s, lab, ftime(mi, s))
            for s, lab in ((450, "regional / slower"), (500, "typical airliner"), (550, "fast jet / tailwind"))
        )
        body = f"""
<section class="block">
<h2>{esc(ca)} to {esc(cb)} air miles at a glance</h2>
<div class="stat-grid">
<div class="stat"><span class="num">{n(mi)}</span><span class="unit">air miles</span></div>
<div class="stat"><span class="num">{n(km)}</span><span class="unit">kilometres</span></div>
<div class="stat"><span class="num">{n(nm)}</span><span class="unit">nautical miles</span></div>
<div class="stat"><span class="num">{t}</span><span class="unit">est. flight time</span></div>
</div>
<p class="note">Great-circle distance between {esc(AP[a][1])} ({a}) and {esc(AP[b][1])} ({b}).</p>
</section>

<section class="block prose">
<h2>About the {a} to {b} route</h2>
<p>The distance from {esc(ca)} to {esc(cb)} is {n(mi)} air miles ({n(km)} km), which makes this a {haul(mi)} journey. The route covers about {pct:.1f}% of the Earth's circumference at the equator.</p>
<p>Flying from {esc(AP[a][1])} in {esc(AP[a][3])}, the shortest path heads {compass(brg)} (an initial bearing of {brg:.0f}°) towards {esc(AP[b][1])} in {esc(AP[b][3])}. The midpoint of the great-circle route is near {coords(mlat, mlon)}.</p>
<p>This page is powered by our air miles calculator. Change either airport in the calculator above to measure a different journey.</p>
</section>

<section class="block prose">
<h2>Estimated flight time by speed</h2>
<table><thead><tr><th>Average speed</th><th>Flight time ({a} to {b})</th></tr></thead><tbody>{speed_rows}</tbody></table>
<p class="note">Includes 30 minutes for taxi, take-off and landing. Actual times depend on the aircraft, winds and routing.</p>
</section>

<section class="block prose">
<h2>{esc(ca)} to {esc(cb)} FAQ</h2>
{faq_html(faqs)}
</section>

<section class="block">
<h2>Related air miles routes</h2>
{('<h3>More routes involving ' + esc(ca) + '</h3><ul class="chips">' + rel_a + '</ul>') if rel_a else ''}
{('<h3>More routes involving ' + esc(cb) + '</h3><ul class="chips">' + rel_b + '</ul>') if rel_b else ''}
<p style="margin-top:14px">Airports: <a href="/airport/{a.lower()}/">{esc(AP[a][1])} ({a})</a> · <a href="/airport/{b.lower()}/">{esc(AP[b][1])} ({b})</a> · <a href="/">Back to the air miles calculator</a></p>
</section>
"""
        page(path, head(title, desc, path, ld=ld), hero, body, with_calc=(a, b))
        register(path, "0.7", "monthly")


def build_routes_index():
    path = "/distance/"
    title = "Popular Air Miles Routes – Flight Distances by City"
    desc = "Browse air miles, kilometres and flight times for popular airport pairs worldwide. Pick a route or use the air miles calculator for any journey."
    check_len(path, title, desc)
    rows = ""
    for a, b in sorted(CANON, key=lambda p: (city(p[0]), city(p[1]))):
        mi = mi_between(a, b)
        rows += '<tr><td><a href="/distance/%s/">%s (%s) to %s (%s)</a></td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            slug(a, b), esc(city(a)), a, esc(city(b)), b, n(mi), n(mi * KM_PER_MILE), ftime(mi))
    ld = [crumbs_ld([("Home", "/"), ("Popular routes", path)])]
    hero = crumbs_html([("Home", "/"), ("Popular routes", path)]) + "<h1>Popular Air Miles Routes</h1>" + \
        '<p class="lead">Distance, air miles and estimated flight time for %d popular airport pairs.</p>' % len(CANON)
    body = f"""
<section class="block">
<h2>Flight distances between popular cities</h2>
<p>Select a route for full details, or use the <a href="/">air miles calculator</a> for any other airport pair.</p>
<div style="overflow-x:auto"><table>
<thead><tr><th>Route</th><th>Air miles</th><th>Kilometres</th><th>Est. flight time</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</section>"""
    page(path, head(title, desc, path, ld=ld), hero, body)
    register(path, "0.8", "weekly")


# ----------------------------------------------------------------- AIRPORTS
HUBS = ["LHR", "JFK", "DXB", "SIN", "HKG", "LAX", "CDG", "FRA", "DEL", "SYD", "IST", "NRT"]


def build_airports():
    for code, name, cty, country, lat, lon in AIRPORTS:
        path = "/airport/%s/" % code.lower()
        title = "%s Airport – %s Air Miles & Distances" % (code, cty)
        desc = ("%s (%s) in %s, %s: location plus air miles, km and flight times to major airports."
                % (name, code, cty, country))
        if len(desc) > 158:
            desc = "%s airport in %s, %s: location plus air miles, km and flight times to major airports." % (code, cty, country)
        check_len(path, title, desc)
        hubs = [h for h in HUBS if h != code]
        rows = ""
        dists = []
        for h in hubs:
            mi = mi_between(code, h)
            dists.append((mi, h))
            u = route_url(code, h)
            label = "%s (%s)" % (esc(city(h)), h)
            cell = '<a href="%s">%s</a>' % (u, label) if u else label
            rows += "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (cell, n(mi), n(mi * KM_PER_MILE), ftime(mi))
        dists.sort()
        near, far = dists[0], dists[-1]
        faqs = [
            ("Where is %s?" % name,
             "%s (%s) serves %s, %s. Its coordinates are %s." % (name, code, cty, country, coords(lat, lon))),
            ("How far is %s from major hub airports?" % code,
             "Of the major hubs listed on this page, %s is closest to %s at %s air miles and %s is farthest at %s air miles."
             % (code, "%s (%s)" % (city(near[1]), near[1]), n(near[0]), "%s (%s)" % (city(far[1]), far[1]), n(far[0]))),
        ]
        ld = [
            crumbs_ld([("Home", "/"), ("Airports", "/airports/"), ("%s" % code, path)]),
            faq_ld(faqs),
            {"@context": "https://schema.org", "@type": "Airport", "name": name, "iataCode": code,
             "url": BASE + path,
             "geo": {"@type": "GeoCoordinates", "latitude": lat, "longitude": lon},
             "address": {"@type": "PostalAddress", "addressLocality": cty, "addressCountry": country}},
        ]
        hero = crumbs_html([("Home", "/"), ("Airports", "/airports/"), (code, path)]) + (
            "<h1>%s (%s)</h1>" % (esc(name), code)
            + '<p class="lead">%s, %s · %s</p>' % (esc(cty), esc(country), coords(lat, lon))
        )
        routes_here = [(x, y) for x, y in CANON if code in (x, y)]
        rchips = "".join(
            '<li><a href="/distance/%s/">%s to %s</a></li>' % (slug(x, y), esc(city(x)), esc(city(y))) for x, y in routes_here
        )
        body = f"""
<section class="block prose">
<h2>About {esc(name)}</h2>
<p>{esc(name)} has the IATA code <strong>{code}</strong> and serves {esc(cty)}, {esc(country)}. It sits at {coords(lat, lon)}. Use the air miles calculator above to measure the distance from {code} to any other airport; the departure airport is already filled in.</p>
</section>

<section class="block">
<h2>Air miles from {code} to major airports</h2>
<div style="overflow-x:auto"><table>
<thead><tr><th>Destination</th><th>Air miles</th><th>Kilometres</th><th>Est. flight time</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</section>
{('<section class="block"><h2>Popular routes involving ' + code + '</h2><ul class="chips">' + rchips + '</ul></section>') if rchips else ''}
<section class="block prose">
<h2>{code} airport FAQ</h2>
{faq_html(faqs)}
</section>"""
        page(path, head(title, desc, path, ld=ld), hero, body, with_calc=(code, None))
        register(path, "0.5", "monthly")


def build_airports_index():
    path = "/airports/"
    title = "Airport Codes & Locations – Air Miles Calculator"
    desc = "Browse %d major airports by country with IATA codes and locations, then measure the air miles between any two of them." % len(AIRPORTS)
    check_len(path, title, desc)
    groups = {}
    for a in AIRPORTS:
        groups.setdefault(a[3], []).append(a)
    sections = ""
    for country in sorted(groups):
        items = "".join(
            '<li><a href="/airport/%s/">%s – %s</a></li>' % (a[0].lower(), a[0], esc(a[2])) for a in sorted(groups[country], key=lambda z: z[2])
        )
        sections += "<h3>%s</h3><ul class=\"chips\">%s</ul>" % (esc(country), items)
    ld = [crumbs_ld([("Home", "/"), ("Airports", path)])]
    hero = crumbs_html([("Home", "/"), ("Airports", path)]) + "<h1>Airports and IATA Codes</h1>" + \
        '<p class="lead">%d major airports in %d countries and territories.</p>' % (len(AIRPORTS), len(groups))
    body = f'<section class="block"><h2>Browse airports by country</h2>{sections}</section>'
    page(path, head(title, desc, path, ld=ld), hero, body)
    register(path, "0.7", "weekly")


# ----------------------------------------------------------------- GUIDE
def build_guide():
    path = "/air-miles-calculator-guide/"
    title = "How Air Miles Are Calculated – Great-Circle Distance"
    desc = "Learn how an air miles calculator works: the haversine formula, great-circle distance, units, and why flown distance differs from the straight line."
    check_len(path, title, desc)
    a, b = "JFK", "LHR"
    mi = mi_between(a, b)
    faqs = [
        ("What formula does an air miles calculator use?",
         "Most use the haversine formula, which gives the great-circle distance between two points from their latitude and longitude on a sphere."),
        ("Is the great-circle distance exact?",
         "It is very close. The Earth is slightly flattened, so more complex ellipsoidal formulas can differ by up to roughly 0.5%, which is small for travel planning."),
        ("Do airlines use air miles to award frequent-flyer points?",
         "Some do, but many now award points by fare, cabin and spend. Always check the rules of your loyalty programme."),
    ]
    ld = [
        crumbs_ld([("Home", "/"), ("Guide", path)]),
        faq_ld(faqs),
        {"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc,
         "datePublished": TODAY, "dateModified": TODAY, "mainEntityOfPage": BASE + path,
         "author": {"@type": "Organization", "name": SITE}, "publisher": {"@type": "Organization", "name": SITE}},
    ]
    hero = crumbs_html([("Home", "/"), ("Guide", path)]) + "<h1>How Air Miles Are Calculated</h1>" + \
        '<p class="lead">The maths behind every air miles calculator, explained in plain English.</p>'
    body = f"""
<article class="block prose">
<h2>Great-circle distance</h2>
<p>An air miles calculator reports the shortest distance between two airports across the surface of the Earth. This is called the great-circle distance, because the shortest path lies along a circle whose centre is the centre of the Earth. On a flat map it looks curved; on a globe it is a straight line pulled tight.</p>

<h2>The haversine formula</h2>
<p>Given the latitude (φ) and longitude (λ) of two airports, the haversine formula is:</p>
<code class="f">a = sin²(Δφ / 2) + cos φ₁ · cos φ₂ · sin²(Δλ / 2)<br>c = 2 · atan2(√a, √(1 − a))<br>distance = R · c</code>
<p>Here R is the Earth's mean radius: 3,958.8 miles, 6,371 kilometres or 3,440 nautical miles, depending on the unit you want.</p>

<h2>Worked example: {a} to {b}</h2>
<p>{esc(AP[a][1])} sits at {coords(AP[a][4], AP[a][5])} and {esc(AP[b][1])} at {coords(AP[b][4], AP[b][5])}. Putting those coordinates through the formula gives {n(mi)} air miles ({n(mi * KM_PER_MILE)} km). You can check it on the <a href="/distance/{slug(a, b)}/">{city(a)} to {city(b)} distance page</a>.</p>

<h2>Why flights cover more than the air miles distance</h2>
<ul>
<li><strong>Airways and air-traffic control:</strong> aircraft follow published routes.</li>
<li><strong>Weather and winds:</strong> crews route around storms and towards favourable jet streams.</li>
<li><strong>Restricted airspace:</strong> some regions must be avoided.</li>
<li><strong>Safety rules:</strong> long over-water routes must keep suitable diversion airports within range.</li>
</ul>

<h2>Air miles, kilometres and nautical miles</h2>
<p>One statute mile is 1.609 km and about 0.869 nautical miles. Pilots and air-traffic controllers work in nautical miles, but travel sites and many loyalty schemes use statute miles, which is why this air miles calculator shows all three.</p>

<h2>Estimating flight time</h2>
<p>A simple rule of thumb divides the distance by 500 mph and adds half an hour for taxi, take-off and landing. It is a good planning estimate; the timetable of your airline is always the final word.</p>

<h2>Frequently asked questions</h2>
{faq_html(faqs)}
<p><a href="/">Try the air miles calculator →</a></p>
</article>"""
    page(path, head(title, desc, path, og_type="article", ld=ld), hero, body)
    register(path, "0.7", "monthly")


# ----------------------------------------------------------------- STATIC PAGES
def simple(path, title, desc, h1, lead, body, prio="0.3", index=True):
    check_len(path, title, desc)
    ld = [crumbs_ld([("Home", "/"), (h1, path)])]
    hero = crumbs_html([("Home", "/"), (h1, path)]) + "<h1>%s</h1>" % esc(h1) + '<p class="lead">%s</p>' % esc(lead)
    page(path, head(title, desc, path, ld=ld, noindex=not index), hero, '<section class="block prose">%s</section>' % body)
    if index:
        register(path, prio, "yearly")


def build_static():
    simple(
        "/about/", "About Air Miles Calculators",
        "About Air Miles Calculators, a free air miles calculator that measures flight distances between airports in miles, kilometres and nautical miles.",
        "About Air Miles Calculators", "A fast, free way to measure the distance between airports.",
        f"""<h2>What we do</h2>
<p>{SITE} provides a simple {MAIN_KW.lower()}. Choose two airports and see the great-circle distance in air miles, kilometres and nautical miles, with an estimated flight time. There are no accounts, no sign-up and no fees.</p>
<h2>How the numbers are produced</h2>
<p>Distances come from the haversine formula applied to airport coordinates. Read the full explanation in our <a href="/air-miles-calculator-guide/">guide to how air miles are calculated</a>.</p>
<h2>Accuracy</h2>
<p>Results are great-circle estimates for planning and information. Real flights follow airways and weather, so the distance flown is usually slightly longer. We cannot guarantee that airport data is free from error; if you spot one, <a href="/contact/">let us know</a>.</p>""",
        "0.4")
    simple(
        "/contact/", "Contact Air Miles Calculators",
        "Contact Air Miles Calculators with feedback, corrections to airport data, or questions about the air miles calculator.",
        "Contact Us", "Feedback, corrections and questions are welcome.",
        f"""<h2>Get in touch</h2>
<p>Email us at <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. We read every message about the {MAIN_KW.lower()}, including requests to add an airport and reports of incorrect coordinates.</p>""",
        "0.3")
    simple(
        "/privacy-policy/", "Privacy Policy – Air Miles Calculators",
        "How Air Miles Calculators handles data: no accounts, no personal information collected by the calculator itself.",
        "Privacy Policy", f"Last updated {TODAY}.",
        f"""<h2>Information we collect</h2>
<p>The {MAIN_KW.lower()} runs in your browser. The airports you search for are not sent to our server or stored. We do not ask you to create an account.</p>
<h2>Server logs, cookies and third parties</h2>
<p>Our hosting provider may keep standard server logs, such as IP address, browser and pages requested, for security and performance. If we add analytics or advertising in future, this policy will be updated to name the providers and explain any cookies they set.</p>
<h2>Contact</h2>
<p>Questions about this policy: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>""",
        "0.2")
    simple(
        "/terms/", "Terms of Use – Air Miles Calculators",
        "Terms of use for the Air Miles Calculators website, including accuracy and navigation disclaimers.",
        "Terms of Use", f"Last updated {TODAY}.",
        f"""<h2>Use of this site</h2>
<p>{SITE} is provided free of charge for general information. You may use the calculator for personal or commercial planning.</p>
<h2>No navigation or booking use</h2>
<p>Distances and flight times are estimates. Do not rely on them for flight planning, navigation, safety-critical decisions or to calculate loyalty-programme entitlements. Always confirm with your airline or booking provider.</p>
<h2>No warranty</h2>
<p>The site is provided “as is” without warranties of any kind, and we are not liable for losses arising from its use.</p>""",
        "0.2")

    # 404 (noindex)
    hero = "<h1>Page not found</h1><p class=\"lead\">That page does not exist. Try the air miles calculator instead.</p>"
    body = '<section class="block prose"><p><a href="/">Go to the air miles calculator →</a> · <a href="/distance/">Popular routes</a> · <a href="/airports/">Airports</a></p></section>'
    page("/404.html", head("Page not found – " + SITE, "The page you requested could not be found.", "/404.html", noindex=True), hero, body)


# ----------------------------------------------------------------- assets & files
def build_assets():
    adir = os.path.join(OUT, "assets")
    os.makedirs(adir, exist_ok=True)
    for f in ("style.css", "app.js"):
        shutil.copy(os.path.join(HERE, "assets", f), os.path.join(adir, f))
    data = [[a[0], a[1], a[2], a[3], a[4], a[5]] for a in AIRPORTS]
    js = "window.AMC_AIRPORTS=%s;window.AMC_ROUTES=%s;" % (
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        json.dumps(ROUTE_SLUG, separators=(",", ":")),
    )
    with open(os.path.join(adir, "airports.js"), "w", encoding="utf-8") as f:
        f.write(js)

    with open(os.path.join(OUT, "favicon.svg"), "w", encoding="utf-8") as f:
        f.write(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="15" fill="#1d7fd6"/>'
            '<path d="M6 19.5l8.2-2.1 5.6-8.4c.5-.7 1.5-.9 2.1-.4.5.4.6 1 .3 1.6l-2.6 7 5.3-1.4c.8-.2 1.5.3 1.7 1 .2.8-.3 1.5-1.1 1.7l-7.6 2-5.8 5.3c-.6.5-1.5.5-2-.1-.4-.5-.4-1.2 0-1.7l3.4-4.1-5.3 1.4c-.8.2-1.6-.2-1.8-1-.1-.7.3-1.4 1.1-1.6z" fill="#fff"/></svg>'
        )

    # social image
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (1200, 630), (11, 37, 69))
        d = ImageDraw.Draw(img)
        for i in range(630):
            c = int(11 + (28 - 11) * i / 630), int(37 + (74 - 37) * i / 630), int(69 + (130 - 69) * i / 630)
            d.line([(0, i), (1200, i)], fill=c)
        try:
            big = ImageFont.truetype("DejaVuSans-Bold.ttf", 88)
            small = ImageFont.truetype("DejaVuSans.ttf", 38)
        except Exception:
            big = small = ImageFont.load_default()
        d.text((80, 200), "Air Miles Calculator", font=big, fill=(255, 255, 255))
        d.text((80, 330), "Distance between any two airports", font=small, fill=(207, 224, 245))
        d.text((80, 390), "Miles · Kilometres · Nautical miles · Flight time", font=small, fill=(242, 169, 0))
        d.text((80, 520), "airmilescalculators.com", font=small, fill=(207, 224, 245))
        img.save(os.path.join(adir, "og-image.png"), optimize=True)
    except Exception as e:  # PIL missing
        print("NOTE: og-image.png not generated (%s). Add a 1200x630 PNG at site/assets/og-image.png" % e)


def build_seo_files():
    urls = "".join(
        "<url><loc>%s%s</loc><lastmod>%s</lastmod><changefreq>%s</changefreq><priority>%s</priority></url>" % (BASE, p, TODAY, f, pr)
        for p, pr, f in PAGES
    )
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>\n' % urls)
    write("/robots.txt", "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % BASE)
    vercel = {
        "trailingSlash": True,
        "cleanUrls": False,
        "headers": [
            {"source": "/(.*)", "headers": [
                {"key": "X-Content-Type-Options", "value": "nosniff"},
                {"key": "X-Frame-Options", "value": "SAMEORIGIN"},
                {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
                {"key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()"},
                {"key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains; preload"},
            ]},
            {"source": "/assets/(.*)", "headers": [
                {"key": "Cache-Control", "value": "public, max-age=604800, stale-while-revalidate=86400"},
            ]},
            {"source": "/favicon.svg", "headers": [
                {"key": "Cache-Control", "value": "public, max-age=604800"},
            ]},
        ],
    }
    write("/vercel.json", json.dumps(vercel, indent=2) + "\n")
    write("/.htaccess", """# Apache hosting (ignored by Netlify / Cloudflare Pages / Vercel)
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
ErrorDocument 404 /404.html
DirectoryIndex index.html
DirectorySlash On

<IfModule mod_deflate.c>
AddOutputFilterByType DEFLATE text/html text/css application/javascript application/json image/svg+xml
</IfModule>
<IfModule mod_expires.c>
ExpiresActive On
ExpiresByType text/css "access plus 1 month"
ExpiresByType application/javascript "access plus 1 month"
ExpiresByType image/png "access plus 1 year"
ExpiresByType image/svg+xml "access plus 1 year"
</IfModule>
""")


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    build_home()
    build_routes()
    build_routes_index()
    build_airports()
    build_airports_index()
    build_guide()
    build_static()
    build_assets()
    build_seo_files()
    print("Built %d indexable pages into %s" % (len(PAGES), OUT))


if __name__ == "__main__":
    main()
