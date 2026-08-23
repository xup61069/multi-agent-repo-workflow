from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "skills/multi-agent-repo-workflow/scripts/handoff_check.py"


def run_check(*arguments: object, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HANDOFF), *(str(item) for item in arguments)],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def block(issue: int, scope: list[str], branch: str | None = None, status: str = "claimed") -> str:
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
            self.assertIn("1 claims", result.stdout)

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
            self.assertIn("definite scope overlap", result.stderr)

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
            self.assertIn("possible scope overlap", adaptive.stdout)
            strict = run_check("--issues-json", path, "--mode", "strict")
            self.assertEqual(strict.returncode, 1)
            self.assertIn("possible scope overlap", strict.stderr)

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
            self.assertIn("must not contain '..'", result.stderr)

    def test_git_check_rejects_changed_path_outside_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
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
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True, check=True, capture_output=True
            ).stdout.strip()
            subprocess.run(["git", "switch", "-c", "agent/9-task"], cwd=repo, check=True, capture_output=True)
            (repo / "outside.txt").write_text("outside\n", encoding="utf-8")
            payload = json.loads(block(9, ["src/**"]).split("\n", 1)[1].rsplit("\n", 1)[0])
            payload["base_commit"] = base
            body = "<!-- agent-workflow:handoff-v1\n" + json.dumps(payload) + "\n-->"
            issue_path = repo / "issues.json"
            issue_path.write_text(json.dumps([{"number": 9, "body": body}]), encoding="utf-8")
            result = run_check(
                "--issues-json",
                issue_path,
                "--issue",
                9,
                "--check-git",
                cwd=repo,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("outside scope: outside.txt", result.stderr)


if __name__ == "__main__":
    unittest.main()
