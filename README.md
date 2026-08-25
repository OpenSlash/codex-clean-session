# codex-clean-session

Clean local Codex session transcripts that contain invalid encrypted reasoning data, such as `thinking_signature_invalid`, `invalid_encrypted_content`, `encrypted_content`, or `litellm_enc`.

If Codex cannot resume a session, repeatedly fails after a previous tool call, or shows an error related to encrypted reasoning content, this utility removes the broken local transcript records while preserving the rest of the conversation.

## Problem: Codex Session Resume Errors

Some Codex sessions can become difficult or impossible to continue when the local session transcript contains invalid encrypted reasoning payloads. Common symptoms include errors like:

- `thinking_signature_invalid`
- `invalid_encrypted_content`
- `invalid_request_error`
- failures involving `encrypted_content`, `thinking_signature`, or `litellm_enc`

These errors can appear when resuming an old Codex session, continuing a long conversation, or sending the next request after a failed model response. Restarting Codex may not help if the same bad records are still stored in the local `.jsonl` transcript.

## Why This Happens

Codex stores local session history under `~/.codex/sessions/...` as JSONL transcript files. Some records may include encrypted reasoning metadata or response items that are not valid for later replay. When Codex reloads the transcript, those stale or invalid records can be sent back into the conversation chain and cause the next request to fail.

This project targets the local transcript problem. It does not decrypt or recover hidden reasoning content; it removes records that are known to trigger these resume failures.

## Solution

`codex-clean-session` finds a Codex session transcript by session id or file path, removes invalid encrypted reasoning records, validates the remaining JSONL, and writes a backup before editing.

The tool removes:

- `response_item` records where `payload.type == "reasoning"`
- Any record containing known encrypted-content error markers:
  - `encrypted_content`
  - `litellm_enc`
  - `thinking_signature`
  - `invalid_encrypted_content`
  - `invalid_request_error`

It writes a backup before editing:

```text
~/.codex/session-cleanup-backups/...
```

After cleaning, restart Codex or reopen the session so the repaired transcript is loaded.

## Project Structure

```text
bin/codex-clean-session                # executable wrapper
bin/codex-clean-session-hook           # Codex UserPromptSubmit hook handler
bin/install-codex-hook                 # global Codex hook installer
bin/install-codex-skill                # CLI and skill installer
skills/codex-clean-session/SKILL.md    # optional Codex skill
src/codex_clean_session.py             # source code
README.md
LICENSE
```

## Usage

Clean the current Codex session from inside Codex:

```bash
./bin/codex-clean-session --current --dry-run
./bin/codex-clean-session --current
```

After installing the hook, clean the current session from the Codex prompt without invoking the agent:

```text
clean-session --dry-run
clean-session
```

Clean the newest Codex session from an external terminal:

```bash
codex-clean-session --last --dry-run
codex-clean-session --last --yes
```

Scan all Codex sessions:

```bash
./bin/codex-clean-session --all --dry-run
./bin/codex-clean-session --all --yes
```

Limit a full scan by session date:

```bash
./bin/codex-clean-session --all --date 2026-08-25 --dry-run
./bin/codex-clean-session --all --from 2026-08-01 --to 2026-08-25 --dry-run
```

Preview a cleanup:

```bash
./bin/codex-clean-session --dry-run 019e1c22-7398-77c2-8303-306bf490edcb
```

Clean by session id:

```bash
./bin/codex-clean-session 019e1c22-7398-77c2-8303-306bf490edcb
```

Clean by file path:

```bash
./bin/codex-clean-session ~/.codex/sessions/2026/05/12/rollout-....jsonl
```

Add an extra removal marker:

```bash
./bin/codex-clean-session --pattern "lite...6FvO" 019e1c22-7398-77c2-8303-306bf490edcb
```

## Install Locally

```bash
ln -sf "$PWD/bin/codex-clean-session" ~/.local/bin/codex-clean-session
```

Then run:

```bash
codex-clean-session --dry-run <session-id>
```

## Install the Codex Skill

Install the CLI command and the Codex skill with one command:

```bash
./bin/install-codex-skill
```

The installer copies the skill to:

```text
${CODEX_HOME:-~/.codex}/skills/codex-clean-session/SKILL.md
```

It also links the CLI to:

```text
~/.local/bin/codex-clean-session
```

After installation, restart Codex so it can discover the new skill. In a Codex session, ask it to clean the current session. The skill will run:

```bash
codex-clean-session --current --dry-run
```

## Install the Codex Hook

Install the `UserPromptSubmit` hook:

```bash
./bin/install-codex-hook
```

The installer writes or updates:

```text
${CODEX_HOME:-~/.codex}/hooks.json
```

Restart Codex, run `/hooks`, and trust the installed hook. Then use:

```text
clean-session --dry-run
clean-session
```

The hook runs before the prompt is sent to the model. It can clean the current transcript even when a broken session would prevent the agent or skill from running. Do not prefix the command with `/`; Codex handles unknown slash commands before hooks can see them.

## Notes

After cleaning a session, restart Codex or reopen/resume the session. A running Codex process may already have the old transcript loaded in memory.

If the error still appears after cleaning and restarting, the request may be chained through a server-side `previous_response_id`. In that case, start a new session and carry over only visible context.

`--current` works only inside Codex sessions that expose `CODEX_SESSION_ID` or `CODEX_THREAD_ID`.

If Codex cannot process any request because the broken transcript fails before the agent can run tools, use `--last` from a separate terminal window. This avoids the skill/agent loop entirely.

The hook command `clean-session` is the best in-Codex escape hatch for that same failure mode because it runs before model submission. If the hook is not installed or trusted yet, use `codex-clean-session --last` externally.

`--last` scans global Codex transcripts under `${CODEX_HOME:-~/.codex}/sessions`; it is not limited to the current project directory. It chooses the newest session by the rollout timestamp in the transcript filename. Use `--last-modified` only if you explicitly want the file with the newest filesystem modification time.

For safety, `--last`, `--last-modified`, and `--all` do not clean unless you add `--yes`. Running `codex-clean-session --last` without `--dry-run` or `--yes` only prints the selected file.

If Codex prints `To continue this session, run codex resume <session-id>`, the most precise cleanup command is:

```bash
codex-clean-session <session-id>
```

`--all` scans active transcript files under `${CODEX_HOME:-~/.codex}/sessions`. Date filters use the `YYYY/MM/DD` path in the Codex session directory, falling back to file modification time for manually supplied layouts.
