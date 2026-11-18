# Loom script (about 4.5 minutes, face and screen)

Speak it in your own words and use these as a guide, not a script to read. Keep your camera on throughout. Do not quote any number you have not measured: fill in the accuracy and cost from your sheet before recording.

## 0:00 to 0:25, what it is
Say what you built in one sentence: a live site that collects fresher and internship jobs in India from sources that allow it, removes duplicates, tags each post by role and city with an LLM, and refreshes itself every morning. Show the live site, type a skill into the box, and click a role chip. Say the post count you see.

## 0:25 to 1:45, architecture
Show the diagram in the README. Walk left to right: the sources (Adzuna, company boards on Greenhouse, Lever and Ashby, two remote feeds), the collector that filters and dedupes, the tagging step with a cache, then jobs.json that the static site reads. Mention that a GitHub Action runs it every day at 6 AM IST and commits the result, so there is no server. Say why you left out Naukri, LinkedIn and Indeed: their terms forbid scraping. Show daily.yml for five seconds.

## 1:45 to 3:15, what broke and how I fixed it
Pick your three best stories from the README table, told as problem, how you found it, fix. Good ones: the site showing 1 job because the secrets were never saved (found by a log line and `gh secret list`), the push conflicts from overlapping runs (fixed with a concurrency group), and the scam-looking posts you only noticed by reading real data instead of counts. Show the log or the commit for each. One sentence on the rest is enough.

## 3:15 to 4:15, the numbers
Open the Summary tab. Say how you sampled (50 random posts, fixed seed 42, you labelled them by hand), then read your accuracy for role and city, and the keyword baseline for comparison. Say the margin of error out loud: with 50 posts it is about plus or minus 10 points. Then open the Cost tab and give the measured cost per 1,000 posts, and say it is cheap because each post is tagged once and cached.

## 4:15 to 4:30, what I would do next
One or two things: report-post button and a block list, and checking that apply links still work.

## Checklist before you record
Add the Anthropic key and run the workflow once so the tags and cost are real. Fill the 50 rows and the yellow cells in the Cost tab. Replace the "to fill" lines in the README. Have the repo, the sheet and the live site open in tabs.
