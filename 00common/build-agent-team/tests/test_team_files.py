from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/team_files.py"
EXAMPLE_SPEC = ROOT / "references/example-team-spec.json"
MODULE_SPEC = importlib.util.spec_from_file_location("team_files", MODULE_PATH)
assert MODULE_SPEC and MODULE_SPEC.loader
team_files = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(team_files)


class TeamFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.spec = json.loads(EXAMPLE_SPEC.read_text(encoding="utf-8"))
        self.spec_path = self.root / "draft.json"
        self.write_spec(self.spec)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_spec(self, spec: dict) -> None:
        self.spec_path.write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def finalize_team(self) -> dict:
        return team_files.finalize(
            self.root,
            {
                "product_lead": "thread-1",
                "fullstack_developer": "thread-2",
                "release_reviewer": "thread-3",
            },
        )

    def test_example_spec_is_valid(self) -> None:
        validated = team_files.validate_spec_file(EXAMPLE_SPEC)
        self.assertEqual(validated["entry_role"], "product_lead")
        self.assertEqual(len(validated["roles"]), 3)

    def test_prepare_is_idempotent_and_preserves_logs(self) -> None:
        first = team_files.prepare(self.root, self.spec_path)
        self.assertFalse(first["complete"])
        self.assertTrue(first["spec_consistent"])
        log = self.root / "agents/product_lead/log.md"
        log.write_text("# custom log\nkept\n", encoding="utf-8")

        second = team_files.prepare(self.root, self.spec_path)
        self.assertEqual(second["created_or_updated"], [])
        self.assertEqual(log.read_text(encoding="utf-8"), "# custom log\nkept\n")
        rules = (self.root / "agents/TEAM_RULES.md").read_text(encoding="utf-8")
        usage = (self.root / "agents/USAGE.md").read_text(encoding="utf-8")
        self.assertIn("发布验收", rules)
        self.assertIn("production-release", usage)

    def test_finalize_requires_complete_unique_ids(self) -> None:
        team_files.prepare(self.root, self.spec_path)
        with self.assertRaises(team_files.TeamFileError):
            team_files.finalize(self.root, {"product_lead": "thread-1"})
        with self.assertRaises(team_files.TeamFileError):
            team_files.finalize(
                self.root,
                {
                    "product_lead": "same",
                    "fullstack_developer": "same",
                    "release_reviewer": "thread-3",
                },
            )

        result = self.finalize_team()
        self.assertTrue(result["complete"])
        self.assertEqual(result["duplicate_thread_ids"], [])

    def test_finalize_refuses_to_replace_an_id(self) -> None:
        team_files.prepare(self.root, self.spec_path)
        self.finalize_team()
        with self.assertRaises(team_files.TeamFileError):
            team_files.finalize(self.root, {"product_lead": "replacement"})

    def test_live_team_spec_migration_is_rejected(self) -> None:
        team_files.prepare(self.root, self.spec_path)
        self.finalize_team()
        changed = copy.deepcopy(self.spec)
        changed["spec_version"] = 2
        changed["mission"] = "changed mission"
        self.write_spec(changed)
        with self.assertRaises(team_files.TeamFileError):
            team_files.prepare(self.root, self.spec_path)

    def test_direct_live_spec_edit_cannot_bypass_version_gate(self) -> None:
        team_files.prepare(self.root, self.spec_path)
        self.finalize_team()
        target = self.root / "agents/team-spec.json"
        changed = json.loads(target.read_text(encoding="utf-8"))
        changed["mission"] = "manually changed mission"
        target.write_text(
            json.dumps(changed, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(team_files.TeamFileError):
            team_files.prepare(self.root, target)

    def test_pre_thread_direct_spec_edit_requires_new_version(self) -> None:
        team_files.prepare(self.root, self.spec_path)
        target = self.root / "agents/team-spec.json"
        changed = json.loads(target.read_text(encoding="utf-8"))
        changed["mission"] = "manually changed mission"
        target.write_text(
            json.dumps(changed, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(team_files.TeamFileError):
            team_files.prepare(self.root, target)

        changed["spec_version"] = 2
        target.write_text(
            json.dumps(changed, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = team_files.prepare(self.root, target)
        self.assertEqual(result["spec_version"], 2)
        self.assertTrue(result["spec_consistent"])

    def test_legacy_registry_is_not_overwritten(self) -> None:
        agents = self.root / "agents"
        agents.mkdir()
        legacy = {"agents": [{"role": "product_planner", "conv_id": "legacy-thread"}]}
        registry = agents / "registry.json"
        registry.write_text(json.dumps(legacy), encoding="utf-8")
        before = registry.read_text(encoding="utf-8")
        with self.assertRaises(team_files.TeamFileError):
            team_files.prepare(self.root, self.spec_path)
        self.assertEqual(registry.read_text(encoding="utf-8"), before)
        self.assertFalse((agents / "team-spec.json").exists())

    def test_onboarding_prompts_require_finalize_and_include_dynamic_rules(
        self,
    ) -> None:
        team_files.prepare(self.root, self.spec_path)
        bootstrap = team_files.prompts_payload(self.root, "bootstrap")
        self.assertEqual(len(bootstrap["prompts"]), 3)
        with self.assertRaises(team_files.TeamFileError):
            team_files.prompts_payload(self.root, "onboarding")
        self.finalize_team()
        onboarding = team_files.prompts_payload(self.root, "onboarding")
        developer = next(
            item
            for item in onboarding["prompts"]
            if item["role_id"] == "fullstack_developer"
        )
        self.assertIn("src/", developer["prompt"])
        self.assertIn("thread-3", developer["prompt"])
        self.assertIn(str(MODULE_PATH), developer["prompt"])
        self.assertIn("Skill 只提供方法，不扩大权限", developer["prompt"])

    def test_record_handoff_validates_route_and_appends_jsonl(self) -> None:
        team_files.prepare(self.root, self.spec_path)
        self.finalize_team()
        args = type(
            "Args",
            (),
            {
                "from_role": "product_lead",
                "to_role": "fullstack_developer",
                "type": "plan_confirmed",
                "title": "Implement confirmed scope",
                "task_id": "task-1",
                "status": "sent",
                "artifact": ["agents/product_lead/log.md"],
            },
        )()
        result = team_files.append_audit(self.root, args)
        self.assertTrue(result["recorded"])
        records = [
            json.loads(line)
            for line in (self.root / "agents/messages.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual(records[0]["to_thread_id"], "thread-2")
        self.assertEqual(records[0]["type"], "plan_confirmed")

        args.type = "unknown-route"
        with self.assertRaises(team_files.TeamFileError):
            team_files.append_audit(self.root, args)

    def test_single_role_team_is_supported(self) -> None:
        solo = copy.deepcopy(self.spec)
        solo["team_id"] = "solo-research"
        solo["team_name"] = "单角色研究团队"
        solo["entry_role"] = "researcher"
        solo["completion_role"] = "researcher"
        solo["roles"] = [
            {
                "role_id": "researcher",
                "display_name": "研究员",
                "purpose": "研究并汇报",
                "responsibilities": ["研究"],
                "non_responsibilities": ["执行外部操作"],
                "accepted_sources": ["user"],
                "may_modify_business_code": False,
                "allowed_paths": [],
                "prohibited_actions": ["伪造来源"],
                "outputs": ["报告"],
                "escalation_to": "user",
            }
        ]
        solo["workflow"] = [
            {
                "from": "user",
                "to": "researcher",
                "trigger": "new_request",
                "condition": "",
                "required_payload": ["研究目标"],
            },
            {
                "from": "researcher",
                "to": "user",
                "trigger": "final_report",
                "condition": "",
                "required_payload": ["结论", "证据"],
            },
        ]
        solo["human_gates"] = []
        self.write_spec(solo)
        validated = team_files.validate_spec_file(self.spec_path)
        self.assertEqual(len(validated["roles"]), 1)

    def test_cli_end_to_end(self) -> None:
        validate = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "validate",
                "--spec",
                str(self.spec_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertTrue(json.loads(validate.stdout)["valid"])
        subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "prepare",
                "--root",
                str(self.root),
                "--spec",
                str(self.spec_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        finalized = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "finalize",
                "--root",
                str(self.root),
                "--agent-id",
                "product_lead=thread-1",
                "--agent-id",
                "fullstack_developer=thread-2",
                "--agent-id",
                "release_reviewer=thread-3",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertTrue(json.loads(finalized.stdout)["complete"])
        prompts = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "prompts",
                "--root",
                str(self.root),
                "--phase",
                "onboarding",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(len(json.loads(prompts.stdout)["prompts"]), 3)


if __name__ == "__main__":
    unittest.main()
