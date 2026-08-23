from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "multi-agent-repo-workflow" / "scripts"
BOOTSTRAP = SCRIPTS / "bootstrap.py"
VALIDATE = SCRIPTS / "validate_setup.py"


def run_script(
    script: Path, *arguments: object, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *(str(item) for item in arguments)],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


class BootstrapTests(unittest.TestCase):
    def test_dry_run_does_not_create_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "new-project"
            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example",
                "--mode",
                "adaptive",
                "--tracker",
                "github",
                "--dry-run",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("預演完成", result.stdout)
            self.assertFalse(target.exists())

    def test_dry_run_can_preview_rendered_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "new-project"
            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "預覽專案",
                "--dry-run",
                "--show-content",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("# 預覽專案 AI 協作規範", result.stdout)
            self.assertIn("===== ", result.stdout)
            self.assertFalse(target.exists())

    def test_show_content_requires_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "new-project"
            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example",
                "--show-content",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("--show-content 必須搭配 --dry-run", result.stderr)
            self.assertFalse(target.exists())

    def test_bootstrap_and_validate_github_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example Project",
                "--mode",
                "adaptive",
                "--tracker",
                "github",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((target / "AGENTS.md").is_file())
            self.assertTrue(
                (target / ".github/ISSUE_TEMPLATE/agent-task.yml").is_file()
            )
            config = (target / ".agent-workflow/config.json").read_text(
                encoding="utf-8"
            )
            self.assertIn('"project_name": "Example Project"', config)
            self.assertIn('"mode": "adaptive"', config)

            validation = run_script(VALIDATE, target)
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertIn("工作流程設定通過", validation.stdout)

            unrelated = target / "src/template.txt"
            unrelated.parent.mkdir()
            unrelated.write_text("{{ application_owned_template }}\n", encoding="utf-8")
            validation = run_script(VALIDATE, target)
            self.assertEqual(validation.returncode, 0, validation.stderr)

    def test_template_values_are_json_escaped_without_recursive_substitution(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            project_name = '台灣 "範例" {{DEFAULT_BRANCH}}'
            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                project_name,
                "--default-branch",
                "release/台灣",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads(
                (target / ".agent-workflow/config.json").read_text(encoding="utf-8")
            )
            self.assertEqual(config["project_name"], project_name)
            self.assertEqual(config["default_branch"], "release/台灣")
            agents = (target / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn(project_name, agents)

    def test_invalid_default_branch_is_rejected_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example",
                "--default-branch",
                "main-->closed",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("不是有效且安全的 Git 分支名稱", result.stderr)
            self.assertFalse(target.exists())

    def test_project_name_cannot_inject_managed_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example <!-- multi-agent-repo-workflow:start -->",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("不得包含工作流程管理標記", result.stderr)
            self.assertFalse(target.exists())

    def test_validate_setup_rejects_unknown_and_missing_config_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            config_path = target / ".agent-workflow/config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            del config["handoff_marker"]
            config["unexpected"] = True
            config_path.write_text(
                json.dumps(config, ensure_ascii=False),
                encoding="utf-8",
            )
            validation = run_script(VALIDATE, target)
            self.assertEqual(validation.returncode, 1)
            self.assertIn("config 缺少欄位：handoff_marker", validation.stderr)
            self.assertIn("config 含有未知欄位：unexpected", validation.stderr)

    def test_validate_setup_rejects_duplicate_config_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            config_path = target / ".agent-workflow/config.json"
            config = config_path.read_text(encoding="utf-8")
            config_path.write_text(
                config.replace(
                    '"schema_version": 1,',
                    '"schema_version": 1,\n  "schema_version": 1,',
                    1,
                ),
                encoding="utf-8",
            )
            validation = run_script(VALIDATE, target)
            self.assertEqual(validation.returncode, 1)
            self.assertIn("JSON 欄位重複：schema_version", validation.stderr)

    def test_preflight_conflict_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            conflict = target / "docs/ai/GOALS.md"
            conflict.parent.mkdir(parents=True)
            conflict.write_text("keep me\n", encoding="utf-8")

            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example",
                "--mode",
                "adaptive",
                "--tracker",
                "github",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("沒有寫入任何檔案", result.stderr)
            self.assertEqual(conflict.read_text(encoding="utf-8"), "keep me\n")
            self.assertFalse((target / "AGENTS.md").exists())

    def test_merge_agents_preserves_existing_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            target.mkdir()
            agents = target / "AGENTS.md"
            agents.write_text("# Existing rules\n\nKeep this.\n", encoding="utf-8")
            result = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example",
                "--mode",
                "adaptive",
                "--tracker",
                "manual",
                "--merge-agents",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = agents.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("# Existing rules\n\nKeep this."))
            self.assertEqual(content.count("multi-agent-repo-workflow:start"), 1)
            self.assertFalse((target / ".github").exists())

    def test_existing_managed_block_requires_force_to_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            first = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example",
                "--mode",
                "solo",
                "--tracker",
                "manual",
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            second = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example",
                "--mode",
                "strict",
                "--tracker",
                "manual",
                "--merge-agents",
            )
            self.assertEqual(second.returncode, 2)
            forced = run_script(
                BOOTSTRAP,
                target,
                "--project-name",
                "Example",
                "--mode",
                "strict",
                "--tracker",
                "manual",
                "--merge-agents",
                "--force",
            )
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertIn(
                "`strict`", (target / "AGENTS.md").read_text(encoding="utf-8")
            )


if __name__ == "__main__":
    unittest.main()
