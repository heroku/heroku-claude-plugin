"""Unit tests for scripts/heroku_glue/common.py"""

import json
import stat
from pathlib import Path

import pytest

from heroku_glue.common import (
    BASE_GITIGNORE,
    ADDON_CONFIG_VARS,
    ScaffoldError,
    build_docker_compose,
    build_project_toml,
    effective_addons,
    merge_gitignore,
    require_tools,
    resolve_addons,
    write_file,
    write_json,
)


# ---------------------------------------------------------------------------
# resolve_addons
# ---------------------------------------------------------------------------

class TestResolveAddons:
    def test_postgres_friendly_name(self):
        assert resolve_addons(["postgres"]) == ["heroku-postgresql"]

    def test_postgresql_friendly_name(self):
        assert resolve_addons(["postgresql"]) == ["heroku-postgresql"]

    def test_redis_friendly_name(self):
        assert resolve_addons(["redis"]) == ["heroku-redis"]

    def test_canonical_slug_passthrough(self):
        assert resolve_addons(["heroku-postgresql"]) == ["heroku-postgresql"]

    def test_canonical_redis_passthrough(self):
        assert resolve_addons(["heroku-redis"]) == ["heroku-redis"]

    def test_sorted_output(self):
        result = resolve_addons(["redis", "postgres"])
        assert result == sorted(result)

    def test_deduplication(self):
        result = resolve_addons(["postgres", "postgresql", "heroku-postgresql"])
        assert result == ["heroku-postgresql"]

    def test_unsupported_addon_raises(self):
        with pytest.raises(ScaffoldError, match="not supported"):
            resolve_addons(["kafka"])

    def test_unknown_addon_raises(self):
        with pytest.raises(ScaffoldError, match="Unknown addon"):
            resolve_addons(["mongodb"])

    def test_case_insensitive(self):
        assert resolve_addons(["Postgres"]) == ["heroku-postgresql"]

    def test_whitespace_stripped(self):
        assert resolve_addons([" redis "]) == ["heroku-redis"]

    def test_empty_list(self):
        assert resolve_addons([]) == []

    def test_both_addons_sorted(self):
        result = resolve_addons(["redis", "postgres"])
        assert result == ["heroku-postgresql", "heroku-redis"]


# ---------------------------------------------------------------------------
# effective_addons
# ---------------------------------------------------------------------------

class TestEffectiveAddons:
    def _make_module(self, defaults):
        """Create a minimal module-like object with DEFAULT_ADDONS."""
        class M:
            DEFAULT_ADDONS = defaults
        return M()

    def test_merges_defaults_and_options(self):
        m = self._make_module(["postgres"])
        result = effective_addons(m, {"addons": ["redis"]})
        assert result == ["heroku-postgresql", "heroku-redis"]

    def test_empty_options_returns_defaults(self):
        m = self._make_module(["postgres"])
        result = effective_addons(m, {})
        assert result == ["heroku-postgresql"]

    def test_empty_defaults_returns_options(self):
        m = self._make_module([])
        result = effective_addons(m, {"addons": ["redis"]})
        assert result == ["heroku-redis"]

    def test_both_empty_returns_empty(self):
        m = self._make_module([])
        result = effective_addons(m, {})
        assert result == []

    def test_deduplication_across_defaults_and_options(self):
        m = self._make_module(["postgres"])
        result = effective_addons(m, {"addons": ["postgres"]})
        assert result == ["heroku-postgresql"]

    def test_module_without_default_addons_attr(self):
        class M:
            pass
        result = effective_addons(M(), {})
        assert result == []


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------

class TestWriteFile:
    def test_creates_file(self, tmp_path):
        p = tmp_path / "test.txt"
        write_file(p, "hello")
        assert p.exists()

    def test_utf8_encoding(self, tmp_path):
        p = tmp_path / "utf8.txt"
        write_file(p, "héllo wörld")
        assert p.read_text(encoding="utf-8") == "héllo wörld\n"

    def test_trailing_newline_added(self, tmp_path):
        p = tmp_path / "nonl.txt"
        write_file(p, "no newline")
        assert p.read_bytes().endswith(b"\n")

    def test_trailing_newline_not_doubled(self, tmp_path):
        p = tmp_path / "nl.txt"
        write_file(p, "already\n")
        assert p.read_text(encoding="utf-8") == "already\n"

    def test_crlf_normalized_to_lf(self, tmp_path):
        p = tmp_path / "crlf.txt"
        write_file(p, "line1\r\nline2\r\n")
        assert b"\r\n" not in p.read_bytes()
        assert b"line1\nline2\n" == p.read_bytes()

    def test_cr_only_normalized(self, tmp_path):
        p = tmp_path / "cr.txt"
        write_file(p, "line1\rline2")
        assert b"\r" not in p.read_bytes()

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "a" / "b" / "c.txt"
        write_file(p, "deep")
        assert p.exists()

    def test_executable_bit(self, tmp_path):
        p = tmp_path / "script.sh"
        write_file(p, "#!/bin/bash\necho hi", executable=True)
        mode = p.stat().st_mode
        assert mode & stat.S_IXUSR

    def test_non_executable_by_default(self, tmp_path):
        p = tmp_path / "file.txt"
        write_file(p, "content")
        mode = p.stat().st_mode
        assert not (mode & stat.S_IXUSR)


