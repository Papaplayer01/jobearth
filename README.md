# JoBearth

Fresher and internship posts across India. A daily GitHub Action collects posts from Greenhouse, Lever and Ashby boards, Adzuna, Jooble and robots.txt-compliant JSON-LD career pages, removes duplicates, tags each post by role and city with Claude, and writes `docs/jobs.json`. `docs/index.html` is the static search site.

## Publish
1. Create an empty repo named `jobearth` on GitHub, then in this folder run:
   `git init && git add . && git commit -m "JoBearth" && git branch -M main && git remote add origin https://github.com/Papaplayer01/jobearth.git && git push -u origin main`
2. Settings > Pages > Deploy from branch > `main` and folder `/docs`.
3. Settings > Secrets and variables > Actions: add `ANTHROPIC_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_KEY` (the last three are free to get).
4. Actions tab > Daily refresh > Run workflow. After that it runs every day at 06:00 IST.

Edit `collector/sources.json` to add company board slugs. Slugs that do not exist are skipped.
Replace `Papaplayer01` in `collector/collect.py` (the user agent) with your GitHub username.
