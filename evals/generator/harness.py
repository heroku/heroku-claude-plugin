"""Generator eval harness — shared base class for Layer 2 determinism tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
EVALS_TMP = REPO_ROOT / "evals" / ".tmp"
SCAFFOLD = REPO_ROOT / "scripts" / "scaffold.py"

# Layer 2 files asserted for byte-identity across runs
LAYER2_FILES = {
    "node":   ["Procfile", "app.json", "project.toml", "eslint.config.js", ".prettierrc", ".pre-commit-config.yaml"],
    "python": ["Procfile", "app.json", "project.toml", "requirements.txt", ".python-version", ".pre-commit-config.yaml", "pyproject.toml"],
    "rails":  ["Procfile", "app.json", "project.toml", ".rubocop.yml", ".pre-commit-config.yaml"],
    "go":     ["Procfile", "app.json", "project.toml", "main.go", "go.mod", ".golangci.yml", ".pre-commit-config.yaml"],
}

LAYER2_DOCKER_FILES = ["Dockerfile", "docker-compose.yml"]


def run_scaffold(target_dir: Path, *, name: str, stack: str, **kwargs) -> tuple[int, dict, str]:
    """Run scaffold.py into target_dir. Returns (returncode, summary_dict, stderr)."""
    cmd = [
        sys.executable, str(SCAFFOLD),
        "--name", name,
        "--stack", stack,
        "--dir", str(target_dir),
    ]
    if kwargs.get("addons"):
        cmd += ["--addons", kwargs["addons"]]
    if kwargs.get("variant"):
        cmd += ["--variant", kwargs["variant"]]
    if kwargs.get("with_docker"):
        cmd.append("--with-docker")

    result = subprocess.run(cmd, capture_output=True, text=True)
    summary = {}
    if result.stdout.strip():
        try:
            summary = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
    return result.returncode, summary, result.stderr


class ScaffoldEvalCase(unittest.TestCase):
    """Base class for per-stack generator evals."""

    STACK: str = ""
    VARIANT: str | None = None

    def setUp(self) -> None:
        EVALS_TMP.mkdir(parents=True, exist_ok=True)
        self.workdir = EVALS_TMP / self._testMethodName
        self.workdir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if not os.environ.get("KEEP_EVAL_ARTIFACTS"):
            shutil.rmtree(self.workdir, ignore_errors=True)

    def scaffold(self, name: str, **kw) -> tuple[Path, dict]:
        """Scaffold into a fresh subdir. Returns (target_dir, summary)."""
        target = self.workdir / name
        # VARIANT from class takes precedence unless caller explicitly overrides
        if "variant" not in kw and self.VARIANT:
            kw["variant"] = self.VARIANT
        rc, summary, stderr = run_scaffold(target, name=name, stack=self.STACK, **kw)
        self.assertEqual(rc, 0, f"scaffold failed:\n{stderr}")
        self.assertEqual(summary.get("status"), "ok", f"unexpected summary: {summary}")
        return target, summary

    # -----------------------------------------------------------------------
    # Assertion helpers
    # -----------------------------------------------------------------------

    def assert_procfile_web(self, target_dir: Path, expected_substr: str) -> None:
        procfile = target_dir / "Procfile"
        self.assertTrue(procfile.exists(), "Procfile missing")
        content = procfile.read_text(encoding="utf-8")
        web_lines = [ln for ln in content.splitlines() if ln.startswith("web:")]
        self.assertEqual(len(web_lines), 1, f"Expected exactly one web: line, got: {web_lines}")
        self.assertIn(expected_substr, web_lines[0], f"web: line missing '{expected_substr}'")

    def assert_procfile_release(self, target_dir: Path, expected_substr: str) -> None:
        content = (target_dir / "Procfile").read_text(encoding="utf-8")
        release_lines = [ln for ln in content.splitlines() if ln.startswith("release:")]
        self.assertTrue(release_lines, "No release: line found")
        self.assertIn(expected_substr, release_lines[0])

    def assert_project_toml(self, target_dir: Path, expected_buildpack: str) -> None:
        path = target_dir / "project.toml"
        self.assertTrue(path.exists(), "project.toml missing")
        content = path.read_text(encoding="utf-8")
        self.assertIn('schema-version = "0.2"', content, "project.toml missing schema-version")
        self.assertIn('builder = "heroku/builder:24"', content, "project.toml missing pinned builder")
        self.assertIn(f'id = "{expected_buildpack}"', content, f"project.toml missing buildpack {expected_buildpack}")
        self.assertIn('id = "heroku/procfile"', content, "project.toml missing heroku/procfile")

    def assert_app_json_addons(self, target_dir: Path, expected_slugs: list[str]) -> dict:
        app_json_path = target_dir / "app.json"
        self.assertTrue(app_json_path.exists(), "app.json missing")
        data = json.loads(app_json_path.read_text(encoding="utf-8"))
        actual = sorted(data.get("addons", []))
        self.assertEqual(actual, sorted(expected_slugs), f"addon mismatch: {actual} != {expected_slugs}")
        return data

    def assert_no_app_json_buildpacks(self, target_dir: Path) -> None:
        data = json.loads((target_dir / "app.json").read_text(encoding="utf-8"))
        self.assertNotIn("buildpacks", data, "app.json should not declare buildpacks (use project.toml)")

    def assert_gitignore_has(self, target_dir: Path, *entries: str) -> None:
        gitignore = target_dir / ".gitignore"
        self.assertTrue(gitignore.exists(), ".gitignore missing")
        lines = {ln.strip() for ln in gitignore.read_text(encoding="utf-8").splitlines()}
        for entry in entries:
            self.assertIn(entry, lines, f".gitignore missing '{entry}'")

    def assert_no_duplicate_gitignore(self, target_dir: Path) -> None:
        lines = [
            ln.strip()
            for ln in (target_dir / ".gitignore").read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        self.assertEqual(len(lines), len(set(lines)), f"Duplicate .gitignore entries: {lines}")

    def assert_lf_only(self, path: Path) -> None:
        raw = path.read_bytes()
        self.assertNotIn(b"\r\n", raw, f"CRLF found in {path}")

    def assert_trailing_newline(self, path: Path) -> None:
        raw = path.read_bytes()
        self.assertTrue(raw.endswith(b"\n"), f"No trailing newline in {path}")

    def assert_layer2_deterministic(self, name: str, **kw) -> tuple[Path, Path]:
        """Scaffold twice with identical inputs; assert Layer 2 files are byte-identical.

        Both runs use the same app name so Procfile and app.json content is identical.
        They scaffold into different subdirs (run1/, run2/) for isolation.
        """
        run1_dir = self.workdir / f"{name}-run1" / name
        run2_dir = self.workdir / f"{name}-run2" / name

        kw_copy = dict(kw)
        if "variant" not in kw_copy and self.VARIANT:
            kw_copy["variant"] = self.VARIANT

        rc1, _, stderr1 = run_scaffold(run1_dir, name=name, stack=self.STACK, **kw_copy)
        self.assertEqual(rc1, 0, f"run1 scaffold failed:\n{stderr1}")
        rc2, _, stderr2 = run_scaffold(run2_dir, name=name, stack=self.STACK, **kw_copy)
        self.assertEqual(rc2, 0, f"run2 scaffold failed:\n{stderr2}")

        t1, t2 = run1_dir, run2_dir

        stack_key = self.VARIANT if self.VARIANT and self.VARIANT in LAYER2_FILES else self.STACK
        files = LAYER2_FILES.get(stack_key, LAYER2_FILES.get(self.STACK, []))

        if kw.get("with_docker"):
            files = files + LAYER2_DOCKER_FILES

        for fname in files:
            f1, f2 = t1 / fname, t2 / fname
            if not f1.exists() and not f2.exists():
                continue
            self.assertTrue(f1.exists(), f"Layer 2 file missing in run1: {fname}")
            self.assertTrue(f2.exists(), f"Layer 2 file missing in run2: {fname}")
            self.assertEqual(
                f1.read_bytes(), f2.read_bytes(),
                f"Layer 2 file not deterministic: {fname}"
            )
        return t1, t2
