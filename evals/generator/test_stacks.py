"""Generator evals — Layer 2 determinism + contract assertions per stack.

Run all:  python3 -m unittest discover -s evals/generator -v
Run one:  python3 -m unittest evals.generator.test_stacks.GoStackEval -v
Keep:     KEEP_EVAL_ARTIFACTS=1 python3 -m unittest discover -s evals/generator
"""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from harness import ScaffoldEvalCase  # noqa: E402


# ---------------------------------------------------------------------------
# Node.js
# ---------------------------------------------------------------------------

class NodeStackEval(ScaffoldEvalCase):
    STACK = "node"

    def test_contract(self) -> None:
        """Layer 2 files exist with correct content."""
        target, summary = self.scaffold("hello-node")
        self.assertEqual(summary["stack"], "node")
        self.assertTrue((target / "server.js").exists())
        self.assertTrue((target / "package.json").exists())
        self.assert_procfile_web(target, "npm start")
        self.assert_no_app_json_buildpacks(target)
        self.assert_app_json_addons(target, [])
        self.assert_project_toml(target, "heroku/nodejs")
        self.assert_gitignore_has(target, "node_modules/")
        self.assert_no_duplicate_gitignore(target)

    def test_contract_with_addons(self) -> None:
        target, summary = self.scaffold("node-addons", addons="postgres,redis")
        self.assertEqual(
            summary["addons"],
            ["heroku-postgresql", "heroku-redis"],
        )
        self.assert_app_json_addons(target, ["heroku-postgresql", "heroku-redis"])
        data = json.loads((target / "app.json").read_text())
        self.assertIn("DATABASE_URL", data.get("env", {}))
        self.assertIn("REDIS_URL", data.get("env", {}))

    def test_determinism(self) -> None:
        self.assert_layer2_deterministic("det-node")

    def test_package_json_engines(self) -> None:
        target, _ = self.scaffold("node-engines")
        pkg = json.loads((target / "package.json").read_text())
        self.assertIn("node", pkg.get("engines", {}))

    def test_linting_config(self) -> None:
        target, _ = self.scaffold("node-lint")
        self.assertTrue((target / "eslint.config.js").exists(), "eslint.config.js missing")
        self.assertTrue((target / ".prettierrc").exists(), ".prettierrc missing")
        self.assertTrue((target / ".pre-commit-config.yaml").exists(), ".pre-commit-config.yaml missing")
        pkg = json.loads((target / "package.json").read_text())
        self.assertIn("lint", pkg.get("scripts", {}))
        self.assertIn("format", pkg.get("scripts", {}))
        self.assertIn("lint-staged", pkg)

    def test_lf_newlines(self) -> None:
        target, _ = self.scaffold("node-lf")
        for fname in ["Procfile", "app.json", "server.js"]:
            self.assert_lf_only(target / fname)
            self.assert_trailing_newline(target / fname)


# ---------------------------------------------------------------------------
# Python — FastAPI
# ---------------------------------------------------------------------------

class PythonFastAPIEval(ScaffoldEvalCase):
    STACK = "python"
    VARIANT = "fastapi"

    def test_contract(self) -> None:
        target, summary = self.scaffold("hello-fastapi", variant="fastapi")
        self.assertTrue((target / "main.py").exists())
        self.assertTrue((target / "requirements.txt").exists())
        self.assertTrue((target / ".python-version").exists())
        self.assert_procfile_web(target, "gunicorn")
        self.assert_procfile_web(target, "$PORT")
        self.assert_no_app_json_buildpacks(target)
        self.assert_project_toml(target, "heroku/python")
        self.assert_gitignore_has(target, "__pycache__/", ".venv/")

    def test_contract_with_postgres(self) -> None:
        target, summary = self.scaffold("fastapi-pg", variant="fastapi", addons="postgres")
        self.assert_app_json_addons(target, ["heroku-postgresql"])
        reqs = (target / "requirements.txt").read_text()
        self.assertIn("psycopg2-binary", reqs)

    def test_determinism(self) -> None:
        self.assert_layer2_deterministic("det-fastapi", variant="fastapi")

    def test_python_version_file(self) -> None:
        target, _ = self.scaffold("fastapi-ver", variant="fastapi")
        ver = (target / ".python-version").read_text().strip()
        self.assertTrue(ver.startswith("3."), f"Unexpected python version: {ver}")

    def test_linting_config(self) -> None:
        target, _ = self.scaffold("fastapi-lint", variant="fastapi")
        self.assertTrue((target / ".pre-commit-config.yaml").exists(), ".pre-commit-config.yaml missing")
        self.assertTrue((target / "pyproject.toml").exists(), "pyproject.toml missing")
        precommit = (target / ".pre-commit-config.yaml").read_text()
        self.assertIn("ruff", precommit)
        self.assertIn("gitleaks", precommit)

    def test_lf_newlines(self) -> None:
        target, _ = self.scaffold("fastapi-lf", variant="fastapi")
        for fname in ["Procfile", "app.json", "requirements.txt", ".python-version"]:
            self.assert_lf_only(target / fname)
            self.assert_trailing_newline(target / fname)


