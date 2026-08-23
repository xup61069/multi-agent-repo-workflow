# Parallel collaboration

Read this reference only when more than one writer may be active or the user asks for handoffs, task slicing, worktrees, or integration policy.

## Truth hierarchy

A practical default is:

1. accepted product specifications and architecture decisions;
2. source, tests, and reproducible evidence;
3. current integration or baseline status;
4. the active task's handoff and scope;
5. chat history and model memory.

Lower levels must not silently override higher ones. Record a document conflict and stop the overlapping edit when two authoritative sources disagree.

## Roles

- The maintainer sets product intent and authorizes material external or risky actions.
- One orchestrator selects and assigns concurrent slices, dependencies, shared-path owners, and merge order.
- A writer owns one independently verifiable outcome and its exclusive scope.
- An integrator owns shared snapshots, registries, aggregate tests, and cross-slice reconciliation when those paths would otherwise collide.
- A verifier independently checks a named result and stays read-only unless separately assigned a fix.

One person or agent may hold several roles when only one writer is active. Roles are about ownership, not headcount.

## Task slice contract

For strict concurrent work, each active writer needs:

- one named outcome with acceptance criteria;
- one task or issue;
- one non-default branch;
- one isolated checkout when another writer, branch occupancy, or uncertainty exists;
- one handoff block with owner, base, target, exclusive `scope_globs`, `shared_paths`, dependencies, validation, and one next safe action;
- one review surface after the first reproducible work exists.

In adaptive mode, create this machinery only when concurrency appears. Read-only reconnaissance does not need a claim. A direct maintainer assignment is sufficient authority to materialize a task after checking overlap.

## Scope

`scope_globs` announce exclusive write intent. They should be narrow enough to make overlap meaningful and broad enough to include the tests and documentation the outcome must change.

`shared_paths` announce files that need a named integrator or ordered edits. Listing a shared path does not make concurrent writes safe.

`depends_on` records a real contract or merge dependency. Prefer merging a shared contract first, then starting dependent work from the new base. Use stacked work only when waiting would be worse and the dependency is explicit.

Directory lanes are routing hints, not universal locks. Two tasks in one directory can run safely when their files and semantic contracts do not overlap. Two tasks in different directories can still conflict when they change the same public behavior.

## Workspace isolation

- `solo`: a separate worktree is optional.
- `adaptive`: require isolation when another writer is active, the branch is already attached elsewhere, or occupancy cannot be proven.
- `strict`: use a separate clone or worktree for every writer.

Never enter, clean, reset, rebase, build, or commit another active writer's workspace. A shared Git identity does not imply shared ownership.

## Handoff and takeover

Before handing off, the current writer records a reproducible checkpoint, pushes it when external Git use is authorized, updates validation and limitations, names one next safe action, and stops writing. The next writer rereads remote state and the handoff before editing.

If a different session already completed the slice, accept the current remote result, validate it independently, and record the takeover. Do not resurrect stale uncommitted work merely because it existed first.

## Conflict stop conditions

Stop overlapping writes when:

- two active claims overlap in files or public contract meaning;
- a change expands outside its assigned scope;
- a shared path has no single owner or merge order;
- branch, base, handoff, or remote head differs from the recorded state;
- authoritative documents contradict one another.

Report the conflicting tasks, paths or contracts, observed state, and smallest decision needed. Do not solve ownership conflicts by force-pushing or copying another writer's working tree.

## Maintainer reports

The workflow exists to protect development, not dominate the conversation. Report in this order:

1. what capability is being built or fixed;
2. what the user will notice;
3. what was actually verified;
4. what remains or needs a decision;
5. a short branch, review, or CI note only when it changes trust or next action.
