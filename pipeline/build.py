"""build — render docs/index.html from templates/index.template.html with embedded data."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone

from .common import ROOT, load_profile, log

TEMPLATE = ROOT / "templates" / "index.template.html"
DOCS = ROOT / "docs"
OUT = DOCS / "index.html"


def build_site(jobs: list[dict], config: dict) -> None:
    DOCS.mkdir(exist_ok=True)
    html = TEMPLATE.read_text(encoding="utf-8")

    replacements = {
        "__PROFILE_NAME__": config.get("profile_name", "Job Search"),
        "__ROLES__": ", ".join(config.get("roles", [])),
        "__LAST_UPDATED__": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "__JOBS_JSON__": json.dumps(jobs, ensure_ascii=False),
        "__CONFIG_JSON__": json.dumps(config, ensure_ascii=False),
        "__PROFILE_MD__": json.dumps(load_profile(), ensure_ascii=False),
    }
    for key, val in replacements.items():
        html = html.replace(key, val)

    OUT.write_text(html, encoding="utf-8")
    # Keep a copy of the raw data alongside the page for inspection / external tools.
    shutil.copyfile(ROOT / "scored_jobs.json", DOCS / "scored_jobs.json")
    log.info("build: wrote %s (%d jobs embedded)", OUT, len(jobs))
