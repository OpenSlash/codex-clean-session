"""
Clean Codex session transcripts that contain invalid encrypted reasoning data.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


DEFAULT_PATTERNS = (
    "encrypted_content",
    "litellm_enc",
    "thinking_signature",
    "invalid_encrypted_content",
    "invalid_request_error",
)


def current_session_id() -> str:
    for name in ("CODEX_SESSION_ID", "CODEX_THREAD_ID"):
        value = os.environ.get(name)
        if value:
            return value
    raise SystemExit("--current requires CODEX_SESSION_ID or CODEX_THREAD_ID in the environment")


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def find_session(target: str, home: Path) -> Path:
    candidate = Path(target).expanduser()
    if candidate.exists():
        return candidate

    sessions_dir = home / "sessions"
    matches: list[Path] = []
    if sessions_dir.exists():
        for path in sessions_dir.rglob("*.jsonl"):
            name = path.name
            if ".bak-" in name or ".scrub-bak-" in name:
                continue
            if target in str(path):
                matches.append(path)

    if not matches:
        raise SystemExit(f"No active session transcript found for: {target}")
    if len(matches) > 1:
        lines = "\n".join(f"  {path}" for path in matches[:20])
        suffix = "\n  ..." if len(matches) > 20 else ""
        raise SystemExit(f"Multiple transcripts matched {target}:\n{lines}{suffix}")
    return matches[0]


def record_text(record: object) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def should_remove(record: dict, patterns: tuple[str, ...]) -> tuple[bool, str]:
    payload = record.get("payload")
    if (
        record.get("type") == "response_item"
        and isinstance(payload, dict)
        and payload.get("type") == "reasoning"
    ):
        return True, "reasoning"

    text = record_text(record)
    for pattern in patterns:
        if pattern in text:
            return True, f"pattern:{pattern}"
    return False, ""


def backup_path(source: Path, home: Path) -> Path:
    try:
        rel = source.relative_to(home / "sessions")
        dated = rel.parent
    except ValueError:
        dated = Path("manual")

    backup_dir = home / "session-cleanup-backups" / dated
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return backup_dir / f"{source.name}.bak-{stamp}"


def clean_file(path: Path, home: Path, patterns: tuple[str, ...], dry_run: bool) -> dict:
    counts: dict[str, int | str | bool] = {
        "total": 0,
        "kept": 0,
        "removed": 0,
        "invalid_json": 0,
        "reasoning": 0,
        "pattern": 0,
    }

    backup = backup_path(path, home)
    tmp_name = None

    try:
        with path.open("r", encoding="utf-8") as src:
            if dry_run:
                dst = None
            else:
                tmp = tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=str(path.parent),
                    prefix=f".{path.name}.",
                    suffix=".tmp",
                    delete=False,
                )
                tmp_name = tmp.name
                dst = tmp

            try:
                for raw in src:
                    counts["total"] += 1
                    try:
                        record = json.loads(raw)
                    except json.JSONDecodeError:
                        counts["invalid_json"] += 1
                        counts["kept"] += 1
                        if dst:
                            dst.write(raw)
                        continue

                    remove, reason = should_remove(record, patterns)
                    if remove:
                        counts["removed"] += 1
                        if reason == "reasoning":
                            counts["reasoning"] += 1
                        else:
                            counts["pattern"] += 1
                        continue

                    counts["kept"] += 1
                    if dst:
                        dst.write(record_text(record) + "\n")
            finally:
                if dst:
                    dst.close()

        if not dry_run:
            shutil.copy2(path, backup)
            os.replace(tmp_name, path)
            tmp_name = None

    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

    counts["remaining_reasoning"] = count_remaining(path, patterns, mode="reasoning") if not dry_run else -1
    counts["remaining_patterns"] = count_remaining(path, patterns, mode="patterns") if not dry_run else -1
    counts["valid_jsonl"] = validate_jsonl(path) if not dry_run else True
    counts["backup"] = str(backup) if not dry_run else ""
    return counts


def count_remaining(path: Path, patterns: tuple[str, ...], mode: str) -> int:
    total = 0
    with path.open("r", encoding="utf-8") as src:
        for raw in src:
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if mode == "reasoning":
                payload = record.get("payload")
                if (
                    record.get("type") == "response_item"
                    and isinstance(payload, dict)
                    and payload.get("type") == "reasoning"
                ):
                    total += 1
            else:
                text = record_text(record)
                if any(pattern in text for pattern in patterns):
                    total += 1
    return total


def validate_jsonl(path: Path) -> bool:
    with path.open("r", encoding="utf-8") as src:
        for raw in src:
            try:
                json.loads(raw)
            except json.JSONDecodeError:
                return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean invalid encrypted reasoning data from a Codex session transcript.",
    )
    parser.add_argument("target", nargs="?", help="Session id substring or .jsonl transcript path")
    parser.add_argument(
        "--current",
        action="store_true",
        help="Clean the current Codex session using CODEX_SESSION_ID or CODEX_THREAD_ID",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report what would be removed without editing")
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        help="Additional string pattern to remove from records. Can be repeated.",
    )
    args = parser.parse_args()

    if args.current and args.target:
        parser.error("target cannot be used with --current")
    if not args.current and not args.target:
        parser.error("target is required unless --current is used")

    home = codex_home()
    target = current_session_id() if args.current else args.target
    path = find_session(target, home)
    patterns = DEFAULT_PATTERNS + tuple(args.pattern)

    result = clean_file(path, home, patterns, args.dry_run)

    print(f"file={path}")
    if args.dry_run:
        print("mode=dry-run")
    else:
        print(f"backup={result['backup']}")
    print(f"total={result['total']}")
    print(f"kept={result['kept']}")
    print(f"removed={result['removed']}")
    print(f"removed_reasoning={result['reasoning']}")
    print(f"removed_pattern_records={result['pattern']}")
    print(f"invalid_json_lines={result['invalid_json']}")
    if not args.dry_run:
        print(f"remaining_reasoning={result['remaining_reasoning']}")
        print(f"remaining_pattern_records={result['remaining_patterns']}")
        print(f"valid_jsonl={'ok' if result['valid_jsonl'] else 'bad'}")
    return 0
