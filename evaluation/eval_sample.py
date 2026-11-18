"""Hand-check helper.
  python3 evaluation/eval_sample.py make    -> writes evaluation/sample_50.csv (50 random posts, fixed seed)
  python3 evaluation/eval_sample.py score   -> reads the CSV after you fill human_role and human_city, prints accuracy
"""
import csv, json, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{ROOT}/collector")
import collect  # noqa: E402  (for the keyword baseline and the role list)

CSV = f"{ROOT}/evaluation/sample_50.csv"
COLS = ["n", "id", "title", "company", "location", "description", "tagger", "site_role", "site_city",
        "baseline_role", "baseline_city", "human_role", "human_city"]


def make():
    jobs = json.load(open(f"{ROOT}/docs/jobs.json"))["jobs"]
    jobs = [j for j in jobs if j.get("last_seen")]
    pick = random.Random(42).sample(jobs, min(50, len(jobs)))
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(COLS)
        for n, j in enumerate(pick, 1):
            b = collect.keyword_tag(j)
            w.writerow([n, j["id"], j["title"], j["company"], j["location_raw"], j["description"][:300],
                        j.get("by", "unknown"), j["role"], j["city"], b["role"], b["city"], "", ""])
    print(f"Wrote {len(pick)} posts to {CSV}")
    print("Fill human_role (one of:", ", ".join(collect.ROLES) + ") and human_city (the real city, Remote, or Other).")


def score():
    rows = [r for r in csv.DictReader(open(CSV, encoding="utf-8")) if r["human_role"].strip()]
    if not rows: sys.exit("No rows have human_role filled in yet.")
    eq = lambda a, b: a.strip().lower() == b.strip().lower()
    n = len(rows)
    def acc(pred_r, pred_c, subset):
        if not subset: return None
        r = sum(eq(x[pred_r], x["human_role"]) for x in subset) / len(subset)
        c = sum(eq(x[pred_c], x["human_city"]) for x in subset) / len(subset)
        both = sum(eq(x[pred_r], x["human_role"]) and eq(x[pred_c], x["human_city"]) for x in subset) / len(subset)
        return r, c, both
    print(f"Checked {n} posts")
    for label, pr, pc in [("Site tags", "site_role", "site_city"), ("Keyword baseline", "baseline_role", "baseline_city")]:
        r, c, both = acc(pr, pc, rows)
        print(f"{label:17} role {r:.0%} | city {c:.0%} | both {both:.0%}")
    for t in sorted({x["tagger"] for x in rows}):
        sub = [x for x in rows if x["tagger"] == t]
        r, c, both = acc("site_role", "site_city", sub)
        print(f"  tagger={t:8} ({len(sub)} posts): role {r:.0%} | city {c:.0%} | both {both:.0%}")
    print("\nMistakes by the site tags:")
    for x in rows:
        if not (eq(x["site_role"], x["human_role"]) and eq(x["site_city"], x["human_city"])):
            print(f"  #{x['n']} {x['title'][:50]} | site {x['site_role']}/{x['site_city']} | you {x['human_role']}/{x['human_city']}")


if __name__ == "__main__":
    {"make": make, "score": score}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
