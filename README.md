# devops-tashtiot.github.io

Landing zone of the **devops-tashtiot** organization — a static homepage with cards and explanations for every repo in the org, plus a technical documentation site.

Live at **https://devops-tashtiot.github.io/**

> The repo name must stay exactly `devops-tashtiot.github.io` — GitHub only serves an org's root Pages site from a repo with that exact name. Renaming it breaks the URL above.

## What's in here

- **`index.html`** — the landing page. A single static HTML/CSS/JS file that renders repo cards grouped by section, reading its data from `repos.json` and `status.json`.
- **`repos.json`** — the source of truth for the landing page: org tagline plus a list of sections, each with repos (`name`, `url`, `icon`, `description`). Add or edit a card by editing this file — no HTML changes needed.
- **`status.json`** — generated at deploy time by `scripts/generate_status.py` (open-issue count + "in-progress" GitHub topic per repo); don't edit by hand, it's overwritten on every deploy.
- **`docs-src/`** + **`mkdocs.yml`** — a separate [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) technical docs site, served at `/docs/`.
- **`.github/workflows/docs.yml`** — on every push to `main` (and every 6 hours on a schedule), builds the MkDocs site, regenerates `status.json`, and deploys `index.html`, `repos.json`, `status.json`, and the built docs together to the `gh-pages` branch (`peaceiris/actions-gh-pages`, `force_orphan: true`).
- **`.claude/commands/`** — Claude Code slash commands for maintaining this repo:
  - `add-github-pages-section.md` — add a new section/repo card to the homepage.
  - `update-github-docs.md` — pull new technical content out of a conversation and add it to the MkDocs docs.

## What does NOT belong here

This site is **public**. Never put account-specific security or infrastructure detail here — real SCP policy IDs, real resource IDs, which security detections are/aren't enabled, real internal hostnames, etc. That kind of content lives in the private `devops-tashtiot/aws-internal-docs` repo instead.

## Updating the homepage

Edit `repos.json` (add a repo/section) or `index.html` (layout/style), commit to `main`, and the GitHub Actions workflow republishes automatically.

## Updating the docs

Add/edit Markdown under `docs-src/`, register new pages in `mkdocs.yml`'s `nav`, commit to `main` — the workflow rebuilds and republishes `/docs/`.

See also [`CLAUDE.md`](./CLAUDE.md) for guidance on working in this repo with Claude Code.
