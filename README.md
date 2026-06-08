# 🎯 AI Job Search Engine

An automated, AI-powered job search engine and application tracker — deployed free on GitHub Pages.

- **Finds** currently-open postings with Claude Opus 4.8 + web search, plus public Greenhouse/Lever/Ashby boards.
- **Scores** each posting 1–10 against your profile with Claude Haiku 4.5 (location-aware).
- **Tracks** everything in a Material 3, mobile-first, installable PWA — statuses, interview rounds, notes, analytics.
- **Assists** per job: cover letter, interview prep, voice-simulated mock interview, company dossier, CV tailoring, and emotional support.

`scored_jobs.json` is the **single source of truth**. The pipeline never deletes jobs and always preserves anything you added manually.

---

## How it works

```
run_pipeline.py
 ├─ search_jobs()  → Claude Opus 4.8 + web_search   → real open postings (8–15)
 ├─ scrape_ats()   → Greenhouse / Lever / Ashby APIs → more postings
 ├─ score_jobs()   → Claude Haiku 4.5               → fit 1-10 + reason + opener + location_ok
 ├─ merge()        → upsert into scored_jobs.json    → filter: score ≥ 4, location OK, ≤ 30 days
 └─ build_site()   → render docs/index.html          → committed + deployed to Pages
```

Two GitHub Actions run it: **`pipeline.yml`** (cron 3×/day, Sun–Thu) and **`pages.yml`** (deploys `docs/`).

The tracker page calls Claude **directly from your browser** using an API key you paste once (stored only in `localStorage`). Your application state (statuses, notes, interview rounds, manually-added jobs) also lives in `localStorage`, so a pipeline run never wipes your progress.

---

## One-time setup

### 1. Create the GitHub repo and push
```bash
cd C:\Users\rache\ai-job-search
git add .
git commit -m "Initial commit: AI job search engine"
# create a repo named e.g. ai-job-search on github.com, then:
git remote add origin https://github.com/<your-username>/ai-job-search.git
git branch -M master
git push -u origin master
```

### 2. Add your Anthropic API key as a repo secret
Repo → **Settings → Secrets and variables → Actions → New repository secret**
- Name: `ANTHROPIC_API_KEY`
- Value: your `sk-ant-…` key

### 3. Enable GitHub Pages
Repo → **Settings → Pages → Build and deployment → Source: GitHub Actions**.
After the first `pages.yml` run, your tracker is live at
`https://<your-username>.github.io/ai-job-search/`.

### 4. First run
Repo → **Actions → "Job Search Pipeline" → Run workflow**. It searches, scores, commits, and the Pages workflow deploys. After that it runs automatically 3×/day, Sun–Thu.

### 5. Open the tracker → Settings → paste your API key
Needed for the in-browser AI features (cover letters, dossiers, voice sim, add-by-URL). Same key, stored locally on your device.

---

## Configuration — `config.json`
- `roles` — titles the search targets.
- `locations` — your location rules (drives the strict `location_ok` scoring).
- `filters.min_score` (default 4) and `filters.max_age_days` (default 30).
- `search.min_results` / `max_results` — how many postings Opus should return.
- `ats` — company board tokens to scrape. Add tokens of companies you target; bad tokens are skipped:
  ```json
  "ats": {
    "greenhouse": ["companytoken"],   // boards-api.greenhouse.io/v1/boards/<token>/jobs
    "lever":      ["companytoken"],   // api.lever.co/v0/postings/<token>?mode=json
    "ashby":      ["companytoken"]    // api.ashbyhq.com/posting-api/job-board/<token>
  }
  ```

Your background and strengths live in **`profile.md`** (two personas: Full Stack + SAP). Edit it anytime — it feeds both scoring and every browser AI feature.

---

## Running locally
```bash
pip install -r requirements.txt
setx ANTHROPIC_API_KEY "sk-ant-..."   # or $env:ANTHROPIC_API_KEY in PowerShell
python run_pipeline.py                # full run
python run_pipeline.py --build-only   # just rebuild docs/ from saved jobs (no API calls)
python run_pipeline.py --no-search    # ATS only
```

Then open `docs/index.html` in a browser (or serve it: `python -m http.server -d docs`).

---

## The single-source-of-truth rule
- Everything lives in `scored_jobs.json`.
- Jobs you add manually (in the app, by URL) carry an `initial_status` field and live in your browser; the pipeline **never** removes them.
- The merged set shown in the app = pipeline jobs (baked into the page) **+** your manual jobs (localStorage) **+** your per-job state overlay (status, notes, rounds).

---

## Models
| Step | Model | Why |
|---|---|---|
| Search | `claude-opus-4-8` + `web_search` | best at finding & verifying real postings |
| Scoring | `claude-haiku-4-5` | fast, cheap, structured output |
| Browser features | `claude-opus-4-8` (+ `web_search`/`web_fetch`) | quality writing & research, low volume |
