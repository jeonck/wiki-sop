# IT SOP Wiki

An **agent-ready** Standard Operating Procedure (SOP) knowledge base for IT
operations (AIOps). Written for humans, structured for machines.

- **Site:** https://jeonck.github.io/wiki-sop/
- **Stack:** [Hugo](https://gohugo.io/) + [Hextra](https://github.com/imfing/hextra) theme
- **Content:** Markdown + YAML frontmatter, versioned in Git

## Why this exists

Each SOP is a single Markdown file with two layers:

1. **Frontmatter** — machine-readable metadata (`sop_id`, `symptoms`,
   `severity`, `verification_metrics`, `escalation`) that an AIOps agent uses to
   match incoming error logs and generate incident reports.
2. **Body** — a human runbook in a fixed order: Situation → Symptoms →
   Diagnosis → Action → Verification → Escalation → Prevention.

The static site is only the human view; the agent indexes the raw `.md` directly
via `git pull` — no API, no scraping.

## Repository layout

```
content/docs/
  getting-started.md      # how to read/write/validate SOPs
  agent.md                # how agents consume the wiki
  sop/<category>/*.md     # the SOP library (DB, API, INFRA, NETWORK, SECURITY)
templates/SOP-TEMPLATE.md # canonical template for new SOPs
schema/sop.schema.json    # frontmatter contract (enforced in CI)
scripts/validate_sops.py  # local + CI validator
```

## Local development

```bash
# Clone with the theme submodule
git clone --recurse-submodules https://github.com/jeonck/wiki-sop.git
cd wiki-sop

# Run the site (Hugo Extended required)
hugo server -D
# → http://localhost:1313/wiki-sop/

# Validate SOP frontmatter
pip install pyyaml jsonschema
python scripts/validate_sops.py
```

## Writing a new SOP

1. Copy `templates/SOP-TEMPLATE.md` to `content/docs/sop/<category>/<SOP-ID>-<slug>.md`.
2. Assign the next free `sop_id` (e.g. `DB-003`).
3. Fill every required frontmatter field — CI rejects incomplete SOPs.
4. Open a PR. The **Validate SOP frontmatter** workflow runs automatically.

## Deployment

Pushing to `main` triggers the **Deploy Hugo to GitHub Pages** workflow.
Set the repo's Pages source to **GitHub Actions**.
