# Multi-Agent Repo Workflow

A small, reusable workflow for letting several coding agents work in one repository without sharing stale chat context, overwriting each other, or burying the maintainer in Git mechanics.

The core is tool-neutral. The repository also ships a Codex Skill, starter files, and dependency-free Python checks.

## What it solves

- Durable project instructions live in the repository instead of one chat window.
- Each concurrent writer gets an explicit outcome and exclusive write scope.
- Shared integration files have one owner and an intentional merge order.
- Safety constraints, product defaults, and validation gates are kept separate.
- Validation scales with the change instead of running every expensive check every time.
- Maintainer updates lead with product behavior, user impact, verification, and remaining gaps; branch and PR details stay in a short audit tail.

## Choose the lightest mode that works

| Mode | Use it when | Coordination cost |
| --- | --- | --- |
| `solo` | One writer is active and overlap is not possible | Minimal; durable instructions and scoped validation only |
| `adaptive` | Usually one writer, but parallel windows or machines may appear | Claims and isolated workspaces become required only when concurrency or occupancy is uncertain |
| `strict` | Several writers are expected to run at the same time | One task, branch, workspace, handoff, scope, and review surface per writer |

`adaptive` is the default. Strict process is a tool for real collision risk, not a universal measure of engineering quality.

## Quick start

Preview the files that would be added:

```shell
python skills/multi-agent-repo-workflow/scripts/bootstrap.py /path/to/project \
  --project-name "My Project" --mode adaptive --tracker github --dry-run
```

Apply them:

```shell
python skills/multi-agent-repo-workflow/scripts/bootstrap.py /path/to/project \
  --project-name "My Project" --mode adaptive --tracker github
```

For an existing repository with its own `AGENTS.md`, add only the managed block:

```shell
python skills/multi-agent-repo-workflow/scripts/bootstrap.py /path/to/project \
  --project-name "My Project" --mode adaptive --tracker github --merge-agents
```

Then replace the generic validation examples with the project's real commands and check the installation:

```shell
python skills/multi-agent-repo-workflow/scripts/validate_setup.py /path/to/project
```

The bootstrapper performs a full conflict preflight before writing. It never overwrites an existing file unless `--force` is supplied, and `--dry-run` never writes.

## Codex Skill

The installable skill is in [`skills/multi-agent-repo-workflow`](skills/multi-agent-repo-workflow). Copy that folder into your Codex skills directory, then invoke:

```text
$multi-agent-repo-workflow Set up an adaptive multi-agent workflow for this repository. Preserve existing instructions, derive validation from the real build and CI, and preview every file before writing.
```

The skill can also audit an existing workflow, simplify rules that create ceremony without reducing risk, or upgrade an adaptive project to strict concurrent operation.

## Handoff checks

Task handoffs use a JSON block inside an issue or task description. Validate one saved body:

```shell
python skills/multi-agent-repo-workflow/scripts/handoff_check.py --body-file issue-body.md
```

Validate a saved GitHub issue-list response and detect overlapping scopes:

```shell
python skills/multi-agent-repo-workflow/scripts/handoff_check.py \
  --issues-json open-issues.json --mode strict
```

With GitHub CLI authenticated, `--github --repo OWNER/REPO` reads open issues without changing them. Add `--issue N --check-git` inside the assigned checkout to verify branch, ancestry, and changed paths.

## Design boundaries

- This project does not decide your product architecture, legal constraints, test commands, or release policy.
- It does not make GitHub writes, create branches, install software, or alter a machine unless the user explicitly asks for those actions.
- Worktrees are mandatory only when parallel writers, occupied branches, or uncertain ownership create a concrete collision risk.
- A queued or running check is not a pass, and a smoke test must not be described as evidence for a different layer.
- Long-running goals still need one outcome, a validation loop, and a stopping or pause condition.

## Development

The tools require Python 3.10+ and use only the standard library.

```shell
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance. Licensed under the [MIT License](LICENSE).
