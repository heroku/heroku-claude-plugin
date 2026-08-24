"""Node.js (Express) stack module."""

from pathlib import Path

from . import common

STACK = "node"
DISPLAY_NAME = "Node.js (Express)"
REQUIRED_TOOLS = [
    ("node", "https://nodejs.org/en/download/"),
    ("npm", "https://nodejs.org/en/download/"),
]
DEFAULT_ADDONS: list[str] = []

NODE_VERSION = "24.x"

_SERVER_JS = """\
const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());

app.get('/', (req, res) => {
  res.json({ status: 'ok', message: 'Hello from Express on Heroku!' });
});

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
"""

_DOCKERIGNORE = """\
node_modules/
npm-debug.log
.env
.env.*
dist/
build/
"""

_ESLINT_CONFIG = """\
import js from '@eslint/js';

export default [
  js.configs.recommended,
  {
    rules: {
      'no-console': 'warn',
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
];
"""

_PRETTIERRC = """\
{
  "singleQuote": true,
  "trailingComma": "es5"
}
"""

_PRECOMMIT_CONFIG = """\
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: end-of-file-fixer
      - id: trailing-whitespace
"""


def effective_addons(options: dict) -> list[str]:
    all_addons = DEFAULT_ADDONS + list(options.get("addons", []))
    return common.resolve_addons(all_addons) if all_addons else []


def scaffold(app_name: str, target_dir: Path, options: dict) -> None:
    """Layer 1: npm init + express install."""
    common.require_tools(REQUIRED_TOOLS)
    target_dir.mkdir(parents=True, exist_ok=True)
    common.run(["npm", "init", "-y"], cwd=target_dir)
    common.run(["npm", "install", "express"], cwd=target_dir)


def apply_glue(app_name: str, target_dir: Path, options: dict) -> None:
    """Layer 2: write deterministic Heroku glue files."""
    addons = effective_addons(options)

    # Update package.json: engines + scripts + lint-staged
    pkg_path = target_dir / "package.json"
    if pkg_path.exists():
        import json
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        pkg.setdefault("engines", {})["node"] = NODE_VERSION
        scripts = pkg.setdefault("scripts", {})
        scripts["start"] = "node server.js"
        scripts["lint"] = "eslint ."
        scripts["format"] = "prettier --write ."
        scripts["test"] = "jest"
        scripts["prepare"] = "husky"
        pkg["lint-staged"] = {
            "*.js": ["eslint --fix", "prettier --write"],
        }
        common.write_json(pkg_path, pkg)

    common.write_file(target_dir / "server.js", _SERVER_JS)
    common.write_file(target_dir / "Procfile", "web: npm start")
    common.write_file(target_dir / "eslint.config.js", _ESLINT_CONFIG)
    common.write_file(target_dir / ".prettierrc", _PRETTIERRC)
    common.write_file(target_dir / ".pre-commit-config.yaml", _PRECOMMIT_CONFIG)

    common.write_file(target_dir / "project.toml", common.build_project_toml("heroku/nodejs"))
    common.merge_gitignore(target_dir, common.BASE_GITIGNORE + gitignore_lines(options))

    if options.get("with_docker"):
        _write_dockerfile(target_dir)
        common.write_docker_compose(target_dir, app_name, addons)


def secret_env_vars(options: dict) -> list[str]:
    return []


def gitignore_lines(options: dict) -> list[str]:
    return ["node_modules/", "npm-debug.log", "dist/", "build/", ".npm/"]


def _write_dockerfile(target_dir: Path) -> None:
    dockerfile = f"""\
FROM node:{NODE_VERSION.replace('x', 'lts')}-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
ENV PORT=3000
EXPOSE $PORT
CMD ["npm", "start"]
"""
    common.write_file(target_dir / "Dockerfile", dockerfile)
    common.write_file(target_dir / ".dockerignore", _DOCKERIGNORE)
