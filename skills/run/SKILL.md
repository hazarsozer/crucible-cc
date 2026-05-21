---
name: run
description: Run a Crucible review pipeline on the current project. The Profiler reads the project, interviews the user, and casts a 4–8 persona review committee from a 23-persona library. Peers review at the code level, departments hunt for gaps, leadership grades alignment, and the Aggregator synthesizes a final score and verdict. Output is a live terminal stream plus a fully-detailed markdown report at .review/reports/<id>.md.
---

# /crucible:run — Corporate Review Pipeline

You are orchestrating a Crucible review pipeline on the current project. Execute the following stages in order. Stream progress to the terminal in compact form as each stage completes; write the full markdown report to `.review/reports/<review_id>.md` at the end.

The pipeline has five stages: Profiler (Stage 0) → Peer Code Review (Stage 1) → Cross-functional Gap Review (Stage 2) → Leadership (Stage 3) → Aggregator (Stage 4). Each stage is dispatched as one or more Claude Code subagents via the Task tool, with structured JSON handoff between stages.

## Cost preview (mandatory first step)

Before doing anything else — before running `pwd`, before reading files — print the following preview and wait for the user's confirmation:

```
🔥 Crucible — Corporate Review Pipeline

⚠️  Usage note: Crucible runs in your Claude Code main thread, so YOUR session
    model drives most of the cost. If you're on a Claude Pro or Max subscription
    you don't pay per run — your subscription covers usage; you just consume
    more or less of your quota. The dollar figures below are API-equivalent
    token costs (what pay-as-you-go would charge), shown as a reference for
    relative effort. The percentages are share of a Claude Max 5-hour quota
    window; Pro subscribers will see proportionally more of their smaller
    window consumed by the same workload.

    Measured ranges (5–7 file fixtures):

      • Haiku 4.5   — API ~$3-4 per run, ~6-7% of a Claude Max quota window
                      (cheapest; report template adherence is looser — section
                       names may improvise and detail may collapse; single run
                       consumes ~75% of Haiku's 200K context window, so start a
                       fresh session if you've been using Claude Code already)

      • Sonnet 4.6  — API ~$4.50-7 per run, ~10-15% of a Claude Max window
                      (recommended balance of cost + polished report)

      • Opus 4.7    — API ~$8-10 per run, ~15%+ of a Claude Max window
                      (deepest main-thread reasoning, but most reasoning happens
                       in dispatched Opus subagents anyway — Sonnet usually fine)

    Larger projects cost more in proportion to file count and cast size.

    Crucible cannot detect your session model from inside a Skill. If you
    want to manage quota usage, run `/model claude-haiku-4-5-20251001` or
    `/model claude-sonnet-4-6` in this session BEFORE proceeding.

Proceed? (y / n)
```

If the user answers anything other than `y` or `yes`, halt and print: `Run cancelled. No artifacts written.`

If the user answers `y` or `yes`, proceed to Setup. Do NOT print the cost preview again on subsequent steps of the same run.

