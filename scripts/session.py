#!/usr/bin/env python3
"""Plugin session state (.heroku-plugin-session.json) — the single reader/writer.

Skills and the PreCompact hook go through this module instead of hand-writing JSON, so the
file always has the same shape and a malformed or hostile file is only ever parsed as data.

  python3 scripts/session.py show [--dir DIR]
  python3 scripts/session.py set KEY=VALUE [KEY=VALUE ...] [--dir DIR]
  python3 scripts/session.py clear [--if-app-id ID] [--dir DIR]
  python3 scripts/session.py checkpoint [--dir DIR]      # PreCompact hook

Every subcommand prints one JSON object on stdout. Exit codes: 0 ok, 2 bad input.

Stdlib only and standalone (no sibling imports): the hook runs it under `python3 -I`.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

SESSION_FILENAME = ".heroku-plugin-session.json"

# key -> type tag. Anything not listed (including the retired `conversation_id`,
# `app_uuid` and `session_id`) is dropped on load.
FIELDS: dict[str, str] = {
    "app_id": "str",
    "app_name": "str",
    "claim_url": "str",
    "expires_at": "number",  # epoch milliseconds, as returned by get_deployment_status
    "stack": "str",
    "target_dir": "str",
    "deployed_at": "str",
    "timer_start": "str",
    "access_codes": "list",
    "token_budget_tracking": "bool",
    "checkpointed_at": "str",
}

# Environment variables the PreCompact hook reads. An env var that is set — even to an
# empty string — wins over the file.
CHECKPOINT_ENV: dict[str, str] = {
    "app_id": "HEROKU_APP_ID",
    "app_name": "HEROKU_APP_NAME",
    "claim_url": "HEROKU_CLAIM_URL",
    "timer_start": "HEROKU_TIMER_START",
    "stack": "HEROKU_STACK",
    "target_dir": "HEROKU_TARGET_DIR",
}

# Always present in a checkpoint, empty when unknown, so a resumed session has a stable shape.
CHECKPOINT_DEFAULTS: dict[str, object] = {
    "app_id": "",
    "app_name": "",
    "claim_url": "",
    "timer_start": "",
    "stack": "",
    "target_dir": "",
    "access_codes": [],
}


class SessionError(ValueError):
    """Bad key or value passed to `set`."""


def session_path(directory: str | os.PathLike[str] | None = None) -> Path:
    return Path(directory if directory is not None else os.getcwd()) / SESSION_FILENAME


def _valid(tag: str, value: object) -> bool:
    if tag == "str":
        return isinstance(value, str)
    if tag == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if tag == "bool":
        return isinstance(value, bool)
    if tag == "list":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    return False


def sanitize(raw: object) -> dict:
    """Keep only known keys whose values have the right type."""
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k in FIELDS and _valid(FIELDS[k], v)}


def load(path: Path) -> dict:
    """Read the session file as data. Missing, unreadable or malformed files yield {}."""
    try:
        with open(path, encoding="utf-8") as f:
            return sanitize(json.load(f))
    except (OSError, ValueError):
        return {}


def save(path: Path, state: dict) -> None:
    """Write atomically so a crash mid-write can't leave a truncated session file."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".heroku-plugin-session.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def coerce(key: str, text: str) -> object:
    """Turn a CLI `KEY=VALUE` string into the typed value for `key`."""
    tag = FIELDS.get(key)
    if tag is None:
        raise SessionError(f"unknown key {key!r}; allowed: {', '.join(sorted(FIELDS))}")
    if tag == "str":
        return text
    if tag == "number":
        try:
            return int(text)
        except ValueError:
            pass
        try:
            return float(text)
        except ValueError:
            raise SessionError(f"{key} must be a number, got {text!r}") from None
    try:
        value = json.loads(text)
    except ValueError:
        raise SessionError(f"{key} must be JSON ({tag}), got {text!r}") from None
    if not _valid(tag, value):
        raise SessionError(f"{key} must be a {tag}, got {text!r}")
    return value


def update(path: Path, **fields: object) -> dict:
    """Merge validated fields into the session file and return the new state."""
    for key, value in fields.items():
        tag = FIELDS.get(key)
        if tag is None or not _valid(tag, value):
            raise SessionError(f"invalid session field {key!r}")
    state = load(path)
    state.update(fields)
    save(path, state)
    return state


def clear(path: Path) -> bool:
    """Remove the session file. Returns whether a file was removed."""
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def clear_session(path: Path, if_app_id: str | None = None) -> dict:
    """CLI `clear`: remove the file, optionally only when it belongs to `if_app_id`.

    The guard keeps a skill that just finished with one app from wiping the state of another.
    """
    out: dict = {"path": str(path), "cleared": False}
    if if_app_id is not None and load(path).get("app_id") != if_app_id:
        out["reason"] = "session app_id does not match"
    elif clear(path):
        out["cleared"] = True
    else:
        out["reason"] = "no session file"
    return out


def checkpoint(path: Path, env: dict[str, str] | None = None, now: datetime.datetime | None = None) -> dict:
    """Merge env overrides into the file and stamp it. Used by the PreCompact hook."""
    env = os.environ if env is None else env
    state = load(path)
    for key, name in CHECKPOINT_ENV.items():
        if name in env:
            state[key] = env[name]
    state["token_budget_tracking"] = env.get("HEROKU_TOKEN_BUDGET_TRACKING", "").strip() == "1"
    stamp = now or datetime.datetime.now(datetime.timezone.utc)
    state["checkpointed_at"] = stamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    for key, default in CHECKPOINT_DEFAULTS.items():
        state.setdefault(key, default)
    save(path, state)
    return state


def _parse_set(pairs: list[str]) -> dict:
    fields: dict[str, object] = {}
    for pair in pairs:
        key, sep, text = pair.partition("=")
        if not sep:
            raise SessionError(f"expected KEY=VALUE, got {pair!r}")
        fields[key] = coerce(key, text)
    return fields


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plugin session state helper.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("show", "checkpoint"):
        sub.add_parser(name).add_argument("--dir", default=None)
    clear_p = sub.add_parser("clear")
    clear_p.add_argument("--dir", default=None)
    clear_p.add_argument(
        "--if-app-id", default=None, metavar="ID",
        help="only clear when the session file belongs to this app_id",
    )
    set_p = sub.add_parser("set")
    set_p.add_argument("pairs", nargs="+", metavar="KEY=VALUE")
    set_p.add_argument("--dir", default=None)
    args = parser.parse_args(argv)

    path = session_path(args.dir)
    try:
        if args.cmd == "show":
            out: dict = {"path": str(path), "exists": path.exists(), "session": load(path)}
        elif args.cmd == "set":
            out = {"path": str(path), "session": update(path, **_parse_set(args.pairs))}
        elif args.cmd == "clear":
            out = clear_session(path, args.if_app_id)
        else:
            checkpoint(path)
            out = {"systemMessage": f"Heroku session state checkpointed to {path.name}"}
    except SessionError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
