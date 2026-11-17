"""Builds static SEO pages (role, city, role+city) and sitemap.xml from docs/jobs.json."""
import json, os, re, html, shutil
from urllib.parse import quote
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://papaplayer01.github.io/jobearth/"
OUT = f"{ROOT}/docs/jobs"
NOW = datetime.now(timezone.utc)
MIN_ROLE, MIN_CITY, MIN_BOTH = 3, 5, 3  # skip thin pages, which search engines dislike
e = html.escape
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

CSS = """:root{--bg:#06242b;--card:#0d414b;--fg:#f3ead3;--mut:#a9c3bd;--acc:#8fd98b;--ink:#06242b;--ln:#ffffff22}
@media(prefers-color-scheme:light){:root{--bg:#f5f0e4;--card:#fff;--fg:#12302f;--mut:#52706a;--acc:#1c7a55;--ink:#fff;--ln:#12302f26}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif}
main{max-width:860px;margin:auto;padding:2rem 1.2rem 4rem}a{color:var(--acc)}h1{font-size:clamp(1.8rem,5vw,2.6rem);line-height:1.1;margin:.4rem 0}
.mut{color:var(--mut)}.btn{display:inline-block;background:var(--acc);color:var(--ink);font-weight:700;border-radius:999px;padding:.55rem 1.2rem;text-decoration:none}
ul.jobs{list-style:none;padding:0;display:grid;gap:.8rem}.jobs li{background:var(--card);border:1px solid var(--ln);border-radius:16px;padding:1rem 1.2rem}
.jobs h2{font-size:1.1rem;margin:0}.jobs h2 a{color:var(--fg);text-decoration:none}.jobs h2 a:hover{color:var(--acc)}
.t{display:inline-block;font-size:.8rem;border:1px solid var(--ln);border-radius:999px;padding:.05rem .6rem;margin:.3rem .3rem 0 0}
nav.rel{margin-top:2rem;display:flex;flex-wrap:wrap;gap:.5rem}nav.rel a{font-size:.9rem;border:1px solid var(--ln);border-radius:999px;padding:.2rem .8rem;text-decoration:none}"""


def page(slg, title, h1, desc, items, hashq, related):
    url = f"{SITE}jobs/{slg}.html"
    lis = "".join(
        f'<li><h2><a href="{e(j["url"], quote=True)}" rel="nofollow noopener" target="_blank">{e(j["title"])}</a></h2>'
        f'<div class="mut">{e(j["company"])} · {e(j["location_raw"] or j["city"])}</div>'
        f'<span class="t">{e(j["role"])}</span><span class="t">{e(j["city"])}</span>'
        + (f'<span class="t">{e(j["type"])}</span>' if j.get("type") else "")
        + (f'<span class="t">{e(j["salary"])}</span>' if j.get("salary") else "")
        + (f'<p class="mut">{e(j["description"][:200])}</p>' if j.get("description") else "") + "</li>"
        for j in items[:60])
    rel = "".join(f'<a href="{e(s)}.html">{e(t)}</a>' for s, t in related)
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} | JoBearth</title><meta name="description" content="{e(desc, quote=True)}"><link rel="canonical" href="{url}">
<meta property="og:title" content="{e(title, quote=True)}"><meta property="og:description" content="{e(desc, quote=True)}"><meta property="og:image" content="{SITE}og.png"><meta property="og:url" content="{url}">
<style>{CSS}</style></head><body><main><a href="../">← JoBearth</a><h1>{e(h1)}</h1>
<p class="mut">{len(items)} open post{'s' if len(items) != 1 else ''}, updated {NOW.strftime('%d %b %Y')}. Always check the original post before applying.</p>
<p><a class="btn" href="../#{hashq}">Open interactive search</a></p><ul class="jobs">{lis}</ul>
<nav class="rel" aria-label="More pages"><a href="index.html">All pages</a>{rel}</nav></main></body></html>"""
    open(f"{OUT}/{slg}.html", "w", encoding="utf-8").write(doc)
    return url


def main():
    jobs = json.load(open(f"{ROOT}/docs/jobs.json"))["jobs"]
    roles, cities, both = {}, {}, {}
    for j in jobs:
        r, c = j.get("role"), j.get("city")
        ok_r, ok_c = r and r != "Other", c and c != "Other"
        if ok_r: roles.setdefault(r, []).append(j)
        if ok_c: cities.setdefault(c, []).append(j)
        if ok_r and ok_c: both.setdefault((r, c), []).append(j)
    shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
    y = NOW.year; specs = []
    for r, it in roles.items():
        if len(it) >= MIN_ROLE:
            specs.append((f"{slug(r)}-jobs-for-freshers", f"{r} Jobs for Freshers in India ({y})", f"{r} jobs for freshers in India",
                          f"{len(it)} open {r} jobs and internships for freshers in India, collected from open job boards and refreshed daily.", it, f"role={quote(r)}"))
    for c, it in cities.items():
        if len(it) >= MIN_CITY:
            t = "Remote Fresher Jobs" if c == "Remote" else f"Fresher Jobs in {c}"
            specs.append((f"fresher-jobs-in-{slug(c)}", f"{t} ({y})", t,
                          f"{len(it)} open fresher jobs and internships{'' if c == 'Remote' else ' in ' + c}, refreshed daily.", it, f"city={quote(c)}"))
    for (r, c), it in both.items():
        if len(it) >= MIN_BOTH:
            where = "remote" if c == "Remote" else f"in {c}"
            specs.append((f"{slug(r)}-jobs-for-freshers-in-{slug(c)}", f"{r} Jobs for Freshers {where} ({y})", f"{r} jobs for freshers {where}",
                          f"{len(it)} open {r} jobs and internships for freshers {where}, refreshed daily.", it, f"role={quote(r)}&city={quote(c)}"))
    nav = [(s[0], s[2]) for s in specs]
    urls = [page(s[0], s[1], s[2], s[3], s[4], s[5], [x for x in nav if x[0] != s[0]][:14]) for s in specs]
    hub = "".join(f'<li><h2><a href="{e(s)}.html">{e(t)}</a></h2></li>' for s, t in nav) or "<li>Pages appear once enough posts are collected.</li>"
    open(f"{OUT}/index.html", "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fresher jobs in India by role and city | JoBearth</title><meta name="description" content="Browse fresher and internship jobs in India by role and city, refreshed daily."><link rel="canonical" href="{SITE}jobs/">
<style>{CSS}</style></head><body><main><a href="../">← JoBearth</a><h1>Fresher jobs in India by role and city</h1><ul class="jobs">{hub}</ul></main></body></html>""")
    today = NOW.strftime("%Y-%m-%d")
    sm = "".join(f"<url><loc>{e(u)}</loc><lastmod>{today}</lastmod></url>" for u in [SITE, SITE + "jobs/"] + urls)
    open(f"{ROOT}/docs/sitemap.xml", "w", encoding="utf-8").write(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>')
    print(f"Built {len(urls)} pages + hub + sitemap")


if __name__ == "__main__":
    main()
