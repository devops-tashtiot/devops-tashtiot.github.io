Review the current conversation and update the devops-tashtiot MkDocs documentation at `devops-tashtiot/devops-tashtiot.github.io` with any new technical content worth documenting.

## Steps

**1. Scan the conversation for documentable content**

Look for:
- New AWS resources discovered or explained (VPCs, subnets, gateways, firewalls, etc.)
- Architecture decisions and the reasoning behind them
- Traffic flows, routing logic, design patterns
- Tool setups (MkDocs, GitHub Actions, CDK stacks, etc.)
- Anything a future team member would need to understand the infrastructure

Skip:
- Ephemeral debugging steps
- Content already fully covered in existing docs
- Anything that is just Q&A with no lasting technical value

**2. Fetch existing docs structure**

```bash
gh api repos/devops-tashtiot/devops-tashtiot.github.io/git/trees/HEAD --recursive --jq '[.tree[] | select(.path | startswith("docs-src/")) | .path]'
```

Read the relevant existing pages to understand what is already covered before deciding what to add or update.

**3. Determine what to create or update**

- If the topic has no existing page → create a new `.md` file in the appropriate subfolder under `docs-src/`
  - AWS topics → `docs-src/aws/`
  - CI/CD topics → `docs-src/cicd/`
  - Platform topics → `docs-src/platform/`
  - Create the subfolder path if it doesn't exist (GitHub API creates intermediate paths automatically)
- If the topic is partially covered → update the existing page with the new information
- If nothing new → tell the user explicitly and stop

**4. Write the content**

Rules:
- Never include IPs, account IDs, access keys, or any credentials
- Explain WHY, not just WHAT — the reason behind a design decision is more valuable than the fact itself
- Use plain language — write for a DevOps engineer joining the team, not an AWS expert
- Use tables for comparisons, code blocks for commands/configs, and `>` blockquotes for important callouts
- Only document things confirmed from actual data or conversation — no guessing

**5. Update `docs-src/index.md` if new pages were added**

Add the new page to the table in the Home doc so it's discoverable.

**6. Update `mkdocs.yml` nav if new pages were added**

Fetch the current `mkdocs.yml`, add the new page under the correct `nav:` section, and push it.

**7. Push all changes via GitHub API**

Get the SHA of each file before updating:
```bash
gh api repos/devops-tashtiot/devops-tashtiot.github.io/contents/<path> --jq '.sha'
```

Use `--method PUT` with the base64-encoded content and the SHA to update, or omit SHA to create.

Commit message format: `docs: <short description of what was added>`

**8. Report to the user**

Tell the user:
- What pages were created or updated
- A one-line summary of what each page covers
- The live URL once GitHub Actions rebuilds (~1–2 min): `https://devops-tashtiot.github.io/docs/`
