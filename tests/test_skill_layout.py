from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/multi-agent-repo-workflow"


class SkillLayoutTests(unittest.TestCase):
    def test_skill_frontmatter_and_ui_metadata(self) -> None:
        content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\n"))
        self.assertRegex(content, r"(?m)^name: multi-agent-repo-workflow$")
        self.assertRegex(content, r"(?m)^description: .{40,}$")
        self.assertNotIn("TODO", content)

        metadata = (SKILL / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "多代理儲存庫工作流程"', metadata)
        self.assertIn("$multi-agent-repo-workflow", metadata)

    def test_every_linked_reference_exists(self) -> None:
        content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        links = re.findall(r"\[[^]]+\]\((references/[^)]+)\)", content)
        self.assertGreaterEqual(len(links), 4)
        for relative in links:
            self.assertTrue((SKILL / relative).is_file(), relative)

    def test_generic_distribution_has_no_source_project_policy(self) -> None:
        forbidden = (
            "Hi" + "biki",
            "Wave" + "RT",
            "AS" + "IO",
            "ISO" + " 226",
            "Microsoft" + " Hardware",
        )
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for term in forbidden:
                self.assertNotIn(term, content, f"{term!r} leaked into {path}")

    def test_generated_json_schemas_parse(self) -> None:
        starter = SKILL / "assets/starter/.agent-workflow"
        for name in ("config.schema.json.tmpl", "handoff-v1.schema.json.tmpl"):
            parsed = json.loads((starter / name).read_text(encoding="utf-8"))
            self.assertEqual(
                parsed["$schema"], "https://json-schema.org/draft/2020-12/schema"
            )
            self.assertEqual(parsed["type"], "object")
            self.assertRegex(parsed["title"], r"[\u4e00-\u9fff]")

    def test_repository_templates_keep_required_review_context(self) -> None:
        pull_request = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## 範圍與取捨", pull_request)

        bug_form = (ROOT / ".github/ISSUE_TEMPLATE/bug.yml").read_text(encoding="utf-8")
        self.assertRegex(bug_form, r"id: environment\n    attributes:")

    def test_ci_covers_minimum_supported_python(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn('python: ["3.10", "3.11"]', workflow)


if __name__ == "__main__":
    unittest.main()
