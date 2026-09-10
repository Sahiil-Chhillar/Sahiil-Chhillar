"""Regenerate the RECENT WORK table in README.md from the GitHub API.

Run by .github/workflows/update-readme.yml on a schedule. Rewrites only the
text between the RECENT-PROJECTS markers, so the hand-written parts of the
README are never touched.

Usage:  python scripts/update_readme.py [--user USER] [--count N] [--check]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"
START = "<!-- RECENT-PROJECTS:START -->"
END = "<!-- RECENT-PROJECTS:END -->"

# Repos that are not portfolio pieces (the profile repo itself, forks, etc.).
EXCLUDE = {"Sahiil-Chhillar"}

# Slug -> the name I actually want shown. Anything not listed falls back to
# title-casing the slug, which is fine for well-named repos.
NAME_OVERRIDES = {
    "Attendyy": "Attendyy",
    "attendyy": "Attendyy",
    "PlaceIt": "PlaceIt",
    "placeit": "PlaceIt",
}

# Used only when a repo has no GitHub description. Setting the description on
# GitHub is better -- it shows up in search and on the repo page too -- but this
# keeps the table readable until then.
DESC_FALLBACK = {
    "Attendyy": "Full-stack attendance system using dynamic QR codes and Haversine-based geolocation verification",
    "attendyy": "Full-stack attendance system using dynamic QR codes and Haversine-based geolocation verification",
    "PlaceIt": "Campus placement simulator with an AI interviewer and auto-graded online assessment rounds",
    "placeit": "Campus placement simulator with an AI interviewer and auto-graded online assessment rounds",
}

# Language -> shields.io colour, so the table reads at a glance.
LANG_COLOUR = {
    "Python": "3776AB",
    "TypeScript": "3178C6",
    "JavaScript": "F7DF1E",
    "C++": "00599C",
    "Java": "ED8B00",
    "Go": "00ADD8",
    "Rust": "000000",
    "HTML": "E34F26",
    "CSS": "1572B6",
}


def fetch(url: str) -> list | dict:
    """GET and parse JSON, authenticating when a token is available."""
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-updater",
    })
    # GITHUB_TOKEN lifts the rate limit from 60/hr to 5000/hr in Actions.
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def pretty(name: str) -> str:
    """Turn a repo slug into something a human would read."""
    if name in NAME_OVERRIDES:
        return NAME_OVERRIDES[name]
    cleaned = name.rstrip("-").replace("_", "-")
    words = [w for w in cleaned.split("-") if w]
    if len(words) > 4:
        words = words[:4]
    return " ".join(w if w.isupper() else w.capitalize() for w in words)


def build_rows(repos: list[dict], count: int) -> str:
    """Render the repo list as a centred markdown table."""
    live = [r for r in repos
            if not r["fork"] and not r["archived"] and r["name"] not in EXCLUDE]
    live.sort(key=lambda r: r["pushed_at"], reverse=True)
    chosen = live[:count]

    if not chosen:
        return "<p align=\"center\"><sub>No public repositories yet.</sub></p>"

    lines = [
        "<table align=\"center\">",
        "<tr><th align=\"left\">Project</th><th align=\"left\">What it is</th>"
        "<th align=\"left\">Stack</th><th align=\"left\">Updated</th></tr>",
    ]
    for repo in chosen:
        name = pretty(repo["name"])
        url = repo["html_url"]
        desc = (repo["description"]
                or DESC_FALLBACK.get(repo["name"])
                or "—").strip()
        if len(desc) > 90:
            desc = desc[:87].rstrip() + "…"
        # Escape pipes so a description can never break the table.
        desc = desc.replace("|", "\\|")

        language = repo.get("language")
        if language:
            colour = LANG_COLOUR.get(language, "64748B")
            badge_label = language.replace("-", "--").replace("_", "__").replace(" ", "%20")
            badge_label = badge_label.replace("+", "%2B")
            stack = (f'<img src="https://img.shields.io/badge/{badge_label}-{colour}'
                     f'?style=flat-square&logoColor=white" alt="{language}"/>')
        else:
            stack = "—"

        demo = ""
        if repo.get("homepage"):
            demo = f' · <a href="{repo["homepage"]}">live</a>'

        updated = repo["pushed_at"][:10]
        lines.append(
            f'<tr><td><a href="{url}"><b>{name}</b></a>{demo}</td>'
            f"<td>{desc}</td><td>{stack}</td><td><sub>{updated}</sub></td></tr>"
        )
    lines.append("</table>")
    return "\n".join(lines)


def splice(text: str, block: str) -> str:
    """Replace everything between the markers, keeping the markers."""
    pattern = re.compile(
        re.escape(START) + r".*?" + re.escape(END), re.DOTALL
    )
    replacement = (
        f"{START}\n<!-- This block is generated. Do not edit by hand. -->\n"
        f"{block}\n{END}"
    )
    updated, n = pattern.subn(lambda _: replacement, text)
    if n == 0:
        raise SystemExit(
            f"Markers not found in {README.name}. Expected {START} ... {END}."
        )
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default=os.environ.get("GH_USER", "dhanoliya-ji"))
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the README would change, without writing")
    args = parser.parse_args()

    try:
        repos = fetch(
            f"https://api.github.com/users/{args.user}/repos"
            "?per_page=100&sort=pushed"
        )
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        # A transient API failure must not rewrite the README with nothing.
        print(f"Could not reach the GitHub API: {error}", file=sys.stderr)
        return 1

    if not isinstance(repos, list):
        print(f"Unexpected API response: {repos}", file=sys.stderr)
        return 1

    original = README.read_text(encoding="utf-8")
    updated = splice(original, build_rows(repos, args.count))

    if updated == original:
        print("README already up to date.")
        return 0

    if args.check:
        print("README is out of date.")
        return 1

    README.write_text(updated, encoding="utf-8")
    print(f"README updated with {min(args.count, len(repos))} projects.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
