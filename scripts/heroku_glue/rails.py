"""Ruby on Rails stack module."""

from pathlib import Path

from . import common

STACK = "rails"
DISPLAY_NAME = "Ruby on Rails"
REQUIRED_TOOLS = [
    ("ruby", "https://www.ruby-lang.org/en/documentation/installation/"),
    ("rails", "https://guides.rubyonrails.org/getting_started.html"),
    ("bundle", "https://bundler.io/"),
]
DEFAULT_ADDONS = ["postgres"]

RUBY_VERSION = "3.3.12"

_DOCKERIGNORE = """\
.git/
log/
tmp/
.bundle/
vendor/bundle/
.env
.env.*
node_modules/
public/assets/
public/packs/
"""

_RUBOCOP_YML = """\
require:
  - rubocop-rails
  - rubocop-performance

AllCops:
  NewCops: enable
  TargetRubyVersion: 3.3
  Exclude:
    - 'db/schema.rb'
    - 'bin/**/*'
    - 'vendor/**/*'
"""

_PRECOMMIT_CONFIG = """\
repos:
  - repo: local
    hooks:
      - id: rubocop
        name: rubocop
        entry: bundle exec rubocop --autocorrect-all
        language: system
        types: [ruby]
      - id: brakeman
        name: brakeman
        entry: bundle exec brakeman -q --no-pager
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
    """Layer 1: rails new."""
    common.require_tools(REQUIRED_TOOLS)
    parent = target_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    common.run(
        ["rails", "new", target_dir.name, "--database=postgresql", "--skip-git"],
        cwd=parent,
    )


def apply_glue(app_name: str, target_dir: Path, options: dict) -> None:
    """Layer 2: write deterministic Heroku glue files."""
    addons = effective_addons(options)

    common.write_file(
        target_dir / "Procfile",
        "web: bundle exec puma -t 5:5 -p ${PORT:-3000} -e ${RACK_ENV:-production}\n"
        "release: bundle exec rails db:migrate",
    )

    env = {
        "RAILS_MASTER_KEY": {
            "description": "Rails credentials master key — set manually via heroku config:set",
            "required": True,
        },
        "RAILS_LOG_TO_STDOUT": {"value": "enabled"},
        "RAILS_SERVE_STATIC_FILES": {"value": "enabled"},
    }
    if "heroku-postgresql" in addons:
        env["DATABASE_URL"] = {"description": "Heroku Postgres connection string", "required": True}
    if "heroku-redis" in addons:
        env["REDIS_URL"] = {"description": "Heroku Redis connection string", "required": True}

    app_json = common.build_app_json(
        app_name,
        addons=addons,
        env=env,
        formation={"web": {"quantity": 1, "size": "basic"}},
    )
    common.write_json(target_dir / "app.json", app_json)
    common.write_file(target_dir / "project.toml", common.build_project_toml("heroku/ruby"))
    common.merge_gitignore(target_dir, gitignore_lines(options))
    common.write_file(target_dir / ".rubocop.yml", _RUBOCOP_YML)
    common.write_file(target_dir / ".pre-commit-config.yaml", _PRECOMMIT_CONFIG)

    if options.get("with_docker"):
        _write_dockerfile(target_dir)
        common.write_docker_compose(target_dir, app_name, addons)


def gitignore_lines(options: dict) -> list[str]:
    return [
        "log/",
        "tmp/",
        ".bundle/",
        "vendor/bundle/",
        "public/assets/",
        "public/packs/",
        "config/master.key",
        "config/credentials/*.key",
    ]


def _write_dockerfile(target_dir: Path) -> None:
    dockerfile = f"""\
FROM ruby:{RUBY_VERSION}-slim
RUN apt-get update -qq && apt-get install -y nodejs postgresql-client build-essential libpq-dev
WORKDIR /app
COPY Gemfile Gemfile.lock ./
RUN bundle install
COPY . .
ENV PORT=3000 RAILS_ENV=production RAILS_LOG_TO_STDOUT=enabled RAILS_SERVE_STATIC_FILES=enabled
EXPOSE $PORT
CMD bundle exec puma -t 5:5 -p $PORT -e $RAILS_ENV
"""
    common.write_file(target_dir / "Dockerfile", dockerfile)
    common.write_file(target_dir / ".dockerignore", _DOCKERIGNORE)
