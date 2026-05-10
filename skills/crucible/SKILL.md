---
name: crucible
description: Run a Crucible review pipeline on the current project. The Profiler reads the project, interviews the user, and casts a 4–8 persona review committee from a 23-persona library. Peers review at the code level, departments hunt for gaps, leadership grades alignment, and the Aggregator synthesizes a final score and verdict. Output is a live terminal stream plus a fully-detailed markdown report at .review/reports/<id>.md.
---

# /crucible — Corporate Review Pipeline

You are orchestrating a Crucible review pipeline on the current project. Execute the following stages in order. Stream progress to the terminal in compact form as each stage completes; write the full markdown report to `.review/reports/<review_id>.md` at the end.

The pipeline has five stages: Profiler (Stage 0) → Peer Code Review (Stage 1) → Cross-functional Gap Review (Stage 2) → Leadership (Stage 3) → Aggregator (Stage 4). Each stage is dispatched as one or more Claude Code subagents via the Task tool, with structured JSON handoff between stages.

## Setup

1. Generate `review_id` of the form `YYYY-MM-DD-HHMM-<slug>` using the current UTC time. The `<slug>` is derived from the user's review scope description: lowercase, hyphenated, ASCII only, ≤30 characters. If the user has not yet stated a scope, use the placeholder slug `pending`; the Profiler will refine it.
2. Record `started_at` as an ISO 8601 UTC timestamp.
3. Print the banner:
   ```
   🔥 Crucible — Project Review Pipeline
   ```
4. Create directory `.review/runs/<review_id>/` for transient artifacts.

## Stage 0 — Profiler

Print: `[Stage 0] Profiler reading project...`

Dispatch the Profiler agent via the Task tool:

```
Task(
  subagent_type="profiler",
  description="Profile project + interview + cast committee",
  prompt="""
You are running as the Profiler agent for Crucible. Read your full system prompt at agents/profiler.md if it has not already been loaded by the harness.

# Working directory
<absolute path of the user's project>

# User invocation
<the original /crucible invocation, including any free-text scope hint the user typed>

# Your job
Follow your full Profiler workflow:
1. Read project signals (file tree, README, CLAUDE.md, language manifests, recent commits).
2. Detect project type, languages, frameworks, datastores, deployment.
3. Check for existing .review/aims.md — if present, ask "still accurate?"; if missing, run the interview.
4. Write or update .review/aims.md from templates/aims.md.tpl.
5. Update .gitignore if .git/ exists and .review/ is not yet ignored.
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

## Run metadata
{{
  "plugin_version": "0.1.0",
  "wall_clock_seconds": <calculated from started_at to now, integer>,
  "models_used": <unique list of all model identifiers used by Profiler + every successful persona>,
  "estimated_cost_usd": <best-effort estimate, or 0 if unknown>
}}

# Output
Single JSON object conforming to schemas/final-report.schema.json. JSON only — no markdown, no preamble.
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

Render the final report through `templates/report.md.tpl`. Substitute every `{{...}}` placeholder with the corresponding field from the final-report JSON. The template uses Handlebars-like `{{#each ...}} ... {{/each}}` blocks for arrays — iterate the array and emit the inner template once per item, substituting `{{this}}` (or the named field for object arrays) with the current item.

Crucible does not ship a template engine. Implement the substitution inline as you generate the file:
- For `{{key}}` placeholders, substitute the JSON value directly. If the value is an object or array, format it as readable inline text (e.g., a comma-separated list for arrays of strings; a key-value list for objects).
- For `{{#each items}} ... {{/each}}` blocks, emit the inner block once per item.
- For nested-field references like `{{casting_roster.project_profile.type}}`, walk the dotted path through the JSON.
- Preserve markdown structure exactly — don't reflow lists or headings.

Write the rendered output to `.review/reports/<review_id>.md`.

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
   Wall-clock: <Xm Ys> · Estimated cost: $<X.XX>
```

The user has the file path. Stop output here — do not summarize further.

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

Per spec §3.3, the typical run uses Haiku 4.5 for some Stage 1 peers, Sonnet 4.6 for others + all Stage 2 + Profiler, and Opus 4.7 for Stage 3 + Aggregator. If the user lacks Opus access (Pro tier), fall back to Sonnet 4.6 for Stage 3 and Aggregator: when dispatching, append to the prompt: `Note: Opus is unavailable for this run; you are operating on Sonnet 4.6. Maintain rigor.`

## Notes on idempotence

If the user re-runs `/crucible` with the same scope on the same project on the same minute, the `review_id` will collide. Disambiguate by appending `-2`, `-3`, ... to the slug.

If `.review/aims.md` already exists, the Profiler is responsible for asking "still accurate?" (per its own prompt). The orchestrator does not need to handle that case directly.
