Add a new section or subsection to the devops-tashtiot GitHub Pages homepage at `devops-tashtiot/devops-tashtiot.github.io`.

## Usage

```
/add-github-pages-section
```

You can also pass details inline, e.g.:
`/add-github-pages-section Platform / Internal Tools — add repo "deploy-bot"`

## Steps

**1. Fetch the current repos.json**

```bash
gh api repos/devops-tashtiot/devops-tashtiot.github.io/contents/repos.json | jq -r '.content' | base64 -d
gh api repos/devops-tashtiot/devops-tashtiot.github.io/contents/repos.json | jq -r '.sha'
```

Show the user the current sections so they understand what exists.

**2. Ask for any missing details (use AskUserQuestion for each gap)**

Collect:
- **Target section** — is this a new top-level section (e.g. "Security") or a subsection inside an existing one (e.g. "AWS → Monitoring")? If subsection, which parent?
- **Section/subsection name**
- **Repo entries** — for each card:
  - `name` — short repo name (shown as card title)
  - `url` — full GitHub URL or any URL
  - `icon` — a single emoji (e.g. 🔐, 📊, ⚙️)
  - `description` — one sentence describing what it does
  - `tags` — 2–5 short labels (e.g. `["Terraform", "S3", "Bootstrap"]`)

If the user gives you partial info, use sensible defaults for missing fields and tell them what you assumed.

**3. Validate the update**

- A top-level section has a `name` and `repos` array
- A section with subsections has a `name` and `subsections` array — each subsection has a `name` and `repos` array
- Do not mix `repos` and `subsections` in the same section object

**4. Update repos.json and push**

Encode the updated JSON and push:
```bash
gh api repos/devops-tashtiot/devops-tashtiot.github.io/contents/repos.json \
  --method PUT \
  --field message="feat: add <section name> section" \
  --field content="<base64>" \
  --field sha="<current sha>"
```

**5. Confirm**

Tell the user:
- What was added (section name, number of cards)
- Live URL: https://devops-tashtiot.github.io (GitHub Pages rebuilds in ~1 min from the `gh-pages` branch via the Deploy Docs workflow)
