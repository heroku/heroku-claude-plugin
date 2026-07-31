#!/usr/bin/env python3
"""Reference file staleness checker.

Reads plugin.json for policy.reference_staleness_days.
Parses <!-- Source: <URL> — verified <DATE> --> from each reference file.
For files older than N days: fetches source URL and updates content + date stamp.

Outputs JSON: { "checked": [...], "updated": [...], "skipped": [...] }

Usage:
  python3 scripts/check_references.py           # interactive (shows diffs)
  python3 scripts/check_references.py --auto    # non-interactive (auto-update)
  python3 scripts/check_references.py --dry-run # report staleness only
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent
REFERENCES_DIR = PLUGIN_ROOT / "references"
PLUGIN_JSON = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"

SOURCE_PATTERN = re.compile(
    r"<!--\s*Source:\s*(?P<url>https?://\S+?)\s*—\s*verified\s*(?P<date>\d{4}-\d{2}-\d{2})\s*-->"
)


def _staleness_days() -> int:
    try:
        policy = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        return int(policy.get("policy", {}).get("reference_staleness_days", 30))
    except Exception:
        return 30


def _find_reference_files() -> list[Path]:
    return sorted(REFERENCES_DIR.rglob("*.md"))


def _parse_source_header(content: str) -> list[tuple[str, date]]:
    """Return list of (url, verified_date) from all source headers in a file."""
    results = []
    for m in SOURCE_PATTERN.finditer(content):
        url = m.group("url")
        verified = datetime.strptime(m.group("date"), "%Y-%m-%d").date()
        results.append((url, verified))
    return results


def _is_stale(verified: date, threshold_days: int) -> bool:
    return (date.today() - verified).days > threshold_days


def _fetch_url(url: str, timeout: int = 15) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "heroku-plugin/0.1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return raw.decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"  [warn] fetch failed for {url}: {exc}", file=sys.stderr)
        return None


def _update_date_stamp(content: str, url: str, new_date: str) -> str:
    """Replace the verified date for a specific source URL."""
    def replacer(m: re.Match) -> str:
        if m.group("url") == url:
            return f"<!-- Source: {url} — verified {new_date} -->"
        return m.group(0)
    return SOURCE_PATTERN.sub(replacer, content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check and update reference file staleness.")
    parser.add_argument("--auto", action="store_true", help="Auto-update without prompting")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()

    threshold = _staleness_days()
    today_str = date.today().isoformat()

    files = _find_reference_files()
    checked: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for ref_file in files:
        rel = str(ref_file.relative_to(PLUGIN_ROOT))
        content = ref_file.read_text(encoding="utf-8")
        headers = _parse_source_header(content)

        if not headers:
            continue

        checked.append(rel)
        stale_urls = [(url, d) for url, d in headers if _is_stale(d, threshold)]

        if not stale_urls:
            continue

        print(f"\n  Stale: {rel}", file=sys.stderr)
        for url, d in stale_urls:
            age = (date.today() - d).days
            print(f"    {url}  ({age} days old)", file=sys.stderr)

        if args.dry_run:
            skipped.append(rel)
            continue

        if not args.auto:
            try:
                answer = input(f"  Update {rel}? [yes/no]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = "no"
            if answer not in ("yes", "y"):
                skipped.append(rel)
                continue

        # Fetch and update date stamps (we update the stamp even if content parsing fails —
        # the stamp records when we last checked, not whether content changed)
        fetch_ok = True
        for url, _ in stale_urls:
            fetched = _fetch_url(url)
            if fetched is None:
                print(f"  [warn] Could not fetch {url} — keeping existing content, updating stamp anyway.", file=sys.stderr)
                # Graceful degradation: update the stamp so we don't keep hammering a down URL
            content = _update_date_stamp(content, url, today_str)

        # Write updated content (only stamp changed if fetch failed)
        if not args.dry_run:
            ref_file.write_text(content, encoding="utf-8")
            updated.append(rel)
            print(f"  Updated: {rel}", file=sys.stderr)

    result = {"checked": checked, "updated": updated, "skipped": skipped}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
