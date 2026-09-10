# CLAUDE.md

Guidance for Claude Code when working in this repo.

## What this repo is

`devops-tashtiot/devops-tashtiot.github.io` — the devops-tashtiot org's landing zone, published via GitHub Pages at https://devops-tashtiot.github.io/. It is two things in one repo:

1. A static landing page (`index.html` + `repos.json`) showing a card per repo in the org, grouped into sections (Devtools IaC + GitOps, Platform, CI/CD, SaaS, Automation, AWS Environment & Governance).
2. An MkDocs Material technical documentation site (`docs-src/`, built to `/docs/`).

Both are built and deployed together to the `gh-pages` branch by `.github/workflows/docs.yml` on every push to `main`.

**Never rename this repo.** GitHub requires the exact name `devops-tashtiot.github.io` to serve it as the org's root Pages site; renaming breaks the live URL.

**Never put account-specific security/architecture detail in `docs-src/` or `repos.json`.** This site is public. Real SCP policy IDs, real resource IDs (VPC/subnet/NAT/IGW/etc.), which security detections are or aren't enabled, real internal hostnames — none of that belongs here. That content lives in the private `devops-tashtiot/aws-internal-docs` repo instead. If in doubt about whether something is sensitive, ask before publishing it, don't publish first and reconsider later.

## Adding a repo card to the homepage

Edit `repos.json`, not `index.html`. Each entry needs `name`, `url`, `icon` (single emoji), and `description` (what it does + how it relates to sibling repos in its section — these descriptions are read by people unfamiliar with the org). No `tags` field anymore — a card's color (green/yellow) comes from the repo's actual GitHub topics (`in-progress`), fetched into `status.json` at deploy time, not from anything in `repos.json`. Add a new section by adding a new object to `sections` with a `name` and a `repos` array. There is a slash command for this: `.claude/commands/add-github-pages-section.md`.

## Adding/updating technical docs

Add Markdown files under `docs-src/`, and register the page in `mkdocs.yml`'s `nav:` block — pages not listed in `nav` won't appear in the site navigation even if built. There is a slash command for pulling documentable content out of a conversation: `.claude/commands/update-github-docs.md`.

## Local build/test

```bash
pip install -r requirements.txt
mkdocs serve      # live-reload docs at /docs/
# index.html is plain static HTML — just open it in a browser, or serve the repo root with any static server
```

## Deploy

Nothing to do manually — push to `main` (or wait for the every-6-hours schedule) and `.github/workflows/docs.yml` builds MkDocs, regenerates `status.json` via `scripts/generate_status.py`, and force-pushes `index.html`, `repos.json`, `status.json`, and the built `docs/` to `gh-pages` (orphan history, so `gh-pages` has no relation to `main`'s history).
