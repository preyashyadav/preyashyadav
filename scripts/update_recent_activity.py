#!/usr/bin/env python3
"""Update the profile README with selected public GitHub activity."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


USERNAME = "preyashyadav"
MAX_ITEMS = 4
MAX_AGE_DAYS = 365
README = Path(__file__).resolve().parents[1] / "README.md"
START = "<!--START_SECTION:activity-->"
END = "<!--END_SECTION:activity-->"
EXCLUDED_REPOSITORIES = {
    "milaabl/readme-chess",
    "preyashyadav/preyashyadav",
    "preyashyadav/leetcode",
}
IGNORED_TITLE_PHRASES = ("backup", "do not merge", "chess: move", "wip")
ACTIVITY_OVERRIDES = {
    "https://github.com/anthropics/claude-code/issues/78988": (
        "Reported a reproducible macOS configuration-path bug with detailed impact analysis."
    ),
    "https://github.com/Pasternack-Lab/RiverBuilder/pull/7": (
        "Shipped RiverBuilder v1.3 cross-section features and bug fixes."
    ),
}


def github_search(query: str, token: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {"q": query, "sort": "created", "order": "desc", "per_page": 20}
    )
    request = urllib.request.Request(
        f"https://api.github.com/search/issues?{params}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": f"{USERNAME}-profile-readme",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["items"]


def repository_name(item: dict) -> str:
    return item["repository_url"].removeprefix("https://api.github.com/repos/")


def markdown_title(title: str) -> str:
    compact = " ".join(title.split())
    if len(compact) > 120:
        compact = compact[:117].rstrip() + "…"
    return compact.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def is_external_and_recent(item: dict, cutoff: datetime) -> bool:
    repository = repository_name(item)
    owner = repository.split("/", 1)[0].lower()
    created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
    title = item["title"].lower()
    is_merged_pr = (
        "pull_request" not in item
        or item["pull_request"].get("merged_at") is not None
    )
    return (
        repository.lower() not in EXCLUDED_REPOSITORIES
        and owner != USERNAME.lower()
        and created >= cutoff
        and is_merged_pr
        and not any(phrase in title for phrase in IGNORED_TITLE_PHRASES)
    )


def format_item(item: dict) -> str:
    repository = repository_name(item)
    url = item["html_url"]
    title = ACTIVITY_OVERRIDES.get(url, markdown_title(item["title"]))
    if "pull_request" in item:
        merged = item["pull_request"].get("merged_at") is not None
        status = "merged" if merged else item["state"]
        kind = "Pull request"
    else:
        status = item["state"]
        kind = "Issue"
    return f"- **{kind} · {status} · [{repository}]({url})** — {title}"


def update_readme(lines: list[str]) -> bool:
    content = README.read_text(encoding="utf-8")
    if START not in content or END not in content:
        raise RuntimeError("README activity markers are missing")
    replacement = START + "\n" + "\n".join(lines) + "\n" + END
    updated = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        replacement,
        content,
        flags=re.DOTALL,
    )
    if updated == content:
        return False
    README.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 2

    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    base = f"author:{USERNAME} archived:false"
    try:
        results = github_search(f"{base} is:pr", token)
        results += github_search(f"{base} is:issue", token)
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as error:
        print(f"Unable to retrieve GitHub activity: {error}", file=sys.stderr)
        return 1

    selected = [item for item in results if is_external_and_recent(item, cutoff)]
    selected.sort(key=lambda item: item["created_at"], reverse=True)
    unique_repositories: list[dict] = []
    seen_repositories: set[str] = set()
    for item in selected:
        repository = repository_name(item).lower()
        if repository in seen_repositories:
            continue
        seen_repositories.add(repository)
        unique_repositories.append(item)
    lines = [format_item(item) for item in unique_repositories[:MAX_ITEMS]]
    if not lines:
        print("No qualifying external activity found; preserving the current README section.")
        return 0

    changed = update_readme(lines)
    print("Updated recent public activity." if changed else "Recent public activity is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
