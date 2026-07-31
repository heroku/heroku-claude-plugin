"""Container eval tests — Docker boot tests per stack.

Run:  python3 -m unittest discover -s evals/container -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from harness import ContainerEvalCase  # noqa: E402


class PythonFastAPIContainerEval(ContainerEvalCase):
    STACK = "python"
    VARIANT = "fastapi"
    DOCKERFILE = "python.Dockerfile"

    def test_boot(self) -> None:
        self.run_boot_test()


class PythonFastAPIPostgresContainerEval(ContainerEvalCase):
    STACK = "python"
    VARIANT = "fastapi"
    DOCKERFILE = "python.Dockerfile"
    ADDONS = ["heroku-postgresql"]

    def test_boot_with_postgres(self) -> None:
        self.run_boot_test()


class NodeContainerEval(ContainerEvalCase):
    STACK = "node"
    DOCKERFILE = "node.Dockerfile"

    def test_boot(self) -> None:
        self.run_boot_test()


class GoContainerEval(ContainerEvalCase):
    STACK = "go"
    DOCKERFILE = "go.Dockerfile"

    def test_boot(self) -> None:
        self.run_boot_test()


class GoPostgresRedisContainerEval(ContainerEvalCase):
    STACK = "go"
    DOCKERFILE = "go.Dockerfile"
    ADDONS = ["heroku-postgresql", "heroku-redis"]

    def test_boot_with_addons(self) -> None:
        self.run_boot_test()


if __name__ == "__main__":
    unittest.main()