# ---------------------------------------------------------------------------
# write_json
# ---------------------------------------------------------------------------

class TestWriteJson:
    def test_writes_valid_json(self, tmp_path):
        p = tmp_path / "out.json"
        write_json(p, {"b": 2, "a": 1})
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data == {"a": 1, "b": 2}

    def test_sorted_keys(self, tmp_path):
        p = tmp_path / "out.json"
        write_json(p, {"z": 3, "a": 1, "m": 2})
        raw = p.read_text(encoding="utf-8")
        keys = [line.strip().split('"')[1] for line in raw.splitlines() if '":' in line]
        assert keys == sorted(keys)

    def test_two_space_indent(self, tmp_path):
        p = tmp_path / "out.json"
        write_json(p, {"key": "value"})
        raw = p.read_text(encoding="utf-8")
        assert '  "key"' in raw

    def test_deterministic_across_calls(self, tmp_path):
        p1 = tmp_path / "a.json"
        p2 = tmp_path / "b.json"
        data = {"z": 3, "a": 1, "m": [1, 2, 3]}
        write_json(p1, data)
        write_json(p2, data)
        assert p1.read_bytes() == p2.read_bytes()

    def test_lf_newlines(self, tmp_path):
        p = tmp_path / "out.json"
        write_json(p, {"key": "value"})
        assert b"\r\n" not in p.read_bytes()

    def test_trailing_newline(self, tmp_path):
        p = tmp_path / "out.json"
        write_json(p, {"key": "value"})
        assert p.read_bytes().endswith(b"\n")


# ---------------------------------------------------------------------------
# merge_gitignore
# ---------------------------------------------------------------------------

