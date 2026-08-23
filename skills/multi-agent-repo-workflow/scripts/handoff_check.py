#!/usr/bin/env python3
"""驗證 issue 內容交接、範圍重疊和選用的本地 Git 狀態。"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

MARKER_PATTERN = re.compile(
    r"<!--\s*agent-workflow:handoff-v1\s*(.*?)\s*-->", re.DOTALL
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


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="驗證多代理任務交接")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file", help="包含單一交接區塊的 Markdown 檔案")
    source.add_argument("--issues-json", help="GitHub issue 物件的 JSON 陣列")
    source.add_argument(
        "--github", action="store_true", help="唯讀查詢 GitHub 開放中 issue"
    )
    parser.add_argument("--repo", help="--github 使用的 OWNER/REPO")
    parser.add_argument("--issue", type=int, help="對照本地 Git 驗證的任務")
    parser.add_argument(
        "--mode",
        choices=("solo", "adaptive", "strict"),
        default="adaptive",
        help="套用的協作模式（預設：adaptive）",
    )
    parser.add_argument("--check-git", action="store_true", help="檢查目前 Git 工作區")
    parser.add_argument("--json-output", action="store_true", help="以 JSON 輸出結果")
    return parser.parse_args(argv)


def run(
    command: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError(f"JSON 欄位重複：{key}")
        parsed[key] = value
    return parsed


def load_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=reject_duplicate_keys)


def extract_block(text: str) -> dict[str, Any]:
    matches = MARKER_PATTERN.findall(text)
    if len(matches) != 1:
        raise ValueError(f"預期恰好一個交接區塊，找到 {len(matches)} 個")
    try:
        parsed = load_json(matches[0])
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"交接 JSON 無效：{exc}") from exc
    if not isinstance(parsed, dict):
        raise TypeError("交接根必須是物件")
    return parsed


def normalize_pattern(raw: str) -> str:
    value = raw.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"範圍必須是非空儲存庫相對模式：{raw!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"範圍不得包含空白、'.' 或 '..' 路徑片段：{raw!r}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"範圍不得包含控制字元：{raw!r}")
    return value


def validate_claim(issue: int, body: dict[str, Any], mode: str) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - body.keys())
    if missing:
        errors.append(f"issue #{issue}：缺少欄位：{', '.join(missing)}")
        return errors
    unknown = sorted(body.keys() - REQUIRED_FIELDS)
    if unknown:
        errors.append(f"issue #{issue}：含有未知欄位：{', '.join(unknown)}")
    if body.get("schema_version") != 1 or isinstance(body.get("schema_version"), bool):
        errors.append(f"issue #{issue}：schema_version 必須為 1")
    handoff_issue = body.get("issue")
    if (
        not isinstance(handoff_issue, int)
        or isinstance(handoff_issue, bool)
        or handoff_issue < 0
        or handoff_issue != issue
    ):
        errors.append(f"issue #{issue}：交接 issue 值必須與任務編號一致")
    if body.get("status") not in VALID_STATUSES:
        errors.append(f"issue #{issue}：無效狀態 {body.get('status')!r}")
    for key in (
        "branch",
        "target_branch",
        "base_commit",
        "owner",
        "role",
        "next_safe_action",
    ):
        if not isinstance(body.get(key), str) or not body[key].strip():
            errors.append(f"issue #{issue}：{key} 必須是非空字串")
    base_commit = body.get("base_commit")
    if isinstance(base_commit, str) and len(base_commit.strip()) < 7:
        errors.append(f"issue #{issue}：base_commit 至少需要 7 個字元")
    for key in ("scope_globs", "shared_paths", "depends_on", "validation"):
        if not isinstance(body.get(key), list):
            errors.append(f"issue #{issue}：{key} 必須是陣列")

    for key in ("scope_globs", "shared_paths"):
        patterns = body.get(key)
        if not isinstance(patterns, list):
            continue
        string_patterns = [item for item in patterns if isinstance(item, str)]
        if len(string_patterns) != len(set(string_patterns)):
            errors.append(f"issue #{issue}：{key} 不得有重複條目")
        for raw in patterns:
            if not isinstance(raw, str):
                errors.append(f"issue #{issue}：{key} 條目必須是字串")
                continue
            try:
                normalize_pattern(raw)
            except ValueError as exc:
                errors.append(f"issue #{issue}：{exc}")

    scopes = body.get("scope_globs")
    status = body.get("status")
    if isinstance(scopes, list) and status in ACTIVE_STATUSES and not scopes:
        errors.append(f"issue #{issue}：進行中的認領至少需要一個 scope_glob")

    dependencies = body.get("depends_on")
    if isinstance(dependencies, list):
        integer_dependencies = [
            item
            for item in dependencies
            if isinstance(item, int) and not isinstance(item, bool)
        ]
        if len(integer_dependencies) != len(set(integer_dependencies)):
            errors.append(f"issue #{issue}：depends_on 不得有重複條目")
        for dependency in dependencies:
            if (
                not isinstance(dependency, int)
                or isinstance(dependency, bool)
                or dependency < 1
            ):
                errors.append(f"issue #{issue}：depends_on 條目必須是大於 0 的整數")
            elif dependency == issue:
                errors.append(f"issue #{issue}：depends_on 不得指向自己")

    validation = body.get("validation")
    if isinstance(validation, list):
        for command in validation:
            if not isinstance(command, str) or not command.strip():
                errors.append(f"issue #{issue}：validation 條目必須是非空字串")

    if status in ACTIVE_STATUSES and body.get("owner") == "unassigned":
        errors.append(f"issue #{issue}：進行中的認領不得使用 unassigned 負責人")
    if (
        mode == "strict"
        and status in ACTIVE_STATUSES
        and body.get("branch") == body.get("target_branch")
    ):
        errors.append(f"issue #{issue}：strict 模式進行中的認領不得使用目標分支")
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
    normalized_path = path.replace("\\", "/")
    while normalized_path.startswith("./"):
        normalized_path = normalized_path[2:]
    path_parts = tuple(part for part in normalized_path.split("/") if part)
    pattern_parts = tuple(normalize_pattern(pattern).split("/"))

    @cache
    def matches(path_index: int, pattern_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        current = pattern_parts[pattern_index]
        if current == "**":
            return matches(path_index, pattern_index + 1) or (
                path_index < len(path_parts) and matches(path_index + 1, pattern_index)
            )
        return (
            path_index < len(path_parts)
            and fnmatch.fnmatchcase(path_parts[path_index], current)
            and matches(path_index + 1, pattern_index + 1)
        )

    return matches(0, 0)


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
        if not isinstance(issue, int) or isinstance(issue, bool):
            raise ValueError("交接 issue 必須是整數")
        return [{"number": issue, "body": text}]
    if args.issues_json:
        parsed = load_json(Path(args.issues_json).read_text(encoding="utf-8"))
        if not isinstance(parsed, list):
            raise ValueError("issues JSON 根必須是陣列")
        return parsed
    command = [
        "gh",
        "issue",
        "list",
        "--state",
        "open",
        "--limit",
        "1000",
        "--json",
        "number,body",
    ]
    if args.repo:
        command.extend(["--repo", args.repo])
    result = run(command)
    if result.returncode:
        raise ValueError(
            f"GitHub 讀取失敗：{result.stderr.strip() or result.stdout.strip()}"
        )
    parsed = load_json(result.stdout)
    if not isinstance(parsed, list):
        raise TypeError("GitHub 回應根必須是陣列")
    return parsed


def parse_claims(
    issue_objects: list[dict[str, Any]], mode: str
) -> tuple[list[Claim], list[str]]:
    claims: list[Claim] = []
    errors: list[str] = []
    for item in issue_objects:
        number = item.get("number")
        body_text = item.get("body", "")
        if (
            not isinstance(number, int)
            or isinstance(number, bool)
            or not isinstance(body_text, str)
        ):
            errors.append("issue 物件需要整數 number 和字串 body")
            continue
        if "agent-workflow:handoff-v1" not in body_text:
            continue
        try:
            block = extract_block(body_text)
        except ValueError as exc:
            errors.append(f"issue #{number}：{exc}")
            continue
        errors.extend(validate_claim(number, block, mode))
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
                f"issues #{branches[branch]} 和 #{claim.issue} 認領了相同分支 {branch!r}"
            )
        elif isinstance(branch, str):
            branches[branch] = claim.issue

    for index, first in enumerate(active):
        for second in active[index + 1 :]:
            for first_scope in first.body.get("scope_globs", []):
                for second_scope in second.body.get("scope_globs", []):
                    if not isinstance(first_scope, str) or not isinstance(
                        second_scope, str
                    ):
                        continue
                    try:
                        kind = overlap_kind(first_scope, second_scope)
                    except ValueError:
                        continue
                    kind_zh = {"definite": "確定", "possible": "可能", "none": "無"}[
                        kind
                    ]
                    message = (
                        f"issues #{first.issue}（{first_scope}）與 #{second.issue} "
                        f"（{second_scope}）有{kind_zh}範圍重疊"
                    )
                    if kind == "definite" or (kind == "possible" and mode == "strict"):
                        errors.append(message)
                    elif kind == "possible":
                        warnings.append(message)
    return errors, warnings


def git_output(repo: Path, *arguments: str) -> tuple[int, str]:
    result = run(["git", *arguments], cwd=repo)
    return result.returncode, result.stdout.strip()


def input_paths_in_repo(args: argparse.Namespace, repo: Path) -> set[str]:
    code, root_text = git_output(repo, "rev-parse", "--show-toplevel")
    if code:
        return set()
    root = Path(root_text).resolve()
    ignored: set[str] = set()
    for raw_path in (args.body_file, args.issues_json):
        if not raw_path:
            continue
        source = Path(raw_path).expanduser().resolve()
        if source.is_relative_to(root):
            ignored.add(source.relative_to(root).as_posix())
    return ignored


def check_git_state(
    claim: Claim, repo: Path, ignored_paths: set[str] | None = None
) -> list[str]:
    errors: list[str] = []
    code, branch = git_output(repo, "branch", "--show-current")
    if code or branch != claim.body.get("branch"):
        errors.append(
            f"issue #{claim.issue}：目前分支 {branch!r} 與 "
            f"交接記錄 {claim.body.get('branch')!r} 不一致"
        )
    base = str(claim.body.get("base_commit", ""))
    code, _ = git_output(repo, "cat-file", "-e", f"{base}^{{commit}}")
    if code:
        errors.append(f"issue #{claim.issue}：基準 commit 不可用；請抓取完整歷史")
        return errors
    code, _ = git_output(repo, "merge-base", "--is-ancestor", base, "HEAD")
    if code:
        errors.append(f"issue #{claim.issue}：基準 commit 不是 HEAD 的祖先")
    code, changed_text = git_output(repo, "diff", "--name-only", f"{base}...HEAD")
    if code:
        errors.append(f"issue #{claim.issue}：無法列舉已提交的變更路徑")
        return errors
    code, unstaged_text = git_output(repo, "diff", "--name-only")
    if code:
        errors.append(f"issue #{claim.issue}：無法列舉未暫存的變更路徑")
        return errors
    code, staged_text = git_output(repo, "diff", "--cached", "--name-only")
    if code:
        errors.append(f"issue #{claim.issue}：無法列舉已暫存的變更路徑")
        return errors
    code, untracked_text = git_output(
        repo, "ls-files", "--others", "--exclude-standard"
    )
    if code:
        errors.append(f"issue #{claim.issue}：無法列舉未追蹤路徑")
        return errors
    changed_output = f"{changed_text}\n{unstaged_text}\n{staged_text}\n{untracked_text}"
    changed = {line for line in changed_output.splitlines() if line}
    changed.difference_update(ignored_paths or set())
    scopes = [
        item for item in claim.body.get("scope_globs", []) if isinstance(item, str)
    ]
    for path in sorted(changed):
        if not any(glob_matches(path, pattern) for pattern in scopes):
            errors.append(f"issue #{claim.issue}：變更路徑超出範圍：{path}")
    return errors


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    args = parse_args(argv)
    errors: list[str] = []
    warnings: list[str] = []
    claims: list[Claim] = []
    try:
        if args.repo and not args.github:
            errors.append("--repo 只能搭配 --github")
        if args.issue is not None and not args.check_git:
            errors.append("--issue 只能搭配 --check-git")
        if args.check_git and args.issue is None:
            errors.append("--check-git 需要 --issue")
        if not errors:
            issue_objects = load_issue_objects(args)
            claims, parse_errors = parse_claims(issue_objects, args.mode)
            errors.extend(parse_errors)
            overlap_errors, overlap_warnings = check_overlaps(claims, args.mode)
            errors.extend(overlap_errors)
            warnings.extend(overlap_warnings)
            if args.check_git:
                selected = next(
                    (claim for claim in claims if claim.issue == args.issue),
                    None,
                )
                if selected is None:
                    errors.append(f"issue #{args.issue}：找不到交接")
                else:
                    repo = Path.cwd()
                    errors.extend(
                        check_git_state(
                            selected,
                            repo,
                            input_paths_in_repo(args, repo),
                        )
                    )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    if args.json_output:
        print(
            json.dumps(
                {
                    "status": "fail" if errors else "pass",
                    "claims": len(claims),
                    "errors": errors,
                    "warnings": warnings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for warning in warnings:
            print(f"警告：{warning}")
        for error in errors:
            print(f"錯誤：{error}", file=sys.stderr)
        if not errors:
            print(f"交接檢查通過（{len(claims)} 份交接，{len(warnings)} 個警告）。")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
