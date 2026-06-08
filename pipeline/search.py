"""search_jobs() — Claude Opus 4.8 + server-side web_search to find real open postings."""
from __future__ import annotations

import anthropic

from .common import extract_json, log

SEARCH_PROMPT = """Find CURRENTLY OPEN jobs (posted in the last 30 days) for these roles: {roles}.

Candidate location constraints (a posting only counts if it satisfies one of these):
{locations}

Rules:
- Each URL MUST be a DIRECT link to a specific job posting (a careers/ATS posting page),
  NOT a company homepage, a job-board search results page, or an aggregator listing.
- Only include postings you can verify are currently open and were posted within the last 30 days.
- Prefer Israeli employers (Haifa/north first, then Tel Aviv hybrid) and remote roles open to
  UTC+2..UTC+5. Skip full-time on-site roles outside the Haifa area.

Return between {min_results} and {max_results} results as a JSON array ONLY (no prose around it).
Each element MUST have exactly these keys:
{{"company": "", "title": "", "location": "", "url": "", "posted": "YYYY-MM-DD", "description": ""}}
"description" should be 1-3 sentences summarizing the role and key requirements."""


def search_jobs(config: dict, api_key: str) -> list[dict]:
    client = anthropic.Anthropic(api_key=api_key)
    model = config["models"]["search"]

    roles = ", ".join(config["roles"])
    loc = config["locations"]
    locations = (
        f"- Primary (preferred): {', '.join(loc['primary'])}\n"
        f"- Tel Aviv: only if HYBRID (not full-time on-site)\n"
        f"- Remote: worldwide, timezones {loc['remote']['timezone_range']}"
    )
    prompt = SEARCH_PROMPT.format(
        roles=roles,
        locations=locations,
        min_results=config["search"]["min_results"],
        max_results=config["search"]["max_results"],
    )

    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 12}]
    messages = [{"role": "user", "content": prompt}]

    log.info("search_jobs: querying %s with web_search…", model)
    full_text = []
    for _ in range(6):  # bounded pause_turn continuation loop
        resp = client.messages.create(
            model=model,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            tools=tools,
            messages=messages,
        )
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                full_text.append(block.text)
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break

    data = extract_json("\n".join(full_text))
    if not isinstance(data, list):
        log.warning("search_jobs: model returned no parseable JSON array.")
        return []

    jobs = []
    for item in data:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        jobs.append(
            {
                "company": (item.get("company") or "").strip(),
                "title": (item.get("title") or "").strip(),
                "location": (item.get("location") or "").strip(),
                "url": item.get("url").strip(),
                "posted": (item.get("posted") or "").strip(),
                "description": (item.get("description") or "").strip(),
                "source": "opus_search",
            }
        )
    log.info("search_jobs: %d postings returned.", len(jobs))
    return jobs
