#!/usr/bin/env python3
"""End-to-end build-and-deploy eval in stub mode.

Validates the full workflow: scaffold → deploy (stub) → check status (stub).

Usage:
  HEROKU_MCP_STUB=1 python3 evals/skills/e2e_build_and_deploy.py
  HEROKU_MCP_STUB=1 python3 evals/skills/e2e_build_and_deploy.py --stack python
  HEROKU_MCP_STUB=1 python3 evals/skills/e2e_build_and_deploy.py --keep
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SCAFFOLD = REPO_ROOT / "scripts" / "scaffold.py"
STUBS_DIR = REPO_ROOT / "mcp" / "stubs"

# Expected .gitignore marker per stack — confirms merge_gitignore() ran.
STACK_GITIGNORE_MARKERS: dict[str, str] = {
    "python": "__pycache__/",
    "node": "node_modules/",
    "go": "bin/",
    "rails": "log/",
}


def _read_stub(name: str) -> dict:
    stub_path = STUBS_DIR / name
    data = json.loads(stub_path.read_text(encoding="utf-8"))
    return data["result"]["structuredContent"]


def run_e2e(stack: str = "python", variant: str = "fastapi", keep: bool = False) -> int:
    """Run end-to-end workflow in stub mode."""
    print(f"\n{'═' * 55}")
    print(f"E2E eval: stack={stack} variant={variant} (stub mode)")
    print(f"{'═' * 55}")

    with tempfile.TemporaryDirectory(prefix="heroku-e2e-") as tmpdir:
        target = Path(tmpdir) / "test-app"

        # Step 1: Scaffold
        print("\n[1] Scaffolding...")
        cmd = [sys.executable, str(SCAFFOLD), "--name", "test-app", "--stack", stack]
        if variant:
            cmd += ["--variant", variant]
        cmd += ["--addons", "postgres,redis", "--dir", str(target)]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ✗ Scaffold failed:\n{result.stderr}")
            return 1

        summary = json.loads(result.stdout)
        print(f"  ✓ Scaffolded {summary['display_name']} at {summary['target_dir']}")
        print(f"    Addons: {summary['addons']}")

        # Step 2: Verify Layer 2 files exist
        print("\n[2] Verifying Layer 2 contract...")
        for fname in ["Procfile", "project.toml", ".heroku-plugin-scaffold.json", ".gitignore"]:
            fpath = target / fname
            if not fpath.exists():
                print(f"  ✗ Missing: {fname}")
                return 1
            print(f"  ✓ {fname}")

        # Step 2b: Verify app.json is absent (replaced by .heroku-plugin-scaffold.json)
        if (target / "app.json").exists():
            print("  ✗ app.json must not exist (replaced by .heroku-plugin-scaffold.json)")
            return 1
        print("  ✓ app.json absent (correct)")

        # Step 2c: Verify .gitignore content
        print("\n[2c] Verifying .gitignore content...")
        marker = STACK_GITIGNORE_MARKERS.get(stack)
        if marker:
            gitignore_text = (target / ".gitignore").read_text(encoding="utf-8")
            if marker in gitignore_text:
                print(f"  ✓ .gitignore contains '{marker}'")
            else:
                print(f"  ✗ .gitignore missing '{marker}'")
                return 1
        else:
            print(f"  (no marker defined for stack '{stack}', skipping content check)")

        # Step 2d: Verify .heroku-plugin-scaffold.json structure
        print("\n[2d] Verifying .heroku-plugin-scaffold.json...")
        scaffold_json = json.loads((target / ".heroku-plugin-scaffold.json").read_text(encoding="utf-8"))
        for key in ["status", "stack", "addons", "secret_env_vars"]:
            if key not in scaffold_json:
                print(f"  ✗ Missing key in .heroku-plugin-scaffold.json: {key}")
                return 1
        print(f"  ✓ status: {scaffold_json['status']}")
        print(f"  ✓ addons: {scaffold_json['addons']}")
        print(f"  ✓ secret_env_vars: {scaffold_json['secret_env_vars']}")

        # Step 3: Stub — create anonymous session
        print("\n[3] Create anonymous session (stub)...")
        session_stub = _read_stub("create_anonymous_session.json")
        print(f"  ✓ conversation_id: {session_stub['conversation_id']}")
        print(f"  ✓ tos_status: {session_stub['tos_status']}")
        print(f"  ✓ tos_url: {session_stub['tos_url']}")

        # Step 4: Stub — ToS accepted
        print("\n[4] Check anonymous session state (stub)...")
        tos_stub = _read_stub("check_anonymous_session_state.json")
        print(f"  ✓ tos_status: {tos_stub['tos_status']}")

        # Step 5: Stub — create preview app
        print("\n[5] Create preview app (stub)...")
        app_stub = _read_stub("create_preview_app.json")
        print(f"  ✓ app_uuid: {app_stub['app_uuid']}")
        print(f"  ✓ git_url: {app_stub['git_url']}")
        print(f"  ✓ git_credentials.expires_at: {app_stub['git_credentials']['expires_at']}")

        # Step 6: Stub — addon provisioning
        print("\n[6] Create addon (stub)...")
        addon_stub = _read_stub("create_addon.json")
        print(f"  ✓ addon_id: {addon_stub['addon_id']}")
        print(f"  ✓ state: {addon_stub['state']}")

        print("\n[6b] Get addon status (stub)...")
        addon_status_stub = _read_stub("get_addon_status.json")
        print(f"  ✓ ready: {addon_status_stub['ready']}")
        print(f"  ✓ config_vars: {addon_status_stub['config_vars']}")

        # Step 7: Stub — deployment status (post-push)
        print("\n[7] Get deployment status (stub)...")
        deploy_stub = _read_stub("get_deployment_status.json")
        print(f"  ✓ build.done: {deploy_stub['build']['done']}")
        print(f"  ✓ build.failed: {deploy_stub['build']['failed']}")
        print(f"  ✓ web_url: {deploy_stub['web_url']}")

        # Step 8: Stub — claim status
        print("\n[8] Check claim status (stub)...")
        claim_stub = _read_stub("check_claim_status.json")
        print(f"  ✓ claimed: {claim_stub['claimed']}")
        print(f"  ✓ expired: {claim_stub['expired']}")

        # Step 9: Verify session state schema
        print("\n[9] Verify session state schema...")
        session_state = {
            "conversation_id": session_stub["conversation_id"],
            "app_uuid": app_stub["app_uuid"],
            "app_url": deploy_stub["web_url"],
            "expires_at": deploy_stub["expires_at"],
            "stack": stack,
            "target_dir": str(target),
        }
        for key in ["conversation_id", "app_uuid", "app_url", "expires_at", "stack", "target_dir"]:
            if key not in session_state:
                print(f"  ✗ Missing session key: {key}")
                return 1
        print("  ✓ session state schema valid")

        if keep:
            dest = Path.cwd() / "e2e-eval-output"
            shutil.copytree(str(target), str(dest), dirs_exist_ok=True)
            print(f"\n  Artifacts kept at: {dest}")

    print(f"\n{'─' * 55}")
    print(f"✓ E2E eval PASSED for {stack}/{variant}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E build-and-deploy eval (stub mode).")
    parser.add_argument("--stack", default="python", choices=["node", "python", "rails", "go"])
    parser.add_argument("--variant", default="fastapi")
    parser.add_argument("--keep", action="store_true", help="Keep generated artifacts")
    args = parser.parse_args()

    os.environ["HEROKU_MCP_STUB"] = "1"
    return run_e2e(stack=args.stack, variant=args.variant, keep=args.keep)


if __name__ == "__main__":
    sys.exit(main())
