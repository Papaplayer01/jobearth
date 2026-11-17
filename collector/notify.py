"""Sends new posts for your target roles to Telegram. Skips quietly if not configured."""
import os, json, html, requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEN = f"{ROOT}/collector/notified.json"
token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
if not (token and chat):
    print("Telegram not configured, skipping"); raise SystemExit
roles = {r.strip() for r in os.getenv("NOTIFY_ROLES", "Cloud,DevOps,QA & Automation,Backend,Full-stack").split(",")}
jobs = json.load(open(f"{ROOT}/docs/jobs.json"))["jobs"]
seen = set(json.load(open(SEEN))) if os.path.exists(SEEN) else set()
new = [j for j in jobs if j["id"] not in seen and j["role"] in roles]
if not new:
    print("No new matching posts"); raise SystemExit
shown = new[:15]  # newest first; the rest are marked as seen so you are never flooded
lines = [f"<b>JoBearth: {len(new)} new post{'s' if len(new) != 1 else ''} for your roles</b>"]
for j in shown:
    extra = f"\n{html.escape(j['salary'])}" if j.get("salary") else ""
    lines.append(f"\n<b>{html.escape(j['title'])}</b>\n{html.escape(j['company'])}, {html.escape(j['city'])} ({html.escape(j['role'])}){extra}\n"
                 f"<a href=\"{html.escape(j['url'], quote=True)}\">Apply</a>")
if len(new) > len(shown):
    lines.append(f"\n...and {len(new) - len(shown)} more on https://papaplayer01.github.io/jobearth/")
msgs, cur = [], ""
for ln in lines:
    if len(cur) + len(ln) > 3800: msgs.append(cur); cur = ""
    cur += ln + "\n"
msgs.append(cur)
for m in msgs:
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=25, json={
        "chat_id": chat, "text": m, "parse_mode": "HTML", "disable_web_page_preview": True})
    if not r.ok:
        print("Telegram error:", r.status_code, r.text[:200]); raise SystemExit(0)  # do not mark as seen
json.dump(sorted(seen | {j["id"] for j in new}), open(SEEN, "w"))
print(f"Sent {len(shown)} of {len(new)} new posts")
