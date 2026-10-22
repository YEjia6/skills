"""Tests for the packaged CLI. Run: python -m unittest discover -s tests -v"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rules_manager.py"


class CLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "mixed-repo"
        self.root.mkdir()
        for path in [
            "apps/web/src/features/business",
            "apps/web/src/features/analytics",
            "apps/mobile",
            "apps/hmi",
            "services/api",
        ]:
            (self.root / path).mkdir(parents=True, exist_ok=True)
        (self.root / "apps/web/package.json").write_text('{"dependencies": {"react":"*", "vite":"*"}}', encoding="utf-8")
        (self.root / "apps/mobile/pubspec.yaml").write_text("name: mobile\n", encoding="utf-8")
        (self.root / "apps/hmi/main.qml").write_text("Window {}", encoding="utf-8")
        (self.root / "services/api/pyproject.toml").write_text("[project]\nname='api'\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def runcli(self, *args, success=True):
        r = subprocess.run([sys.executable, str(SCRIPT), "--project", str(self.root), *args], capture_output=True, text=True)
        if success and r.returncode:
            self.fail(f"{r.returncode}: {r.stdout}\n{r.stderr}")
        return r

    def test_scan_is_read_only_and_classifies(self):
        data = json.loads(self.runcli("scan").stdout)
        kinds = {(m["path"], m["kind"]) for m in data["modules"]}
        self.assertIn(("apps/web", "web"), kinds)
        self.assertIn(("apps/mobile", "mobile"), kinds)
        self.assertIn(("apps/hmi", "hmi"), kinds)
        self.assertIn(("services/api", "backend"), kinds)
        self.assertFalse((self.root / ".ai-rules").exists())

    def test_init_and_sync_paths_scope_and_check(self):
        self.runcli("init")
        m = json.loads((self.root / ".ai-rules/manifest.json").read_text(encoding="utf-8"))
        active = {r["id"]: r for r in m["rules"] if r["enabled"]}
        regular = next(r for r in active.values() if "WEB-REGULAR-" in r["id"])
        charts = next(r for r in active.values() if "WEB-ANALYTICS-" in r["id"])
        self.assertEqual(regular["anchor"], "apps/web/src/features/business")
        self.assertEqual(charts["anchor"], "apps/web/src/features/analytics")
        self.assertIn("WEB-REGULAR", self.runcli("explain", "apps/web/src/features/business/users.tsx").stdout)
        self.assertNotIn("WEB-REGULAR", self.runcli("explain", "apps/web/src/features/analytics/chart.tsx").stdout)
        self.assertFalse((self.root / "AGENTS.md").exists())
        preview = self.runcli("sync").stdout
        self.assertIn("CREATE", preview)
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.runcli("sync", "--apply")
        for f in [
            "AGENTS.md", "CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md",
            "apps/web/AGENTS.md", "apps/web/src/features/business/AGENTS.md",
            "apps/web/src/features/analytics/AGENTS.md", "apps/web/src/features/analytics/GEMINI.md",
        ]:
            self.assertTrue((self.root / f).exists(), f)
        scoped = list((self.root / ".cursor/rules").glob("*.mdc"))
        self.assertTrue(scoped)
        body = (self.root / "apps/web/src/features/analytics/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("图表与分析页面", body)
        self.assertNotIn("常规 Web 业务页面设计", body)
        self.assertIn("PASS", self.runcli("check").stdout)
        self.assertTrue(all(s == "UNCHANGED" for s in [line.split()[0] for line in self.runcli("sync").stdout.splitlines() if line.startswith("UNCHANGED")]))

    def test_refuses_existing_user_rule_and_backs_up_force(self):
        (self.root / "AGENTS.md").write_text("Handwritten instructions", encoding="utf-8")
        self.runcli("init")
        result = self.runcli("sync", "--apply", success=False)
        self.assertEqual(result.returncode, 3)
        self.assertFalse((self.root / "CLAUDE.md").exists(), "Conflicts should abort before partial writes")
        self.assertEqual((self.root / "AGENTS.md").read_text(encoding="utf-8"), "Handwritten instructions")
        self.runcli("sync", "--apply", "--force")
        backups = list((self.root / ".ai-rules/backups").rglob("AGENTS.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "Handwritten instructions")

    def test_detects_drift_after_manual_edit(self):
        self.runcli("init")
        self.runcli("sync", "--apply")
        with (self.root / "AGENTS.md").open("a", encoding="utf-8") as f:
            f.write("\nUser edits\n")
        self.assertEqual(self.runcli("check", success=False).returncode, 1)
        self.assertEqual(self.runcli("sync", "--apply", success=False).returncode, 3)
        self.runcli("sync", "--apply", "--force")
        self.assertEqual(self.runcli("check").returncode, 0)

    def test_legacy_rules_indexed_disabled(self):
        old = self.root / ".ai-rules/web/legacy.md"
        old.parent.mkdir(parents=True)
        old.write_text("禁止任何图表使用四种颜色", encoding="utf-8")
        self.runcli("init")
        m = json.loads((self.root / ".ai-rules/manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(any(x["file"] == "web/legacy.md" and x["enabled"] is False for x in m["rules"]))
        self.assertEqual(old.read_text(encoding="utf-8"), "禁止任何图表使用四种颜色")

    def test_native_headers_and_selected_tools(self):
        self.runcli("init")
        self.runcli("sync", "--tools", "claude,cursor,copilot", "--apply")
        claude = next((self.root / ".claude/rules").glob("ai-web-analytics-*.md"))
        cursor = next((self.root / ".cursor/rules").glob("ai-web-analytics-*.mdc"))
        copilot = next((self.root / ".github/instructions").glob("ai-web-analytics-*.instructions.md"))
        self.assertTrue(claude.read_text(encoding="utf-8").startswith("---\npaths:\n"))
        self.assertIn("alwaysApply: false", cursor.read_text(encoding="utf-8"))
        self.assertTrue(copilot.read_text(encoding="utf-8").startswith("---\napplyTo:"))
        self.assertFalse((self.root / "GEMINI.md").exists())
        self.assertEqual(self.runcli("check", "--tools", "claude,cursor,copilot").returncode, 0)

    def test_symlink_refused_even_if_force(self):
        self.runcli("init")
        outside = self.root / "user-owned.txt"
        outside.write_text("Do not modify", encoding="utf-8")
        (self.root / "AGENTS.md").symlink_to(outside)
        result = self.runcli("sync", "--apply", "--force", success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(outside.read_text(encoding="utf-8"), "Do not modify")

    def test_conflicting_visual_scopes_are_rejected(self):
        self.runcli("init")
        path = self.root / ".ai-rules/manifest.json"
        m = json.loads(path.read_text(encoding="utf-8"))
        visual = [r for r in m["rules"] if r.get("conflict_group") == "web-visual-mode" and r["enabled"]]
        self.assertEqual(len(visual), 2)
        visual[0]["anchor"] = "apps/web"
        visual[0]["globs"] = ["apps/web/**/*"]
        path.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        bad = self.runcli("sync", success=False)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("互斥规则冲突", bad.stderr)

    def test_excludes_rejected_to_prevent_false_scoping(self):
        self.runcli("init")
        path = self.root / ".ai-rules/manifest.json"
        m = json.loads(path.read_text(encoding="utf-8"))
        m["rules"][0]["excludes"] = ["apps/web/**"]
        path.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.runcli("sync", success=False).returncode, 2)

    def test_render_trae_skips_core(self):
        self.runcli("init")
        self.runcli("sync", "--tools", "trae", "--apply")
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("全仓库工程底线", agents, "core rule should be carried by root AGENTS.md")
        trae_files = list((self.root / ".trae/rules").glob("ai-*.md"))
        self.assertTrue(trae_files)
        for f in trae_files:
            self.assertNotIn("CORE-ENGINEERING", f.read_text(encoding="utf-8"), f"{f.name} must not duplicate core")
        self.assertFalse(any("core-engineering" in f.name for f in trae_files))
        # Trae subset must not create other tools' entries.
        self.assertFalse((self.root / ".cursor").exists())
        self.assertFalse((self.root / "CLAUDE.md").exists())
        self.assertEqual(self.runcli("check", "--tools", "trae").returncode, 0)

    def test_harvest_roundtrip_single_rule_file(self):
        self.runcli("init")
        self.runcli("sync", "--tools", "trae", "--apply")
        target = next((self.root / ".trae/rules").glob("ai-backend-*.md"))
        source_before = (self.root / ".ai-rules/domains/backend/api.md").read_text(encoding="utf-8")
        edited = target.read_text(encoding="utf-8") + "\n- MUST：新增一条后端约定。\n"
        target.write_text(edited, encoding="utf-8")
        preview = self.runcli("harvest", "--tools", "trae").stdout
        self.assertIn("HARVEST", preview)
        self.assertEqual((self.root / ".ai-rules/domains/backend/api.md").read_text(encoding="utf-8"), source_before, "preview must not write")
        self.runcli("harvest", "--tools", "trae", "--apply")
        source_after = (self.root / ".ai-rules/domains/backend/api.md").read_text(encoding="utf-8")
        self.assertIn("新增一条后端约定", source_after)
        self.assertEqual(self.runcli("check", "--tools", "trae").returncode, 0)
        backups = list((self.root / ".ai-rules/backups").rglob("api.md"))
        self.assertTrue(backups)

    def test_harvest_merged_file_rule_id_split(self):
        self.runcli("init")
        self.runcli("sync", "--tools", "codex", "--apply")
        agents = self.root / "AGENTS.md"
        text = agents.read_text(encoding="utf-8")
        text = text.replace("MUST：基于已查看的文件与实际执行结果回答", "MUST：手改后的工程底线表述", 1)
        agents.write_text(text, encoding="utf-8")
        preview = self.runcli("harvest", "--tools", "codex").stdout
        self.assertIn("HARVEST", preview)
        self.assertIn("CORE-ENGINEERING", preview)
        self.runcli("harvest", "--tools", "codex", "--apply")
        core = (self.root / ".ai-rules/core/engineering.md").read_text(encoding="utf-8")
        self.assertIn("手改后的工程底线表述", core)
        self.assertEqual(self.runcli("check", "--tools", "codex").returncode, 0)

    def test_harvest_rejects_multiple_tools(self):
        self.runcli("init")
        self.runcli("sync", "--tools", "trae", "--apply")
        for bad in ("all", "configured", "trae,cursor"):
            result = self.runcli("harvest", "--tools", bad, success=False)
            self.assertNotEqual(result.returncode, 0, bad)

    def test_harvest_orphan_not_written(self):
        self.runcli("init")
        self.runcli("sync", "--tools", "codex", "--apply")
        agents = self.root / "AGENTS.md"
        agents.write_text("用户手写的前言补充。\n" + agents.read_text(encoding="utf-8"), encoding="utf-8")
        preview = self.runcli("harvest", "--tools", "codex").stdout
        self.assertIn("ORPHAN", preview)
        self.assertNotIn("HARVEST", preview)
        core_before = (self.root / ".ai-rules/core/engineering.md").read_text(encoding="utf-8")
        self.runcli("harvest", "--tools", "codex", "--apply")
        self.assertEqual((self.root / ".ai-rules/core/engineering.md").read_text(encoding="utf-8"), core_before, "ORPHAN must never be written back")

    def test_detect_outputs_evidence(self):
        (self.root / ".trae").mkdir()
        data = json.loads(self.runcli("detect").stdout)
        tools = {d["tool"] for d in data["detected"]}
        self.assertIn("trae", tools)
        entry = next(d for d in data["detected"] if d["tool"] == "trae")
        self.assertIn(".trae", entry["evidence"])
        self.assertIn("rule_locations", entry)

    def test_new_rule_creates_skeleton_and_syncs(self):
        self.runcli("init")
        out = self.runcli("new-rule", "--id", "BACKEND-CUSTOM-API", "--file", "domains/backend/custom-api.md",
                          "--anchor", "services/api", "--description", "自定义后端约定").stdout
        self.assertIn("已创建规则骨架", out)
        body = (self.root / ".ai-rules/domains/backend/custom-api.md").read_text(encoding="utf-8")
        self.assertIn("MUST", body)
        self.assertIn("验收", body)
        m = json.loads((self.root / ".ai-rules/manifest.json").read_text(encoding="utf-8"))
        entry = next(r for r in m["rules"] if r["id"] == "BACKEND-CUSTOM-API")
        self.assertEqual(entry["anchor"], "services/api")
        self.assertEqual(entry["globs"], ["services/api/**/*"])
        self.assertEqual(entry["excludes"], [])
        self.assertTrue(entry["enabled"])
        self.assertEqual(entry["layer"], "domain")
        self.runcli("sync", "--tools", "trae", "--apply")
        self.assertTrue((self.root / ".trae/rules/ai-backend-custom-api.md").exists())
        self.assertIn("BACKEND-CUSTOM-API", self.runcli("explain", "services/api/handler.py").stdout)

    def test_new_rule_requires_init(self):
        result = self.runcli("new-rule", "--id", "X-ONE", "--file", "domains/x.md", "--anchor", ".", success=False)
        self.assertNotEqual(result.returncode, 0)

    def test_new_rule_rejects_invalid_input(self):
        self.runcli("init")
        self.runcli("new-rule", "--id", "CUSTOM-ONE", "--file", "domains/x.md", "--anchor", "services/api")
        for args in [
            ("--id", "CUSTOM-ONE", "--file", "domains/y.md", "--anchor", "services/api"),  # duplicate id
            ("--id", "CUSTOM-TWO", "--file", "domains/x.md", "--anchor", "services/api"),  # existing file
            ("--id", "CUSTOM-THREE", "--file", "domains/z.md", "--anchor", "no/such/dir"),  # missing anchor
            ("--id", "lower-case", "--file", "domains/w.md", "--anchor", "services/api"),  # bad id format
            ("--id", "CUSTOM-FOUR", "--file", "domains/v.txt", "--anchor", "services/api"),  # not .md
        ]:
            result = self.runcli("new-rule", *args, success=False)
            self.assertNotEqual(result.returncode, 0, args)
        m = json.loads((self.root / ".ai-rules/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual([r["id"] for r in m["rules"]].count("CUSTOM-ONE"), 1)
        self.assertFalse(any(r["id"] in ("CUSTOM-TWO", "CUSTOM-THREE", "CUSTOM-FOUR") for r in m["rules"]))

    def test_new_rule_conflict_group_overlap_rolls_back(self):
        self.runcli("init")
        result = self.runcli("new-rule", "--id", "WEB-VISUAL-CLASH", "--file", "domains/web/clash.md",
                             "--anchor", "apps/web", "--layer", "scenario",
                             "--conflict-group", "web-visual-mode", success=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("互斥规则冲突", result.stderr)
        self.assertFalse((self.root / ".ai-rules/domains/web/clash.md").exists(), "rollback must remove skeleton")
        m = json.loads((self.root / ".ai-rules/manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(any(r["id"] == "WEB-VISUAL-CLASH" for r in m["rules"]), "rollback must restore manifest")

    def test_new_rule_disabled_is_review_candidate(self):
        self.runcli("init")
        self.runcli("new-rule", "--id", "CANDIDATE-RULE", "--file", "domains/cand.md",
                    "--anchor", "services/api", "--disabled")
        m = json.loads((self.root / ".ai-rules/manifest.json").read_text(encoding="utf-8"))
        entry = next(r for r in m["rules"] if r["id"] == "CANDIDATE-RULE")
        self.assertFalse(entry["enabled"])
        self.runcli("sync", "--tools", "trae", "--apply")
        self.assertFalse((self.root / ".trae/rules/ai-candidate-rule.md").exists())


if __name__ == "__main__":
    unittest.main()
