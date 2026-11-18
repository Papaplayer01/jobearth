"""JoBearth collector: gathers fresher/intern posts in India from sources that allow
programmatic access, dedupes, tags with Claude, writes docs/jobs.json."""
import json, os, re, html, hashlib, difflib, urllib.robotparser as rp
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT, CACHE = f"{ROOT}/docs/jobs.json", f"{ROOT}/collector/tag_cache.json"
UA = "JoBearthBot/1.0 (+https://github.com/YOUR_USER/jobearth)"
NOW = datetime.now(timezone.utc)
CITIES = ["Bengaluru", "Mumbai", "Pune", "Hyderabad", "Delhi NCR", "Chennai", "Kolkata",
          "Ahmedabad", "Nashik", "Remote", "Other"]
ROLES = ["Cloud", "DevOps", "Backend", "Frontend", "Full-stack", "QA & Automation", "Data", "ML & AI",
         "Mobile", "Security", "Support", "Design", "Sales & Marketing", "Operations & HR", "Other"]
ROLE_MAP = [("DevOps", r"devops|\bsre\b|site reliab|platform eng"), ("Cloud", r"cloud|\baws\b|azure|\bgcp\b"),
    ("Security", r"security|cyber|soc analyst"), ("QA & Automation", r"\bqa\b|\btest(ing|er)?\b|sdet|automation"),
    ("ML & AI", r"machine learning|\bml\b|\bai\b|\bnlp\b|data scien"), ("Data", r"\bdata\b|analyst|\bsql\b|\bbi\b"),
    ("Mobile", r"android|\bios\b|mobile|flutter"), ("Full-stack", r"full.?stack"),
    ("Frontend", r"front.?end|react|angular|javascript|\bui\b"),
    ("Backend", r"back.?end|java\b|python|django|node|\.net|software|developer|programmer|engineer"),
    ("Support", r"support|service desk|help ?desk|customer (care|service)"),
    ("Design", r"design|\bux\b|graphic"), ("Sales & Marketing", r"sales|marketing|business development|\bseo\b|content"),
    ("Operations & HR", r"\bhr\b|recruit|operations|admin|account|finance|executive")]
SCAM = re.compile(r"backdoor|charges? (apply|applicable)|paid service|pay anything|registration fee|"
                  r"security deposit|processing fee|nothing comes for free", re.I)
STATES = {"andhra pradesh", "assam", "bihar", "chhattisgarh", "gujarat", "haryana", "himachal pradesh", "jharkhand",
          "karnataka", "kerala", "madhya pradesh", "maharashtra", "odisha", "punjab", "rajasthan", "tamil nadu",
          "telangana", "uttar pradesh", "uttarakhand", "west bengal", "india", "delhi"}
CAT_MAP = [(r"HR|Accounting|Admin", "Operations & HR"), (r"Sales|PR, Advert|Marketing", "Sales & Marketing"),
           (r"Customer", "Support"), (r"Creative", "Design")]
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


def clean(t):
    t = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(t or "")))
    return re.sub(r"\s+", " ", t).strip()

def job(title, company, loc, url, desc, posted, source, **extra):
    d = {"title": title.strip(), "company": company.strip(), "location_raw": (loc or "").strip(),
         "url": url, "description": clean(desc)[:3000], "posted": (posted or "")[:10], "source": source}
    d.update({k: v for k, v in extra.items() if v})
    return d

def salary(j):
    lo, hi = j.get("salary_min"), j.get("salary_max")
    if not lo and not hi: return ""
    f = lambda v: f"Rs {v:,.0f}"
    txt = f(lo or hi) if (not lo or not hi or lo == hi) else f"{f(lo)} to {f(hi)}"
    return txt + " a year" + (" (estimated)" if str(j.get("salary_is_predicted")) == "1" else "")


# ---- sources -------------------------------------------------------------
def greenhouse(slug):
    for j in get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true").json()["jobs"]:
        yield job(j["title"], slug, j["location"]["name"], j["absolute_url"], j.get("content"), j.get("updated_at"), "Greenhouse")

