"""Tests for scripts/session.py — the single reader/writer of the session file."""
import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

import session

SCRIPT = Path(__file__).parents[2] / "scripts" / "session.py"


def cli(cwd, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--dir", str(cwd)],
        capture_output=True, text=True,
    )


class TestLoad:
    def test_missing_file_is_empty(self, tmp_path):
        assert session.load(tmp_path / session.SESSION_FILENAME) == {}

    @pytest.mark.parametrize("content", ["not json", "[]", "1", "null", ""])
    def test_malformed_or_non_dict_is_empty(self, tmp_path, content):
        path = tmp_path / session.SESSION_FILENAME
        path.write_text(content)
        assert session.load(path) == {}

    def test_unknown_and_retired_keys_are_dropped(self, tmp_path):
        path = tmp_path / session.SESSION_FILENAME
        path.write_text(json.dumps({"app_id": "a", "conversation_id": "c", "app_uuid": "u", "x": 1}))
        assert session.load(path) == {"app_id": "a"}

    def test_wrong_types_are_dropped(self, tmp_path):
        path = tmp_path / session.SESSION_FILENAME
        path.write_text(json.dumps({
            "app_id": 5, "expires_at": "soon", "access_codes": ["ok", 3], "token_budget_tracking": "yes",
        }))
        assert session.load(path) == {}

    def test_bool_is_not_a_number(self, tmp_path):
        path = tmp_path / session.SESSION_FILENAME
        path.write_text(json.dumps({"expires_at": True}))
        assert session.load(path) == {}


class TestCoerce:
    def test_string_is_kept_verbatim(self):
        assert session.coerce("app_id", "abc=1") == "abc=1"

    def test_number_int_then_float(self):
        assert session.coerce("expires_at", "4070908800000") == 4070908800000
        assert session.coerce("expires_at", "1.5") == 1.5

    def test_number_rejects_text(self):
        with pytest.raises(session.SessionError):
            session.coerce("expires_at", "soon")

    def test_list_parses_json(self):
        assert session.coerce("access_codes", '["a","b"]') == ["a", "b"]

    @pytest.mark.parametrize("text", ["nope", "[1]", '"x"'])
    def test_list_rejects_bad_json_or_type(self, text):
        with pytest.raises(session.SessionError):
            session.coerce("access_codes", text)

    def test_bool(self):
        assert session.coerce("token_budget_tracking", "true") is True

    def test_unknown_key(self):
        with pytest.raises(session.SessionError, match="unknown key"):
            session.coerce("conversation_id", "x")


class TestUpdateClear:
    def test_update_merges_and_preserves(self, tmp_path):
        path = session.session_path(tmp_path)
        session.update(path, app_id="a", stack="node")
        state = session.update(path, claim_url="https://c.test")
        assert state == {"app_id": "a", "stack": "node", "claim_url": "https://c.test"}
        assert json.loads(path.read_text()) == state

    def test_update_rejects_unknown_or_mistyped(self, tmp_path):
        path = session.session_path(tmp_path)
        with pytest.raises(session.SessionError):
            session.update(path, conversation_id="c")
        with pytest.raises(session.SessionError):
            session.update(path, expires_at="soon")
        assert not path.exists()

    def test_file_is_sorted_lf_with_one_trailing_newline(self, tmp_path):
        path = session.session_path(tmp_path)
        session.update(path, stack="go", app_id="a")
        text = path.read_text()
        assert text.endswith("}\n") and not text.endswith("\n\n") and "\r" not in text
        assert list(json.loads(text)) == ["app_id", "stack"]

    def test_clear(self, tmp_path):
        path = session.session_path(tmp_path)
        assert session.clear(path) is False
        session.update(path, app_id="a")
        assert session.clear(path) is True
        assert not path.exists()

    def test_no_temp_files_left_behind(self, tmp_path):
        session.update(session.session_path(tmp_path), app_id="a")
        assert [p.name for p in tmp_path.iterdir()] == [session.SESSION_FILENAME]


class TestCheckpoint:
    NOW = datetime.datetime(2026, 10, 30, 12, 0, tzinfo=datetime.timezone.utc)

    def test_env_wins_over_file_even_when_empty(self, tmp_path):
        path = session.session_path(tmp_path)
        session.update(path, app_id="old", claim_url="https://c.test")
        state = session.checkpoint(path, env={"HEROKU_APP_ID": "new", "HEROKU_CLAIM_URL": ""}, now=self.NOW)
        assert state["app_id"] == "new"
        assert state["claim_url"] == ""

    def test_defaults_give_stable_shape(self, tmp_path):
        state = session.checkpoint(session.session_path(tmp_path), env={}, now=self.NOW)
        assert state["app_id"] == "" and state["access_codes"] == []
        assert state["token_budget_tracking"] is False
        assert state["checkpointed_at"] == "2026-10-30T12:00:00.000000Z"
        assert "expires_at" not in state and "deployed_at" not in state


class TestCli:
    def test_set_then_show_then_clear(self, tmp_path):
        r = cli(tmp_path, "set", "app_id=abc", "expires_at=4070908800000", 'access_codes=["x"]')
        assert r.returncode == 0
        shown = json.loads(cli(tmp_path, "show").stdout)
        assert shown["exists"] is True
        assert shown["session"] == {"access_codes": ["x"], "app_id": "abc", "expires_at": 4070908800000}
        assert json.loads(cli(tmp_path, "clear").stdout)["cleared"] is True
        assert json.loads(cli(tmp_path, "show").stdout)["exists"] is False

    @pytest.mark.parametrize("pair", ["conversation_id=x", "expires_at=soon", "noequals"])
    def test_bad_input_exits_2_and_writes_nothing(self, tmp_path, pair):
        r = cli(tmp_path, "set", pair)
        assert r.returncode == 2
        assert "error" in json.loads(r.stderr)
        assert list(tmp_path.iterdir()) == []

    def test_set_preserves_hostile_values_as_data(self, tmp_path):
        value = "$(touch MARK)`touch MARK`'\""
        assert cli(tmp_path, "set", f"app_name={value}").returncode == 0
        assert not (tmp_path / "MARK").exists()
        assert json.loads(cli(tmp_path, "show").stdout)["session"]["app_name"] == value
