"""ats_scraper — pull postings from public Greenhouse / Lever / Ashby job-board APIs.

These are unauthenticated public endpoints. Invalid/unknown board tokens are skipped
gracefully so a typo never breaks a pipeline run.
"""
from __future__ import annotations

import requests

from .common import log

TIMEOUT = 20
HEADERS = {"User-Agent": "ai-job-search/1.0 (+github actions)"}

# Title must contain one of these (case-insensitive) to be worth scoring.
RELEVANT_KEYWORDS = (
    "developer", "engineer", "software", "full stack", "fullstack", "full-stack",
    "backend", "back end", "back-end", "frontend", "front end", "front-end",
    ".net", "dotnet", "c#", "react", "angular", "abap", "ui5", "fiori", "sap",
)


def _relevant(title: str) -> bool:
    t = (title or "").lower()
    return any(k in t for k in RELEVANT_KEYWORDS)


def _greenhouse(token: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        out.append(
            {
                "company": token,
                "title": j.get("title", ""),
                "location": loc,
                "url": j.get("absolute_url", ""),
                "posted": (j.get("updated_at") or j.get("created_at") or "")[:10],
                "description": "",  # full HTML available in j['content'] if needed
                "source": "greenhouse",
            }
        )
    return out


def _lever(token: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for j in r.json():
        cat = j.get("categories", {}) or {}
        created = j.get("createdAt")
        posted = ""
        if isinstance(created, (int, float)):
            from datetime import datetime, timezone

            posted = datetime.fromtimestamp(created / 1000, timezone.utc).date().isoformat()
        out.append(
            {
                "company": token,
                "title": j.get("text", ""),
                "location": cat.get("location", ""),
                "url": j.get("hostedUrl", ""),
                "posted": posted,
                "description": (j.get("descriptionPlain") or "")[:600],
                "source": "lever",
            }
        )
    return out


def _ashby(token: str) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=false"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        out.append(
            {
                "company": token,
                "title": j.get("title", ""),
                "location": j.get("location", ""),
                "url": j.get("jobUrl", ""),
                "posted": (j.get("publishedAt") or "")[:10],
                "description": (j.get("descriptionPlain") or "")[:600],
                "source": "ashby",
            }
        )
    return out


_PROVIDERS = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby}


def scrape_ats(config: dict) -> list[dict]:
    ats = config.get("ats", {})
    jobs: list[dict] = []
    for provider, fn in _PROVIDERS.items():
        for token in ats.get(provider, []):
            if not token or token.startswith("_"):
                continue
            try:
                found = fn(token)
            except Exception as e:  # network error, 404, bad JSON — skip the board
                log.warning("ats[%s/%s]: skipped (%s)", provider, token, e)
                continue
            relevant = [j for j in found if j.get("url") and _relevant(j["title"])]
            log.info("ats[%s/%s]: %d postings, %d relevant", provider, token, len(found), len(relevant))
            jobs.extend(relevant)
    return jobs
