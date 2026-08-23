#!/usr/bin/env python3
"""Safely install the starter workflow into a repository."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


START_MARKER = "<!-- multi-agent-repo-workflow:start -->"
END_MARKER = "<!-- multi-agent-repo-workflow:end -->"
TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "assets" / "starter"

MODE_POLICIES = {
    "solo": (
        "One writer is expected. Durable instructions and scoped validation apply, "
        "but task claims and isolated workspaces are optional until concurrency appears."
    ),
    "adaptive": (
        "Use lightweight solo operation by default. Require an explicit task claim and "
        "isolated workspace when another writer is active, a branch is occupied, or "
        "ownership is uncertain."
    ),
    "strict": (
        "Concurrent writers are expected. Every writer requires one assigned task, "
        "exclusive scope, non-default branch, isolated workspace, handoff, and review surface."
    ),
}


@dataclass(frozen=True)
class PlannedWrite:
    destination: Path
    content: str
    action: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or install a repository-backed multi-agent workflow."
    )
    parser.add_argument("target", help="Repository directory to configure")
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--mode", choices=sorted(MODE_POLICIES), default="adaptive")
    parser.add_argument("--tracker", choices=("github", "manual"), default="github")
    parser.add_argument("--default-branch", default="main")
    parser.add_argument(
        "--merge-agents",
        action="store_true",
        help="Append or update only the marked workflow block in an existing AGENTS.md",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace differing generated destinations after a full preflight",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def safe_target(raw_target: str) -> Path:
    target = Path(raw_target).expanduser().resolve(strict=False)
    filesystem_root = Path(target.anchor).resolve(strict=False)
    if target == filesystem_root:
        raise ValueError("Refusing to use a filesystem root as the target")
    if target.exists() and (not target.is_dir() or target.is_symlink()):
        raise ValueError("Target must be a real directory, not a file or symlink")
    return target


def render_template(path: Path, values: dict[str, str]) -> str:
    content = path.read_text(encoding="utf-8")
    for key, value in values.items():
        content = content.replace("{{" + key + "}}", value)
    if re.search(r"\{\{[A-Z][A-Z0-9_]*\}\}", content):
        raise ValueError(f"Unresolved template token in {path}")
    return content.rstrip() + "\n"


def destination_for(template: Path, target: Path) -> Path:
    relative = template.relative_to(TEMPLATE_ROOT)
    if relative.suffix != ".tmpl":
        raise ValueError(f"Unexpected template extension: {template}")
    relative = relative.with_suffix("")
    destination = target / relative
    resolved = destination.resolve(strict=False)
    if not resolved.is_relative_to(target):
        raise ValueError(f"Template escapes target directory: {relative}")
    return destination


def merge_agents(existing: str, generated: str, force: bool) -> tuple[str, str]:
    start_count = existing.count(START_MARKER)
    end_count = existing.count(END_MARKER)
    if start_count != end_count or start_count > 1:
        raise ValueError("Existing AGENTS.md has malformed or duplicate managed markers")
    if start_count == 0:
        separator = "" if not existing.strip() else "\n\n"
        return existing.rstrip() + separator + generated, "MERGE"

    start = existing.index(START_MARKER)
    end = existing.index(END_MARKER, start) + len(END_MARKER)
    current_block = existing[start:end].rstrip() + "\n"
    if current_block == generated:
        return existing, "UNCHANGED"
    if not force:
        raise FileExistsError(
            "Managed AGENTS.md block differs; review it and rerun with --force to update"
        )
    combined = existing[:start] + generated.rstrip() + existing[end:]
    return combined.rstrip() + "\n", "UPDATE-BLOCK"


def build_plan(args: argparse.Namespace, target: Path) -> list[PlannedWrite]:
    values = {
        "PROJECT_NAME": args.project_name,
        "WORKFLOW_MODE": args.mode,
        "TASK_TRACKER": args.tracker,
        "DEFAULT_BRANCH": args.default_branch,
        "MODE_POLICY": MODE_POLICIES[args.mode],
    }
    templates = sorted(TEMPLATE_ROOT.rglob("*.tmpl"))
    if not templates:
        raise ValueError(f"No templates found under {TEMPLATE_ROOT}")

    plan: list[PlannedWrite] = []
    conflicts: list[str] = []
    for template in templates:
        relative = template.relative_to(TEMPLATE_ROOT)
        if args.tracker != "github" and relative.parts[0] == ".github":
            continue
        destination = destination_for(template, target)
        generated = render_template(template, values)

        if destination.exists() and destination.is_symlink():
            conflicts.append(f"{destination}: destination is a symlink")
            continue

        if destination.name == "AGENTS.md" and destination.exists() and args.merge_agents:
            try:
                content, action = merge_agents(
                    destination.read_text(encoding="utf-8"), generated, args.force
                )
            except (ValueError, FileExistsError) as exc:
                conflicts.append(f"{destination}: {exc}")
                continue
            plan.append(PlannedWrite(destination, content, action))
            continue

        if not destination.exists():
            plan.append(PlannedWrite(destination, generated, "CREATE"))
            continue

        existing = destination.read_text(encoding="utf-8")
        if existing == generated:
            plan.append(PlannedWrite(destination, existing, "UNCHANGED"))
        elif args.force:
            plan.append(PlannedWrite(destination, generated, "OVERWRITE"))
        else:
            conflicts.append(f"{destination}: already exists with different content")

    if conflicts:
        details = "\n".join(f"  - {item}" for item in conflicts)
        raise FileExistsError(
            "Preflight found conflicts; no files were written. Review them or use an "
            f"explicit merge/overwrite option:\n{details}"
        )
    return plan


def atomic_write(destination: Path, content: str, target: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    target_resolved = target.resolve(strict=True)
    parent_resolved = destination.parent.resolve(strict=True)
    if not parent_resolved.is_relative_to(target_resolved):
        raise ValueError(f"Destination parent escapes target: {destination.parent}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.tmp-", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        if destination.exists() and destination.is_symlink():
            raise ValueError(f"Refusing to replace symlink: {destination}")
        if destination.parent.resolve(strict=True) != parent_resolved:
            raise ValueError(f"Destination parent changed during write: {destination.parent}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        target = safe_target(args.target)
        plan = build_plan(args, target)
    except (OSError, ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for item in plan:
        print(f"{item.action:12} {item.destination}")

    if args.dry_run:
        print(f"Dry run complete: {len(plan)} destinations checked; nothing written.")
        return 0

    try:
        target.mkdir(parents=True, exist_ok=True)
        for item in plan:
            if item.action != "UNCHANGED":
                atomic_write(item.destination, item.content, target)
    except (OSError, ValueError) as exc:
        print(f"error while writing: {exc}", file=sys.stderr)
        return 3

    changed = sum(item.action != "UNCHANGED" for item in plan)
    print(f"Installed workflow for {args.project_name}: {changed} files changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
