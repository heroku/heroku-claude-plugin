"""Go (net/http) stack module."""

from pathlib import Path

from . import common

STACK = "go"
DISPLAY_NAME = "Go"
REQUIRED_TOOLS = [
    ("go", "https://go.dev/doc/install"),
]
DEFAULT_ADDONS: list[str] = []

GO_VERSION = "1.24"

_MAIN_GO = """\
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":  "ok",
			"message": "Hello from Go on Heroku!",
		})
	})

	log.Printf("Server starting on port %s", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatal(err)
	}
}
"""

_DOCKERIGNORE = """\
bin/
*.test
.env
.env.*
"""

_GOLANGCI_YML = """\
linters:
  enable:
    - errcheck
    - gosimple
    - govet
    - ineffassign
    - staticcheck
    - unused
    - gosec
"""

_PRECOMMIT_CONFIG = """\
repos:
  - repo: local
    hooks:
      - id: gofmt
        name: gofmt
        entry: gofmt -l -w
        language: system
        types: [go]
      - id: go-vet
        name: go vet
        entry: go vet ./...
        language: system
        pass_filenames: false
      - id: golangci-lint
        name: golangci-lint
        entry: golangci-lint run
        language: system
        pass_filenames: false
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
    """Layer 1: go mod init."""
    common.require_tools(REQUIRED_TOOLS)
    target_dir.mkdir(parents=True, exist_ok=True)
    module_name = f"github.com/user/{app_name}"
    common.run(["go", "mod", "init", module_name], cwd=target_dir)


def apply_glue(app_name: str, target_dir: Path, options: dict) -> None:
    """Layer 2: write deterministic Heroku glue files."""
    addons = effective_addons(options)

    common.write_file(target_dir / "main.go", _MAIN_GO)
    common.write_file(target_dir / "Procfile", f"web: bin/{app_name}")
    common.write_file(target_dir / ".golangci.yml", _GOLANGCI_YML)
    common.write_file(target_dir / ".pre-commit-config.yaml", _PRECOMMIT_CONFIG)

    common.write_file(target_dir / "project.toml", common.build_project_toml("heroku/go"))

    common.merge_gitignore(target_dir, common.BASE_GITIGNORE + gitignore_lines(options))

    if options.get("with_docker"):
        _write_dockerfile(target_dir, app_name)
        common.write_docker_compose(target_dir, app_name, addons)


def secret_env_vars(options: dict) -> list[str]:
    return []


def gitignore_lines(options: dict) -> list[str]:
    return ["bin/", "*.test", "*.out"]


def _write_dockerfile(target_dir: Path, app_name: str) -> None:
    dockerfile = f"""\
FROM golang:{GO_VERSION}-alpine AS builder
WORKDIR /app
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o bin/{app_name} .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/bin/{app_name} .
ENV PORT=8080
EXPOSE $PORT
CMD ["./{app_name}"]
"""
    common.write_file(target_dir / "Dockerfile", dockerfile)
    common.write_file(target_dir / ".dockerignore", _DOCKERIGNORE)