The cost preview exists because of a load-bearing v0.1.0 architectural finding: the orchestrator (this skill, running in the user's main thread) is the dominant cost driver, not the dispatched subagent tiers. Earlier v0.1.0 design attempted to move orchestration into a dedicated coordinator subagent (Haiku, then Sonnet) to decouple cost from the user's session model. That approach failed in two ways: (1) Haiku-as-coordinator silently impersonated personas instead of dispatching them via the Task tool, producing complete-looking reports with fabricated `model_used` fields, (2) when the coordinator was escalated to Sonnet to fix the impersonation, the Profiler — which needs to interactively prompt the user for aims confirmation and roster approval — became a sub-subagent, and nested subagent dispatch loses the user-interaction channel. The Profiler ran but didn't ask. v0.1.0 ships main-thread orchestration with this cost warning instead. Note: Haiku **as the main thread** does dispatch subagents correctly (verified 2026-05-12) — the impersonation failure mode was specific to Haiku running as a sub-subagent inside the dispatched coordinator, where the dispatch instructions read as workflow descriptions rather than tool calls. Haiku-main is a viable mode, with the template-adherence caveats noted in the preview text above.

## Setup

1. **Determine the project root.** Run `pwd` via the Bash tool. The absolute path it returns is `project_root` — the working directory the user invoked Crucible from, and the root of the project under review.

   **`project_root` is NOT `git rev-parse --show-toplevel`.** When the user runs Crucible from a fixture (e.g., `tests/fixtures/go-api/`), a monorepo package, or any nested directory, `project_root` is THAT directory. Using git's toplevel would mis-identify the project: running from `plugin-create/tests/fixtures/go-api/` returns `plugin-create/` as git toplevel, and the Profiler would then read Crucible's README and identify Crucible as the project under review instead of the Go service. **Always use the `pwd` value, never git toplevel.**

   Every subsequent step uses `project_root` as the base path. All `.review/` paths resolve as absolute paths within `project_root`. The Profiler and all other subagents are told the exact `project_root` absolute path in their dispatch prompts — you (the orchestrator) are responsible for substituting the literal absolute path into the prompt before dispatching.

2. Generate `review_id` of the form `YYYY-MM-DD-HHMM-<slug>` using the current UTC time. The `<slug>` is derived from the user's review scope description: lowercase, hyphenated, ASCII only, ≤30 characters. If the user has not yet stated a scope, use the placeholder slug `pending`; the Profiler will refine it.

3. Record the run start time as an ISO 8601 string for the report header. Run `date -u -Iseconds` via the Bash tool and use the result as the `started_at` field that flows into the final report's "Generated:" line. The orchestrator does not measure wall-clock or API cost; Claude Code reports both natively at session end and via `/status`, and any number Crucible computed from inside the run would be a strictly worse measurement.

4. Create directory `${project_root}/.review/runs/<review_id>/` for transient artifacts.

## Stage 0 — Profiler

Print: `[Stage 0] Profiler reading project...`

**Before dispatching, substitute `<PROJECT_ROOT>` and `<USER_INVOCATION>` in the prompt below with literal values:**

- `<PROJECT_ROOT>` → the absolute path you captured in Setup step 1 (the result of `pwd`). Example: `/home/user/Dev/my-project/`. This MUST be a real path, not the placeholder string. The most common Profiler dispatch bug is forgetting this substitution and sending the literal `<PROJECT_ROOT>` text — verify the dispatch prompt contains a real absolute path before sending.
- `<USER_INVOCATION>` → the original `/crucible:run` invocation text including any free-text scope hint the user typed.

Then dispatch the Profiler agent via the Task tool:

```
Task(
  subagent_type="profiler",
  description="Profile project + interview + cast committee",
  prompt="""
You are running as the Profiler agent for Crucible. Read your full system prompt at agents/profiler.md if it has not already been loaded by the harness.

# Project root (MANDATORY — this is the project under review; do NOT use git toplevel for nested projects)
<PROJECT_ROOT>

# User invocation
<USER_INVOCATION>

# Your job
Follow your full Profiler workflow:
1. Read project signals **inside the project root only — never traverse upward to a parent repo** (file tree, README, CLAUDE.md, language manifests, recent commits scoped via `git log -- .`).
2. Detect project type, languages, frameworks, datastores, deployment.
3. Check for existing `${project_root}/.review/aims.md` — if present, **YOU MUST ASK the user "still accurate?" and wait for their response** before proceeding (do not skip this prompt even when the aims look fresh); if missing, run the interview.
4. Write or update `${project_root}/.review/aims.md` from templates/aims.md.tpl.
5. Update `${project_root}/.gitignore` only when `.git/` exists as a directory directly inside the project root.
6. Ask the user for review scope (full / phase / files / branch diff).
7. Cast the committee from the 23-persona library and partition files per persona using your File Partitioning Rules.
8. Display the casting roster + reasoning to the user; ask "Proceed?"
9. Output the casting roster as a single JSON object conforming to schemas/casting-roster.schema.json. JSON only.

Begin your reasoning now. Your only response to me is the casting-roster JSON.
"""
)
```

When the Profiler returns, parse its output as JSON and validate against `schemas/casting-roster.schema.json`. On validation failure, retry once with a stricter format prompt. On second failure, halt with: `Profiler returned malformed roster — aborting. Output saved to .review/runs/<review_id>/profiler-output.txt`.

Save the validated roster to `.review/runs/<review_id>/roster.json`.

If the Profiler did not refine the slug (review_id still ends in `-pending`), regenerate `review_id` now using the casting roster's `review_scope.description` to derive a new slug, and rename the run directory accordingly.

Print the casting summary:
```
  ✓ Detected: <project_profile.type> (<languages joined by />, <frameworks joined by />)
  ✓ Aims: .review/aims.md (<created|reused|refreshed>)
  ✓ Scope: <review_scope.description> — <total file count> files

  Casting committee:
    Stage 1 → <stage_1 persona names, comma-separated>
    Stage 2 → <stage_2 persona names, comma-separated>
    Stage 3 → <stage_3 persona names, comma-separated>
```

Confirm with the user: `Proceed with this committee? (y/n)`. If `n` or anything other than `y`/`yes`, halt and print: `Run cancelled. Roster saved at .review/runs/<review_id>/roster.json — re-run with overrides if you need a different cast.`

## Stage 1 — Peer Code Review

Print: `[Stage 1] Peer code review (<N> reviewers, parallel)...` where `<N>` is the length of `casting.stage_1`.

For each `cast_entry` in `casting.stage_1`, dispatch a subagent. Issue all dispatches **in parallel** within a single message: each persona reviews its own scope and never sees another persona's findings within a stage. Independent files; no race condition.

For each entry:

```
Task(
  subagent_type=cast_entry.persona,
  description=f"Stage 1 review: {cast_entry.persona}",
  prompt=f"""
You are running as the {cast_entry.persona} persona for a Crucible review. Your full system prompt lives at agents/{cast_entry.persona}.md. The shared output contract is at templates/persona-protocol.md.

# Review Inputs

## Aims snapshot
<verbatim contents of .review/aims.md>

## Scope files
{json.dumps(cast_entry.files)}

## File contents
<for each path in cast_entry.files, include a fenced block with the path as a header and the full file contents>

## Prior stage findings
None — you are Stage 1.

## Casting reasoning
{casting_roster.casting_reasoning}

# Output
Return a single JSON object conforming to schemas/persona-finding.schema.json. JSON only — no markdown fences, no preamble. Begin with {{ and end with }}.
"""
)
```

Wait for all Stage 1 subagents to complete. As each completes, validate its output against `schemas/persona-finding.schema.json`. On validation failure, retry once with a stricter format prompt that includes the schema validation error message; on second failure, mark the persona's slot as `failed_format` and continue.

Save each successful finding to `.review/runs/<review_id>/stage_1/<persona>.json`.

**Handling hook-blocked writes.** Some users run PreToolUse Write hooks (e.g., the `security-guidance` plugin from the official Claude Code marketplace) that block writes whose content matches dangerous-code substrings. If a persona's findings legitimately discuss such a pattern, the write may be blocked on the first attempt. The hook records the rule in session state and **the second attempt of the same write succeeds**. If you see a `PreToolUse:Write hook error` while saving a persona's JSON, retry the same Write once; if the retry also fails (different rule, different file), retry again. Do not treat hook blocks as persona failures — they are session-state warnings, not data problems. See `templates/persona-protocol.md` § 5 for the structural guidance personas already follow to minimize this case.

Print one line per persona as it finishes:
```
  ✓ <persona> — <score>/10 <verdict> (<N> findings)
```

If a persona is `failed_format` or `failed_dispatch`, print:
```
  ✗ <persona> — skipped (<reason>)
```

After all Stage 1 personas complete, build the `stage_1_findings` array from the successful entries (skipping `failed_format`). If more than half of Stage 1 personas failed, halt and write a partial report (see Error Handling below).

## Stage 2 — Cross-functional

Print: `[Stage 2] Cross-functional (<N> reviewers, parallel)...`

For each `cast_entry` in `casting.stage_2`, dispatch in parallel:

```
Task(
  subagent_type=cast_entry.persona,
  description=f"Stage 2 review: {cast_entry.persona}",
  prompt=f"""
You are running as the {cast_entry.persona} persona for a Crucible review. Your full system prompt lives at agents/{cast_entry.persona}.md.

# Review Inputs

## Aims snapshot
<verbatim contents of .review/aims.md>

## Scope files
{json.dumps(cast_entry.files)}

## File contents
<full contents of each path>

## Prior stage findings (Stage 1)
{json.dumps(stage_1_findings, indent=2)}

## Casting reasoning
{casting_roster.casting_reasoning}

# Output
Single JSON object per schemas/persona-finding.schema.json. JSON only.
"""
)
```

Validate, retry-once-on-failure, save, and print as in Stage 1. Save findings to `.review/runs/<review_id>/stage_2/<persona>.json`. Build `stage_2_findings`.

Stage 2 personas are reading prior findings — that's the differentiator from parallel-fan-out reviewers. Do not strip or summarize the Stage 1 findings before passing them; pass the full JSON.

## Stage 3 — Leadership

Print: `[Stage 3] Leadership (2 reviewers, parallel)...`

Dispatch `lead-senior-architect` and `lead-project-manager` in parallel. Both receive the **full diff or full file set** in scope (regardless of `cast_entry.files === "all"`), plus all prior reports:

```
Task(
  subagent_type=cast_entry.persona,
  description=f"Stage 3 leadership: {cast_entry.persona}",
  prompt=f"""
You are running as the {cast_entry.persona} persona. Your full system prompt is at agents/{cast_entry.persona}.md.

# Aims snapshot
<verbatim contents of .review/aims.md>

# Diff / scope (full)
<full file contents in scope, all paths>

# Stage 1 findings
{json.dumps(stage_1_findings, indent=2)}

# Stage 2 findings
{json.dumps(stage_2_findings, indent=2)}

# Casting reasoning
{casting_roster.casting_reasoning}

# Output
Single JSON object per schemas/persona-finding.schema.json. JSON only.
"""
)
```

Validate, save to `.review/runs/<review_id>/stage_3/<persona>.json`, build `stage_3_findings`.

Print:
```
  ✓ lead-senior-architect — ADR: <verdict> (score <N>/10)
  ✓ lead-project-manager — aim alignment: <score>/10 (verdict <verdict>)
```

## Stage 4 — Aggregator

Print: `[Stage 4] Aggregator synthesizing...`

**Before dispatching, compute the metadata values and substitute them as LITERAL VALUES in the prompt below.** The Aggregator MUST receive real arrays and numbers, never placeholder strings like `<calculated from...>` — if it sees a placeholder it will hallucinate a plausible-looking value, which then appears as fake metrics in the final JSON.

Compute each value now:

- `<MODELS_USED>` → JSON array of unique model identifiers used so far in this run (enumerate each successful persona's `model_used` field, deduplicate). Example: `["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"]`.
- `<WALL_CLOCK_SECONDS>` → **always `0`**. The schema requires the field, but Crucible does not measure wall-clock from inside the skill; Claude Code reports session wall-clock natively (and more accurately) at session end and via `/status`. Hardcode `0`; the rendered markdown report does not display this field.
- `<ESTIMATED_COST_USD>` → **always `0`**. Same reasoning as wall-clock: Claude Code does not expose token-level pricing to skill scripts, and any value the Aggregator inferred would be a hallucination. The rendered markdown report does not display this field either.

Verify the prompt below contains literal arrays/numbers (not `<MODELS_USED>` etc.) before sending.

Dispatch the Aggregator subagent:

```
Task(
  subagent_type="aggregator",
  description="Synthesize final report",
  prompt=f"""
You are running as the Aggregator. Your full system prompt is at agents/aggregator.md.

# Inputs

## Casting roster
{json.dumps(casting_roster, indent=2)}

## Aims snapshot
<verbatim contents of .review/aims.md>

## Stage 1 findings
{json.dumps(stage_1_findings, indent=2)}

## Stage 2 findings
{json.dumps(stage_2_findings, indent=2)}

## Stage 3 findings
{json.dumps(stage_3_findings, indent=2)}

## Run metadata (substituted by orchestrator — echo through verbatim; DO NOT modify, DO NOT re-estimate)
{{
  "plugin_version": "0.1.1",
  "wall_clock_seconds": <WALL_CLOCK_SECONDS>,
  "models_used": <MODELS_USED>,
  "estimated_cost_usd": <ESTIMATED_COST_USD>
}}

# Output
Single JSON object conforming to schemas/final-report.schema.json. JSON only — no markdown, no preamble. Echo the metadata field verbatim; do not re-estimate wall_clock_seconds or estimated_cost_usd — both are hardcoded to 0 by design.
"""
)
```

Validate the Aggregator output against `schemas/final-report.schema.json`. On failure, retry once with a stricter format prompt. On second failure, fall back to a stub report constructed mechanically:
- `final_score`: 5.0 (placeholder — Aggregator failed)
- `final_verdict`: `conditional_approval`
- `verdict_reasoning`: `Aggregator failed to produce a valid final report; this is a mechanical fallback. Read the per-stage findings below for the actual signal.`
- `executive_summary`: same disclaimer.
- `what_is_good`: empty list.
- `what_is_concerning`: list containing the single string `Aggregator synthesis failed.`
- `key_quotes`: pull `summary_quote` from up to 6 personas (prefer Stage 3 then Stage 2 then Stage 1).
- `stage_reports`, `aims_snapshot`, `casting_roster`, `metadata`: populate as normal.

Save the (validated or fallback) final report to `.review/runs/<review_id>/final-report.json`.

## Final Output

### Write the markdown report file

**Render the markdown report by invoking the deterministic Python renderer.** Do not assemble the markdown manually — the v0.1.0 pipeline did that and the LLM drifted across runs (heading text, metadata block style, table vs flat bullet structure all varied). v0.1.1 replaces inline substitution with `scripts/render_report.py`, which reads `final-report.json` plus the sibling `stage_<N>/*.json` files, applies `templates/report.md.tpl` via vendored Jinja2, and writes a byte-stable output.

Run the renderer via Bash:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py" \
  --input "${project_root}/.review/runs/<review_id>/final-report.json" \
  --output "${project_root}/.review/reports/<review_id>.md"
```

Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` to the plugin's absolute install path before the shell sees it, so this works for both installed users (`~/.claude/plugins/cache/<marketplace>/crucible/<version>/`) and developers running from a source checkout. `${project_root}` and `<review_id>` are the values you captured in Setup steps 1–2 — substitute them as literal strings in the Bash command (e.g., `/home/user/my-project/.review/runs/2026-05-21-1530-auth-refactor/final-report.json`) before sending. The renderer's only runtime dependency is Python 3.8+; Jinja2 and MarkupSafe are vendored in `scripts/_vendor/` so no `pip install` or `uv add` is required.

If the Bash invocation exits non-zero, inspect stderr to diagnose. The most common causes:
- Missing `final-report.json` (Stage 4 didn't write it — check the run dir).
- Schema drift in `final-report.json` (a required key like `key_quotes` is absent — the Aggregator drifted; re-run the Aggregator with stricter format prompt).
- `python3` not on PATH (rare; report to the user and fall back to manually rendering using `templates/report.md.tpl` as the literal structural spec — but flag the environment gap as a bug).

If a PreToolUse Write hook (e.g., `security-guidance`) blocks the renderer's output file because a finding's text contains a dangerous-pattern substring, re-run the same Bash command once — the hook records the rule in session state on the first hit and the retry succeeds. See `templates/persona-protocol.md` § 5 for the structural discipline personas follow to minimize this case.

**Do not edit the rendered file after the renderer writes it.** Trust the script's output. If the formatting needs to change, the fix lives in `templates/report.md.tpl` or `scripts/render_report.py`, not in post-processing.

### Print the terminal summary

```
──────────────────────────────────────────────────
📊 FINAL VERDICT: <final_score>/10 — <human_verdict>
──────────────────────────────────────────────────
```

`<human_verdict>` maps the JSON enum:
- `approved` → `Approved`
- `conditional_approval` → `Conditional Approval`
- `blocked` → `Blocked`

Then print the curated lists:
```

What's good:
  • <each item from what_is_good>

What's concerning:
  • <each item from what_is_concerning>

Key notes:
  <emoji> <persona>: "<quote>"
  ...
```

Emoji prefixes by persona prefix:
- `peer-` → 👨‍💻
- `team-security-*` → 🛡️
- `team-frontend-*` → 🎨
- `team-backend-*` → ⚙️
- `team-database-*` → 🗄️
- `team-network-*` → 🌐
- `team-devops-infra-*` → 🚀
- `team-performance-*` → ⚡
- `team-accessibility-*` → ♿
- `team-observability-*` → 📊
- `team-privacy-compliance-*` → 🔒
- `team-data-ml-*` → 🤖
- `lead-senior-architect` → 🏗️
- `lead-project-manager` → 📋
- (any `team-*` not listed above) → 🏢

Then print the footer:
```

📁 Full report: .review/reports/<review_id>.md
```

The user has the file path. Stop output here — do not summarize further. Wall-clock and API cost are not printed by the orchestrator; Claude Code reports both natively at session end and via `/status`.

## Error handling

**Single subagent failure (timeout, refusal, internal error).**
- Mark that persona's slot as `skipped` with the recorded error.
- Continue the pipeline.
- The Aggregator notes the gap (per its prompt's "missing or failed personas" guidance).

**More than half of any single stage fails.**
- Halt the pipeline.
- Save partial outputs and write a partial report at `.review/reports/<review_id>-PARTIAL.md` containing whatever stages completed plus an explicit "incomplete run" header.
- Print: `Run halted: <stage> had <N>/<total> failures. Partial report at .review/reports/<review_id>-PARTIAL.md`.

**User cancels mid-stage (Ctrl-C).**
- Save whatever stages completed.
- Write `.review/reports/<review_id>-PARTIAL.md`.
- Print: `Run cancelled. Partial report at .review/reports/<review_id>-PARTIAL.md`.

**Schema validation failure on a persona output.**
- Retry once with a stricter format prompt that includes the schema error.
- On second failure, mark `failed_format` and proceed.

**Schema validation failure on the Aggregator output.**
- Retry once.
- On second failure, fall back to the mechanical stub report described in the Stage 4 section.

## Notes on parallelism

Stage 1, Stage 2, and Stage 3 each dispatch their personas **in parallel** via multiple Task tool calls in a single message. The personas write to different files in `.review/runs/<review_id>/stage_<N>/` — there is no race. Parallel dispatch reduces wall-clock from N×T to ~T per stage.

Do not parallelize across stages; stage handoff is strictly sequential because Stage 2 reads Stage 1's findings, Stage 3 reads both, and the Aggregator reads all three.

## Notes on cost and tier

The typical run uses Haiku 4.5 for some Stage 1 peers, Sonnet 4.6 for others + all Stage 2 + Profiler, and Opus 4.7 for Stage 3 + Aggregator. Both Pro and Max plans support Opus, so no model substitution is needed in the normal case. Pro users with tight usage budgets should prefer phase- or file-scoped reviews over full-project ones (the Profiler will cast a smaller committee).

**Total cost is dominated by the orchestrator's model — i.e., whichever model your Claude Code session is running.** This is the load-bearing v0.1.0 finding. Measured pre-warning: 5 runs with the user's session on Sonnet 4.6 cost $4.78–$6.75 (median $5.22); 1 run with the user's session on Opus 4.7 cost $8.95 on the cheapest fixture (~1.7× the Sonnet-main equivalent). The cost preview at the top of this skill exists to surface this so the user can `/model claude-sonnet-4-6` before the run if cost matters.

## Notes on idempotence

If the user re-runs `/crucible:run` with the same scope on the same project on the same minute, the `review_id` will collide. Disambiguate by appending `-2`, `-3`, ... to the slug.

If `.review/aims.md` already exists, the Profiler is responsible for asking "still accurate?" (per its own prompt and the dispatch-prompt reinforcement above). The orchestrator does not need to handle that case directly.
