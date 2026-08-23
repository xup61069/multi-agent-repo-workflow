# Reusable Goal prompts

Replace bracketed text with a named milestone. A long-running Goal is not an unlimited backlog: it still needs one outcome, a validation loop, and a stopping or pause condition.

## Long-running integrator

```text
/goal Move [project] to its accepted release criteria. Read the repository instructions, current baseline, and active handoffs first. Maintain a verifiable gap list and advance one non-overlapping milestone at a time; coordinate specialists and only implement work whose write scope is explicitly assigned to this window. Report product change, user impact, verification, and remaining gaps before any Git audit details. Continue until every accepted criterion passes, or pause for a maintainer decision, external account or cost, hardware or machine-changing action, ownership conflict, or genuine blocker.
```

## Assigned specialist

```text
/goal Complete the named milestone [milestone] within its assigned write scope. Read the repository rules, handoff, relevant specification, source, tests, and evidence before editing. Do not expand into another writer's files or public contract. Verify the milestone with the project's relevant checks and explain the result in plain product language before a short development record. Stop when acceptance passes or when a product decision, scope expansion, external authority, or unsafe action is required.
```

## Independent verifier

```text
/goal Independently determine whether [milestone] on the current integration branch really satisfies its accepted user outcome. Stay read-only by default, reproduce the behavior, run relevant checks, distinguish simulated evidence from target-environment evidence, and deliver a pass or fail conclusion with user impact and the smallest next action. Do not take over the fix unless the maintainer separately assigns it.
```

## Workflow maintainer

```text
/goal Audit this repository's AI instructions and collaboration workflow for contradictions, unnecessary ceremony, stale commands, missing ownership boundaries, and unverifiable claims. Preserve concrete safety, legal, privacy, compatibility, and evidence invariants; simplify defaults and gates that do not match current risk. Validate every changed instruction and stop after delivering a coherent, repository-backed workflow with documented remaining decisions.
```
