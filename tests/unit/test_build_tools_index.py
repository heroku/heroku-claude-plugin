"""Tests for scripts/build_tools_index.py (preferred-tools.md -> .json)."""

import json
import subprocess
import sys
from pathlib import Path

import build_tools_index as bti
import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "build_tools_index.py"
REFERENCES = Path(__file__).parents[2] / "references"

HEADER = (
    "| Stack | Package | Registry | Version | License | Link | Vetted on "
    "| Approved by |\n"
    "|---|---|---|---|---|---|---|---|\n"
)
NODE_ROW = (
    "| node | example-qr | npm | 1.2.3 | MIT "
    "| https://www.npmjs.com/package/example-qr "
    "| 2026-11-04 | @someone |\n"
)


def need(
    need_id="qr-code",
    description="Generate QR codes.",
    aliases="qr, qr code",
    rows="",
):
    return (
        f"## {need_id}\n\n"
        f"Description: {description}\n"
        f"Aliases: {aliases}\n\n"
        f"{HEADER}{rows}\n"
    )


def build(text):
    return bti.build_index(text)


class TestParse:
    def test_need_without_tools_is_listed_with_empty_tools(self):
        index = build(need())
        assert index["needs"]["qr-code"] == {
            "description": "Generate QR codes.",
            "aliases": ["qr", "qr code"],
            "tools": {},
        }

    def test_tool_row_is_parsed_into_named_fields(self):
        tool = build(need(rows=NODE_ROW))["needs"]["qr-code"]["tools"]["node"]
        assert tool == {
            "package": "example-qr",
            "registry": "npm",
            "version": "1.2.3",
            "license": "MIT",
            "link": "https://www.npmjs.com/package/example-qr",
            "vetted_on": "2026-11-04",
            "approved_by": "@someone",
        }

    def test_text_before_the_first_need_is_ignored(self):
        index = build("# Preferred Tools\n\nIntro prose.\n\n" + need())
        assert list(index["needs"]) == ["qr-code"]

    def test_aliases_are_lowercased_deduplicated_and_sorted(self):
        index = build(need(aliases="QR Code, qr, QR, qr code"))
        assert index["needs"]["qr-code"]["aliases"] == ["qr", "qr code"]

    def test_generated_marker_is_present(self):
        assert "_generated" in build(need())

    def test_needs_are_independent_of_source_order(self):
        a, b = need("aaa", aliases="alpha"), need("bbb", aliases="beta")
        assert bti.render(build(a + b)) == bti.render(build(b + a))


class TestValidation:
    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("# Only prose\n", "no needs"),
            (need("QR_Code"), "need id"),
            (need() + need(), "duplicate need"),
            (need(aliases="same") + need("other", aliases="same"), "alias"),
        ],
    )
    def test_need_level_errors(self, text, message):
        with pytest.raises(bti.ToolsIndexError, match=message):
            build(text)

    def test_missing_description_is_rejected(self):
        text = need().replace("Description: Generate QR codes.\n", "")
        with pytest.raises(bti.ToolsIndexError, match="Description"):
            build(text)

    def test_missing_aliases_is_rejected(self):
        text = need().replace("Aliases: qr, qr code\n", "")
        with pytest.raises(bti.ToolsIndexError, match="Aliases"):
            build(text)

    def test_missing_table_is_rejected(self):
        text = "## qr-code\n\nDescription: d\nAliases: qr\n"
        with pytest.raises(bti.ToolsIndexError, match="table"):
            build(text)

    def test_wrong_table_header_is_rejected(self):
        text = need().replace("| Package |", "| Pkg |")
        with pytest.raises(bti.ToolsIndexError, match="header"):
            build(text)

    @pytest.mark.parametrize(
        ("old", "new", "message"),
        [
            ("| node |", "| cobol |", "stack"),
            ("| npm |", "| pypi |", "registry"),
            ("| 2026-11-04 |", "| 04/11/2026 |", "date"),
            ("| 2026-11-04 |", "| 2026-13-45 |", "date"),
            ("https://www.npmjs.com/package/example-qr", "http://x.test/a", "link"),
            ("| MIT |", "|  |", "empty"),
        ],
    )
    def test_row_field_errors(self, old, new, message):
        with pytest.raises(bti.ToolsIndexError, match=message):
            build(need(rows=NODE_ROW.replace(old, new)))

    def test_row_with_wrong_column_count_is_rejected(self):
        with pytest.raises(bti.ToolsIndexError, match="columns"):
            build(need(rows="| node | example-qr | npm |\n"))

    def test_duplicate_stack_in_one_need_is_rejected(self):
        with pytest.raises(bti.ToolsIndexError, match="duplicate stack"):
            build(need(rows=NODE_ROW + NODE_ROW))

    def test_error_names_the_line_number(self):
        text = need(rows=NODE_ROW.replace("| node |", "| cobol |"))
        with pytest.raises(bti.ToolsIndexError, match=r"line \d+"):
            build(text)


