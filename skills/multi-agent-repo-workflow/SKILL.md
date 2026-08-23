---
name: multi-agent-repo-workflow
description: Bootstrap, audit, or simplify repository-backed multi-agent coding workflows. Use when a project needs durable AI instructions, scoped parallel ownership, handoffs, validation gates, or reusable agent roles; do not use for ordinary feature implementation.
---

# Multi-Agent Repo Workflow

Build the lightest collaboration system that prevents the project's actual failure modes.

## Choose a mode

- Use `solo` when one writer is active and overlap is not plausible. Keep durable instructions and scoped validation; skip claim ceremony.
- Use `adaptive` by default. Escalate to explicit claims and isolated workspaces only when another writer is active, a branch is occupied, or ownership is uncertain.
- Use `strict` when concurrent writers are expected. Require one independently verifiable task, branch, workspace, handoff, exclusive scope, and review surface per writer.

Do not infer that a more restrictive mode is better. A rule belongs in the workflow only when it prevents a concrete safety, correctness, privacy, licensing, release, or coordination failure.

## Workflow

1. Inspect the repository before proposing files: current instructions, Git state, active work, CI, build/test commands, architecture records, sensitive paths, and the maintainer's reporting preferences.
2. Read [policy-model.md](references/policy-model.md) when defining or simplifying constraints. Separate non-negotiable invariants, changeable product defaults, and scope-triggered validation.
3. Read [collaboration.md](references/collaboration.md) when parallel writers, worktrees, task claims, integration ownership, takeovers, or conflicts are in scope.
4. Read [adoption.md](references/adoption.md) before changing an existing repository or selecting `solo`, `adaptive`, or `strict`.
5. Preview generation with `scripts/bootstrap.py ... --dry-run`. Preserve existing instructions; use `--merge-agents` only when appending the marked block is appropriate. Never use `--force` without reviewing every destination that will be replaced.
6. Replace generic examples with the repository's real authority order, safe actions, validation commands, shared integration paths, and evidence boundaries.
7. Run `scripts/validate_setup.py`. When handoffs are used, read [handoff-format.md](references/handoff-format.md) and run `scripts/handoff_check.py` against fixtures or live read-only issue data.
8. Run the adopting repository's relevant checks. Do not claim a queued check passed or let a smoke test stand in for a different environment or product layer.

Use [goal-prompts.md](references/goal-prompts.md) only when the user wants ready-to-paste agent window or long-running Goal prompts.

## Boundaries

- Repository inspection and dry runs are read-only. Do not create repositories, issues, branches, worktrees, pull requests, or external messages unless the user requested those writes.
- Never copy product-specific legal, hardware, signing, privacy, platform, or release constraints into another project without evidence that they apply.
- Treat `scope_globs` as exclusive write intent and `shared_paths` as coordination signals, not permission for concurrent edits.
- Keep user-facing updates outcome-first: product change, user impact, verification, remaining gaps, then a short Git audit tail only when useful.
- Stop for overlapping claims, contradictory authoritative documents, destructive or costly actions, missing external authority, or a material expansion of scope.
