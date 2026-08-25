# codex-clean-session

Use this skill when the user asks to clean, repair, or recover the current Codex session or multiple Codex sessions after errors such as `thinking_signature_invalid`, `invalid_encrypted_content`, `encrypted_content`, `litellm_enc`, or Codex session resume failures.

## Workflow

1. Run a dry run first:

   ```bash
   codex-clean-session --current --dry-run
   ```

2. Show the user the important counts: `removed`, `removed_reasoning`, `removed_pattern_records`, and `invalid_json_lines`.

3. If the dry run shows records to remove and the user wants to proceed, run:

   ```bash
   codex-clean-session --current
   ```

4. Tell the user that Codex may need to be restarted or the session reopened because the running process may already have loaded the old transcript.

## Cleaning Multiple Sessions

If the user asks to scan every session, run a dry run first:

```bash
codex-clean-session --all --dry-run
```

If the user asks for a date range or specific days, use `--from YYYY-MM-DD`, `--to YYYY-MM-DD`, or repeated `--date YYYY-MM-DD` options:

```bash
codex-clean-session --all --from 2026-08-01 --to 2026-08-25 --dry-run
codex-clean-session --all --date 2026-08-20 --date 2026-08-25 --dry-run
```

Only run the non-dry-run command after the user confirms the scope.

## Notes

- The command uses `CODEX_SESSION_ID` or `CODEX_THREAD_ID` from the current Codex environment.
- The tool writes a backup before modifying a transcript.
- Do not inspect or print transcript contents unless the user explicitly asks.
