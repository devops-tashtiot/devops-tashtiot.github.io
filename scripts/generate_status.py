#!/usr/bin/env python3
"""Build status.json: open-issue count and "in-progress" flag for every repo
this landing page links to, using the workflow's authenticated GH_TOKEN
(5000 req/hour) instead of making visitors hit the unauthenticated GitHub
API (60 req/hour, shared per IP) from their own browser.
"""
import json
import subprocess

EXTRA_REPOS = [
    "Platform-Infra-Org/apis-library",
]


def gh_json(*args):
    out = subprocess.check_output(["gh", "api", *args])
    return json.loads(out)


def main():
    names = json.loads(
        subprocess.check_output(
            ["gh", "repo", "list", "devops-tashtiot", "--limit", "200", "--json", "name"]
        )
    )
    repos = [f"devops-tashtiot/{n['name']}" for n in names] + EXTRA_REPOS

    status = {}
    for full in repos:
        try:
            data = gh_json(f"repos/{full}")
        except subprocess.CalledProcessError:
            continue
        topics = data.get("topics") or []
        status[full] = {
            "issues": data.get("open_issues_count", 0),
            "wip": "in-progress" in topics,
        }

    with open("status.json", "w") as f:
        json.dump(status, f, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