class TestRender:
    def test_output_is_sorted_two_space_json_with_one_trailing_newline(self):
        out = bti.render(build(need(rows=NODE_ROW)))
        assert out.endswith("}\n") and not out.endswith("\n\n")
        assert "\r" not in out
        data = json.loads(out)
        assert (
            out == json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        )

    def test_rendering_twice_is_byte_identical(self):
        text = need(rows=NODE_ROW)
        assert bti.render(build(text)) == bti.render(build(text))


class TestCli:
    def run(self, *args):
        return subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
        )

    def test_writes_json_next_to_the_source(self, tmp_path):
        src, out = tmp_path / "t.md", tmp_path / "t.json"
        src.write_text(need(rows=NODE_ROW))
        result = self.run("--source", str(src), "--output", str(out))
        assert result.returncode == 0
        assert out.read_text() == bti.render(build(src.read_text()))

    def test_check_passes_when_json_is_current(self, tmp_path):
        src, out = tmp_path / "t.md", tmp_path / "t.json"
        src.write_text(need())
        self.run("--source", str(src), "--output", str(out))
        assert (
            self.run("--check", "--source", str(src), "--output", str(out)).returncode
            == 0
        )

    def test_check_fails_when_json_is_stale(self, tmp_path):
        src, out = tmp_path / "t.md", tmp_path / "t.json"
        src.write_text(need())
        self.run("--source", str(src), "--output", str(out))
        src.write_text(need(description="Changed."))
        result = self.run("--check", "--source", str(src), "--output", str(out))
        assert result.returncode == 1
        assert "out of date" in result.stderr

    def test_check_does_not_modify_the_json(self, tmp_path):
        src, out = tmp_path / "t.md", tmp_path / "t.json"
        src.write_text(need())
        out.write_text("stale")
        self.run("--check", "--source", str(src), "--output", str(out))
        assert out.read_text() == "stale"

    def test_check_fails_when_json_is_missing(self, tmp_path):
        src = tmp_path / "t.md"
        src.write_text(need())
        result = self.run(
            "--check", "--source", str(src), "--output", str(tmp_path / "x.json")
        )
        assert result.returncode == 1

    def test_invalid_source_exits_2_and_writes_nothing(self, tmp_path):
        src, out = tmp_path / "t.md", tmp_path / "t.json"
        src.write_text("# nothing here\n")
        result = self.run("--source", str(src), "--output", str(out))
        assert result.returncode == 2
        assert "no needs" in result.stderr
        assert not out.exists()

    def test_missing_source_exits_2(self, tmp_path):
        result = self.run("--source", str(tmp_path / "nope.md"))
        assert result.returncode == 2


class TestShippedIndex:
    def test_json_matches_markdown(self):
        source = (REFERENCES / "preferred-tools.md").read_text(encoding="utf-8")
        shipped = (REFERENCES / "preferred-tools.json").read_text(encoding="utf-8")
        assert shipped == bti.render(bti.build_index(source))

    def test_qr_code_need_is_defined(self):
        data = json.loads(
            (REFERENCES / "preferred-tools.json").read_text(encoding="utf-8")
        )
        assert "qr-code" in data["needs"]


class TestMainInProcess:
    def test_writes_the_expected_json(self, tmp_path, capsys):
        src, out = tmp_path / "t.md", tmp_path / "t.json"
        src.write_text(need(rows=NODE_ROW))
        assert bti.main(["--source", str(src), "--output", str(out)]) == 0
        assert out.read_text() == bti.render(build(src.read_text()))
        assert "Wrote" in capsys.readouterr().out

    def test_check_reports_stale_json(self, tmp_path, capsys):
        src, out = tmp_path / "t.md", tmp_path / "t.json"
        src.write_text(need())
        out.write_text("stale")
        argv = ["--check", "--source", str(src), "--output", str(out)]
        assert bti.main(argv) == 1
        assert "out of date" in capsys.readouterr().err

    def test_check_passes_after_a_build(self, tmp_path):
        src, out = tmp_path / "t.md", tmp_path / "t.json"
        src.write_text(need())
        bti.main(["--source", str(src), "--output", str(out)])
        argv = ["--check", "--source", str(src), "--output", str(out)]
        assert bti.main(argv) == 0

    def test_invalid_source_returns_2_without_writing(self, tmp_path, capsys):
        src, out = tmp_path / "t.md", tmp_path / "t.json"
        src.write_text("# nothing\n")
        assert bti.main(["--source", str(src), "--output", str(out)]) == 2
        assert "no needs" in capsys.readouterr().err
        assert not out.exists()
