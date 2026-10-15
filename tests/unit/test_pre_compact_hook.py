"""Tests for hooks/pre_compact.sh — the session file is untrusted input."""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parents[2] / "hooks"
HOOK = HOOKS_DIR / "pre_compact.sh"
SESSION = ".heroku-plugin-session.json"


def run_hook(cwd, **env_overrides):
    env = {k: v for k, v in os.environ.items() if not k.startswith("HEROKU_")}
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(HOOK)], cwd=cwd, env=env, capture_output=True, text=True
    )


def read_session(cwd):
    return json.loads((Path(cwd) / SESSION).read_text())


# --- injection regression ---


class TestInjection:
    PAYLOADS = [
        # closes the ''' string and runs code (original report)
        "{}'''+str(__import__('os').system('touch MARK'))+'''",
        "{}''');import os;os.system('touch MARK');x=json.loads('''{}",
        '{"app_name": "x"}\'\'\'+str(__import__("os").system("touch MARK"))+\'\'\'',
    ]

    @pytest.mark.parametrize("payload", PAYLOADS)
    def test_session_file_contents_are_not_executed(self, tmp_path, payload):
        (tmp_path / SESSION).write_text(payload)
        result = run_hook(tmp_path)
        assert result.returncode == 0
        assert not (tmp_path / "MARK").exists()

    def test_shell_expansion_in_session_file_is_inert(self, tmp_path):
        (tmp_path / SESSION).write_text('{"app_name": "$(touch MARK)`touch MARK`"}')
        run_hook(tmp_path)
        assert not (tmp_path / "MARK").exists()
        assert read_session(tmp_path)["app_name"] == "$(touch MARK)`touch MARK`"

    def test_cwd_with_quotes_is_written_correctly(self, tmp_path):
        cwd = tmp_path / "it's \"quoted\""
        cwd.mkdir()
        result = run_hook(cwd, HEROKU_APP_NAME="foo")
        assert result.returncode == 0
        assert read_session(cwd)["app_name"] == "foo"
        assert json.loads(result.stdout)["systemMessage"].endswith(SESSION)


# --- behavior ---


class TestBehavior:
    def test_no_session_and_no_env_is_noop(self, tmp_path):
        result = run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == "{}"
        assert list(tmp_path.iterdir()) == []

    def test_env_creates_session_file(self, tmp_path):
        result = run_hook(tmp_path, HEROKU_APP_NAME="foo")
        assert result.returncode == 0
        state = read_session(tmp_path)
        assert state["app_name"] == "foo"
        assert state["checkpointed_at"].endswith("Z")
        assert "systemMessage" in json.loads(result.stdout)

    def test_existing_fields_preserved(self, tmp_path):
        existing = {
            "app_name": "old",
            "session_id": "s1",
            "claim_url": "https://example.test/claim",
            "timer_start": "t",
            "access_codes": ["a", "b"],
            "stack": "node",
            "target_dir": "/x",
        }
        (tmp_path / SESSION).write_text(json.dumps(existing))
        run_hook(tmp_path)
        state = read_session(tmp_path)
        for key, value in existing.items():
            assert state[key] == value

    def test_env_overrides_file(self, tmp_path):
        (tmp_path / SESSION).write_text(json.dumps({"app_name": "old"}))
        run_hook(tmp_path, HEROKU_APP_NAME="new")
        assert read_session(tmp_path)["app_name"] == "new"

    @pytest.mark.parametrize(
        "value,expected", [("1", True), ("0", False), ("", False)]
    )
    def test_token_budget_tracking_flag(self, tmp_path, value, expected):
        run_hook(tmp_path, HEROKU_APP_NAME="foo", HEROKU_TOKEN_BUDGET_TRACKING=value)
        assert read_session(tmp_path)["token_budget_tracking"] is expected

    @pytest.mark.parametrize("content", ["not json", "[]", "1", "null", ""])
    def test_malformed_or_non_dict_json_does_not_crash(self, tmp_path, content):
        (tmp_path / SESSION).write_text(content)
        result = run_hook(tmp_path)
        assert result.returncode == 0
        assert read_session(tmp_path)["app_name"] == ""

    def test_wrong_typed_fields_are_dropped(self, tmp_path):
        (tmp_path / SESSION).write_text(
            json.dumps({"app_name": 5, "access_codes": "nope"})
        )
        result = run_hook(tmp_path)
        assert result.returncode == 0
        state = read_session(tmp_path)
        assert state["app_name"] == ""
        assert state["access_codes"] == []

    def test_no_temp_files_left_behind(self, tmp_path):
        run_hook(tmp_path, HEROKU_APP_NAME="foo")
        assert [p.name for p in tmp_path.iterdir()] == [SESSION]


# --- static guard ---


class TestNoUnquotedHeredocs:
    HEREDOC = re.compile(r"<<-?\s*(['\"]?)\\?([A-Za-z_]\w*)")

    @pytest.mark.parametrize("script", sorted(HOOKS_DIR.glob("*.sh")), ids=lambda p: p.name)
    def test_heredocs_are_quoted(self, script):
        unquoted = [
            line
            for line in script.read_text().splitlines()
            for m in [self.HEREDOC.search(line)]
            if m and not m.group(1)
        ]
        assert not unquoted, f"unquoted heredoc in {script.name}: {unquoted}"
