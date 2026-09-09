# devops-tashtiot.github.io

Landing zone of the **devops-tashtiot** organization — a static homepage with cards and explanations for every repo in the org, plus a technical documentation site.

Live at **https://devops-tashtiot.github.io/**

> The repo name must stay exactly `devops-tashtiot.github.io` — GitHub only serves an org's root Pages site from a repo with that exact name. Renaming it breaks the URL above.

## What's in here

- **`index.html`** — the landing page. A single static HTML/CSS/JS file that renders repo cards grouped by section, reading its data from `repos.json`.
- **`repos.json`** — the source of truth for the landing page: org tagline plus a list of sections, each with repos (`name`, `url`, `icon`, `description`, `tags`). Add or edit a card by editing this file — no HTML changes needed.
- **`docs-src/`** + **`mkdocs.yml`** — a separate [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) technical docs site (AWS architecture, IAM, VPC, governance notes, etc.), served at `/docs/`.
- **`vpc-architecture.html`** — a standalone static diagram page linked from the docs.
- **`.github/workflows/docs.yml`** — on every push to `main`, builds the MkDocs site and deploys `index.html`, `repos.json`, `vpc-architecture.html`, and the built docs together to the `gh-pages` branch (`peaceiris/actions-gh-pages`, `force_orphan: true`).
- **`.claude/commands/`** — Claude Code slash commands for maintaining this repo:
  - `add-github-pages-section.md` — add a new section/repo card to the homepage.
  - `update-github-docs.md` — pull new technical content out of a conversation and add it to the MkDocs docs.

## Updating the homepage

Edit `repos.json` (add a repo/section) or `index.html` (layout/style), commit to `main`, and the GitHub Actions workflow republishes automatically.

## Updating the docs

Add/edit Markdown under `docs-src/`, register new pages in `mkdocs.yml`'s `nav`, commit to `main` — the workflow rebuilds and republishes `/docs/`.

See also [`CLAUDE.md`](./CLAUDE.md) for guidance on working in this repo with Claude Code.
