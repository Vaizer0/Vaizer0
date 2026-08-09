"""Sync the Projects table in README.md with the user's live public repos.

Regenerates the block between PROJECTS:START / PROJECTS:END markers from
https://api.github.com/users/<USER>/repos. Only the profile repo itself is
excluded; forks are shown with their upstream owner/repo. Runs on a schedule
via .github/workflows/sync-readme.yml and is idempotent: it exits with no
commit when nothing changed.
"""
import json
import os
import re
import urllib.request
from pathlib import Path

USER = "Vaizer0"
PROFILE_REPO = "Vaizer0"  # the profile repo itself is never listed
MAX_REPOS = 20

README = Path(__file__).resolve().parent.parent / "README.md"
START = "<!-- PROJECTS:START -->"
END = "<!-- PROJECTS:END -->"
API = f"https://api.github.com/users/{USER}/repos?per_page=100&sort=updated"


def fetch_repos():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_parent(full_name, headers):
    """The list endpoint omits `parent`; fetch it per fork."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{full_name}", headers=headers
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return (json.load(resp).get("parent") or {}).get("full_name")


def row(repo, headers):
    name = repo["name"]
    desc = (repo.get("description") or "").replace("|", "\\|").strip() or "—"
    lang = repo.get("language") or "—"
    if repo.get("fork"):
        try:
            parent = fetch_parent(repo["full_name"], headers)
        except Exception:
            parent = None
        typ = f"🍴 fork of {parent}" if parent else "🍴 fork"
    else:
        typ = "—"
    return f"| [{name}]({repo['html_url']}) | {desc} | {lang} | {typ} |"


def main():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    repos = [r for r in fetch_repos() if r["name"] != PROFILE_REPO]
    repos.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    repos = repos[:MAX_REPOS]

    lines = [row(r, headers) for r in repos]
    table = "\n".join(lines) if lines else "| _No public repositories yet._ | — | — | — |"
    block = f"{START}\n| Repo | Description | Language | Type |\n|---|---|---|---|\n{table}\n{END}"

    readme = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(readme):
        raise SystemExit(f"markers {START}/{END} not found in {README}")
    new_readme = pattern.sub(lambda _: block, readme)
    if new_readme == readme:
        print("No changes")
        return
    README.write_text(new_readme, encoding="utf-8")
    print(f"README.md updated ({len(repos)} repos)")


if __name__ == "__main__":
    main()
