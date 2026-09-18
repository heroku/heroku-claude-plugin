#!/usr/bin/env python3
"""Heroku app scaffolder — orchestration spine.

Outputs a JSON summary on stdout; all progress and errors go to stderr.

Usage:
  python3 scripts/scaffold.py \\
    --name <app-name> --stack <node|python|rails|go|website> \\
    [--dir <path>] [--addons postgres,redis] [--variant fastapi|django|flask] \\
    [--with-docker] [--dry-run]
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# Allow running as a script from any location
sys.path.insert(0, str(Path(__file__).parent))

from heroku_glue import common

STACK_MODULES: dict = {}


def _load_modules() -> None:
    from heroku_glue import go, node, python, rails, website

    STACK_MODULES.update({
        "node": node,
        "python": python,
        "rails": rails,
        "go": go,
        "website": website,
    })


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold a Heroku-ready app.")
    parser.add_argument("--name", required=True, help="Application name (kebab-case)")
    parser.add_argument(
        "--stack",
        required=True,
        choices=["node", "python", "rails", "go", "website"],
        help="Stack to scaffold",
    )
    parser.add_argument("--dir", help="Target directory (default: ./<name>)")
    parser.add_argument("--addons", help="Comma-separated addon names: postgres, redis")
    parser.add_argument("--variant", help="Stack variant (e.g. fastapi, django, flask)")
    parser.add_argument(
        "--with-docker",
        action="store_true",
        help="Generate Dockerfile + docker-compose.yml for local dev",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate toolchain and inputs without writing files",
    )
    return parser.parse_args()


def main() -> int:
    _load_modules()
    args = _parse_args()

    app_name = args.name
    stack = args.stack
    target_dir = Path(args.dir) if args.dir else Path.cwd() / app_name
    addons = [a.strip() for a in args.addons.split(",")] if args.addons else []
    options = {
        "addons": addons,
        "variant": args.variant,
        "with_docker": args.with_docker,
    }

    module = STACK_MODULES[stack]

    try:
        # Validate addons before touching filesystem
        canonical_addons = module.effective_addons(options)

        if args.dry_run:
            common.require_tools(module.REQUIRED_TOOLS)
            summary = {
                "status": "dry-run-ok",
                "stack": stack,
                "display_name": module.DISPLAY_NAME,
                "target_dir": str(target_dir.resolve()),
                "addons": canonical_addons,
                "secret_env_vars": module.secret_env_vars(options),
                "variant": args.variant,
                "with_docker": args.with_docker,
            }
            print(json.dumps(summary))
            return 0

        # Safety: track if we created target_dir for rollback purposes
        created_target = not target_dir.exists()

        try:
            common.require_tools(module.REQUIRED_TOOLS)
            common.log(f"Scaffolding {module.DISPLAY_NAME} into {target_dir}")
            module.scaffold(app_name, target_dir, options)
            module.apply_glue(app_name, target_dir, options)
        except Exception:
            if created_target and target_dir.exists():
                common.log(f"Rolling back — removing {target_dir}")
                shutil.rmtree(target_dir, ignore_errors=True)
            raise

        summary = {
            "status": "ok",
            "stack": stack,
            "display_name": module.DISPLAY_NAME,
            "app_name": app_name,
            "target_dir": str(target_dir.resolve()),
            "addons": canonical_addons,
            "secret_env_vars": module.secret_env_vars(options),
            "variant": args.variant,
            "with_docker": args.with_docker,
        }
        # Write scaffold file without target_dir so it's deterministic across runs
        scaffold_file = {k: v for k, v in summary.items() if k != "target_dir"}
        common.write_json(target_dir / ".heroku-plugin-scaffold.json", scaffold_file)
        print(json.dumps(summary))
        return 0

    except common.ScaffoldError as exc:
        print(f"[heroku-scaffold] ERROR\n{exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[heroku-scaffold] UNEXPECTED ERROR\n{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
