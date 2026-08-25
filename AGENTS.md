# Repository Guidelines

## Project Structure & Module Organization

This repository is a small Python CLI utility for cleaning Codex session transcript JSONL files.

- `src/codex_clean_session.py` contains all application logic, including session lookup, filtering, backup creation, validation, and the CLI entry point.
- `bin/codex-clean-session` is the executable wrapper that adds `src/` to `sys.path` and calls `main()`.
- `bin/codex-clean-session-hook` is the Codex `UserPromptSubmit` hook handler for `clean-session`.
- `bin/install-codex-hook` installs the global hook in `${CODEX_HOME:-~/.codex}/hooks.json`.
- `bin/install-codex-skill` installs the CLI symlink and Codex skill in one step.
- `skills/codex-clean-session/SKILL.md` defines the optional Codex skill workflow.
- `README.md` documents user-facing usage and installation.
- `LICENSE` contains the project license.

No tests, assets, packaging metadata, or dependency manifests are currently committed.

## Build, Test, and Development Commands

- `./bin/codex-clean-session --dry-run <session-id-or-path>` previews cleanup without editing a transcript.
- `./bin/codex-clean-session --current --dry-run` previews cleanup for the current Codex session using `CODEX_SESSION_ID` or `CODEX_THREAD_ID`.
- `./bin/codex-clean-session --last --dry-run` previews cleanup for the newest session by rollout timestamp without requiring Codex to run.
- `./bin/codex-clean-session --last-modified --dry-run` previews cleanup for the most recently modified transcript.
- `./bin/codex-clean-session --project --dry-run` previews cleanup for the newest session whose transcript cwd matches the current directory.
- `./bin/codex-clean-session --all --from 2026-08-01 --to 2026-08-25 --dry-run` scans all sessions in a date range.
- `./bin/codex-clean-session --last --yes` confirms cleanup for a heuristic target after previewing.
- `./bin/codex-clean-session <session-id-or-path>` cleans a matching transcript and writes a backup under `~/.codex/session-cleanup-backups/`.
- `python3 -m py_compile src/codex_clean_session.py bin/codex-clean-session` performs a quick syntax check.
- `ln -sf "$PWD/bin/codex-clean-session" ~/.local/bin/codex-clean-session` installs the CLI locally, assuming `~/.local/bin` is on `PATH`.
- `./bin/install-codex-skill` installs the CLI symlink and copies the skill to `${CODEX_HOME:-~/.codex}/skills/codex-clean-session`.
- `./bin/install-codex-hook` installs the `clean-session` prompt hook.

There is no build step; the tool uses only the Python standard library.

## Coding Style & Naming Conventions

Use Python 3 style consistent with the existing code: 4-space indentation, type hints for function signatures and structured return values where useful, and small functions with clear responsibilities. Prefer `pathlib.Path` for filesystem work and keep JSONL parsing explicit with `json.loads`.

Use `snake_case` for functions, variables, and module names. Constants should use `UPPER_CASE`, as in `DEFAULT_PATTERNS`. Keep comments sparse and reserve them for behavior that is not obvious from the code.

## Testing Guidelines

There is no formal test suite yet. For changes, at minimum run:

```bash
python3 -m py_compile src/codex_clean_session.py bin/codex-clean-session
./bin/codex-clean-session --dry-run <sample-jsonl-path>
```

When adding tests, place them under `tests/` and prefer `pytest`. Name files `test_*.py` and cover dry-run behavior, `--current`, `--last`, `--last-modified`, `--project` cwd matching, `--all` date filtering, hook prompt parsing, backup creation, invalid JSONL handling, session matching, and pattern-based removals.

## Commit & Pull Request Guidelines

This checkout does not include Git history, so no project-specific commit convention can be inferred. Use concise imperative commit messages such as `Add transcript validation test` or `Preserve invalid JSON lines`.

Pull requests should include a short description, the reason for the change, manual or automated verification commands, and any behavior changes affecting transcript cleanup or backups. Link related issues when available. For CLI output changes, include before-and-after examples.

## Security & Configuration Tips

The tool edits local session transcripts and may process sensitive content. Always use `--dry-run` first when validating removal rules. Do not commit real transcript files, backup files, or user-specific paths. Respect `CODEX_HOME` when testing alternate session directories.
