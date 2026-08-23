#!/usr/bin/env python3
"""驗證已產生的多代理儲存庫工作流程。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

START_MARKER = "<!-- multi-agent-repo-workflow:start -->"
END_MARKER = "<!-- multi-agent-repo-workflow:end -->"
VALID_MODES = {"solo", "adaptive", "strict"}
VALID_TRACKERS = {"github", "manual"}
VALID_ACTIVE_STATUSES = {"claimed", "in_review"}
REQUIRED_CONFIG_FIELDS = {
    "schema_version",
    "project_name",
    "mode",
    "task_tracker",
    "default_branch",
    "branch_pattern",
    "handoff_marker",
    "active_statuses",
    "reporting_order",
    "validation",
    "shared_integration_paths",
}
REQUIRED_VALIDATION_FIELDS = {"always_run", "conditional_gates"}
REQUIRED_REPORT_ORDER = [
    "product_outcome",
    "user_impact",
    "verification",
    "remaining_gaps",
    "development_audit_when_relevant",
]


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError(f"JSON 欄位重複：{key}")
        parsed[key] = value
    return parsed


def load_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=reject_duplicate_keys)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="驗證已安裝的工作流程")
    parser.add_argument("target", help="已設定的儲存庫目錄")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 輸出結果",
    )
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
            errors.append(f"缺少一般檔案：{relative.as_posix()}")

    for relative in (
        Path(".agent-workflow/config.schema.json"),
        Path(".agent-workflow/handoff-v1.schema.json"),
    ):
        path = target / relative
        if not path.is_file() or path.is_symlink():
            continue
        try:
            schema = load_json(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{relative.as_posix()} 不是有效的 UTF-8 JSON：{exc}")
            continue
        if not isinstance(schema, dict) or schema.get("type") != "object":
            errors.append(f"{relative.as_posix()} 必須是 object 類型的 JSON Schema")

    agents_path = target / "AGENTS.md"
    if agents_path.is_file() and not agents_path.is_symlink():
        agents = agents_path.read_text(encoding="utf-8")
        if agents.count(START_MARKER) != 1 or agents.count(END_MARKER) != 1:
            errors.append("AGENTS.md 必須包含恰好一個完整的受管理標記區塊")
        elif agents.index(START_MARKER) > agents.index(END_MARKER):
            errors.append("AGENTS.md 受管理標記順序顛倒")

    config_path = target / ".agent-workflow/config.json"
    config: dict[str, object] = {}
    config_read = False
    if config_path.is_file() and not config_path.is_symlink():
        try:
            parsed = load_json(config_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise TypeError("根必須是物件")
            config = parsed
            config_read = True
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            errors.append(f".agent-workflow/config.json 無效：{exc}")

    if config_read:
        missing_fields = sorted(REQUIRED_CONFIG_FIELDS - config.keys())
        unknown_fields = sorted(config.keys() - REQUIRED_CONFIG_FIELDS)
        if missing_fields:
            errors.append(f"config 缺少欄位：{', '.join(missing_fields)}")
        if unknown_fields:
            errors.append(f"config 含有未知欄位：{', '.join(unknown_fields)}")
        if config.get("schema_version") != 1 or isinstance(
            config.get("schema_version"), bool
        ):
            errors.append("config schema_version 必須為 1")
        if (
            not isinstance(config.get("project_name"), str)
            or not config["project_name"].strip()
        ):
            errors.append("config project_name 必須是非空字串")
        if config.get("mode") not in VALID_MODES:
            errors.append("config mode 必須是 solo、adaptive 或 strict")
        if config.get("task_tracker") not in VALID_TRACKERS:
            errors.append("config task_tracker 必須是 github 或 manual")
        if (
            not isinstance(config.get("default_branch"), str)
            or not config["default_branch"].strip()
        ):
            errors.append("config default_branch 必須是非空字串")
        pattern = config.get("branch_pattern")
        if (
            not isinstance(pattern, str)
            or "{issue}" not in pattern
            or "{slug}" not in pattern
        ):
            errors.append("config branch_pattern 必須包含 {issue} 和 {slug}")
        if config.get("handoff_marker") != "agent-workflow:handoff-v1":
            errors.append("config handoff_marker 必須是 agent-workflow:handoff-v1")
        active_statuses = config.get("active_statuses")
        if (
            not isinstance(active_statuses, list)
            or not active_statuses
            or not all(
                isinstance(status, str) and status in VALID_ACTIVE_STATUSES
                for status in active_statuses
            )
            or len(active_statuses) != len(set(active_statuses))
        ):
            errors.append(
                "config active_statuses 必須是由 claimed、in_review 組成的非空且不重複陣列"
            )
        if config.get("reporting_order") != REQUIRED_REPORT_ORDER:
            errors.append("config reporting_order 必須保持結果優先的報告順序")
        shared_paths = config.get("shared_integration_paths")
        if not isinstance(shared_paths, list) or not all(
            isinstance(path, str) and path.strip() for path in shared_paths
        ):
            errors.append("config shared_integration_paths 必須是非空字串陣列")

        validation = config.get("validation")
        if not isinstance(validation, dict):
            errors.append("config validation 必須是物件")
        else:
            missing_validation = sorted(REQUIRED_VALIDATION_FIELDS - validation.keys())
            unknown_validation = sorted(validation.keys() - REQUIRED_VALIDATION_FIELDS)
            if missing_validation:
                errors.append(
                    f"config validation 缺少欄位：{', '.join(missing_validation)}"
                )
            if unknown_validation:
                errors.append(
                    f"config validation 含有未知欄位：{', '.join(unknown_validation)}"
                )
            always = validation.get("always_run")
            if (
                not isinstance(always, list)
                or not always
                or not all(
                    isinstance(command, str) and command.strip() for command in always
                )
            ):
                errors.append("validation.always_run 必須是非空字串陣列")
            elif always == ["git diff --check"]:
                warnings.append("只設定了通用 diff 關卡；請加入真實的專案檢查")
            conditional = validation.get("conditional_gates")
            if not isinstance(conditional, list) or not all(
                isinstance(gate, dict) for gate in conditional
            ):
                errors.append("validation.conditional_gates 必須是物件陣列")

        if config.get("task_tracker") == "github":
            for relative in (
                Path(".github/ISSUE_TEMPLATE/agent-task.yml"),
                Path(".github/PULL_REQUEST_TEMPLATE.md"),
            ):
                managed_paths.append(relative)
                path = target / relative
                if not path.is_file() or path.is_symlink():
                    errors.append(f"github 追蹤器需要 {relative.as_posix()}")

    for relative in managed_paths:
        path = target / relative
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(
                f"{path.relative_to(target).as_posix()} 不是有效的 UTF-8 文字檔：{exc}"
            )
            continue
        if re.search(r"\{\{[A-Z][A-Z0-9_]*\}\}", text):
            errors.append(f"{path.relative_to(target).as_posix()} 中有未解析的模板標記")

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
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
            print(f"工作流程設定通過：{target}（{len(warnings)} 個警告）。")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
