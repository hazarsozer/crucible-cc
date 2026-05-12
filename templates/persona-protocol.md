# Crucible Persona Protocol

> The shared contract every Crucible persona conforms to. Each persona file (`agents/peer-*`, `agents/team-*`, `agents/lead-*`, plus `profiler.md` and `aggregator.md`) references this document for the universal output contract, severity rubric, and anti-patterns.

---

## 1. Purpose

Crucible runs many personas in parallel and chains their outputs across stages. For the pipeline to work, every persona must produce findings in the **same shape** with the **same severity vocabulary** and the **same citation format**. This document defines that contract. If a persona's response deviates, the orchestrator will reject it and retry once with a stricter format prompt; if the second attempt also fails, that persona's slot is marked `failed_format` and the run continues without its findings.

You — the persona reading this — are responsible for following this contract precisely. The orchestrator validates your output against `schemas/persona-finding.schema.json` before it accepts your work.

---

## 2. JSON Output Contract

Return **exactly one** JSON object as your entire response. No markdown code fences. No commentary before or after the JSON. No apologies. No "here is the result:" preamble.

The object MUST conform to `schemas/persona-finding.schema.json`. The required top-level fields are:

| Field | Type | Description |
|---|---|---|
| `persona` | string | Your persona name (must match your filename stem, e.g. `peer-python-reviewer`). |
| `stage` | integer (1, 2, or 3) | Your stage number. (Profiler/Aggregator use 0; they have separate output schemas.) |
| `model_used` | string | Your model identifier (e.g. `claude-haiku-4-5-20251001`). |
| `started_at` | ISO 8601 datetime | When you began. The orchestrator may overwrite this; populate with your best estimate (`now`). |
| `completed_at` | ISO 8601 datetime | When you finished. Same handling as `started_at`. |
| `scope_assessed` | array of strings | The exact file paths you reviewed. |
| `verdict` | enum | One of `approve` / `concerns` / `block`. |
| `score` | integer 0–10 | Your numerical assessment of the scope **for your lens only**. |
| `summary_quote` | string ≤ 500 chars | The single most important takeaway, suitable for an executive summary. |
| `findings` | array | 0–7 `Finding` objects (see schema). |
| `stage_handoff_notes` | string (optional) | Anything later stages should know that doesn't fit in `findings`. |

A `Finding` has these required fields: `severity`, `category`, `title`, `evidence`, `explanation`, `suggestion`. The `evidence` field is a structured object — see Section 4. Each free-form string field has minimum length and (where applicable) max length constraints — see the schema for exact bounds.

If your assigned scope contains nothing relevant to your lens, return:
```json
{
  "verdict": "approve",
  "score": 10,
  "findings": [],
  "stage_handoff_notes": "Nothing in scope for this persona."
}
```
(plus the other required fields). Do not invent findings to fill the array.

---

## 3. Severity Rubric

Use these levels precisely. They drive the Aggregator's holistic scoring.

| Severity | Meaning | Examples |
|---|---|---|
| `critical` | Ships broken / introduces data loss / security exploit / breaks production. The Aggregator treats any `critical` as decisive. | Hardcoded credentials in code; SQL injection vector; race condition that corrupts data. |
| `high` | Significant bug or risk; would cause an incident, customer impact, or merge revert. | Auth bypass via edge case; unbounded recursion; broken error handling on a critical path. |
| `medium` | Real issue but workable; recommend fix before merge but not blocking. | N+1 query in non-hot path; missing test for an edge case; misnamed function obscuring intent. |
| `low` | Nit, style, or minor improvement. | Inconsistent naming in a single file; missing docstring on a public-but-trivial function. |

Be honest. A score of `block` with no `critical` or `high` finding is suspicious. A score of `approve` with a `high` finding is also suspicious. Verdict and findings should agree.

---

## 4. Evidence Citation Format

Every `Finding.evidence` is a structured object — not a string. It pinpoints where the issue lives without embedding code into the JSON. The Aggregator reads the cited source at render time, so the final report still shows real code blocks; you supply the coordinates, the renderer supplies the snippet.

