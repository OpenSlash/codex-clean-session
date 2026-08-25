# codex-clean-session

Use this skill when the user asks to clean, repair, or recover the current Codex session after errors such as `thinking_signature_invalid`, `invalid_encrypted_content`, `encrypted_content`, `litellm_enc`, or Codex session resume failures.

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

## Notes

- The command uses `CODEX_SESSION_ID` or `CODEX_THREAD_ID` from the current Codex environment.
- The tool writes a backup before modifying a transcript.
- Do not inspect or print transcript contents unless the user explicitly asks.
