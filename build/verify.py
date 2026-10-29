import os, re, sys, json, collections
site = sys.argv[1]
pages = []
for d, _, fs in os.walk(site):
    for f in fs:
        if f.endswith(".html"):
            pages.append(os.path.join(d, f))
titles = collections.Counter(); descs = collections.Counter()
problems = []
def exists(url):
    p = url.split("#")[0].split("?")[0]
    if p.endswith("/"): p += "index.html"
    return os.path.exists(os.path.join(site, p.lstrip("/")))
for p in pages:
    s = open(p, encoding="utf-8").read()
    rel = os.path.relpath(p, site)
    t = re.search(r"<title>(.*?)</title>", s); dsc = re.search(r'<meta name="description" content="(.*?)">', s)
    if not t or not dsc: problems.append((rel, "missing title/desc")); continue
    titles[t.group(1)] += 1; descs[dsc.group(1)] += 1
    if len(re.findall(r"<h1[ >]", s)) != 1: problems.append((rel, "h1 count != 1"))
    if rel != "404.html" and '<link rel="canonical"' not in s: problems.append((rel, "no canonical"))
    for m in re.findall(r'(?:href|src)="(/[^"]*)"', s):
        if not exists(m): problems.append((rel, "broken link " + m))
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s):
        try: json.loads(m.replace("<\\/", "</"))
        except Exception as e: problems.append((rel, "bad json-ld " + str(e)))
for k, v in titles.items():
    if v > 1: problems.append(("dup title", k))
for k, v in descs.items():
    if v > 1: problems.append(("dup desc", k))
print("pages:", len(pages), "problems:", len(problems))
for x in problems[:30]: print(x)
sm = open(os.path.join(site, "sitemap.xml")).read()
locs = re.findall(r"<loc>https?://[^/]+(.*?)</loc>", sm)
print("sitemap urls:", len(locs), "missing files:", [l for l in locs if not exists(l)][:5])
