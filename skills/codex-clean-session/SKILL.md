---
name: codex-clean-session
description: "Clean, repair, or recover current or multiple Codex session transcripts after thinking_signature_invalid, invalid_encrypted_content, encrypted_content, litellm_enc, or resume failures."
---
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

## When the Current Session Cannot Run Tools

If the user is already seeing `thinking_signature_invalid` before the agent can run commands, tell them to run this from a separate terminal, outside the broken Codex session:

```bash
codex-clean-session --last --dry-run
codex-clean-session --last --yes
```

This avoids the loop where the skill needs the agent, but the agent cannot start because the transcript is invalid. If Codex prints a resume command with a session id, prefer `codex-clean-session <session-id>` because it is exact.

If the Codex hook is installed and trusted, the user can also submit this directly in Codex:

```text
clean-session
```

The hook runs before model submission and does not require the agent to start. Do not prefix it with `/`; unknown slash commands are rejected by Codex before hooks can see them.

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
