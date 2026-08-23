# Adoption guide

## Existing repository

1. Inspect current `AGENTS.md`, contributor docs, CI, test commands, architecture records, active branches, and uncommitted work.
2. Preserve existing instructions. Use the bootstrapper's `--merge-agents` only after reviewing the marked block it will append.
3. Start in `solo` or `adaptive` unless simultaneous writers already exist.
4. Replace generated examples with real project commands. Do not invent gates or product claims.
5. Identify high-conflict registries, lockfiles, aggregate tests, release files, and global snapshots; name an integrator only for those paths.
6. Validate locally before enabling repository branch rules or required checks.

If existing instructions and the proposed workflow disagree, stop and present the smallest policy decision. Do not overwrite the existing file with `--force` merely to make validation pass.

## New repository

Generate the starter in `adaptive` mode, write the first accepted product specification, and keep the always-run gate minimal. Add strict task claims only when a second writer starts.

## Mode changes

### Solo to adaptive

Add a task tracker or handoff location, exclusive scopes, and an isolation decision. Existing solo work does not need retroactive issues.

### Adaptive to strict

Before starting another writer, materialize every active write slice, assign owners, check scope and semantic overlap, choose shared-path owners, and create isolated workspaces. Do not infer ownership from a common account.

### Strict to adaptive or solo

Finish or close active claims, preserve useful evidence, then remove ceremony that no longer prevents a live risk. Do not delete historical decisions or evidence merely because concurrency ended.

## GitHub integration

The starter issue form stores a JSON handoff block in the issue body. Suggested labels are `claimed` and `in-review`; closed means done. A draft pull request begins after the first reproducible checkpoint, not before the edits required to create it.

Branch protection and required CI are repository settings. Documentation may recommend them but must not claim they are enabled without reading the live setting.

All scripts in this skill are read-only with respect to GitHub. Repository, issue, label, branch, pull-request, and settings changes require a separate explicit user request.
