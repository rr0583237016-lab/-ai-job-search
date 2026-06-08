"""merge — combine pipeline results into scored_jobs.json, the ONE source of truth.

CRITICAL RULE:
  scored_jobs.json is the single source of truth. The pipeline NEVER deletes jobs.
  Manually-added jobs (those carrying an `initial_status` field) are preserved untouched.
  Final set = everything already saved  +  newly found pipeline jobs that pass the filter.
"""
from __future__ import annotations

from .common import days_old, job_id, log, today


def passes_filter(job: dict, config: dict) -> bool:
    f = config["filters"]
    if int(job.get("fit_score", 0)) < f["min_score"]:
        return False
    if not job.get("location_ok", False):
        return False
    age = days_old(job.get("posted"))
    if age is not None and age > f["max_age_days"]:
        return False  # unparseable dates (age is None) are allowed through
    return True


def merge(existing: list[dict], found: list[dict], config: dict) -> list[dict]:
    by_id: dict[str, dict] = {}
    for job in existing:
        jid = job.get("id") or job_id(job.get("url", ""), job.get("company", ""), job.get("title", ""))
        job["id"] = jid
        by_id[jid] = job

    manual_count = sum(1 for j in existing if j.get("initial_status"))
    added, updated, skipped = 0, 0, 0

    for job in found:
        jid = job_id(job.get("url", ""), job.get("company", ""), job.get("title", ""))
        if not passes_filter(job, config):
            skipped += 1
            continue
        if jid in by_id:
            prev = by_id[jid]
            # Never touch a manually-added job's identity/state — only refresh score fields.
            for k in ("fit_score", "score_reason", "ai_opener", "location_ok", "description", "posted", "location"):
                if job.get(k) not in (None, ""):
                    prev[k] = job[k]
            prev["last_seen"] = today()
            updated += 1
        else:
            job["id"] = jid
            job["first_seen"] = today()
            job["last_seen"] = today()
            by_id[jid] = job
            added += 1

    log.info(
        "merge: %d added, %d updated, %d skipped(filtered); %d manual preserved; %d total",
        added, updated, skipped, manual_count, len(by_id),
    )
    # Sort: highest fit first, then most recently seen.
    return sorted(
        by_id.values(),
        key=lambda j: (int(j.get("fit_score", 0)), j.get("last_seen", "")),
        reverse=True,
    )
