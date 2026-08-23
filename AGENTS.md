# Multi-Agent Repo Workflow contributor rules

Read `README.md`, `skills/multi-agent-repo-workflow/SKILL.md`, and the relevant reference or script before changing behavior.

## Non-negotiable

- Keep the toolkit project-neutral. Product-specific safety, platform, licensing, account, and release rules belong in the adopting repository.
- Preserve user authorization boundaries. Read-only inspection never implies permission for GitHub writes, branch creation, installation, purchases, or machine changes.
- Bootstrap and validation scripts must be deterministic, dependency-free, path-safe, and non-destructive by default.
- Do not silently overwrite existing project instructions. Managed edits need explicit markers, preflight, and an opt-in overwrite path.

## Product defaults

- `adaptive` is the recommended mode; `solo` and `strict` remain supported choices.
- The Codex Skill should guide judgment instead of turning every example into a universal rule.
- Maintainer-facing reports lead with outcome, user impact, verification, and remaining gaps. Git mechanics are trailing audit details when relevant.
- Keep `SKILL.md` concise. Put conditional detail in `references/` and generated boilerplate in `assets/`.

## Validation

Run after any behavior change:

```shell
python -m unittest discover -s tests -v
```

Also run the Codex skill validator when its runtime dependency is available:

```shell
python /path/to/skill-creator/scripts/quick_validate.py skills/multi-agent-repo-workflow
```
