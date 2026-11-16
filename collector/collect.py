"""JoBearth collector: gathers fresher/intern posts in India from sources that allow
programmatic access, dedupes, tags with Claude, writes docs/jobs.json."""
import json, os, re, hashlib, difflib, urllib.robotparser as rp
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT, CACHE = f"{ROOT}/docs/jobs.json", f"{ROOT}/collector/tag_cache.json"
UA = "JoBearthBot/1.0 (+https://github.com/Papaplayer01/jobearth)"
NOW = datetime.now(timezone.utc)
CITIES = ["Bengaluru", "Mumbai", "Pune", "Hyderabad", "Delhi NCR", "Chennai", "Kolkata",
          "Ahmedabad", "Nashik", "Remote", "Other"]
ROLES = ["Cloud", "DevOps", "Backend", "Frontend", "Full-stack", "QA & Automation",
         "Data", "ML & AI", "Mobile", "Support", "Other"]
INDIA = re.compile(r"india|bengal|bangal|mumbai|pune|hyderabad|delhi|gurgaon|gurugram|noida|"
                   r"chennai|kolkata|ahmedabad|nashik|jaipur|kochi|indore|remote", re.I)
FRESHER = re.compile(r"fresher|graduate|intern\b|internship|entry[- ]level|trainee|junior|"
                     r"\b0\s*(-|to)\s*[12]\s*(yrs|years)|associate (software )?engineer|batch of 202", re.I)
SENIOR = re.compile(r"senior|\bsr\.?\b|lead|manager|principal|director|staff|architect|"
                    r"\b([3-9]|1\d)\s*\+?\s*(-|to)?\s*\d*\s*(yrs|years)", re.I)


def get(url, **kw):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=25, **kw)
    r.raise_for_status()
    return r


def job(title, company, loc, url, desc, posted, source):
    return {"title": title.strip(), "company": company.strip(), "location_raw": (loc or "").strip(),
            "url": url, "description": re.sub(r"<[^>]+>|\s+", " ", desc or "").strip()[:1500],
            "posted": (posted or "")[:10], "source": source}


# ---- sources -------------------------------------------------------------
def greenhouse(slug):
    for j in get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true").json()["jobs"]:
        yield job(j["title"], slug, j["location"]["name"], j["absolute_url"], j.get("content"), j.get("updated_at"), "Greenhouse")

def lever(slug):
    for j in get(f"https://api.lever.co/v0/postings/{slug}?mode=json").json():
        ts = datetime.fromtimestamp(j["createdAt"] / 1000, timezone.utc).isoformat() if j.get("createdAt") else ""
        yield job(j["text"], slug, j["categories"].get("location"), j["hostedUrl"], j.get("descriptionPlain"), ts, "Lever")

def ashby(slug):
    for j in get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}").json()["jobs"]:
        yield job(j["title"], slug, j.get("location"), j["jobUrl"], j.get("descriptionPlain"), j.get("publishedAt"), "Ashby")

def adzuna():
    i, k = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (i and k): print("Adzuna keys missing"); return
    for q in ["fresher", "intern", "graduate engineer", "junior devops", "junior cloud", "qa automation fresher"]:
        for p in (1, 2, 3):
            r = get(f"https://api.adzuna.com/v1/api/jobs/in/search/{p}", params={
                "app_id": i, "app_key": k, "results_per_page": 50, "what": q, "max_days_old": 30})
            for j in r.json().get("results", []):
                yield job(j["title"], j["company"]["display_name"], j["location"]["display_name"],
                          j["redirect_url"], j["description"], j.get("created"), "Adzuna")

def jooble():
    key = os.getenv("JOOBLE_KEY")
    if not key: print("Jooble key missing"); return
    for q in ["fresher", "intern", "graduate trainee", "junior developer"]:
        r = requests.post(f"https://jooble.org/api/{key}", json={"keywords": q, "location": "India"}, timeout=25)
        for j in r.json().get("jobs", []):
            yield job(j["title"], j.get("company") or "Unknown", j.get("location"), j["link"],
                      j.get("snippet"), j.get("updated"), "Jooble")

def jsonld(url):
    """Career pages that publish schema.org JobPosting data; robots.txt is honoured."""
    p = urlparse(url); r = rp.RobotFileParser(f"{p.scheme}://{p.netloc}/robots.txt"); r.read()
    if not r.can_fetch(UA, url): return
    for blob in re.findall(r'<script[^>]+ld\+json[^>]*>(.*?)</script>', get(url).text, re.S):
        try: data = json.loads(blob)
        except ValueError: continue
        for d in (data if isinstance(data, list) else data.get("@graph", [data])):
            if d.get("@type") == "JobPosting":
                loc = d.get("jobLocation", {}); loc = loc[0] if isinstance(loc, list) and loc else loc
                addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
                yield job(d["title"], (d.get("hiringOrganization") or {}).get("name", p.netloc),
                          addr.get("addressLocality", "") + " " + addr.get("addressCountry", ""),
                          d.get("url") or url, d.get("description"), d.get("datePosted"), "Career page")


