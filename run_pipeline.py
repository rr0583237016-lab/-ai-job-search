#!/usr/bin/env python3
"""
run_pipeline.py — automated AI job search pipeline.

Flow:
  search_jobs()   -> Claude Opus 4.8 + web_search  -> real open postings
  scrape_ats()    -> Greenhouse / Lever / Ashby public APIs
  score_jobs()    -> Claude Haiku 4.5              -> fit 1-10 + opener + location_ok
  merge()         -> upsert into scored_jobs.json (NEVER deletes; preserves manual jobs)
  build_site()    -> render docs/index.html from template

scored_jobs.json is the ONLY source of truth.

Usage:
  python run_pipeline.py            # full run
  python run_pipeline.py --no-search   # skip Opus web search (ATS only)
  python run_pipeline.py --build-only  # just rebuild docs/ from existing scored_jobs.json
"""
from __future__ import annotations

import argparse

from pipeline.ats import scrape_ats
from pipeline.build import build_site
from pipeline.common import get_api_key, load_config, load_jobs, load_profile, log, save_jobs
from pipeline.merge import merge
from pipeline.score import score_jobs
from pipeline.search import search_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="AI job search pipeline")
    parser.add_argument("--no-search", action="store_true", help="skip the Opus web search step")
    parser.add_argument("--no-ats", action="store_true", help="skip ATS scraping")
    parser.add_argument("--build-only", action="store_true", help="only rebuild docs/ from saved jobs")
    args = parser.parse_args()

    config = load_config()
    existing = load_jobs()

    if args.build_only:
        build_site(existing, config)
        return

    api_key = get_api_key()
    profile = load_profile()

    # 1. Discover postings.
    found: list[dict] = []
    if not args.no_search:
        try:
            found += search_jobs(config, api_key)
        except Exception as e:
            log.error("search_jobs failed: %s", e)
    if not args.no_ats:
        found += scrape_ats(config)

    log.info("discovered %d candidate postings before scoring", len(found))

    # 2. Score only postings we haven't scored before (saves tokens; existing ones keep their state).
    seen_urls = {j.get("url") for j in existing}
    fresh = [j for j in found if j.get("url") not in seen_urls]
    log.info("%d are new and will be scored", len(fresh))
    if fresh:
        score_jobs(fresh, profile, config, api_key)

    # 3. Merge into the single source of truth (never deletes; preserves manual jobs).
    merged = merge(existing, fresh, config)
    save_jobs(merged)

    # 4. Build the static tracker page.
    build_site(merged, config)
    log.info("done.")


if __name__ == "__main__":
    main()
