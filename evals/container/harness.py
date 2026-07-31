"""Container eval harness — Docker-based boot tests for scaffolded apps.

Scaffolds an app, builds it with a minimal eval Dockerfile, spins up
docker-compose with Postgres + Redis sidecars, probes HTTP and addons,
then tears down.

Run all:  python3 -m unittest discover -s evals/container -v
Run one:  python3 -m unittest evals.container.test_containers.PythonFastAPIContainerEval -v

Requires Docker daemon running.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
EVALS_TMP = REPO_ROOT / "evals" / ".tmp"
DOCKERFILES_DIR = Path(__file__).parent / "dockerfiles"
SCAFFOLD = REPO_ROOT / "scripts" / "scaffold.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _docker_available() -> bool:
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _http_probe(port: int, path: str = "/", retries: int = 20, delay: float = 1.5) -> tuple[bool, str]:
    import urllib.request
    url = f"http://127.0.0.1:{port}{path}"
    for _ in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                return resp.status < 500, f"HTTP {resp.status}"
        except Exception:
            time.sleep(delay)
    return False, f"No response after {retries} retries on {url}"


class ContainerEvalCase(unittest.TestCase):
    """Base class for Docker container boot tests."""

    STACK: str = ""
    VARIANT: str | None = None
    DOCKERFILE: str = ""  # filename in evals/container/dockerfiles/
    ADDONS: list[str] = []
    HTTP_PATH: str = "/"

    @classmethod
    def setUpClass(cls) -> None:
        if not _docker_available():
            raise unittest.SkipTest("Docker not available — skipping container evals")

    def setUp(self) -> None:
        EVALS_TMP.mkdir(parents=True, exist_ok=True)
        self.workdir = EVALS_TMP / f"container-{self._testMethodName}"
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.app_name = f"eval-{self.STACK}"
        self.target_dir = self.workdir / self.app_name
        self.image_tag = f"heroku-plugin-eval:{self.STACK}-{id(self)}"
        self.port = _free_port()

    def tearDown(self) -> None:
        # Stop any running containers
        _run(["docker", "compose", "down", "--volumes", "--remove-orphans"], cwd=self.target_dir)
        _run(["docker", "rmi", self.image_tag, "-f"])
        if not os.environ.get("KEEP_EVAL_ARTIFACTS"):
            shutil.rmtree(self.workdir, ignore_errors=True)

    def _scaffold(self) -> None:
        cmd = [
            sys.executable, str(SCAFFOLD),
            "--name", self.app_name,
            "--stack", self.STACK,
            "--dir", str(self.target_dir),
        ]
        if self.VARIANT:
            cmd += ["--variant", self.VARIANT]
        if self.ADDONS:
            cmd += ["--addons", ",".join(self.ADDONS)]
        result = _run(cmd)
        self.assertEqual(result.returncode, 0, f"scaffold failed:\n{result.stderr}")

    def _copy_eval_dockerfile(self) -> None:
        src = DOCKERFILES_DIR / self.DOCKERFILE
        dst = self.target_dir / "Dockerfile"
        shutil.copy(src, dst)

    def _build_image(self) -> None:
        result = _run(
            ["docker", "build", "-t", self.image_tag, "."],
            cwd=self.target_dir,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, f"docker build failed:\n{result.stderr}")

    def _write_test_compose(self) -> None:
        """Write a docker-compose for testing: app + sidecars."""
        services: dict = {
            "app": {
                "image": self.image_tag,
                "ports": [f"{self.port}:{self.port}"],
                "environment": {"PORT": str(self.port)},
            }
        }
        if "heroku-postgresql" in self.ADDONS:
            services["postgres"] = {
                "image": "postgres:16",
                "environment": {
                    "POSTGRES_DB": self.app_name.replace("-", "_"),
                    "POSTGRES_USER": "postgres",
                    "POSTGRES_PASSWORD": "postgres",
                },
            }
            services["app"]["environment"]["DATABASE_URL"] = (
                f"postgres://postgres:postgres@postgres:5432/{self.app_name.replace('-', '_')}?sslmode=disable"
            )
            services["app"].setdefault("depends_on", []).append("postgres")

        if "heroku-redis" in self.ADDONS:
            services["redis"] = {"image": "redis:7-alpine"}
            services["app"]["environment"]["REDIS_URL"] = "redis://redis:6379"
            services["app"].setdefault("depends_on", []).append("redis")

        compose = {"version": "3.8", "services": services}
        dc_path = self.target_dir / "docker-compose.test.yml"
        dc_path.write_text(
            json.dumps(compose, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return dc_path

    def run_boot_test(self) -> None:
        """Full lifecycle: scaffold → build → compose up → probe → assert."""
        self._scaffold()
        self._copy_eval_dockerfile()
        self._build_image()
        dc_file = self._write_test_compose()

        _run(["docker", "compose", "-f", str(dc_file), "up", "-d"], cwd=self.target_dir)
        time.sleep(3)  # give containers a moment to start

        ok, detail = _http_probe(self.port, self.HTTP_PATH)
        self.assertTrue(ok, f"App did not respond: {detail}")
