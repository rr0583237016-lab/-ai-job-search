"""Shared helpers: config/profile loading, job IDs, dates, logging, JSON I/O."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
PROFILE_PATH = ROOT / "profile.md"
JOBS_PATH = ROOT / "scored_jobs.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_profile() -> str:
    return PROFILE_PATH.read_text(encoding="utf-8")


def load_jobs() -> list[dict]:
    """scored_jobs.json is the ONLY source of truth. Returns [] if missing/empty."""
    if not JOBS_PATH.exists():
        return []
    text = JOBS_PATH.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return json.loads(text)


def save_jobs(jobs: list[dict]) -> None:
    JOBS_PATH.write_text(
        json.dumps(jobs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def normalize_url(url: str) -> str:
    """Strip query/fragment and trailing slash so the same posting hashes identically."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def job_id(url: str, company: str = "", title: str = "") -> str:
    """Stable id. Prefer the normalized URL; fall back to company+title."""
    basis = normalize_url(url) or f"{company.strip().lower()}|{title.strip().lower()}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def parse_date(value: str | None) -> datetime | None:
    """Best-effort parse of a posted date. Accepts ISO and a few common shapes."""
    if not value:
        return None
    value = value.strip()
    # Relative phrases the search model sometimes returns.
    m = re.search(r"(\d+)\s*(day|week|month)s?\s*ago", value.lower())
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        days = n * {"day": 1, "week": 7, "month": 30}[unit]
        return datetime.now(timezone.utc) - timedelta(days=days)
    if value.lower() in ("today", "just posted", "new"):
        return datetime.now(timezone.utc)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d", "%d/%m/%Y", "%d.%m.%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # ISO with timezone
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def days_old(value: str | None) -> int | None:
    dt = parse_date(value)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days


def get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Add it as a GitHub Actions secret "
            "(Settings → Secrets and variables → Actions) or export it locally."
        )
    return key


def extract_json(text: str):
    """Pull the first JSON object/array out of a model response, tolerant of code fences."""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Find the outermost { } or [ ].
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