# ---------------------------------------------------------------------------
# Python — Flask
# ---------------------------------------------------------------------------

class PythonFlaskEval(ScaffoldEvalCase):
    STACK = "python"
    VARIANT = "flask"

    def test_contract(self) -> None:
        target, _ = self.scaffold("hello-flask", variant="flask")
        self.assertTrue((target / "app.py").exists())
        self.assert_procfile_web(target, "gunicorn app:app")
        self.assert_procfile_web(target, "$PORT")

    def test_determinism(self) -> None:
        self.assert_layer2_deterministic("det-flask", variant="flask")


# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------

class GoStackEval(ScaffoldEvalCase):
    STACK = "go"

    def test_contract(self) -> None:
        target, summary = self.scaffold("hello-go")
        self.assertTrue((target / "main.go").exists())
        self.assertTrue((target / "go.mod").exists())
        self.assert_procfile_web(target, "bin/hello-go")
        self.assert_no_app_json_buildpacks(target)
        self.assert_app_json_addons(target, [])
        self.assert_project_toml(target, "heroku/go")
        self.assert_gitignore_has(target, "bin/")

    def test_contract_with_addons(self) -> None:
        target, summary = self.scaffold("go-addons", addons="postgres,redis")
        self.assert_app_json_addons(target, ["heroku-postgresql", "heroku-redis"])

    def test_determinism(self) -> None:
        self.assert_layer2_deterministic("det-go")

    def test_port_binding_in_main(self) -> None:
        target, _ = self.scaffold("go-port")
        main = (target / "main.go").read_text()
        self.assertIn("PORT", main, "main.go does not read $PORT")
        self.assertIn("ListenAndServe", main)

    def test_linting_config(self) -> None:
        target, _ = self.scaffold("go-lint")
        self.assertTrue((target / ".golangci.yml").exists(), ".golangci.yml missing")
        self.assertTrue((target / ".pre-commit-config.yaml").exists(), ".pre-commit-config.yaml missing")
        golangci = (target / ".golangci.yml").read_text()
        self.assertIn("gosec", golangci)
        self.assertIn("errcheck", golangci)
        precommit = (target / ".pre-commit-config.yaml").read_text()
        self.assertIn("gofmt", precommit)
        self.assertIn("gitleaks", precommit)

    def test_lf_newlines(self) -> None:
        target, _ = self.scaffold("go-lf")
        for fname in ["Procfile", "app.json", "main.go", "go.mod"]:
            self.assert_lf_only(target / fname)
            self.assert_trailing_newline(target / fname)


# ---------------------------------------------------------------------------
# Docker output (when --with-docker)
# ---------------------------------------------------------------------------

class DockerOutputEval(ScaffoldEvalCase):
    STACK = "python"

    def test_dockerfile_generated(self) -> None:
        target, _ = self.scaffold("docker-py", variant="fastapi", with_docker=True)
        self.assertTrue((target / "Dockerfile").exists())
        self.assertTrue((target / "docker-compose.yml").exists())
        self.assertTrue((target / ".dockerignore").exists())

    def test_docker_compose_addons(self) -> None:
        target, _ = self.scaffold("docker-pg-redis", variant="fastapi", addons="postgres,redis", with_docker=True)
        dc = json.loads((target / "docker-compose.yml").read_text())
        services = dc.get("services", {})
        self.assertIn("postgres", services)
        self.assertIn("redis", services)
        env = services["app"]["environment"]
        self.assertIn("DATABASE_URL", env)
        self.assertIn("REDIS_URL", env)

    def test_docker_determinism(self) -> None:
        self.assert_layer2_deterministic("det-docker", variant="fastapi", with_docker=True)


# ---------------------------------------------------------------------------
# Addon validation
# ---------------------------------------------------------------------------

class AddonValidationEval(ScaffoldEvalCase):
    STACK = "go"

    def test_unsupported_addon_raises(self) -> None:
        from scripts.heroku_glue.common import ScaffoldError
        import scripts.heroku_glue.go as go_module

        with self.assertRaises(ScaffoldError):
            go_module.effective_addons({"addons": ["kafka"]})

    def test_addon_list_sorted(self) -> None:
        target, summary = self.scaffold("sorted-addons", addons="redis,postgres")
        self.assertEqual(summary["addons"], ["heroku-postgresql", "heroku-redis"])
        data = json.loads((target / "app.json").read_text())
        addons = data.get("addons", [])
        self.assertEqual(addons, sorted(addons), "app.json addons not sorted")