def lever(slug):
    for j in get(f"https://api.lever.co/v0/postings/{slug}?mode=json").json():
        ts = datetime.fromtimestamp(j["createdAt"] / 1000, timezone.utc).isoformat() if j.get("createdAt") else ""
        yield job(j["text"], slug, j["categories"].get("location"), j["hostedUrl"], j.get("descriptionPlain"), ts, "Lever",
                  type=j["categories"].get("commitment"), category=j["categories"].get("team"))

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
                          j["redirect_url"], j["description"], j.get("created"), "Adzuna", salary=salary(j),
                          type=(j.get("contract_time") or "").replace("_", " "), category=(j.get("category") or {}).get("label"))

def jooble():
    key = os.getenv("JOOBLE_KEY")
    if not key: print("Jooble key missing"); return
    for q in ["fresher", "intern", "graduate trainee", "junior developer"]:
        r = requests.post(f"https://jooble.org/api/{key}", json={"keywords": q, "location": "India"}, timeout=25)
        for j in r.json().get("jobs", []):
            yield job(j["title"], j.get("company") or "Unknown", j.get("location"), j["link"],
                      j.get("snippet"), j.get("updated"), "Jooble", salary=j.get("salary"), type=j.get("type"))

REMOTE_OK = re.compile(r"india|worldwide|anywhere|apac|asia|global|^$", re.I)

def remotive():
    """Remotive's public API; their terms ask for a visible credit and a link back, which the site footer gives."""
    for j in get("https://remotive.com/api/remote-jobs").json().get("jobs", []):
        loc = j.get("candidate_required_location") or ""
        if REMOTE_OK.search(loc):
            yield job(j["title"], j["company_name"], "Remote, " + (loc or "Worldwide"), j["url"], j.get("description"),
                      j.get("publication_date"), "Remotive", type=(j.get("job_type") or "").replace("_", " "),
                      category=j.get("category"), salary=j.get("salary"))

def remoteok():
    """RemoteOK's public API; credit and link back are required, which the site footer gives."""
    for j in get("https://remoteok.com/api").json()[1:]:
        loc = j.get("location") or ""
        if REMOTE_OK.search(loc):
            lo, hi = j.get("salary_min"), j.get("salary_max")
            yield job(j["position"], j["company"], "Remote, " + (loc or "Worldwide"), j["url"], j.get("description"),
                      j.get("date"), "RemoteOK", salary=f"${lo:,} to ${hi:,} a year (USD)" if lo and hi else "")

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
    pick = lambda text: next((r for r, w in ROLE_MAP if re.search(w, text)), None)
    cat = j.get("category", "")
    role = pick(j["title"].lower()) or next((r for w, r in CAT_MAP if re.search(w, cat)), None)
    if not role and "IT" in cat: role = pick(j["description"][:300].lower())
    role = role or "Other"
    loc = j["location_raw"].lower()
    city = "Remote" if "remote" in loc else next((c for c, w in [("Bengaluru", "bengal|bangal"),
        ("Delhi NCR", "delhi|gurgaon|gurugram|noida|ghaziabad|faridabad"), ("Mumbai", "mumbai|thane"),
        ("Pune", "pune|pimpri"), ("Hyderabad", "hyderabad|secunderabad"), ("Chennai", "chennai"),
        ("Kolkata", "kolkata"), ("Ahmedabad", "ahmedabad"), ("Nashik", "nashik")] if re.search(w, loc)), None)
    if not city:
        parts = [x.strip() for x in j["location_raw"].split(",") if x.strip()]
        # "Locality, City" puts the city last; "City, State" puts the state last
        pick_part = parts[-1] if len(parts) > 1 and parts[-1].lower() not in STATES else (parts[0] if parts else "")
        city = pick_part.title() if pick_part and pick_part.lower() not in STATES and len(pick_part) <= 25 else "Other"
    return {"role": role, "city": city}

