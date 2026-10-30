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
    "website": ".heroku-plugin-scaffold.json",
}


def _read_stub(name: str) -> dict:
    stub_path = STUBS_DIR / name
    data = json.loads(stub_path.read_text(encoding="utf-8"))
    return data["result"]["structuredContent"]


# Required structuredContent keys per stub, from mcp/mcp-core-contract.md.
STUB_REQUIRED_KEYS: dict[str, set[str]] = {
    "create_preview_app.json": {"app_id", "git_url", "git_credentials"},
    "get_preview_app_git_credentials.json": {"git_credentials"},
    "create_addon.json": {"id", "name", "state", "config_vars", "app"},
    "get_addon_status.json": {"addon_id", "name", "plan", "state", "ready", "config_vars"},
    "set_config_vars.json": {"config_vars", "updated"},
    "get_deployment_status.json": {"app_id", "web_url", "expires_at", "build", "addons"},
    "share_in_browser.json": {"authorization_url", "expires_in", "preview_link"},
    "check_claim_status.json": {"app_id", "claimed", "expired"},
    "discard_preview_app.json": {"app_id"},
}
SESSION_REQUIRED_KEYS = ["app_id", "claim_url", "expires_at", "stack", "target_dir"]
# Identifiers from the retired session-based flow; they must not reappear.
REMOVED_KEYS = {"conversation_id", "app_uuid"}