# ---- pipeline ------------------------------------------------------------
def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())

def dedupe(jobs):
    seen, out = {}, []
    for j in jobs:
        key = norm(j["company"]) + norm(j["title"]) + norm(j["location_raw"].split(",")[0])
        if key in seen: continue
        if any(norm(o["company"]) == norm(j["company"]) and
               difflib.SequenceMatcher(None, norm(o["title"]), norm(j["title"])).ratio() > .93 and
               norm(o["location_raw"][:6]) == norm(j["location_raw"][:6]) for o in out[-400:]): continue
        seen[key] = 1; out.append(j)
    return out

def keyword_tag(j):
    t, loc = j["title"].lower(), j["location_raw"].lower()
    role = next((r for r, w in [("DevOps", "devops|sre|site reliab"), ("Cloud", "cloud|aws|azure|gcp"),
        ("QA & Automation", "qa|test|sdet"), ("ML & AI", "machine|ml |ai |nlp"), ("Data", "data|analyst"),
        ("Mobile", "android|ios|mobile"), ("Full-stack", "full.?stack"), ("Frontend", "front|react|ui"),
        ("Backend", "backend|java|python|django|node|software|developer|engineer"),
        ("Support", "support|service desk")] if re.search(w, t)), "Other")
    city = "Remote" if "remote" in loc else next((c for c, w in [("Bengaluru", "bengal|bangal"),
        ("Delhi NCR", "delhi|gurgaon|gurugram|noida"), ("Mumbai", "mumbai|navi"), ("Pune", "pune"),
        ("Hyderabad", "hyderabad"), ("Chennai", "chennai"), ("Kolkata", "kolkata"),
        ("Ahmedabad", "ahmedabad"), ("Nashik", "nashik")] if re.search(w, loc)), "Other")
    return {"role": role, "city": city}

def llm_tag(jobs, cache):
    todo = [j for j in jobs if j["id"] not in cache]
    key = os.getenv("ANTHROPIC_API_KEY")
    if todo and key:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        for i in range(0, len(todo), 20):
            batch = todo[i:i + 20]
            prompt = (f"Tag each job. role must be one of {ROLES}. city must be one of {CITIES} "
                      "(use Remote if remote, Other if unlisted). Reply with ONLY a JSON object mapping "
                      'id to {"role":..., "city":...}.\n' + json.dumps(
                          [{"id": j["id"], "title": j["title"], "location": j["location_raw"],
                            "text": j["description"][:300]} for j in batch]))
            try:
                msg = client.messages.create(model=os.getenv("TAG_MODEL", "claude-haiku-5-5"),
                                             max_tokens=2000, messages=[{"role": "user", "content": prompt}])
                cache.update(json.loads(re.search(r"\{.*\}", msg.content[0].text, re.S).group()))
            except Exception as e:
                print("LLM batch failed, using keywords:", e)
    for j in todo:
        if j["id"] not in cache or cache[j["id"]].get("role") not in ROLES:
            cache[j["id"]] = keyword_tag(j)
    return cache

def main():
    cfg = json.load(open(f"{ROOT}/collector/sources.json"))
    raw = []
    runners = [(greenhouse, s) for s in cfg["greenhouse"]] + [(lever, s) for s in cfg["lever"]] + \
              [(ashby, s) for s in cfg["ashby"]] + [(jsonld, u) for u in cfg["career_pages"]] + \
              [(adzuna, None), (jooble, None)]
    for fn, arg in runners:
        try:
            got = list(fn(arg) if arg else fn()); raw += got; print(f"{fn.__name__} {arg or ''}: {len(got)}")
        except Exception as e:
            print(f"skip {fn.__name__} {arg}: {e}")
    keep = [j for j in raw if INDIA.search(j["location_raw"] + " " + j["description"][:200])
            and FRESHER.search(j["title"] + " " + j["description"]) and not SENIOR.search(j["title"])]
    for j in keep:
        j["id"] = hashlib.sha1((j["company"] + j["title"] + j["location_raw"]).lower().encode()).hexdigest()[:12]
    keep = dedupe(keep)
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    cache = llm_tag(keep, cache); json.dump(cache, open(CACHE, "w"))
    old = {j["id"]: j for j in json.load(open(OUT)).get("jobs", []) if j.get("last_seen")} if os.path.exists(OUT) else {}
    today = NOW.strftime("%Y-%m-%d")
    for j in keep:
        j.update(cache[j["id"]]); j["first_seen"] = old.get(j["id"], {}).get("first_seen", today); j["last_seen"] = today
        old[j["id"]] = j
    cutoff = (NOW - timedelta(days=21)).strftime("%Y-%m-%d")
    jobs = sorted((j for j in old.values() if j["last_seen"] >= cutoff), key=lambda j: j["first_seen"], reverse=True)
    json.dump({"updated": NOW.isoformat(timespec="minutes"), "count": len(jobs), "jobs": jobs},
              open(OUT, "w"), ensure_ascii=False, indent=1)
    print("total jobs:", len(jobs))

if __name__ == "__main__":
    main()
