"""
Clean Codex session transcripts that contain invalid encrypted reasoning data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path


DEFAULT_PATTERNS = (
    "encrypted_content",
    "litellm_enc",
    "thinking_signature",
    "invalid_encrypted_content",
    "invalid_request_error",
)

ROLLOUT_TIME_RE = re.compile(
    r"rollout-(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})-(\d{2})"
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


def active_session_paths(home: Path) -> list[Path]:
    sessions_dir = home / "sessions"
    if not sessions_dir.exists():
        return []

    paths: list[Path] = []
    for path in sessions_dir.rglob("*.jsonl"):
        name = path.name
        if ".bak-" in name or ".scrub-bak-" in name:
            continue
        paths.append(path)
    return sorted(paths)


def session_sort_time(path: Path, home: Path) -> datetime:
    match = ROLLOUT_TIME_RE.search(path.name)
    if match:
        year, month, day, hour, minute, second = (int(part) for part in match.groups())
        return datetime(year, month, day, hour, minute, second)

    try:
        rel = path.relative_to(home / "sessions")
        year, month, day = rel.parts[:3]
        return datetime(int(year), int(month), int(day))
    except (ValueError, IndexError):
        return datetime.fromtimestamp(path.stat().st_mtime)


def last_session_path(home: Path, *, by_modified_time: bool = False) -> Path:
    paths = active_session_paths(home)
    if not paths:
        raise SystemExit(f"No active Codex session transcripts found under: {home / 'sessions'}")
    if by_modified_time:
        return max(paths, key=lambda path: path.stat().st_mtime)
    return max(paths, key=lambda path: session_sort_time(path, home))


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}; expected YYYY-MM-DD")


def session_date(path: Path, home: Path) -> date:
    try:
        rel = path.relative_to(home / "sessions")
        year, month, day = rel.parts[:3]
        return date(int(year), int(month), int(day))
    except (ValueError, IndexError):
        return datetime.fromtimestamp(path.stat().st_mtime).date()


def filter_paths_by_date(
    paths: list[Path],
    home: Path,
    selected_dates: set[date],
    from_date: date | None,
    to_date: date | None,
) -> list[Path]:
    selected: list[Path] = []
    for path in paths:
        day = session_date(path, home)
        if selected_dates and day not in selected_dates:
            continue
        if from_date and day < from_date:
            continue
        if to_date and day > to_date:
            continue
        selected.append(path)
    return selected


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

        if not dry_run and counts["removed"]:
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
    counts["backup"] = str(backup) if not dry_run and counts["removed"] else ""
    return counts


def combine_counts(results: list[dict]) -> dict[str, int]:
    keys = (
        "total",
        "kept",
        "removed",
        "invalid_json",
        "reasoning",
        "pattern",
        "remaining_reasoning",
        "remaining_patterns",
    )
    summary = {key: 0 for key in keys}
    for result in results:
        for key in keys:
            value = result.get(key, 0)
            if isinstance(value, int) and value >= 0:
                summary[key] += value
    return summary


def print_result(path: Path, result: dict, dry_run: bool) -> None:
    print(f"file={path}")
    if dry_run:
        print("mode=dry-run")
    elif result["backup"]:
        print(f"backup={result['backup']}")
    else:
        print("backup=")
    print(f"total={result['total']}")
    print(f"kept={result['kept']}")
    print(f"removed={result['removed']}")
    print(f"removed_reasoning={result['reasoning']}")
    print(f"removed_pattern_records={result['pattern']}")
    print(f"invalid_json_lines={result['invalid_json']}")
    if not dry_run:
        print(f"remaining_reasoning={result['remaining_reasoning']}")
        print(f"remaining_pattern_records={result['remaining_patterns']}")
        print(f"valid_jsonl={'ok' if result['valid_jsonl'] else 'bad'}")


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
    parser.add_argument(
        "--last",
        action="store_true",
        help="Clean the newest Codex session transcript by rollout timestamp",
    )
    parser.add_argument(
        "--last-modified",
        action="store_true",
        help="Clean the most recently modified Codex session transcript",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan and clean all active Codex session transcripts",
    )
    parser.add_argument(
        "--date",
        action="append",
        type=parse_date,
        default=[],
        help="Limit --all to one date in YYYY-MM-DD format. Can be repeated.",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        type=parse_date,
        help="Limit --all to sessions on or after YYYY-MM-DD",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=parse_date,
        help="Limit --all to sessions on or before YYYY-MM-DD",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report what would be removed without editing")
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        help="Additional string pattern to remove from records. Can be repeated.",
    )
    args = parser.parse_args()

    modes = [bool(args.target), args.current, args.last, args.last_modified, args.all]
    if sum(modes) != 1:
        parser.error("choose exactly one of target, --current, --last, --last-modified, or --all")
    if (args.date or args.from_date or args.to_date) and not args.all:
        parser.error("--date, --from, and --to can only be used with --all")
    if args.from_date and args.to_date and args.from_date > args.to_date:
        parser.error("--from cannot be later than --to")

    home = codex_home()
    patterns = DEFAULT_PATTERNS + tuple(args.pattern)

    if args.all:
        paths = filter_paths_by_date(
            active_session_paths(home),
            home,
            set(args.date),
            args.from_date,
            args.to_date,
        )
        results = []
        for path in paths:
            result = clean_file(path, home, patterns, args.dry_run)
            results.append(result)
            if result["removed"] or result["invalid_json"]:
                print_result(path, result, args.dry_run)
                print()

        summary = combine_counts(results)
        print(f"files_scanned={len(paths)}")
        print(f"total={summary['total']}")
        print(f"kept={summary['kept']}")
        print(f"removed={summary['removed']}")
        print(f"removed_reasoning={summary['reasoning']}")
        print(f"removed_pattern_records={summary['pattern']}")
        print(f"invalid_json_lines={summary['invalid_json']}")
        if not args.dry_run:
            print(f"remaining_reasoning={summary['remaining_reasoning']}")
            print(f"remaining_pattern_records={summary['remaining_patterns']}")
        return 0

    if args.last or args.last_modified:
        path = last_session_path(home, by_modified_time=args.last_modified)
    else:
        target = current_session_id() if args.current else args.target
        path = find_session(target, home)
    result = clean_file(path, home, patterns, args.dry_run)
    print_result(path, result, args.dry_run)
    return 0