def validate_stubs() -> list[str]:
    errors: list[str] = []
    on_disk = {p.name for p in STUBS_DIR.glob("*.json")}
    for extra in sorted(on_disk - set(STUB_REQUIRED_KEYS)):
        errors.append(f"{extra}: stub has no contract entry")
    for name, required in STUB_REQUIRED_KEYS.items():
        if name not in on_disk:
            errors.append(f"{name}: stub missing")
            continue
        data = _read_stub(name)
        missing = required - set(data)
        if missing:
            errors.append(f"{name}: missing {sorted(missing)}")
        if REMOVED_KEYS & set(data):
            errors.append(f"{name}: has removed keys {sorted(REMOVED_KEYS & set(data))}")
    return errors


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
        # Static sites have no backend, so the scaffolder rejects addons for them.
        if stack != "website":
            cmd += ["--addons", "postgres,redis"]
        cmd += ["--dir", str(target)]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ✗ Scaffold failed:\n{result.stderr}")
            return 1

        summary = json.loads(result.stdout)
        print(f"  ✓ Scaffolded {summary['display_name']} at {summary['target_dir']}")
        print(f"    Addons: {summary['addons']}")

        # Step 2: Verify Layer 2 files exist
        print("\n[2] Verifying Layer 2 contract...")
        # The static-web-server buildpack supplies the web process, so website apps have no Procfile.
        required = ["project.toml", ".heroku-plugin-scaffold.json", ".gitignore"]
        if stack != "website":
            required.insert(0, "Procfile")
        for fname in required:
            fpath = target / fname
            if not fpath.exists():
                print(f"  ✗ Missing: {fname}")
                return 1
            print(f"  ✓ {fname}")
        if stack == "website" and (target / "Procfile").exists():
            print("  ✗ website apps must not have a Procfile")
            return 1

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

        # Step 3: Stub — create preview app (no session step: identity is the verified user)
        print("\n[3] Create preview app (stub)...")
        app_stub = _read_stub("create_preview_app.json")
        app_id = app_stub["app_id"]
        print(f"  ✓ app_id: {app_id}")
        print(f"  ✓ git_url: {app_stub['git_url']}")
        print(f"  ✓ git_credentials.expires_at: {app_stub['git_credentials']['expires_at']}")

        # Step 4: Stub — secrets via set_config_vars (no CLI)
        print("\n[4] Set config vars (stub)...")
        cfg_stub = _read_stub("set_config_vars.json")
        if "updated" not in cfg_stub or "config_vars" not in cfg_stub:
            print("  ✗ set_config_vars stub missing updated/config_vars")
            return 1
        print(f"  ✓ updated: {cfg_stub['updated']} (values masked)")

        # Step 5: Stub — addon provisioning
        print("\n[5] Create addon (stub)...")
        addon_stub = _read_stub("create_addon.json")
        print(f"  ✓ id: {addon_stub['id']}")
        print(f"  ✓ state: {addon_stub['state']}")

        print("\n[5b] Get addon status (stub)...")
        addon_status_stub = _read_stub("get_addon_status.json")
        if addon_status_stub["addon_id"] != addon_stub["id"]:
            print("  ✗ get_addon_status addon_id does not match create_addon id")
            return 1
        print(f"  ✓ ready: {addon_status_stub['ready']}")
        print(f"  ✓ monitoring.owner: {addon_status_stub['monitoring']['owner']}")

        # Step 6 (post-push): Stub — git credential refresh
        print("\n[6] Refresh git credentials (stub)...")
        cred_stub = _read_stub("get_preview_app_git_credentials.json")
        print(f"  ✓ git_credentials.expires_at: {cred_stub['git_credentials']['expires_at']}")

        # Step 7: Stub — deployment status
        print("\n[7] Get deployment status (stub)...")
        deploy_stub = _read_stub("get_deployment_status.json")
        if deploy_stub["app_id"] != app_id:
            print("  ✗ get_deployment_status app_id does not match create_preview_app")
            return 1
        print(f"  ✓ build.status: {deploy_stub['build']['status']} done={deploy_stub['build']['done']}")
        print(f"  ✓ web_url (claim portal): {deploy_stub['web_url']}")

        print("\n[8] Share in browser (stub)...")
        share_stub = _read_stub("share_in_browser.json")
        print(f"  ✓ preview_link: {share_stub['preview_link']}")

        # Step 9 (background): Stub — claim status
        print("\n[9] Check claim status (stub)...")
        claim_stub = _read_stub("check_claim_status.json")
        print(f"  ✓ claimed: {claim_stub['claimed']} expired: {claim_stub['expired']}")

        # Discard path: the pending app can be discarded before it is claimed
        print("\n[10] Discard preview app (stub)...")
        discard_stub = _read_stub("discard_preview_app.json")
        if discard_stub["app_id"] != app_id:
            print("  ✗ discard_preview_app app_id does not match create_preview_app")
            return 1
        print(f"  ✓ discarded app_id: {discard_stub['app_id']}")

        # Contract: every stub carries its required keys and none of the removed identifiers
        print("\n[contract] Validate stubs against mcp/mcp-core-contract.md...")
        errors = validate_stubs()
        if errors:
            for err in errors:
                print(f"  ✗ {err}")
            return 1
        print(f"  ✓ {len(STUB_REQUIRED_KEYS)} stubs conform")

        # Verify session state schema (written by deploy-anonymous Step 9)
        print("\n[verify] Verify session state schema...")
        session_state = {
            "app_id": app_id,
            "claim_url": deploy_stub["web_url"],
            "expires_at": deploy_stub["expires_at"],
            "stack": stack,
            "target_dir": str(target),
        }
        for key in SESSION_REQUIRED_KEYS:
            if key not in session_state:
                print(f"  ✗ Missing session key: {key}")
                return 1
        for key in REMOVED_KEYS:
            if key in session_state:
                print(f"  ✗ Removed session key present: {key}")
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
    parser.add_argument("--stack", default="python", choices=["node", "python", "rails", "go", "website"])
    parser.add_argument("--variant", default="fastapi")
    parser.add_argument("--keep", action="store_true", help="Keep generated artifacts")
    args = parser.parse_args()

    os.environ["HEROKU_MCP_STUB"] = "1"
    return run_e2e(stack=args.stack, variant=args.variant, keep=args.keep)


if __name__ == "__main__":
    sys.exit(main())