class TestMergeGitignore:
    def test_creates_gitignore_if_absent(self, tmp_path):
        merge_gitignore(tmp_path, [".env"])
        assert (tmp_path / ".gitignore").exists()

    def test_appends_new_entries(self, tmp_path):
        gi = tmp_path / ".gitignore"
        gi.write_text("*.log\n", encoding="utf-8")
        merge_gitignore(tmp_path, [".env"])
        content = gi.read_text(encoding="utf-8")
        assert ".env" in content
        assert "*.log" in content

    def test_does_not_duplicate_existing_entries(self, tmp_path):
        gi = tmp_path / ".gitignore"
        gi.write_text(".env\n", encoding="utf-8")
        merge_gitignore(tmp_path, [".env"])
        lines = [l.strip() for l in gi.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert lines.count(".env") == 1

    def test_adds_header_once(self, tmp_path):
        merge_gitignore(tmp_path, [".env"])
        merge_gitignore(tmp_path, ["*.log"])
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert content.count("heroku-plugin") == 1

    def test_noop_when_all_entries_exist(self, tmp_path):
        gi = tmp_path / ".gitignore"
        gi.write_text(".env\n*.log\n", encoding="utf-8")
        original_mtime = gi.stat().st_mtime
        merge_gitignore(tmp_path, [".env", "*.log"])
        # File should not be rewritten (no new content to add)
        content = gi.read_text(encoding="utf-8")
        assert content == ".env\n*.log\n"

    def test_ignores_blank_lines_in_new_entries(self, tmp_path):
        merge_gitignore(tmp_path, ["", "  ", ".env"])
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert ".env" in content
        # Blank entries should not appear as bare blank lines in content
        non_comment_lines = [l for l in content.splitlines() if l.strip() and not l.startswith("#")]
        assert "" not in non_comment_lines


# ---------------------------------------------------------------------------
# build_project_toml
# ---------------------------------------------------------------------------

class TestBuildProjectToml:
    def test_contains_schema_version(self):
        result = build_project_toml("heroku/python")
        assert 'schema-version = "0.2"' in result

    def test_omits_builder(self):
        result = build_project_toml("heroku/python")
        assert "builder" not in result

    def test_contains_language_buildpack(self):
        result = build_project_toml("heroku/nodejs")
        assert 'id = "heroku/nodejs"' in result

    def test_contains_procfile_buildpack(self):
        result = build_project_toml("heroku/python")
        assert 'id = "heroku/procfile"' in result

    def test_procfile_is_last_buildpack(self):
        result = build_project_toml("heroku/go")
        lang_pos = result.index('id = "heroku/go"')
        procfile_pos = result.index('id = "heroku/procfile"')
        assert lang_pos < procfile_pos

    def test_deterministic_across_calls(self):
        assert build_project_toml("heroku/ruby") == build_project_toml("heroku/ruby")

    def test_lf_newlines_only(self):
        result = build_project_toml("heroku/python")
        assert "\r\n" not in result

    def test_trailing_newline(self):
        result = build_project_toml("heroku/python")
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# build_docker_compose
# ---------------------------------------------------------------------------

class TestBuildDockerCompose:
    def test_no_addons_basic_structure(self):
        result = build_docker_compose("my-app", [])
        assert "version" in result
        assert "app" in result["services"]
        assert "depends_on" not in result["services"]["app"]

    def test_postgres_service_added(self):
        result = build_docker_compose("my-app", ["heroku-postgresql"])
        services = result["services"]
        assert "postgres" in services
        assert "DATABASE_URL" in services["app"]["environment"]
        assert "postgres" in services["app"]["depends_on"]

    def test_redis_service_added(self):
        result = build_docker_compose("my-app", ["heroku-redis"])
        services = result["services"]
        assert "redis" in services
        assert "REDIS_URL" in services["app"]["environment"]
        assert "redis" in services["app"]["depends_on"]

    def test_both_addons(self):
        result = build_docker_compose("my-app", ["heroku-postgresql", "heroku-redis"])
        services = result["services"]
        assert "postgres" in services
        assert "redis" in services
        assert "DATABASE_URL" in services["app"]["environment"]
        assert "REDIS_URL" in services["app"]["environment"]
        assert "postgres" in services["app"]["depends_on"]
        assert "redis" in services["app"]["depends_on"]

    def test_database_url_uses_app_name(self):
        result = build_docker_compose("cool-app", ["heroku-postgresql"])
        db_url = result["services"]["app"]["environment"]["DATABASE_URL"]
        assert "cool_app" in db_url

    def test_database_url_hyphen_to_underscore(self):
        result = build_docker_compose("my-cool-app", ["heroku-postgresql"])
        db_url = result["services"]["app"]["environment"]["DATABASE_URL"]
        assert "my_cool_app" in db_url

    def test_redis_url_correct(self):
        result = build_docker_compose("my-app", ["heroku-redis"])
        assert result["services"]["app"]["environment"]["REDIS_URL"] == "redis://redis:6379"

    def test_deterministic_across_calls(self):
        r1 = build_docker_compose("app", ["heroku-postgresql", "heroku-redis"])
        r2 = build_docker_compose("app", ["heroku-postgresql", "heroku-redis"])
        assert r1 == r2


# ---------------------------------------------------------------------------
# require_tools
# ---------------------------------------------------------------------------

class TestRequireTools:
    def test_passes_when_tool_exists(self):
        # python3 is always present in our test environment
        require_tools([("python3", "https://python.org")])

    def test_raises_when_tool_missing(self):
        with pytest.raises(ScaffoldError, match="not found on PATH"):
            require_tools([("__nonexistent_binary_xyz__", "https://example.com")])

    def test_error_includes_install_url(self):
        with pytest.raises(ScaffoldError, match="https://example.com/install"):
            require_tools([("__nonexistent_binary_xyz__", "https://example.com/install")])

    def test_multiple_missing_tools_reported(self):
        with pytest.raises(ScaffoldError) as exc_info:
            require_tools([
                ("__missing_1__", "https://one.com"),
                ("__missing_2__", "https://two.com"),
            ])
        msg = str(exc_info.value)
        assert "__missing_1__" in msg
        assert "__missing_2__" in msg

    def test_partial_missing_raises(self):
        with pytest.raises(ScaffoldError):
            require_tools([
                ("python3", "https://python.org"),
                ("__nonexistent_binary_xyz__", "https://example.com"),
            ])
