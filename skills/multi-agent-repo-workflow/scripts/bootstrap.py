#!/usr/bin/env python3
"""安全地將起始工作流程安裝到儲存庫。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

START_MARKER = "<!-- multi-agent-repo-workflow:start -->"
END_MARKER = "<!-- multi-agent-repo-workflow:end -->"
TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "assets" / "starter"
TOKEN_PATTERN = re.compile(r"{{([A-Z][A-Z0-9_]*)}}")
ACTION_LABELS = {
    "CREATE": "建立",
    "MERGE": "合併",
    "UNCHANGED": "未變更",
    "UPDATE-BLOCK": "更新區塊",
    "OVERWRITE": "覆寫",
}

MODE_POLICIES = {
    "solo": (
        "預期只有一個寫入者。仍須保存專案指令並依變更範圍執行驗證，"
        "但在出現並行作業前，不強制認領任務或隔離工作區。"
    ),
    "adaptive": (
        "預設採用輕量的單人作業。當另一個寫入者正在作業、分支已被使用，"
        "或責任範圍不明時，要求明確認領任務並隔離工作區。"
    ),
    "strict": (
        "預期多個寫入者同時作業。每個寫入者都需要一個指派任務、"
        "獨占範圍、非預設分支、隔離工作區、交接，以及可供審查的變更。"
    ),
}


@dataclass(frozen=True)
class PlannedWrite:
    destination: Path
    content: str
    action: str


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def validate_text_argument(label: str, value: str) -> str:
    if not value.strip():
        raise ValueError(f"{label} 不得為空")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{label} 不得包含換行或控制字元")
    return value


def validate_branch_name(value: str) -> str:
    validate_text_argument("預設分支", value)
    invalid = (
        value == "@"
        or value.startswith(("/", ".", "-"))
        or value.endswith(("/", ".", ".lock"))
        or "//" in value
        or ".." in value
        or "@{" in value
        or "-->" in value
        or chr(96) in value
        or any(
            part.startswith(".") or part.endswith(".lock") for part in value.split("/")
        )
        or re.search(r"[ ~^:?*\[\\]", value)
    )
    if invalid:
        raise ValueError(f"預設分支不是有效且安全的 Git 分支名稱：{value!r}")
    return value


def json_string_content(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="預覽或安裝基於儲存庫的多代理工作流程。"
    )
    parser.add_argument("target", help="要設定的儲存庫目錄")
    parser.add_argument(
        "--project-name", required=True, help="顯示在產生文件中的專案名稱"
    )
    parser.add_argument(
        "--mode",
        choices=sorted(MODE_POLICIES),
        default="adaptive",
        help="協作模式（預設：adaptive）",
    )
    parser.add_argument(
        "--tracker",
        choices=("github", "manual"),
        default="github",
        help="任務追蹤方式（預設：github）",
    )
    parser.add_argument("--default-branch", default="main", help="預設整合分支")
    parser.add_argument(
        "--merge-agents",
        action="store_true",
        help="在現有 AGENTS.md 中只附加或更新標記的工作流程區塊",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="在完整預檢後替換不同的產生目的地",
    )
    parser.add_argument("--dry-run", action="store_true", help="只預演，不寫入檔案")
    parser.add_argument(
        "--show-content",
        action="store_true",
        help="搭配 --dry-run 顯示每個預計寫入檔案的完整內容",
    )
    return parser.parse_args(argv)


def safe_target(raw_target: str) -> Path:
    if not raw_target.strip():
        raise ValueError("目標目錄不得為空")
    target = Path(raw_target).expanduser().resolve(strict=False)
    filesystem_root = Path(target.anchor).resolve(strict=False)
    if target == filesystem_root:
        raise ValueError("拒絕使用檔案系統根目錄作為目標")
    if target.exists() and (not target.is_dir() or target.is_symlink()):
        raise ValueError("目標必須是真實目錄，不能是檔案或符號連結")
    return target


def render_template(path: Path, values: dict[str, str]) -> str:
    content = path.read_text(encoding="utf-8")

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise ValueError(f"{path} 含有未知的模板標記：{key}")
        return values[key]

    return TOKEN_PATTERN.sub(substitute, content).rstrip() + "\n"


def destination_for(template: Path, target: Path) -> Path:
    relative = template.relative_to(TEMPLATE_ROOT)
    if relative.suffix != ".tmpl":
        raise ValueError(f"未預期的模板副檔名：{template}")
    relative = relative.with_suffix("")
    destination = target / relative
    resolved = destination.resolve(strict=False)
    if not resolved.is_relative_to(target):
        raise ValueError(f"模板逃脫了目標目錄：{relative}")
    return destination


def merge_agents(existing: str, generated: str, force: bool) -> tuple[str, str]:
    start_count = existing.count(START_MARKER)
    end_count = existing.count(END_MARKER)
    if start_count != end_count or start_count > 1:
        raise ValueError("現有 AGENTS.md 有格式錯誤或重複的受管理標記")
    if start_count == 0:
        separator = "" if not existing.strip() else "\n\n"
        return existing.rstrip() + separator + generated, "MERGE"

    start = existing.index(START_MARKER)
    end = existing.index(END_MARKER, start) + len(END_MARKER)
    current_block = existing[start:end].rstrip() + "\n"
    if current_block == generated:
        return existing, "UNCHANGED"
    if not force:
        raise FileExistsError("受管理的 AGENTS.md 區塊不同；請檢視後加 --force 更新")
    combined = existing[:start] + generated.rstrip() + existing[end:]
    return combined.rstrip() + "\n", "UPDATE-BLOCK"


def build_plan(args: argparse.Namespace, target: Path) -> list[PlannedWrite]:
    project_name = validate_text_argument("專案名稱", args.project_name)
    if START_MARKER in project_name or END_MARKER in project_name:
        raise ValueError("專案名稱不得包含工作流程管理標記")
    default_branch = validate_branch_name(args.default_branch)
    values = {
        "PROJECT_NAME": project_name,
        "PROJECT_NAME_JSON": json_string_content(project_name),
        "WORKFLOW_MODE": args.mode,
        "TASK_TRACKER": args.tracker,
        "DEFAULT_BRANCH": default_branch,
        "DEFAULT_BRANCH_JSON": json_string_content(default_branch),
        "MODE_POLICY": MODE_POLICIES[args.mode],
    }
    templates = sorted(TEMPLATE_ROOT.rglob("*.tmpl"))
    if not templates:
        raise ValueError(f"{TEMPLATE_ROOT} 下找不到模板")

    plan: list[PlannedWrite] = []
    conflicts: list[str] = []
    for template in templates:
        relative = template.relative_to(TEMPLATE_ROOT)
        if args.tracker != "github" and relative.parts[0] == ".github":
            continue
        destination = destination_for(template, target)
        generated = render_template(template, values)

        if destination.exists() and destination.is_symlink():
            conflicts.append(f"{destination}：目的地是符號連結")
            continue

        if (
            destination.name == "AGENTS.md"
            and destination.exists()
            and args.merge_agents
        ):
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
            conflicts.append(f"{destination}：已存在且內容不同")

    if conflicts:
        details = "\n".join(f"  - {item}" for item in conflicts)
        raise FileExistsError(
            "預檢發現衝突；沒有寫入任何檔案。請檢視後使用明確的"
            f"合併/覆寫選項：\n{details}"
        )
    return plan


def atomic_write(destination: Path, content: str, target: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    target_resolved = target.resolve(strict=True)
    parent_resolved = destination.parent.resolve(strict=True)
    if not parent_resolved.is_relative_to(target_resolved):
        raise ValueError(f"目的地父目錄逃脫了目標：{destination.parent}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.tmp-", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        if destination.exists() and destination.is_symlink():
            raise ValueError(f"拒絕替換符號連結：{destination}")
        if destination.parent.resolve(strict=True) != parent_resolved:
            raise ValueError(f"寫入期間目的地父目錄改變了：{destination.parent}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    args = parse_args(argv)
    try:
        if args.show_content and not args.dry_run:
            raise ValueError("--show-content 必須搭配 --dry-run")
        target = safe_target(args.target)
        plan = build_plan(args, target)
    except (OSError, ValueError, FileExistsError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 2

    for item in plan:
        label = ACTION_LABELS[item.action]
        print(f"{label:8} {item.destination}")

    if args.dry_run:
        if args.show_content:
            for item in plan:
                if item.action == "UNCHANGED":
                    continue
                print(f"\n===== {item.destination} =====")
                print(item.content, end="")
                print(f"===== {item.destination} 結束 =====")
        print(f"預演完成：已檢查 {len(plan)} 個目的地；未寫入任何檔案。")
        return 0

    try:
        target.mkdir(parents=True, exist_ok=True)
        for item in plan:
            if item.action != "UNCHANGED":
                atomic_write(item.destination, item.content, target)
    except (OSError, ValueError) as exc:
        print(f"寫入時發生錯誤：{exc}", file=sys.stderr)
        return 3

    changed = sum(item.action != "UNCHANGED" for item in plan)
    print(f"已為 {args.project_name} 安裝工作流程：變更 {changed} 個檔案。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