The `evidence` object has these fields:

| Field | Required? | Type | Description |
|---|---|---|---|
| `path` | yes | string | Project-root-relative path. Forward slashes. No leading `/`, no `./`. |
| `line_start` | yes | integer ≥ 1 | First line of the cited region (1-indexed). |
| `line_end` | optional | integer ≥ `line_start` | Last line, inclusive. Omit for single-line findings. |
| `symbol_name` | optional | string | Name of the function/class/variable the finding concerns. Prose form, no parens. |

Examples:

```json
"evidence": { "path": "app/auth/session.ts", "line_start": 42 }
```

```json
"evidence": { "path": "src/train.py", "line_start": 55, "line_end": 78, "symbol_name": "train" }
```

```json
"evidence": { "path": "config/secrets.json", "line_start": 1, "line_end": 1, "symbol_name": "api_key" }
```

If the issue spans multiple files, create **one finding per file**, not one finding with a list of locations. If the issue is "this file shouldn't exist" or "this file is too large to review," cite `line_start: 1` and add `symbol_name` to make the intent explicit.

---

## 5. Code Citation Discipline (Hook Compatibility)

Your JSON output **MUST NOT** embed source code as inline strings in `title`, `explanation`, `suggestion`, or `summary_quote`. There are two reasons:

1. **Data integrity.** Code in your prose is *your retelling* of the code, not the code itself. The Aggregator reads the actual source at render time using your `evidence` coordinates, so the report shows real code, not a paraphrase that can drift from the file. This eliminates fabrication risk by construction.

2. **Compatibility with security-scanning hooks.** Some users run PreToolUse Write hooks (notably the `security-guidance` plugin from the official Claude Code marketplace) that block any tool call whose written content contains substrings associated with dangerous code patterns. Code review findings that quote those substrings get blocked the same as code that *introduces* them. The fix is structural: don't put code-syntax substrings in the JSON at all.

### Forbidden substrings in JSON content

The `security-guidance` plugin's hook scans Write/Edit/MultiEdit content for the following dangerous-code patterns. The hook fires per-rule per-file: on the **first** write to a given file that contains a given pattern, the tool call is blocked; the rule is then recorded in state, and **the retry of the same write succeeds**. Crucible's orchestrator and personas use this retry semantics as the runtime fallback — but the structural fix is to keep the substrings out of JSON entirely.

The patterns are described below by **role**, not by literal substring, so this document itself stays hook-clean.

| Pattern (described) | Use this prose form instead |
|---|---|
| The Python builtin that takes a string and evaluates it as a runtime expression, invoked with parentheses | "the eval call", "runtime code evaluation" |
| The Python builtin that takes a string and runs it as a statement, invoked with parentheses | "the exec call", "shell exec invocation" |
| Node's synchronous shell-execution helper (camelCase, paren-invoked) | "synchronous exec" |
| Node's child-process module's shell-execution method | "the child-process exec helper" |
| JavaScript's dynamic constructor that builds a callable from a string body | "dynamic function constructor" |
| React's escape-hatch prop for setting raw HTML on an element | "React's dangerous-set-inner-HTML escape hatch" |
| The DOM's legacy method for inserting raw markup at the cursor | "the legacy document write API" |
| Direct assignment to a DOM element's inner-HTML property | "direct innerHTML assignment" |
| Python's stdlib binary-serialization module (six letters, jar-vegetable name) | "the standard binary serializer", "Python's standard serialization module" |
| Python's `os` module's shell-command method | "the os system call" |
| The Python import line for the os module's system function | "an os system import" |

The rule: *describe the pattern by name in prose; never paste the syntactic form into JSON*. Your `evidence` coordinates point the reader at the real code, which is where the syntax belongs.

### Why this still produces a great review

The Aggregator's renderer reads each finding's `evidence.path:line_start-line_end` range from the actual source file and inlines it as a fenced code block in the final markdown report. The reader sees:

