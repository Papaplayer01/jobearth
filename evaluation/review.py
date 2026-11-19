"""Faster hand-check: shows the site's tags for each post; you confirm them or correct them."""
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
    for r in rows:
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
    print(f">>> SITE SAYS: role = {r['site_role']} | city = {r['site_city']}")
    print("   ".join(f"{k}) {x}" for k, x in enumerate(ROLES, 1)))
    a = input("Enter = both right | role number = role wrong | c = only city wrong | u = undo | q = quit: ").strip().lower()
    if a == "q": save(); print("Saved."); sys.exit()
    if a == "u":
        if i: i -= 1; todo[i]["human_role"] = todo[i]["human_city"] = ""; save()
        continue
    if a == "":
        role, city = r["site_role"], r["site_city"]
    elif a == "c":
        role = r["site_role"]; city = input("correct city (name, Remote, or Other): ").strip()
        if not city: print("Type the correct city."); continue
    elif a.isdigit() and 1 <= int(a) <= len(ROLES):
        role = ROLES[int(a) - 1]
        city = input(f"correct city (Enter = site's '{r['site_city']}' is right): ").strip() or r["site_city"]
    else:
        print("Not understood."); continue
    r["human_role"], r["human_city"] = role, city
    save(); i += 1
print("\nAll done. Now run: python3 evaluation/eval_sample.py score")