USAGE = {"calls": 0, "in": 0, "out": 0, "posts": 0}
GH_URL = "https://models.github.ai/inference/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def provider():
    """anthropic if a key is set, else the free GitHub Models tier if a GitHub token is present, else keyword rules."""
    want = os.getenv("TAG_PROVIDER", "").lower()
    if want in ("anthropic", "github", "gemini"): return want
    if os.getenv("ANTHROPIC_API_KEY"): return "anthropic"
    if os.getenv("GEMINI_API_KEY"): return "gemini"
    return None


def model_name():
    return os.getenv("TAG_MODEL") or {"gemini": "gemini-2.5-flash-lite", "github": "openai/gpt-4o-mini"}.get(provider(), "claude-haiku-5-5")


def ask_llm(prompt):
    """Returns the model's text and records token use. Retries once on a rate limit (429)."""
    if provider() == "anthropic":
        import anthropic
        msg = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).messages.create(
            model=model_name(), max_tokens=2000, messages=[{"role": "user", "content": prompt}])
        u = getattr(msg, "usage", None)
        if u: USAGE["in"] += u.input_tokens; USAGE["out"] += u.output_tokens
        return msg.content[0].text
    for attempt in (1, 2):
        r = requests.post(GEMINI_URL if provider() == "gemini" else GH_URL, timeout=90, headers={"Authorization": f"Bearer {os.getenv('GEMINI_API_KEY') if provider() == 'gemini' else os.getenv('GITHUB_TOKEN')}",
                          "Content-Type": "application/json"},
                          json={"model": model_name(), "temperature": 0, "max_tokens": 2000,
                                "messages": [{"role": "user", "content": prompt}]})
        if r.status_code == 429 and attempt == 1:
            import time; time.sleep(int(r.headers.get("retry-after", 30)) if str(r.headers.get("retry-after", "")).isdigit() else 30); continue
        if r.status_code >= 400 or not r.text.strip().startswith("{"):
            print(f"LLM HTTP {r.status_code}: {r.text[:300]!r}")
        r.raise_for_status(); data = r.json()
        u = data.get("usage") or {}
        USAGE["in"] += u.get("prompt_tokens", 0); USAGE["out"] += u.get("completion_tokens", 0)
        return data["choices"][0]["message"]["content"]


def llm_tag(jobs, cache):
    todo = [j for j in jobs if j["id"] not in cache
            or (provider() and cache[j["id"]].get("by") == "kw")]
    if todo and provider():
        for i in range(0, len(todo), 20):
            batch = todo[i:i + 20]
            prompt = (f"Tag each job. role must be one of {ROLES}. city is the main Indian city in English, for example Pune "
                      "(Remote if remote, Other if no city is named). Reply with ONLY a JSON object mapping "
                      'id to {"role":..., "city":...}.\n' + json.dumps(
                          [{"id": j["id"], "title": j["title"], "location": j["location_raw"],
                            "text": j["description"][:300]} for j in batch]))
            try:
                import time; time.sleep(6)
                USAGE["calls"] += 1
                parsed = json.loads(re.search(r"\{.*\}", ask_llm(prompt), re.S).group())
                for k, v in parsed.items():
                    if isinstance(v, dict): v["by"] = "llm"; USAGE["posts"] += 1
                cache.update(parsed)
            except Exception as e:
                print("LLM batch failed, using keywords:", e)
    for j in todo:
        if j["id"] not in cache or cache[j["id"]].get("role") not in ROLES:
            cache[j["id"]] = {**keyword_tag(j), "by": "kw"}
    return cache


