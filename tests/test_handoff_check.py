from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "skills/multi-agent-repo-workflow/scripts/handoff_check.py"
SPEC = importlib.util.spec_from_file_location("handoff_check_module", HANDOFF)
assert SPEC and SPEC.loader
HANDOFF_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HANDOFF_MODULE
SPEC.loader.exec_module(HANDOFF_MODULE)


def run_check(
    *arguments: object, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HANDOFF), *(str(item) for item in arguments)],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def block(
    issue: int, scope: list[str], branch: str | None = None, status: str = "claimed"
) -> str:
    payload = {
        "schema_version": 1,
        "issue": issue,
        "branch": branch or f"agent/{issue}-task",
        "target_branch": "main",
        "base_commit": "0123456789abcdef",
        "owner": f"writer-{issue}",
        "role": "writer",
        "status": status,
        "scope_globs": scope,
        "shared_paths": [],
        "depends_on": [],
        "validation": ["python -m unittest"],
        "next_safe_action": "Implement the named acceptance criteria.",
    }
    return "<!-- agent-workflow:handoff-v1\n" + json.dumps(payload) + "\n-->"


class HandoffTests(unittest.TestCase):
    def write_issues(self, directory: Path, issues: list[dict[str, object]]) -> Path:
        path = directory / "issues.json"
        path.write_text(json.dumps(issues), encoding="utf-8")
        return path

    def test_body_file_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "body.md"
            path.write_text(block(7, ["src/parser/**"]), encoding="utf-8")
            result = run_check("--body-file", path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("1 份交接", result.stdout)

    def test_handoff_json_allows_braces_inside_strings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "body.md"
            payload = json.loads(
                block(7, ["src/parser/**"]).split("\n", 1)[1].rsplit("\n", 1)[0]
            )
            payload["next_safe_action"] = "Update the {parser} contract."
            body = "<!-- agent-workflow:handoff-v1\n" + json.dumps(payload) + "\n-->"
            path.write_text(body, encoding="utf-8")
            result = run_check("--body-file", path)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_handoff_json_rejects_duplicate_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "body.md"
            payload = block(7, ["src/parser/**"]).split("\n", 1)[1].rsplit("\n", 1)[0]
            duplicate = payload.replace(
                '"issue": 7,',
                '"issue": 7, "issue": 8,',
                1,
            )
            path.write_text(
                "<!-- agent-workflow:handoff-v1\n" + duplicate + "\n-->",
                encoding="utf-8",
            )
            result = run_check("--body-file", path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("JSON 欄位重複：issue", result.stderr)

    def test_claim_rejects_unknown_fields_and_invalid_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "body.md"
            payload = json.loads(
                block(7, ["src/parser/**"]).split("\n", 1)[1].rsplit("\n", 1)[0]
            )
            payload["unknown"] = True
            payload["depends_on"] = [True, 7]
            body = "<!-- agent-workflow:handoff-v1\n" + json.dumps(payload) + "\n-->"
            path.write_text(body, encoding="utf-8")
            result = run_check("--body-file", path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("含有未知欄位：unknown", result.stderr)
            self.assertIn("depends_on 條目必須是大於 0 的整數", result.stderr)
            self.assertIn("depends_on 不得指向自己", result.stderr)

    def test_definite_overlap_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = self.write_issues(
                directory,
                [
                    {"number": 1, "body": block(1, ["src/**"])},
                    {"number": 2, "body": block(2, ["src/feature/**"])},
                ],
            )
            result = run_check("--issues-json", path, "--mode", "adaptive")
            self.assertEqual(result.returncode, 1)
            self.assertIn("確定範圍重疊", result.stderr)

    def test_possible_overlap_warns_in_adaptive_and_fails_in_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = self.write_issues(
                directory,
                [
                    {"number": 1, "body": block(1, ["src/*.py"])},
                    {"number": 2, "body": block(2, ["src/*.md"])},
                ],
            )
            adaptive = run_check("--issues-json", path, "--mode", "adaptive")
            self.assertEqual(adaptive.returncode, 0, adaptive.stderr)
            self.assertIn("可能範圍重疊", adaptive.stdout)
            strict = run_check("--issues-json", path, "--mode", "strict")
            self.assertEqual(strict.returncode, 1)
            self.assertIn("可能範圍重疊", strict.stderr)

    def test_unrelated_prefixes_do_not_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = self.write_issues(
                directory,
                [
                    {"number": 1, "body": block(1, ["src/feature/**"])},
                    {"number": 2, "body": block(2, ["docs/**"])},
                ],
            )
            result = run_check("--issues-json", path, "--mode", "strict")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_strict_mode_rejects_active_claim_on_target_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "body.md"
            path.write_text(block(7, ["src/**"], branch="main"), encoding="utf-8")
            result = run_check("--body-file", path, "--mode", "strict")
            self.assertEqual(result.returncode, 1)
            self.assertIn("不得使用目標分支", result.stderr)

    def test_draft_claim_is_excluded_from_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = self.write_issues(
                directory,
                [
                    {"number": 1, "body": block(1, ["src/**"], status="claimed")},
                    {"number": 2, "body": block(2, ["src/**"], status="draft")},
                ],
            )
            result = run_check("--issues-json", path, "--mode", "strict")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_repository_relative_scope_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "body.md"
            path.write_text(block(7, ["../outside/**"]), encoding="utf-8")
            result = run_check("--body-file", path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("'..' 路徑片段", result.stderr)

    def test_glob_star_does_not_cross_directories(self) -> None:
        self.assertTrue(HANDOFF_MODULE.glob_matches("src/app.py", "src/*.py"))
        self.assertFalse(HANDOFF_MODULE.glob_matches("src/nested/app.py", "src/*.py"))
        self.assertTrue(HANDOFF_MODULE.glob_matches("src/nested/app.py", "src/**/*.py"))

    def test_git_check_rejects_changed_path_outside_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True
            )
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-m",
                    "base",
                ],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            base = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                text=True,
                check=True,
                capture_output=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "switch", "-c", "agent/9-task"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            (repo / "outside.txt").write_text("outside\n", encoding="utf-8")
            payload = json.loads(
                block(9, ["src/**"]).split("\n", 1)[1].rsplit("\n", 1)[0]
            )
            payload["base_commit"] = base
            body = "<!-- agent-workflow:handoff-v1\n" + json.dumps(payload) + "\n-->"
            issue_path = repo / "issues.json"
            issue_path.write_text(
                json.dumps([{"number": 9, "body": body}]), encoding="utf-8"
            )
            result = run_check(
                "--issues-json",
                issue_path,
                "--issue",
                9,
                "--check-git",
                cwd=repo,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("超出範圍：outside.txt", result.stderr)
            self.assertNotIn("超出範圍：issues.json", result.stderr)

    def test_git_check_includes_unstaged_and_staged_tracked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            repo = directory / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True
            )
            (repo / "outside.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "outside.txt"], cwd=repo, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-m",
                    "base",
                ],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            base = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                text=True,
                check=True,
                capture_output=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "switch", "-c", "agent/10-task"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            payload = json.loads(
                block(10, ["src/**"]).split("\n", 1)[1].rsplit("\n", 1)[0]
            )
            payload["base_commit"] = base
            body = "<!-- agent-workflow:handoff-v1\n" + json.dumps(payload) + "\n-->"
            issue_path = directory / "issues.json"
            issue_path.write_text(
                json.dumps([{"number": 10, "body": body}]),
                encoding="utf-8",
            )

            (repo / "outside.txt").write_text("unstaged\n", encoding="utf-8")
            unstaged = run_check(
                "--issues-json",
                issue_path,
                "--issue",
                10,
                "--check-git",
                cwd=repo,
            )
            self.assertEqual(unstaged.returncode, 1)
            self.assertIn("超出範圍：outside.txt", unstaged.stderr)

            subprocess.run(["git", "add", "outside.txt"], cwd=repo, check=True)
            staged = run_check(
                "--issues-json",
                issue_path,
                "--issue",
                10,
                "--check-git",
                cwd=repo,
            )
            self.assertEqual(staged.returncode, 1)
            self.assertIn("超出範圍：outside.txt", staged.stderr)


if __name__ == "__main__":
    unittest.main()
