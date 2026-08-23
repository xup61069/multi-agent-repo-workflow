#!/usr/bin/env python3
"""Validate a generated multi-agent repository workflow."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


START_MARKER = "<!-- multi-agent-repo-workflow:start -->"
END_MARKER = "<!-- multi-agent-repo-workflow:end -->"
VALID_MODES = {"solo", "adaptive", "strict"}
VALID_TRACKERS = {"github", "manual"}
REQUIRED_REPORT_ORDER = [
    "product_outcome",
    "user_impact",
    "verification",
    "remaining_gaps",
    "development_audit_when_relevant",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an installed workflow")
    parser.add_argument("target", help="Configured repository directory")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv)


def validate(target: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required = [
        Path("AGENTS.md"),
        Path(".agent-workflow/config.json"),
        Path(".agent-workflow/config.schema.json"),
        Path(".agent-workflow/handoff-v1.schema.json"),
        Path("docs/ai/START_HERE.md"),
        Path("docs/ai/MULTI_AGENT.md"),
        Path("docs/ai/GOALS.md"),
    ]

    managed_paths = list(required)
    for relative in required:
        path = target / relative
        if not path.is_file() or path.is_symlink():
            errors.append(f"missing regular file: {relative.as_posix()}")

    agents_path = target / "AGENTS.md"
    if agents_path.is_file() and not agents_path.is_symlink():
        agents = agents_path.read_text(encoding="utf-8")
        if agents.count(START_MARKER) != 1 or agents.count(END_MARKER) != 1:
            errors.append("AGENTS.md must contain exactly one complete managed marker block")
        elif agents.index(START_MARKER) > agents.index(END_MARKER):
            errors.append("AGENTS.md managed markers are reversed")

    config_path = target / ".agent-workflow/config.json"
    config: dict[str, object] = {}
    if config_path.is_file() and not config_path.is_symlink():
        try:
            parsed = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("root must be an object")
            config = parsed
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid .agent-workflow/config.json: {exc}")

    if config:
        if config.get("schema_version") != 1:
            errors.append("config schema_version must be 1")
        if not isinstance(config.get("project_name"), str) or not config["project_name"].strip():
            errors.append("config project_name must be a non-empty string")
        if config.get("mode") not in VALID_MODES:
            errors.append("config mode must be solo, adaptive, or strict")
        if config.get("task_tracker") not in VALID_TRACKERS:
            errors.append("config task_tracker must be github or manual")
        if not isinstance(config.get("default_branch"), str) or not config["default_branch"].strip():
            errors.append("config default_branch must be a non-empty string")
        pattern = config.get("branch_pattern")
        if not isinstance(pattern, str) or "{issue}" not in pattern or "{slug}" not in pattern:
            errors.append("config branch_pattern must contain {issue} and {slug}")
        if config.get("reporting_order") != REQUIRED_REPORT_ORDER:
            errors.append("config reporting_order must keep outcome-first reporting order")

        validation = config.get("validation")
        if not isinstance(validation, dict):
            errors.append("config validation must be an object")
        else:
            always = validation.get("always_run")
            if not isinstance(always, list) or not all(isinstance(x, str) and x for x in always):
                errors.append("validation.always_run must be a non-empty string array")
            elif always == ["git diff --check"]:
                warnings.append("only the generic diff gate is configured; add real project checks")
            conditional = validation.get("conditional_gates")
            if not isinstance(conditional, list):
                errors.append("validation.conditional_gates must be an array")

        if config.get("task_tracker") == "github":
            for relative in (
                Path(".github/ISSUE_TEMPLATE/agent-task.yml"),
                Path(".github/PULL_REQUEST_TEMPLATE.md"),
            ):
                managed_paths.append(relative)
                path = target / relative
                if not path.is_file() or path.is_symlink():
                    errors.append(f"github tracker requires {relative.as_posix()}")

    for relative in managed_paths:
        path = target / relative
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if re.search(r"\{\{[A-Z][A-Z0-9_]*\}\}", text):
            errors.append(f"unresolved template token in {path.relative_to(target).as_posix()}")

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target = Path(args.target).expanduser().resolve(strict=False)
    errors, warnings = validate(target)
    if args.json_output:
        print(
            json.dumps(
                {
                    "status": "fail" if errors else "pass",
                    "target": str(target),
                    "errors": errors,
                    "warnings": warnings,
                },
                indent=2,
            )
        )
    else:
        for warning in warnings:
            print(f"warning: {warning}")
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if not errors:
            print(f"Workflow setup passed for {target} ({len(warnings)} warnings).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
