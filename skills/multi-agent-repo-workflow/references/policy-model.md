# Policy model

Use three tiers so agents can distinguish real invariants from defaults and validation.

## 1. Non-negotiable invariants

Reserve absolute language for constraints whose violation creates a concrete failure:

- safety or real-time execution properties;
- law, license, privacy, secrets, or restricted data;
- destructive actions and external authorization;
- public compatibility promises that cannot silently break;
- truthful evidence boundaries.

For every proposed invariant, ask: What specific failure does this prevent? Who can change it? What evidence proves it still applies? If those answers are unclear, it is probably not an invariant.

## 2. Product and workflow defaults

Record current choices that may evolve through an accepted decision:

- supported platform, language, framework, or architecture;
- preferred branch and review model;
- naming conventions and repository layout;
- recommended workspace isolation;
- documentation ownership.

State how a default changes, such as a new ADR, accepted specification, maintainer decision, or migration plan. Avoid wording that turns today's architecture into a permanent prohibition.

## 3. Scope-triggered validation

Keep a very small always-run set, then map additional checks to affected risk:

| Change | Typical evidence |
| --- | --- |
| Any tracked edit | format/diff hygiene and repository policy check |
| Public API or schema | contract tests and compatibility evidence |
| Native or performance-critical code | focused unit/integration tests and relevant benchmarks |
| UI behavior | interaction, accessibility, and rendered-state checks |
| Build or toolchain | clean build and reproducibility checks |
| Packaging or release | artifact, signature, provenance, and installer checks |
| Live system behavior | explicit opt-in probe with privacy and machine-state boundaries |

Do not run expensive environment discovery or release-only checks for a documentation edit merely to satisfy ceremony. Conversely, do not use a cheap unit test to claim a hardware, production, accessibility, or release property.

## Compression test

Remove or rewrite a rule when it:

- repeats a higher-priority platform or security policy;
- describes a one-time incident without a reusable decision rule;
- prescribes exact commands where several safe approaches exist;
- requires unavailable infrastructure before ordinary development can begin;
- forces every task through a gate unrelated to its changed risk;
- makes reports longer without changing a decision.

Prefer one durable rule plus a deterministic check over several paragraphs of reminders.
