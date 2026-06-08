"""score_jobs() — Claude Haiku 4.5 scores each posting 1-10 against the candidate profile."""
from __future__ import annotations

import anthropic

from .common import log

SCORE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "fit_score": {"type": "integer", "description": "1-10 fit, or 0 if location is not OK"},
        "score_reason": {"type": "string", "description": "One or two sentences explaining the score"},
        "ai_opener": {"type": "string", "description": "A punchy 1-2 sentence outreach opener tailored to this role"},
        "location_ok": {"type": "boolean", "description": "True only if the job location matches the candidate constraints"},
    },
    "required": ["fit_score", "score_reason", "ai_opener", "location_ok"],
}

PROMPT = """Evaluate this job for the candidate below. Judge fit on roles, tech stack, and seniority,
and judge location strictly against the candidate's location constraints.

If the location is NOT OK (e.g. full-time on-site outside the Haifa area, or a timezone/region the
candidate cannot work), set location_ok=false and fit_score=0.

Return JSON only matching the schema: fit_score (1-10, or 0 if location not OK), score_reason,
ai_opener (a tailored 1-2 sentence outreach opener), location_ok.

=== CANDIDATE PROFILE ===
{profile}

=== JOB ===
Company: {company}
Title: {title}
Location: {location}
Posted: {posted}
Description: {description}
"""


def _score_one(client, model, profile, job) -> dict | None:
    prompt = PROMPT.format(
        profile=profile,
        company=job.get("company", ""),
        title=job.get("title", ""),
        location=job.get("location", ""),
        posted=job.get("posted", ""),
        description=job.get("description", "")[:1500],
    )
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            output_config={"format": {"type": "json_schema", "schema": SCORE_SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        log.warning("score: API error for %s — %s", job.get("url", ""), e)
        return None

    import json

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("score: unparseable result for %s", job.get("url", ""))
        return None


def score_jobs(jobs: list[dict], profile: str, config: dict, api_key: str) -> list[dict]:
    """Adds fit_score, score_reason, ai_opener, location_ok to each job (in place)."""
    client = anthropic.Anthropic(api_key=api_key)
    model = config["models"]["score"]
    log.info("score_jobs: scoring %d postings with %s…", len(jobs), model)

    for i, job in enumerate(jobs, 1):
        result = _score_one(client, model, profile, job)
        if result is None:
            job.setdefault("fit_score", 0)
            job.setdefault("score_reason", "Scoring failed — review manually.")
            job.setdefault("ai_opener", "")
            job.setdefault("location_ok", False)
            continue
        job["fit_score"] = int(result.get("fit_score", 0))
        job["score_reason"] = result.get("score_reason", "")
        job["ai_opener"] = result.get("ai_opener", "")
        job["location_ok"] = bool(result.get("location_ok", False))
        if i % 5 == 0:
            log.info("score_jobs: %d/%d", i, len(jobs))
    return jobs