# ---------------------------------------------------------------------------
# Python — Django
# ---------------------------------------------------------------------------

@unittest.skipUnless(shutil.which("django-admin"), "django-admin not installed")
class PythonDjangoEval(ScaffoldEvalCase):
    STACK = "python"
    VARIANT = "django"

    def test_contract(self) -> None:
        target, summary = self.scaffold("hello-django")
        # requirements.txt must exist and contain django + gunicorn
        reqs_path = target / "requirements.txt"
        self.assertTrue(reqs_path.exists(), "requirements.txt missing")
        reqs = reqs_path.read_text(encoding="utf-8")
        self.assertIn("django", reqs.lower())
        self.assertIn("gunicorn", reqs)
        # Procfile web: gunicorn config.wsgi, $PORT
        self.assert_procfile_web(target, "gunicorn config.wsgi")
        self.assert_procfile_web(target, "$PORT")
        # Procfile release: python manage.py migrate
        self.assert_procfile_release(target, "python manage.py migrate")
        # app.json buildpack
        self.assert_no_app_json_buildpacks(target)
        # app.json addons — Django default includes postgres
        self.assert_app_json_addons(target, ["heroku-postgresql"])
        # app.json env must include DJANGO_SECRET_KEY and DJANGO_DEBUG
        data = json.loads((target / "app.json").read_text(encoding="utf-8"))
        env = data.get("env", {})
        self.assertIn("DJANGO_SECRET_KEY", env)
        self.assertIn("DJANGO_DEBUG", env)
        # .python-version must exist
        self.assertTrue((target / ".python-version").exists(), ".python-version missing")

    def test_contract_with_redis(self) -> None:
        target, _ = self.scaffold("django-redis", addons="redis")
        self.assert_app_json_addons(target, ["heroku-postgresql", "heroku-redis"])
        reqs = (target / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("redis", reqs)

    def test_determinism(self) -> None:
        self.assert_layer2_deterministic("det-django")

    def test_linting_config(self) -> None:
        target, _ = self.scaffold("django-lint")
        self.assertTrue(
            (target / ".pre-commit-config.yaml").exists(),
            ".pre-commit-config.yaml missing",
        )
        precommit = (target / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        self.assertIn("ruff", precommit)
        self.assertTrue((target / "pyproject.toml").exists(), "pyproject.toml missing")

    def test_lf_newlines(self) -> None:
        target, _ = self.scaffold("django-lf")
        for fname in ["Procfile", "app.json", "requirements.txt", ".python-version"]:
            self.assert_lf_only(target / fname)
            self.assert_trailing_newline(target / fname)


# ---------------------------------------------------------------------------
# Ruby on Rails
# ---------------------------------------------------------------------------

@unittest.skipUnless(shutil.which("rails"), "rails not installed")
class RailsStackEval(ScaffoldEvalCase):
    STACK = "rails"

    def test_contract(self) -> None:
        target, summary = self.scaffold("hello-rails")
        # Procfile web: bundle exec puma, PORT env var referenced
        self.assert_procfile_web(target, "bundle exec puma")
        self.assert_procfile_web(target, "PORT")
        # Procfile release: bundle exec rails db:migrate
        self.assert_procfile_release(target, "bundle exec rails db:migrate")
        # app.json buildpack
        self.assert_no_app_json_buildpacks(target)
        self.assert_project_toml(target, "heroku/ruby")
        # app.json addons — Rails default includes postgres
        self.assert_app_json_addons(target, ["heroku-postgresql"])
        # app.json env
        data = json.loads((target / "app.json").read_text(encoding="utf-8"))
        env = data.get("env", {})
        self.assertIn("RAILS_MASTER_KEY", env)
        self.assertIn("RAILS_LOG_TO_STDOUT", env)
        self.assertIn("RAILS_SERVE_STATIC_FILES", env)
        # Linting config files
        self.assertTrue((target / ".rubocop.yml").exists(), ".rubocop.yml missing")
        self.assertTrue(
            (target / ".pre-commit-config.yaml").exists(),
            ".pre-commit-config.yaml missing",
        )

    def test_contract_with_redis(self) -> None:
        target, _ = self.scaffold("rails-redis", addons="redis")
        self.assert_app_json_addons(target, ["heroku-postgresql", "heroku-redis"])

    def test_determinism(self) -> None:
        self.assert_layer2_deterministic("det-rails")

    def test_lf_newlines(self) -> None:
        target, _ = self.scaffold("rails-lf")
        for fname in ["Procfile", "app.json"]:
            self.assert_lf_only(target / fname)
            self.assert_trailing_newline(target / fname)


if __name__ == "__main__":
    unittest.main()
