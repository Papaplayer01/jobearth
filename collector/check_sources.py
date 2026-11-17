"""Tests candidate company board names against the Greenhouse, Lever and Ashby APIs and keeps the ones that
exist and have at least one India post. Run from GitHub Actions (find-sources workflow); writes sources.json."""
import json, os, re, time, requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "JoBearthBot/1.0 (+https://github.com/Papaplayer01/jobearth)"
INDIA = re.compile(r"india|bengal|bangal|mumbai|pune|hyderabad|delhi|gurgaon|gurugram|noida|chennai|kolkata|ahmedabad|nashik|jaipur|kochi", re.I)
CAND = {
 "greenhouse": "razorpaysoftwareprivatelimited groww phonepe postman browserstack cleartax zeta druva freshworks chargebee whatfix clevertap sprinklr thoughtspot nutanix stripe databricks cloudflare mongodb elastic twilio okta zscaler rubrik samsara datadog gitlab hashicorp confluent snowflake atlassian intuit paypal airbnb pinterest dropbox github mckinsey wizards carwale cars24 spinny pocketfm lenskart urbancompany swiggy zomato bigbasket dailyhunt innovaccer sharechat unacademy vedantu coursera toptal hackerrank bluecore agoda grab gojek sumologic highradius icertis media-net inmobi mindtickle moengage postmanapi capillary uniphore turing".split(),
 "lever": "cred meesho kuvera dream11 paytm upgrad shadowfax slice licious mpl khatabook rapido dunzo navi jupiter zeta sharechat winzo ofbusiness cars24 uniphore leadsquared browserstack gupshup lissun mindtickle eightfold palantir zenoti".split(),
 "ashby": "zepto sarvam openai notion linear ramp supabase vercel replit deel retool posthog scale cohere anthropic perplexity mercor decagon glean cursor harvey runway elevenlabs".split(),
}
URL = {"greenhouse": "https://boards-api.greenhouse.io/v1/boards/{}/jobs", "lever": "https://api.lever.co/v0/postings/{}?mode=json",
       "ashby": "https://api.ashbyhq.com/posting-api/job-board/{}"}

def locs(kind, data):
    if kind == "greenhouse": return [j["location"]["name"] for j in data["jobs"]]
    if kind == "lever": return [j["categories"].get("location") or "" for j in data]
    return [j.get("location") or "" for j in data["jobs"]]

def main():
    path = f"{ROOT}/collector/sources.json"
    cfg = json.load(open(path)); out = {k: [] for k in CAND}
    for kind, names in CAND.items():
        for n in dict.fromkeys(names):
            try:
                r = requests.get(URL[kind].format(n), headers={"User-Agent": UA}, timeout=20)
                if r.status_code != 200: print(f"x {kind} {n}: {r.status_code}"); continue
                L = locs(kind, r.json()); k = sum(bool(INDIA.search(x)) for x in L)
                print(f"{'OK' if k else '--'} {kind} {n}: {len(L)} posts, {k} India")
                if k: out[kind].append(n)
            except Exception as ex:
                print(f"x {kind} {n}: {ex}")
            time.sleep(.3)
    cfg.update(out); json.dump(cfg, open(path, "w"), indent=1)
    print({k: len(v) for k, v in out.items()})

if __name__ == "__main__":
    main()
