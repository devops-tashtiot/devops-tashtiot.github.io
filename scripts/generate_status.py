#!/usr/bin/env python3
"""Build status.json: open-issue count and "in-progress" flag for every repo
this landing page links to, using the workflow's authenticated GH_TOKEN
(5000 req/hour) instead of making visitors hit the unauthenticated GitHub
API (60 req/hour, shared per IP) from their own browser.

Issue count uses the Search API with `type:issue` rather than the repo
object's `open_issues_count`, since that field counts open pull requests
too (a PR is internally a kind of issue) and would otherwise show a
count with nothing to find in the repo's actual Issues tab.
"""
import json
import subprocess
import urllib.parse

EXTRA_REPOS = [
    "Platform-Infra-Org/apis-library",
]


def gh_json(path):
    out = subprocess.check_output(["gh", "api", path])
    return json.loads(out)


def open_issue_count(full):
    q = urllib.parse.quote(f"repo:{full} type:issue state:open")
    return gh_json(f"search/issues?q={q}").get("total_count", 0)


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
        try:
            issues = open_issue_count(full)
        except subprocess.CalledProcessError:
            issues = 0
        status[full] = {
            "issues": issues,
            "wip": "in-progress" in topics,
        }

    with open("status.json", "w") as f:
        json.dump(status, f, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
