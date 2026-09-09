# CLAUDE.md

Guidance for Claude Code when working in this repo.

## What this repo is

`devops-tashtiot/devops-tashtiot.github.io` — the devops-tashtiot org's landing zone, published via GitHub Pages at https://devops-tashtiot.github.io/. It is two things in one repo:

1. A static landing page (`index.html` + `repos.json`) showing a card per repo in the org, grouped into sections (Devtools IaC + GitOps, Platform, CI/CD, SaaS, Automation, AWS Env Limits & Permissions).
2. An MkDocs Material technical documentation site (`docs-src/`, built to `/docs/`) covering AWS architecture, IAM, VPC, governance, etc.

Both are built and deployed together to the `gh-pages` branch by `.github/workflows/docs.yml` on every push to `main`.

**Never rename this repo.** GitHub requires the exact name `devops-tashtiot.github.io` to serve it as the org's root Pages site; renaming breaks the live URL.

## Adding a repo card to the homepage

Edit `repos.json`, not `index.html`. Each entry needs `name`, `url`, `icon` (single emoji), `description` (what it does + how it relates to sibling repos in its section — these descriptions are read by people unfamiliar with the org), and `tags`. Add a new section by adding a new object to `sections` with a `name` and a `repos` array. There is a slash command for this: `.claude/commands/add-github-pages-section.md`.

## Adding/updating technical docs

Add Markdown files under `docs-src/`, and register the page in `mkdocs.yml`'s `nav:` block — pages not listed in `nav` won't appear in the site navigation even if built. There is a slash command for pulling documentable content out of a conversation: `.claude/commands/update-github-docs.md`.

## Local build/test

```bash
pip install -r requirements.txt
mkdocs serve      # live-reload docs at /docs/
# index.html is plain static HTML — just open it in a browser, or serve the repo root with any static server
```

## Deploy

Nothing to do manually — push to `main` and `.github/workflows/docs.yml` builds MkDocs and force-pushes `index.html`, `repos.json`, `vpc-architecture.html`, and the built `docs/` to `gh-pages` (orphan history, so `gh-pages` has no relation to `main`'s history).
