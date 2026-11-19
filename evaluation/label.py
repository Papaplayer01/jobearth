"""Terminal helper to hand-label evaluation/sample_50.csv (blind: it does not show the site's tags)."""
import csv, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = f"{ROOT}/evaluation/sample_50.csv"
ROLES = ["Cloud", "DevOps", "Backend", "Frontend", "Full-stack", "QA & Automation", "Data", "ML & AI",
         "Mobile", "Security", "Support", "Design", "Sales & Marketing", "Operations & HR", "Other"]
ALIAS = {"bengaluru": "Bangalore", "bengalore": "Bangalore", "gurgaon": "Gurugram", "bombay": "Mumbai",
         "madras": "Chennai", "calcutta": "Kolkata"}
canon = lambda c: ALIAS.get(c.strip().lower(), c.strip())

rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
cols = list(rows[0].keys())

def save():
    for r in rows:                      # spelling variants of one city count as the same city
        for k in ("site_city", "baseline_city", "human_city"):
            r[k] = canon(r[k])
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

todo = [r for r in rows if not r["human_role"].strip()]
done0 = len(rows) - len(todo)
i = 0
while i < len(todo):
    r = todo[i]
    print(f"\n=== #{r['n']} of {len(rows)} ({done0 + i} done) ===")
    print(r["title"], "|", r["company"], "|", r["location"])
    print(r["description"][:300].replace("\n", " "))
    print("   ".join(f"{k}) {x}" for k, x in enumerate(ROLES, 1)))
    a = input("role number (u = undo previous, q = save and quit): ").strip().lower()
    if a == "q": save(); print("Saved."); sys.exit()
    if a == "u":
        if i: i -= 1; todo[i]["human_role"] = todo[i]["human_city"] = ""; save()
        continue
    if not (a.isdigit() and 1 <= int(a) <= len(ROLES)): print("Type a number from the list."); continue
    city = input("city (name, Remote, or Other): ").strip() or "Other"
    r["human_role"], r["human_city"] = ROLES[int(a) - 1], city
    save(); i += 1
print("\nAll done. Now run: python3 evaluation/eval_sample.py score")