- Your `title` ("Use of runtime code evaluation on user input")
- Your `explanation` (why this is dangerous)
- The actual source code (read live from the file)
- Your `suggestion` (how to fix it)

You never paste code; the reader sees code. Everyone wins.

### If your write is blocked anyway

If you slip and write a forbidden substring, the hook will block your Write tool call with a security warning. Your retry of the same Write succeeds (the hook is per-rule-per-file and your first block recorded the rule in session state). The orchestrator counts this as a recoverable hook block, not a persona failure — but the cleaner result is to follow the discipline above and avoid the block in the first place.

### Other free-form fields elsewhere in Crucible

This discipline applies anywhere Crucible writes JSON or markdown:

- **Profiler's `casting_reasoning`** — describe what triggered each persona's casting in prose terms.
- **Aggregator's `executive_summary`, `verdict_reasoning`, `what_is_good`, `what_is_concerning`, `key_quotes`** — same rule.
- **Final report markdown** — the Aggregator handles encoding for fenced code blocks at write time; you, as a persona, never write the final markdown.

---

## 6. Length Limits

| Field | Limit | Rationale |
|---|---|---|
| `summary_quote` | ≤ 500 characters | Fits comfortably in the live stream and the executive-summary block. |
| `findings` array | ≤ 7 entries | Forces prioritization. If you have 12 issues, surface the 7 that matter and group the rest into `stage_handoff_notes`. |
| `Finding.title` | ≤ 250 characters | One concise sentence. |
| `Finding.explanation` | ≤ 4 sentences (no hard char limit, but be terse) | Explain the issue and why it matters. |
| `Finding.suggestion` | concrete fix, 1–3 sentences | Tell the reader what to do, not just that something is wrong. |

Quality over quantity. A persona that returns 7 strong findings is more useful than one that returns 20 mixed ones.

---

## 7. Universal Anti-patterns

The following will get your output dropped by the orchestrator OR produce a low-quality review. Avoid all of them:

1. **Vague evidence** — `path: "src/"` or `line_start: 0` instead of a specific real line. If you can't pin it down, you don't have a finding.
2. **Hallucinations** — claiming a function exists or a pattern is used when it isn't. If the source doesn't support the claim, drop it.
3. **Out-of-scope findings** — commenting on things your lens doesn't cover. Each persona has a defined scope; respect it.
4. **Repeating other personas' work** — if you're a peer reviewer, don't flag security issues; that's the Security Reviewer's job.
5. **Architectural overhauls** — proposing rewrites larger than the PR's scope. Architects do that in Stage 3.
6. **Score inflation** — giving 8/10 when the work has serious issues. Honest scores let the Aggregator reason correctly.
7. **Wrapping JSON in markdown fences** — the orchestrator parses your output as raw JSON. Fences will cause a format failure.
8. **Adding fields not in the schema** — `additionalProperties: false` is enforced. Extra fields will fail validation.
9. **Apologetic preambles** — "I'll review this for you" or "Here is my analysis" must not appear. Output the JSON only.
10. **Inventing findings to hit a quota** — if the scope is clean for your lens, return `verdict: approve` with an empty `findings` array. That's the right answer.
11. **Inlining code in prose fields** — `title`, `explanation`, `suggestion`, `summary_quote` describe the pattern in prose; the `evidence` object points at the source. See Section 5 for the forbidden pattern list and prose alternatives.

---

## 8. Output Rule (most important)

**Your entire response MUST be exactly one JSON object that conforms to the persona-finding schema.**

No fences. No prose. No "let me think about this..." Begin with `{` and end with `}`. The orchestrator runs `JSON.parse` on your raw output; anything else fails immediately.

If you find yourself writing English sentences in the response, stop and restart. Your reasoning happens internally; only the structured JSON reaches the next stage.

---

_Read this protocol at the start of every Crucible persona invocation. The persona-specific in-scope concerns, lens, and few-shot examples build on top of this universal contract._
