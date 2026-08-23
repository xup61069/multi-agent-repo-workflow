from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "multi-agent-repo-workflow" / "scripts"
BOOTSTRAP = SCRIPTS / "bootstrap.py"
VALIDATE = SCRIPTS / "validate_setup.py"


def run_script(script: Path, *arguments: object, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
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
            self.assertIn("Dry run complete", result.stdout)
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
            self.assertTrue((target / ".github/ISSUE_TEMPLATE/agent-task.yml").is_file())
            config = (target / ".agent-workflow/config.json").read_text(encoding="utf-8")
            self.assertIn('"project_name": "Example Project"', config)
            self.assertIn('"mode": "adaptive"', config)

            validation = run_script(VALIDATE, target)
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertIn("Workflow setup passed", validation.stdout)

            unrelated = target / "src/template.txt"
            unrelated.parent.mkdir()
            unrelated.write_text("{{ application_owned_template }}\n", encoding="utf-8")
            validation = run_script(VALIDATE, target)
            self.assertEqual(validation.returncode, 0, validation.stderr)

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
            self.assertIn("no files were written", result.stderr)
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
            self.assertIn("`strict`", (target / "AGENTS.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
