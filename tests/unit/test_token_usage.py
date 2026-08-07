"""Unit tests for scripts/token_usage.py."""

import json
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

# scripts/ is on sys.path via conftest.py
import token_usage


class TestTrackingFlag(TestCase):
    def test_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("HEROKU_TOKEN_BUDGET_TRACKING", None)
            self.assertFalse(token_usage._tracking_enabled())

    def test_enabled_when_set_to_1(self):
        with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "1"}):
            self.assertTrue(token_usage._tracking_enabled())

    def test_disabled_when_set_to_0(self):
        with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "0"}):
            self.assertFalse(token_usage._tracking_enabled())

    def test_disabled_when_empty_string(self):
        with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": ""}):
            self.assertFalse(token_usage._tracking_enabled())


import os


class TestLoadBudgets(TestCase):
    def test_returns_budgets_from_plugin_json(self):
        budgets = token_usage._load_budgets()
        self.assertIn("preflight", budgets)
        self.assertIn("scaffold-app", budgets)
        self.assertIsInstance(budgets["preflight"], int)

    def test_filters_description_metadata_key(self):
        budgets = token_usage._load_budgets()
        for key in budgets:
            self.assertFalse(key.startswith("_"), f"metadata key leaked: {key!r}")

    def test_returns_empty_dict_on_missing_file(self):
        with patch.object(token_usage, "PLUGIN_JSON", Path("/nonexistent/plugin.json")):
            self.assertEqual(token_usage._load_budgets(), {})


class TestCmdRecord(TestCase):
    def test_noop_when_tracking_disabled(self, tmp_path=None):
        log = Path(self._make_tmp()) / "usage.jsonl"
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("HEROKU_TOKEN_BUDGET_TRACKING", None)
            with patch.object(token_usage, "USAGE_LOG", log):
                result = token_usage.cmd_record("preflight", 50)
        self.assertEqual(result, 0)
        self.assertFalse(log.exists())

    def test_writes_jsonl_record_when_enabled(self):
        log = Path(self._make_tmp()) / "usage.jsonl"
        with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "1"}):
            with patch.object(token_usage, "USAGE_LOG", log):
                token_usage.cmd_record("preflight", 50)
        self.assertTrue(log.exists())
        record = json.loads(log.read_text())
        self.assertEqual(record["skill"], "preflight")
        self.assertEqual(record["tokens"], 50)
        self.assertIn("ts", record)
        self.assertIn("budget", record)

    def test_record_includes_over_budget_flag(self):
        log = Path(self._make_tmp()) / "usage.jsonl"
        with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "1"}):
            with patch.object(token_usage, "USAGE_LOG", log):
                # preflight budget is 300; 9999 should be over
                token_usage.cmd_record("preflight", 9999)
        record = json.loads(log.read_text())
        self.assertTrue(record["over_budget"])

    def test_record_within_budget_sets_flag_false(self):
        log = Path(self._make_tmp()) / "usage.jsonl"
        with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "1"}):
            with patch.object(token_usage, "USAGE_LOG", log):
                token_usage.cmd_record("preflight", 1)
        record = json.loads(log.read_text())
        self.assertFalse(record["over_budget"])

    def test_appends_multiple_records(self):
        log = Path(self._make_tmp()) / "usage.jsonl"
        with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "1"}):
            with patch.object(token_usage, "USAGE_LOG", log):
                token_usage.cmd_record("preflight", 50)
                token_usage.cmd_record("scaffold-app", 200)
        lines = log.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["skill"], "preflight")
        self.assertEqual(json.loads(lines[1])["skill"], "scaffold-app")

    def test_returns_0_even_on_log_write_error(self):
        with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "1"}):
            with patch.object(token_usage, "USAGE_LOG", Path("/nonexistent/dir/usage.jsonl")):
                result = token_usage.cmd_record("preflight", 50)
        self.assertEqual(result, 0)

    def test_unknown_skill_sets_budget_to_none(self):
        log = Path(self._make_tmp()) / "usage.jsonl"
        with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "1"}):
            with patch.object(token_usage, "USAGE_LOG", log):
                token_usage.cmd_record("unknown-skill", 100)
        record = json.loads(log.read_text())
        self.assertIsNone(record["budget"])
        self.assertIsNone(record["over_budget"])

    def _make_tmp(self) -> str:
        import tempfile
        d = tempfile.mkdtemp()
        self._tmpdirs = getattr(self, "_tmpdirs", [])
        self._tmpdirs.append(d)
        return d

    def tearDown(self):
        import shutil
        for d in getattr(self, "_tmpdirs", []):
            shutil.rmtree(d, ignore_errors=True)


class TestCmdReport(TestCase):
    def test_noop_when_tracking_disabled(self):
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("HEROKU_TOKEN_BUDGET_TRACKING", None)
            result = token_usage.cmd_report()
        self.assertEqual(result, 0)

    def test_reports_from_log(self, capsys=None):
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        log = Path(tmp) / "usage.jsonl"
        try:
            with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "1"}):
                with patch.object(token_usage, "USAGE_LOG", log):
                    token_usage.cmd_record("preflight", 50)
                    token_usage.cmd_record("preflight", 80)
                    result = token_usage.cmd_report()
            self.assertEqual(result, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_empty_log_exits_cleanly(self):
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        log = Path(tmp) / "usage.jsonl"
        log.write_text("")
        try:
            with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "1"}):
                with patch.object(token_usage, "USAGE_LOG", log):
                    result = token_usage.cmd_report()
            self.assertEqual(result, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_log_exits_cleanly(self):
        with patch.dict("os.environ", {"HEROKU_TOKEN_BUDGET_TRACKING": "1"}):
            with patch.object(token_usage, "USAGE_LOG", Path("/nonexistent/usage.jsonl")):
                result = token_usage.cmd_report()
        self.assertEqual(result, 0)
