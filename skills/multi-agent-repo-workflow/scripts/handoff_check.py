#!/usr/bin/env python3
"""Validate issue-body handoffs, scope overlap, and optional local Git state."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MARKER_PATTERN = re.compile(
    r"<!--\s*agent-workflow:handoff-v1\s*(\{.*?\})\s*-->", re.DOTALL
)
ACTIVE_STATUSES = {"claimed", "in_review"}
VALID_STATUSES = {"draft", "claimed", "in_review", "done"}
REQUIRED_FIELDS = {
    "schema_version",
    "issue",
    "branch",
    "target_branch",
    "base_commit",
    "owner",
    "role",
    "status",
    "scope_globs",
    "shared_paths",
    "depends_on",
    "validation",
    "next_safe_action",
}
WILDCARD_CHARS = set("*?[")


@dataclass(frozen=True)
class Claim:
    issue: int
    body: dict[str, Any]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate multi-agent task handoffs")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file")
    source.add_argument("--issues-json")
    source.add_argument("--github", action="store_true")
    parser.add_argument("--repo", help="OWNER/REPO for --github")
    parser.add_argument("--issue", type=int, help="Task to validate against local Git")
    parser.add_argument("--mode", choices=("solo", "adaptive", "strict"), default="adaptive")
    parser.add_argument("--check-git", action="store_true")
    parser.add_argument("--json-output", action="store_true")
    return parser.parse_args(argv)


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def extract_block(text: str) -> dict[str, Any]:
    matches = MARKER_PATTERN.findall(text)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one handoff block, found {len(matches)}")
    try:
        parsed = json.loads(matches[0])
    except json.JSONDecodeError as exc:
        raise ValueError(f"handoff JSON is invalid: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("handoff root must be an object")
    return parsed


def normalize_pattern(raw: str) -> str:
    value = raw.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"scope must be a non-empty repository-relative pattern: {raw!r}")
    if any(part == ".." for part in value.split("/")):
        raise ValueError(f"scope must not contain '..': {raw!r}")
    return value


def validate_claim(issue: int, body: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - body.keys())
    if missing:
        errors.append(f"issue #{issue}: missing fields: {', '.join(missing)}")
        return errors
    if body.get("schema_version") != 1:
        errors.append(f"issue #{issue}: schema_version must be 1")
    if body.get("issue") != issue:
        errors.append(f"issue #{issue}: handoff issue value must match the task number")
    if body.get("status") not in VALID_STATUSES:
        errors.append(f"issue #{issue}: invalid status {body.get('status')!r}")
    for key in ("branch", "target_branch", "base_commit", "owner", "role", "next_safe_action"):
        if not isinstance(body.get(key), str) or not body[key].strip():
            errors.append(f"issue #{issue}: {key} must be a non-empty string")
    for key in ("scope_globs", "shared_paths", "depends_on", "validation"):
        if not isinstance(body.get(key), list):
            errors.append(f"issue #{issue}: {key} must be an array")
    scopes = body.get("scope_globs")
    if isinstance(scopes, list):
        if body.get("status") in ACTIVE_STATUSES and not scopes:
            errors.append(f"issue #{issue}: active claim needs at least one scope_glob")
        for raw in scopes:
            if not isinstance(raw, str):
                errors.append(f"issue #{issue}: scope_globs entries must be strings")
                continue
            try:
                normalize_pattern(raw)
            except ValueError as exc:
                errors.append(f"issue #{issue}: {exc}")
    return errors


def literal_prefix(pattern: str) -> tuple[str, ...]:
    parts: list[str] = []
    for part in normalize_pattern(pattern).split("/"):
        if any(char in part for char in WILDCARD_CHARS):
            break
        parts.append(part)
    return tuple(parts)


def has_wildcard(pattern: str) -> bool:
    return any(char in pattern for char in WILDCARD_CHARS)


def glob_matches(path: str, pattern: str) -> bool:
    path = path.replace("\\", "/").lstrip("./")
    pattern = normalize_pattern(pattern)
    if pattern.endswith("/**") and path.startswith(pattern[:-3].rstrip("/") + "/"):
        return True
    return fnmatch.fnmatchcase(path, pattern)


def overlap_kind(first: str, second: str) -> str:
    first = normalize_pattern(first)
    second = normalize_pattern(second)
    if first == second:
        return "definite"
    if not has_wildcard(first) and glob_matches(first, second):
        return "definite"
    if not has_wildcard(second) and glob_matches(second, first):
        return "definite"
    for broad, other in ((first, second), (second, first)):
        if broad.endswith("/**"):
            prefix = tuple(part for part in broad[:-3].rstrip("/").split("/") if part)
            other_prefix = literal_prefix(other)
            if other_prefix[: len(prefix)] == prefix:
                return "definite"
    first_prefix = literal_prefix(first)
    second_prefix = literal_prefix(second)
    common = min(len(first_prefix), len(second_prefix))
    if common and first_prefix[:common] != second_prefix[:common]:
        return "none"
    if first_prefix and second_prefix and first_prefix[0] != second_prefix[0]:
        return "none"
    return "possible"


def load_issue_objects(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.body_file:
        text = Path(args.body_file).read_text(encoding="utf-8")
        body = extract_block(text)
        issue = body.get("issue")
        if not isinstance(issue, int):
            raise ValueError("handoff issue must be an integer")
        return [{"number": issue, "body": text}]
    if args.issues_json:
        parsed = json.loads(Path(args.issues_json).read_text(encoding="utf-8"))
        if not isinstance(parsed, list):
            raise ValueError("issues JSON root must be an array")
        return parsed
    command = [
        "gh",
        "issue",
        "list",
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        "number,body",
    ]
    if args.repo:
        command.extend(["--repo", args.repo])
    result = run(command)
    if result.returncode:
        raise ValueError(f"GitHub read failed: {result.stderr.strip() or result.stdout.strip()}")
    parsed = json.loads(result.stdout)
    if not isinstance(parsed, list):
        raise ValueError("GitHub response root must be an array")
    return parsed


def parse_claims(issue_objects: list[dict[str, Any]]) -> tuple[list[Claim], list[str]]:
    claims: list[Claim] = []
    errors: list[str] = []
    for item in issue_objects:
        number = item.get("number")
        body_text = item.get("body", "")
        if not isinstance(number, int) or not isinstance(body_text, str):
            errors.append("issue objects require integer number and string body")
            continue
        if "agent-workflow:handoff-v1" not in body_text:
            continue
        try:
            block = extract_block(body_text)
        except ValueError as exc:
            errors.append(f"issue #{number}: {exc}")
            continue
        errors.extend(validate_claim(number, block))
        claims.append(Claim(number, block))
    return claims, errors


def check_overlaps(claims: list[Claim], mode: str) -> tuple[list[str], list[str]]:
    active = [claim for claim in claims if claim.body.get("status") in ACTIVE_STATUSES]
    errors: list[str] = []
    warnings: list[str] = []
    branches: dict[str, int] = {}
    for claim in active:
        branch = claim.body.get("branch")
        if isinstance(branch, str) and branch in branches:
            errors.append(
                f"issues #{branches[branch]} and #{claim.issue} claim the same branch {branch!r}"
            )
        elif isinstance(branch, str):
            branches[branch] = claim.issue

    for index, first in enumerate(active):
        for second in active[index + 1 :]:
            for first_scope in first.body.get("scope_globs", []):
                for second_scope in second.body.get("scope_globs", []):
                    if not isinstance(first_scope, str) or not isinstance(second_scope, str):
                        continue
                    try:
                        kind = overlap_kind(first_scope, second_scope)
                    except ValueError:
                        continue
                    message = (
                        f"issues #{first.issue} ({first_scope}) and #{second.issue} "
                        f"({second_scope}) have {kind} scope overlap"
                    )
                    if kind == "definite" or (kind == "possible" and mode == "strict"):
                        errors.append(message)
                    elif kind == "possible":
                        warnings.append(message)
    return errors, warnings


def git_output(repo: Path, *arguments: str) -> tuple[int, str]:
    result = run(["git", *arguments], cwd=repo)
    return result.returncode, result.stdout.strip()


def check_git_state(claim: Claim, repo: Path) -> list[str]:
    errors: list[str] = []
    code, branch = git_output(repo, "branch", "--show-current")
    if code or branch != claim.body.get("branch"):
        errors.append(
            f"issue #{claim.issue}: current branch {branch!r} does not match "
            f"{claim.body.get('branch')!r}"
        )
    base = str(claim.body.get("base_commit", ""))
    code, _ = git_output(repo, "cat-file", "-e", f"{base}^{{commit}}")
    if code:
        errors.append(f"issue #{claim.issue}: base commit is unavailable; fetch full history")
        return errors
    code, _ = git_output(repo, "merge-base", "--is-ancestor", base, "HEAD")
    if code:
        errors.append(f"issue #{claim.issue}: base commit is not an ancestor of HEAD")
    code, changed_text = git_output(repo, "diff", "--name-only", f"{base}...HEAD")
    if code:
        errors.append(f"issue #{claim.issue}: failed to enumerate changed paths")
        return errors
    code, untracked_text = git_output(repo, "ls-files", "--others", "--exclude-standard")
    if code:
        errors.append(f"issue #{claim.issue}: failed to enumerate untracked paths")
        return errors
    changed = {line for line in (changed_text + "\n" + untracked_text).splitlines() if line}
    scopes = [item for item in claim.body.get("scope_globs", []) if isinstance(item, str)]
    for path in sorted(changed):
        if not any(glob_matches(path, pattern) for pattern in scopes):
            errors.append(f"issue #{claim.issue}: changed path is outside scope: {path}")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    errors: list[str] = []
    warnings: list[str] = []
    try:
        issue_objects = load_issue_objects(args)
        claims, parse_errors = parse_claims(issue_objects)
        errors.extend(parse_errors)
        overlap_errors, overlap_warnings = check_overlaps(claims, args.mode)
        errors.extend(overlap_errors)
        warnings.extend(overlap_warnings)
        if args.check_git:
            if args.issue is None:
                errors.append("--check-git requires --issue")
            else:
                selected = next((claim for claim in claims if claim.issue == args.issue), None)
                if selected is None:
                    errors.append(f"issue #{args.issue}: no handoff found")
                else:
                    errors.extend(check_git_state(selected, Path.cwd()))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    if args.json_output:
        print(
            json.dumps(
                {
                    "status": "fail" if errors else "pass",
                    "claims": len(locals().get("claims", [])),
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
            print(
                f"Handoff checks passed ({len(locals().get('claims', []))} claims, "
                f"{len(warnings)} warnings)."
            )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