def log_usage():
    """Records real token use per run so cost per 1,000 posts can be measured, not guessed."""
    if not USAGE["calls"]: return
    pin, pout = float(os.getenv("PRICE_IN", "0.10")), float(os.getenv("PRICE_OUT", "0.50"))  # USD per million tokens, Haiku 5.5
    paid = (USAGE["in"] * pin + USAGE["out"] * pout) / 1e6
    free = provider() in ("github", "gemini")
    rec = {"date": NOW.strftime("%Y-%m-%d"), "provider": provider(), "model": model_name(), **USAGE,
           "cost_usd": 0.0 if free else round(paid, 6), "equivalent_haiku_cost_usd": round(paid, 6)}
    path = f"{ROOT}/collector/usage_log.json"
    log = json.load(open(path)) if os.path.exists(path) else []
    json.dump(log + [rec], open(path, "w"), indent=1)
    print("LLM usage:", rec)


def main():
    cfg = json.load(open(f"{ROOT}/collector/sources.json"))
    raw = []
    runners = [(greenhouse, s) for s in cfg["greenhouse"]] + [(lever, s) for s in cfg["lever"]] + \
              [(ashby, s) for s in cfg["ashby"]] + [(jsonld, u) for u in cfg["career_pages"]] + \
              [(adzuna, None), (jooble, None), (remotive, None), (remoteok, None)]
    for fn, arg in runners:
        try:
            got = list(fn(arg) if arg else fn()); raw += got; print(f"{fn.__name__} {arg or ''}: {len(got)}")
        except Exception as e:
            print(f"skip {fn.__name__} {arg}: {e}")
    keep = [j for j in raw if INDIA.search(j["location_raw"] + " " + j["description"][:200])
            and FRESHER.search(j["title"] + " " + j["description"]) and not SENIOR.search(j["title"])]
    for j in keep:
        j["id"] = hashlib.sha1((j["company"] + j["title"] + j["location_raw"]).lower().encode()).hexdigest()[:12]
    keep = dedupe([j for j in keep if not SCAM.search(j["title"] + " " + j["description"])])
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    cache = llm_tag(keep, cache); json.dump(cache, open(CACHE, "w"))
    log_usage()
    old = {j["id"]: j for j in json.load(open(OUT)).get("jobs", []) if j.get("last_seen")} if os.path.exists(OUT) else {}
    old = {k: v for k, v in old.items() if not SCAM.search(v["title"] + " " + v["description"])}
    today = NOW.strftime("%Y-%m-%d")
    for j in keep:
        j.update(cache[j["id"]]); j["first_seen"] = old.get(j["id"], {}).get("first_seen", today); j["last_seen"] = today
        old[j["id"]] = j
    cutoff = (NOW - timedelta(days=21)).strftime("%Y-%m-%d")
    jobs = sorted((j for j in old.values() if j["last_seen"] >= cutoff), key=lambda j: j["first_seen"], reverse=True)
    json.dump({"updated": NOW.isoformat(timespec="minutes"), "count": len(jobs), "jobs": jobs},
              open(OUT, "w"), ensure_ascii=False, indent=1)
    write_feed(jobs)
    print("total jobs:", len(jobs))

SITE = "https://papaplayer01.github.io/jobearth/"

def write_feed(jobs):
    from email.utils import format_datetime
    from xml.sax.saxutils import escape
    items = []
    for j in jobs[:50]:
        try: when = format_datetime(datetime.strptime(j["first_seen"], "%Y-%m-%d").replace(tzinfo=timezone.utc))
        except Exception: when = format_datetime(NOW)
        items.append(f"<item><title>{escape(j['title'])} at {escape(j['company'])} ({escape(j['city'])})</title>"
                     f"<link>{escape(j['url'])}</link><guid isPermaLink=\"false\">{j['id']}</guid><pubDate>{when}</pubDate>"
                     f"<category>{escape(j['role'])}</category><description>{escape(j['description'][:300])}</description></item>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>JoBearth new jobs</title>'
           f'<link>{SITE}</link><description>Fresher and internship posts across India</description>' + "".join(items) + "</channel></rss>")
    open(f"{ROOT}/docs/feed.xml", "w", encoding="utf-8").write(xml)

if __name__ == "__main__":
    main()
