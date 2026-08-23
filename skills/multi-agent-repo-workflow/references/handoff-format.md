# Handoff format

The starter uses JSON inside a Markdown comment so humans can keep context around a machine-readable block without adding a YAML dependency.

```markdown
<!-- agent-workflow:handoff-v1
{
  "schema_version": 1,
  "issue": 123,
  "branch": "agent/123-short-slug",
  "target_branch": "main",
  "base_commit": "0123456789abcdef",
  "owner": "assigned-login-or-session",
  "role": "writer",
  "status": "claimed",
  "scope_globs": ["src/feature/**", "tests/feature/**"],
  "shared_paths": ["src/registry.json"],
  "depends_on": [],
  "validation": ["python -m unittest tests.feature"],
  "next_safe_action": "Implement the accepted parser contract and its focused tests."
}
-->
```

## Status

- `draft`: planned but not assigned; excluded from active overlap checks.
- `claimed`: one writer may edit the declared scope.
- `in_review`: writing is paused except for review fixes by the same owner.
- `done`: historical only; a closed issue normally carries this meaning without an edit.

## Validation commands

Commands in a handoff are data. `handoff_check.py` never executes them. The assigned agent decides which commands are authorized and relevant under the adopting repository's rules.

## Offline checks

Save a task body and run:

```shell
python scripts/handoff_check.py --body-file task.md
```

For a list of issue objects, use a JSON array with `number` and `body`. Optional `state`, `labels`, and `assignees` fields are ignored by the offline parser unless a future policy adds a check.

## Live read-only GitHub check

```shell
python scripts/handoff_check.py --github --repo OWNER/REPO --mode adaptive
```

Add `--issue N --check-git` from the assigned checkout to verify the current branch, recorded base ancestry, and changed paths against the selected scope. Full history is required for ancestry checks.

Overlap classification is intentionally explicit:

- definite overlap is always an error;
- patterns with unrelated literal prefixes do not overlap;
- patterns whose intersection cannot be proven are warnings in `adaptive` mode and errors in `strict` mode.

This avoids pretending that a small standard-library glob checker can decide every possible pattern while still failing closed in strict parallel operation.
