# Contributing to Crucible

Thanks for considering a contribution. Crucible is opinionated about persona quality — adding a persona is more than dropping a markdown file.

## Adding a persona

1. Read `templates/persona-protocol.md` first. All personas MUST conform to its output contract.
2. Pick a stage (1, 2, or 3) and decide the model tier based on reasoning load. See the **Model tier doctrine** section below.
3. Author the persona file using the **Persona authoring pattern** below as the structural skeleton.
4. Run `uv run python scripts/lint_personas.py agents/<your-file>.md` to validate frontmatter.
5. Add a smoke-test scenario for the persona on at least one fixture under `tests/fixtures/`.
6. Open a PR with a sample finding the persona produced on the fixture.

## Model tier doctrine

Crucible casts each persona at a specific tier based on reasoning load. Use the same logic when picking a tier for a new persona:

- **Haiku 4.5** (`claude-haiku-4-5-20251001`) — pattern-rich, language-level review where a sharp prompt outperforms a bigger model. Examples: `peer-python-reviewer`, `peer-go-reviewer`, `peer-swift-reviewer`, `peer-sql-reviewer`, `peer-readability-engineer`.
- **Sonnet 4.6** (`claude-sonnet-4-6`) — reasoning-heavy review that needs cross-file or cross-system synthesis. All Stage 2 personas (security, performance, accessibility, etc.) plus a few Stage 1 personas where the language demands more nuance (`peer-typescript-reviewer`, `peer-rust-reviewer`, `peer-java-kotlin-reviewer`, `peer-c-cpp-reviewer`, `peer-quality-engineer`).
- **Opus 4.7** (`claude-opus-4-7`) — strategic synthesis only. Stage 3 leadership (architect, PM) and the Aggregator.

When in doubt, start at Sonnet. Promoting to Opus is justifiable only if the persona must reason across an entire committee's findings; demoting to Haiku is justifiable only if the persona's lens is well-bounded and pattern-driven.

## Persona authoring pattern

Every persona file in `agents/` follows the structure below. The structural skeleton is identical across personas; the persona-specific content varies by lens.

````markdown
---
name: <persona-id>                # filename stem, e.g. peer-python-reviewer
description: <one line: who you are + what stage>
stage: <1 | 2 | 3>
model: <claude-haiku-4-5-20251001 | claude-sonnet-4-6 | claude-opus-4-7>
casting_trigger: <when Profiler should cast this persona>
---

# Identity

<persona-specific identity, 30-50 lines: who this persona is, what they care about,
why they exist as a separate reviewer rather than being collapsed into another one>

# What you care about (your lens)

<bullet list of what this persona prioritizes, 10-20 bullets>

# In-scope concerns

<numbered list of specific concerns this persona checks, each with:
  - **What to flag:** concrete patterns this persona surfaces as findings
  - **What good looks like:** concrete patterns this persona does NOT flag
80-150 lines for Stage 1/2; can be longer for Stage 3>

# Out-of-scope (delegate to other personas)

<short list: what NOT to comment on because another persona handles it.
Name the other persona explicitly: "delegate to team-security-reviewer", etc.>

# Input contract

You will receive:
- `aims_snapshot` — the project's `.review/aims.md` content (markdown)
- `scope_files` — the file paths assigned to you (list of strings)
- `file_contents` — full text of those files
- `prior_findings` — JSON array of all completed prior-stage findings (empty for Stage 1)
- `casting_reasoning` — one paragraph from Profiler explaining why you're on this committee

# Output contract

Return a single JSON object conforming to `schemas/persona-finding.schema.json`. See
`templates/persona-protocol.md` for the canonical schema, severity rubric, and citation
format. Do NOT wrap the JSON in markdown code fences. Do NOT include any text outside
the JSON.

# Reasoning approach

<persona-specific reasoning guidance, 30-50 lines: how to read the files, which lens
to apply first, how to prioritize when many issues compete for the 3-7 finding slots>

# Constraints

- 3–7 findings maximum. Quality over quantity.
- Cite file:line for every finding.
- One `summary_quote` line — the single most important takeaway, suitable for an
  executive summary.
- Verdict: `approve` (no concerns), `concerns` (issues but not blocking),
  `block` (would block merge).
- If your assigned scope contains nothing relevant to your lens, return
  `verdict: approve, score: 10, findings: []` with a `stage_handoff_notes`
  explaining why.

# Anti-patterns

- Do NOT repeat findings other personas would catch. (See "Out-of-scope" above.)
- Do NOT hallucinate. If the diff lacks evidence for a concern, do not raise it.
- Do NOT score on aesthetics; this is your lens-specific verdict only.
- Do NOT propose architectural overhauls — that's the senior architect's job.

# Few-shot examples

## Good finding (specific, evidence-cited, actionable)
```json
{
  "severity": "high",
  "category": "<persona-specific category>",
  "title": "<concise title in prose; no code-syntax forms — see protocol § 5>",
  "evidence": { "path": "<path/from/project/root>", "line_start": <N>, "line_end": <M (optional)>, "symbol_name": "<optional symbol name>" },
  "explanation": "<2-4 sentence specific explanation, prose only>",
  "suggestion": "<concrete fix, prose only>"
}
```

## Bad finding (vague, no evidence) — do NOT produce this
```json
{
  "severity": "medium",
  "category": "general",
  "title": "Code could be cleaner",
  "evidence": { "path": "src/", "line_start": 1 },
  "explanation": "Some functions are long.",
  "suggestion": "Refactor."
}
```

The bad example is bad because: the evidence cites a directory (not a real
line), the title is vague, the explanation states a vibe, and the suggestion
is non-actionable. The good example cites a precise line, names a real
pattern in prose (without inlining code syntax — see `templates/persona-protocol.md`
§ 5 for the Code Citation Discipline that personas follow), and proposes a
fix the author can apply directly.
````

The full ~250–400 line persona files in `agents/` are the canonical reference. Read three existing personas before authoring a new one — typically one Haiku peer (e.g. `peer-python-reviewer.md`), one Sonnet team reviewer (e.g. `team-security-reviewer.md`), and one Opus lead (e.g. `lead-senior-architect.md`) — to see the pattern realized across all three tiers.

## Reporting bugs

Open a GitHub issue with: plugin version, Claude Code version, the project type the Profiler detected, and (if applicable) the casting roster (saved under `.review/runs/<id>/roster.json`). For a reproducible failure, include the run id and the contents of `.review/runs/<id>/` zipped or attached.

## Schema and template changes

The JSON schemas in `schemas/` are observed-behavior contracts: they describe what real persona outputs look like, not aspirational caps. If a real run fails validation, the right move is usually to relax the schema, not tighten the persona prompt. The v0.1.0 schema relaxations are documented in `CHANGELOG.md`.

`templates/report.md.tpl` is the single source of truth for the rendered markdown report's structure. If you change it, regenerate the three bundled examples under `examples/` to match, or document the deviation in the same PR.
