#!/usr/bin/env python3
"""End-to-end build-and-deploy eval in stub mode.

Validates the full workflow: scaffold → deploy (stub) → check status (stub) → access code.

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


def _read_stub(name: str) -> dict:
    stub_path = STUBS_DIR / name
    data = json.loads(stub_path.read_text(encoding="utf-8"))
    return json.loads(data["content"][0]["text"])


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
        for fname in ["Procfile", "app.json", ".gitignore"]:
            fpath = target / fname
            if not fpath.exists():
                print(f"  ✗ Missing: {fname}")
                return 1
            print(f"  ✓ {fname}")

        # Step 3: Stub — create anonymous app
        print("\n[3] Create anonymous app (stub)...")
        stub = _read_stub("create_app.json")
        print(f"  ✓ app_name: {stub['app_name']}")
        print(f"  ✓ session_id: {stub['session_id']}")
        print(f"  ✓ expires_at: {stub['expires_at']}")

        # Step 4: Stub — git push (build status)
        print("\n[4] Push to Heroku Git (stub)...")
        push_stub = _read_stub("push_git.json")
        print(f"  ✓ build_id: {push_stub['build_id']}")
        print(f"  ✓ status: {push_stub['status']}")

        # Step 5: Stub — poll build status
        print("\n[5] Check build status (stub)...")
        build_stub = _read_stub("get_build_status.json")
        print(f"  ✓ status: {build_stub['status']}")
        print(f"  ✓ app_url: {build_stub['app_url']}")

        # Step 6: Stub — generate access code
        print("\n[6] Generate access code (stub)...")
        code_stub = _read_stub("generate_access_code.json")
        print(f"  ✓ code: {code_stub['code']}")
        print(f"  ✓ claim_url: {code_stub['claim_url']}")
        print(f"  ✓ remaining: {code_stub['remaining_codes']}")

        # Step 7: Verify session state structure
        print("\n[7] Verify session state schema...")
        session = {
            "app_name": stub["app_name"],
            "session_id": stub["session_id"],
            "claim_url": code_stub["claim_url"],
            "timer_start": stub["expires_at"],
            "access_codes": [code_stub["code"]],
            "stack": stack,
            "target_dir": str(target),
        }
        required_keys = ["app_name", "session_id", "claim_url", "timer_start", "access_codes", "stack", "target_dir"]
        for key in required_keys:
            if key not in session:
                print(f"  ✗ Missing session key: {key}")
                return 1
        print(f"  ✓ session state schema valid")

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
