# Crucible

[![Listed on ClaudePluginHub](https://www.claudepluginhub.com/badge/hazarsozer-crucible)](https://www.claudepluginhub.com/plugins/hazarsozer-crucible?ref=badge)

> **Not Another Code Reviewer.**

A Claude Code plugin that runs your code through a corporate review pipeline. A **Profiler** reads your project, interviews you about the phase, and casts a 4–8 persona review committee from a 23-persona library. **Peers** review at the code level, **departments** hunt for gaps, and **leadership** grades alignment to your stated aims. An **Aggregator** synthesizes the holistic verdict — no math, no averaging, just Opus reasoning over the committee's reports.

The output is a live terminal stream while the pipeline runs and a fully-detailed markdown report saved at `.review/reports/<id>.md`. See [`examples/`](examples/) for sample reports.

---

## Why this exists

Every Claude Code plugin's reviewer fans out agents in parallel and aggregates their findings. Crucible is structurally different in three ways:

1. **Adaptive cast.** A Profiler reads your project and picks the right reviewers from a 23-persona library. A Next.js auth refactor casts TypeScript + SQL + Security + Backend + Database + Architect + PM. A PyTorch training change casts Python + Quality + Data-ML + Performance + Architect + PM. The committee fits the work.
2. **Three altitudes.** Stage 1 peers review at the **code** level (idioms, bugs, quality). Stage 2 cross-functional reviewers hunt for **gaps** (security, performance, accessibility, observability — domain-specific lenses). Stage 3 leadership reasons at the **strategic** level (architectural coherence, aim alignment).
3. **Aim alignment.** A `lead-project-manager` persona reads your `.review/aims.md` — written interactively by the Profiler — and grades the change against your stated success criteria. Nobody else does this. Your code isn't graded in a vacuum; it's graded against what you said you were trying to do.

The result: every persona reasons in their lane, the stages hand off structured findings, and one final reasoning agent synthesizes everything into a single score, verdict, and curated executive summary. No mechanical roll-up; the Aggregator weighs signals as a thoughtful executive would when reading a 7-person review committee.

---

## Quick start

Inside Claude Code, add Crucible as a self-hosted marketplace and install the plugin (one-time setup):

```bash
/plugin marketplace add hazarsozer/crucible-cc
/plugin install crucible@crucible
/reload-plugins
```

Then, in any project directory:

```bash
cd your-project
/crucible:run
```

<details>
<summary><em>Alternative: ClaudePluginHub Quick Install</em></summary>

```bash
npx claudepluginhub hazarsozer/crucible-cc --plugin crucible
```

A single line of code provided by Claude Plugin Hub.
</details>

<details>
<summary><em>Alternative: clone the repo and load it directly (no install step)</em></summary>

```bash
git clone https://github.com/hazarsozer/crucible-cc.git
claude --plugin-dir ./crucible-cc
```

Useful if you want full source on disk to read, modify, or contribute back. The `/plugin install` path above copies Crucible to Claude Code's cache automatically.
</details>

Optional commands:

```bash
/crucible:aims      # refresh .review/aims.md without running a full review
/crucible:history   # list past reviews stored in .review/reports/
```

The first run of `/crucible:run` will:

1. Read your project files (file tree, README, language manifests, recent commits).
2. Detect project type (web-app, api, ml-pipeline, cli, library, mobile, data-pipeline, mixed).
3. Interview you about the phase: goal, success criteria, non-goals, constraints.
4. Write `.review/aims.md` and update `.gitignore` if needed.
5. Ask what to review (full project, phase, files, branch diff).
6. Cast the committee and confirm with you before dispatching.
7. Run the 5-stage pipeline and write the report.

Subsequent runs reuse `.review/aims.md` (with a "still accurate?" prompt).

---

## ⚠️ When NOT to use `/crucible:run`

Crucible runs **5 stages and 4–8 specialized agents** per review. It is not another lightweight reviewer — it is a corporate-review simulation, and that shape costs tokens.

**Use `/crucible:run` for:**
- Full-project reviews (initial audit, pre-release, milestone gate)
- Partial-implementation reviews (a feature, a phase, a refactor in flight)

**Don't use `/crucible:run` for:**
- A single script or one-file change
- Trivial PRs or one-line tweaks
- Anything where one specialist's perspective is enough

For those, **call a specific persona directly** via the Task tool — `crucible:peer-python-reviewer`, `crucible:team-security-reviewer`, `crucible:lead-senior-architect`, etc. The full list of 23 personas is below; each is independently invokable. The pipeline is the heavyweight; individual personas are the scalpel.

Measured cost and wall-time ranges (from runs on a 7-file Next.js fixture) are in the [Costs](#costs) section below. A recommended-scope threshold (e.g. "≥N files") will land in v0.1.1 once we have measured runs on larger projects and other project types.

---

## What it does — the 5-stage pipeline

```
                User: /crucible:run from project dir
                            │
                            ▼
 STAGE 0  ┌──────────────────────────────────────┐
   ░░░    │  PROFILER  (Sonnet 4.6)              │
          │  Reads project, interviews user,     │
          │  casts the committee, partitions     │
          │  files per persona                   │
          └──────────────────┬───────────────────┘
                             │ casting roster
                             ▼
 STAGE 1  ┌──────────────────────────────────────┐
   ███    │  PEER engineers (Haiku/Sonnet × 3-5) │
          │  Code-level: idioms, bugs, quality   │
          └──────────────────┬───────────────────┘
                             │ stage-1 findings
                             ▼
 STAGE 2  ┌──────────────────────────────────────┐
   ███    │  CROSS-FUNCTIONAL  (Sonnet × 2-4)    │
          │  Gap-level: security, perf, infra,   │
          │  privacy, observability, etc.        │
          └──────────────────┬───────────────────┘
                             │ stage-1 + stage-2
                             ▼
 STAGE 3  ┌──────────────────────────────────────┐
   ███    │  LEADERSHIP  (Opus × 2)              │
          │  Architect: ADR verdict              │
          │  PM: aim-alignment grade             │
          └──────────────────┬───────────────────┘
                             │ all stage findings
                             ▼
 STAGE 4  ┌──────────────────────────────────────┐
   ███    │  AGGREGATOR  (Opus)                  │
          │  Holistic score + verdict +          │
          │  curated executive summary           │
          └──────────────────┬───────────────────┘
                             │
                             ▼
              Live terminal stream (compact)
              + .review/reports/<id>.md (detailed)
```

**Key invariants:**
- Within a stage, personas run **in parallel** and **never see each other's findings**.
- Across stages, handoff is via **structured JSON**. Stage 2 reads Stage 1's findings; Stage 3 reads both; Aggregator reads everything plus the aims snapshot.
- File partitioning is computed by the Profiler. Each persona only sees its assigned scope.
- No mechanical roll-up — the final score and verdict are reasoned by the Aggregator.

---

## The 23 personas

<details>
<summary><strong>Stage 1 — Peer code reviewers (10)</strong></summary>

| Persona | Model | Lens |
|---|---|---|
| `peer-python-reviewer` | Haiku 4.5 | PEP 8, idioms, type hints, common pitfalls |
| `peer-typescript-reviewer` | Sonnet 4.6 | Type safety, async correctness, strict-mode patterns |
| `peer-go-reviewer` | Haiku 4.5 | Idiomatic Go, error handling, concurrency |
| `peer-rust-reviewer` | Sonnet 4.6 | Ownership, lifetimes, `unsafe` audit |
| `peer-java-kotlin-reviewer` | Sonnet 4.6 | JVM idioms, Spring/Android patterns |
| `peer-c-cpp-reviewer` | Sonnet 4.6 | Memory safety, modern C++ idioms, UB hunting |
| `peer-swift-reviewer` | Haiku 4.5 | Swift idioms, iOS patterns |
| `peer-sql-reviewer` | Haiku 4.5 | Schema, queries, indexing, migration safety |
| `peer-quality-engineer` | Sonnet 4.6 | Test coverage, edge cases, missing assertions |
| `peer-readability-engineer` | Haiku 4.5 | Naming, structure, function size, comment quality |

</details>

<details>
<summary><strong>Stage 2 — Cross-functional gap reviewers (11)</strong></summary>

| Persona | Model | Lens |
|---|---|---|
| `team-security-reviewer` | Sonnet 4.6 | OWASP, auth flaws, secret leakage, crypto misuse |
| `team-frontend-reviewer` | Sonnet 4.6 | UI/UX bugs, state, rendering, framework patterns |
| `team-backend-reviewer` | Sonnet 4.6 | Server logic, request handling, error paths, idempotency |
| `team-network-reviewer` | Sonnet 4.6 | API contracts, retries, timeouts, idempotency over the wire |
| `team-database-reviewer` | Sonnet 4.6 | Schema, query plans, migrations, indexing |
| `team-devops-infra-reviewer` | Sonnet 4.6 | CI/CD, IaC, secrets management, deployment safety |
| `team-performance-reviewer` | Sonnet 4.6 | Cross-system bottlenecks, capacity, hot paths |
| `team-accessibility-reviewer` | Sonnet 4.6 | WCAG, semantic HTML, keyboard support |
| `team-observability-reviewer` | Sonnet 4.6 | Logging, metrics, tracing, alertability |
| `team-privacy-compliance-reviewer` | Sonnet 4.6 | PII handling, GDPR-style rights, retention |
| `team-data-ml-reviewer` | Sonnet 4.6 | Data quality, training correctness, reproducibility |

</details>

<details>
<summary><strong>Stage 3 — Leadership (2)</strong></summary>

| Persona | Model | Output style |
|---|---|---|
| `lead-senior-architect` | Opus 4.7 | ADR-style verdict (Context / Decision / Consequences / Recommendation) |
| `lead-project-manager` | Opus 4.7 | Aim alignment grade + scope discipline memo |

</details>

Each persona prompt is 250–400 lines of authored content covering identity, lens, in-scope concerns, out-of-scope delegation, output contract, reasoning approach, anti-patterns, and few-shot examples grounded in the test fixtures. See [`agents/`](agents/) for all 25 agent definitions (23 personas + Profiler + Aggregator).

---

## What the output looks like

Live terminal stream while running:

```
🔥 Crucible — Project Review Pipeline

[Stage 0] Profiler reading project...
  ✓ Detected: Next.js + Prisma web app (TypeScript, SQL)
  ✓ Aims: .review/aims.md (created)
  ✓ Scope: auth module rewrite — 8 files

  Casting committee:
    Stage 1 → peer-typescript-reviewer, peer-sql-reviewer, peer-quality-engineer
    Stage 2 → team-security-reviewer, team-backend-reviewer, team-database-reviewer
    Stage 3 → lead-senior-architect, lead-project-manager

[Stage 1] Peer code review (3 reviewers, parallel)...
  ✓ peer-typescript-reviewer — 7/10 concerns (4 findings)
  ✓ peer-sql-reviewer — 9/10 approve  (1 finding)
  ✓ peer-quality-engineer — 5/10 concerns (6 findings — low test coverage)

[Stage 2] Cross-functional (3 reviewers, parallel)...
  ✓ team-security-reviewer — 6/10 concerns (2 high)
  ✓ team-backend-reviewer — 7/10 concerns (3 medium)
  ✓ team-database-reviewer — 8/10 approve  (1 finding)

[Stage 3] Leadership (2 reviewers, parallel)...
  ✓ lead-senior-architect — ADR: approved with conditions
  ✓ lead-project-manager — aim alignment: 8/10

[Stage 4] Aggregator synthesizing...

──────────────────────────────────────────────────
📊 FINAL VERDICT: 7.1/10 — Conditional Approval
──────────────────────────────────────────────────

What's good:
  • SQL migrations are clean and reversible
  • Backend API contracts well-defined
  • Database schema strong

What's concerning:
  • Session tokens stored where client JS can read them (security)
  • Auth tests cover only happy paths (quality)
  • No rate limiting on /login (security)

Key notes:
  🛡️  team-security-reviewer: "Move session storage to httpOnly cookies before merge."
  🏗️  lead-senior-architect: "Auth boundary is right; storage decision is a 1-day fix."
  📋 lead-project-manager: "Phase aim achieved; one security gap blocks 'production-ready'."

📁 Full report: .review/reports/2026-05-10-1430-auth-refactor.md
```

The saved markdown report is fully detailed — every persona's full findings, scoring, reasoning, and stage-handoff notes are preserved, plus the aims snapshot, casting roster, and run metadata. See [`examples/nextjs-auth-refactor.md`](examples/nextjs-auth-refactor.md) for a complete demo.

Wall-clock time and API cost are not printed by Crucible — Claude Code reports both natively at session end and on demand via `/status`, with measurements more accurate than anything a plugin skill can compute from inside the run.

---

## Sample reports

- [`examples/nextjs-auth-refactor.md`](examples/nextjs-auth-refactor.md) — Next.js + Prisma auth module review *(real Crucible output, 2/10 blocked, $5.22 / 25 min run)*
- [`examples/go-api-service.md`](examples/go-api-service.md) — Go HTTP service review *(real Crucible output, 2.5/10 blocked, $5.60 / 23 min run)*
- [`examples/ml-training-loop.md`](examples/ml-training-loop.md) — PyTorch training pipeline review *(real Crucible output, 3.5/10 blocked, $4.78 / 20 min run)*

All three are markdown reports produced by `/crucible:run` against the corresponding test fixtures under [`tests/fixtures/`](tests/fixtures/), where the fixtures contain deliberate gaps for the personas to find. Run Crucible on any fixture and you'll get a report of comparable structure and severity (with run-to-run variance in exact wording and ~30% in cost).

---

## Why subagents show "no tools used" — the orchestration pattern

When you watch a Crucible run in the Claude Code UI, the orchestrator (main thread) does all visible file I/O — reads, writes, grep — while each dispatched subagent (the personas) shows "no tools used." This is correct by design, not a bug.

The orchestrator pastes every persona's input into the dispatch prompt as inline content: the aims snapshot, the persona's scope file contents, prior-stage findings, and the casting reasoning. Each persona's output is a single JSON object validated against `schemas/persona-finding.schema.json`. The orchestrator parses the JSON return value and writes it to `.review/runs/<id>/stage_X/<persona>.json` itself.

Three reasons this is the right pattern:

1. **Schema validation.** The orchestrator can `JSON.parse` + schema-validate each persona's output and retry on malformed responses. If subagents wrote files directly, you'd lose the validation gate.
2. **Cache efficiency.** The inline file payload is cached once and reused across every persona that shares scope (typically 5–7× cache-reuse ratio on a 10-persona run). If each persona called `Read` themselves, you'd lose the orchestrator-level cache and pay full input cost per persona — total cost would roughly double.
3. **Reproducibility.** A persona's output is a pure function of its prompt. No side-effects, no race conditions on `.review/`, no "which persona wrote first" ambiguity.

The subagents are not waiting on permissions — they inherit the orchestrator's full tool set. They simply don't need tools for the inline-context + JSON-output pattern. This is why the 25–35 minute wall time is dominated by Sonnet/Opus reasoning, not tool-call round-trips.

---

## Costs

Crucible uses **per-persona model tiering** to keep cost reasonable while preserving quality where reasoning matters:

| Stage | Model | Why |
|---|---|---|
| Profiler | Sonnet 4.6 | Strong tool use + interview ergonomics |
| Stage 1 (mixed) | Haiku 4.5 / Sonnet 4.6 | Pattern-rich language reviewers on Haiku; reasoning-heavy ones (Rust, Java/Kotlin, C/C++, TypeScript, Quality) on Sonnet |
| Stage 2 | Sonnet 4.6 | Gap-finding requires synthesis across files + prior findings |
| Stage 3 | Opus 4.7 | Strategic judgment, ADR-quality reasoning, aim alignment |
| Aggregator | Opus 4.7 | Holistic synthesis of 7–11 reports + aims |

**Measured run cost (v0.1.0, across all three bundled fixtures — 5–7 files each):**

> **What these numbers mean.** If you're on a **Claude Pro or Max subscription**, you do not pay per run — your subscription covers usage and you just consume more or less of your quota. The dollar column shows the **API-equivalent token cost** (what an equivalent pay-as-you-go API call would cost) as a reference for relative effort. The percentage column shows the share of a **Claude Max** 5-hour quota window a single run consumes; Pro subscribers see the same workload consume a proportionally larger share of their smaller budget. Wall time **10–35 min** · larger projects scale up proportionally to file count and cast size.

| Session model | API-equivalent cost per run | Claude Max quota share | Notes |
|---|---|---|---|
| **Haiku 4.5** | **~$3–4** (1 measured run at $3.26 on pytorch-trainer) | **~6–7%** | Cheapest. Report template adherence is looser — section names may improvise, per-persona detail may collapse to one-liners, the Run Metadata block may be skipped. Pipeline integrity is good (real subagent dispatches, real findings — see "Architectural finding" below). Heads-up: a single Crucible run consumes **~75% of Haiku's 200K context window**, so start a fresh Claude Code session before running Crucible if you've been using it heavily already. |
| **Sonnet 4.6** (recommended) | **~$4.50–7** (6 measured runs, median $5.22, range $4.78–$6.75) | **~10–15%** | Balanced. Detailed per-persona findings sections with full file:line citations. Template adherence is usually canonical but not always — one of the six measured runs improvised (table-style stage blocks, condensed headings, the `## Stage 0 — Profiler` section skipped). The deterministic Python renderer in v0.1.1 fixes this. The default recommendation regardless. |
| **Opus 4.7** | **~$8–10** (1 measured run at $8.95 on the cheapest fixture; ~1.7× Sonnet) | **~15%+** | Most expensive. Doesn't add much value at the orchestrator layer — the deep reasoning the pipeline needs already happens in dispatched Opus subagents (Stage 3 leadership + Aggregator), regardless of your main-thread model. Pay Opus rates only if you have a specific reason. |

### Architectural finding: orchestrator model dominates cost

Crucible's orchestration runs in your Claude Code main thread (`skills/run/SKILL.md` is read and executed by your current session). The bookkeeping work — reading scope files, parsing 7–11 persona JSON returns, validating against schemas, rendering the markdown report — accumulates cache reads at your session's model rate. This makes the orchestrator's model the dominant cost variable, not the per-stage subagent tiers.

**`/crucible:run` opens with a cost preview and a y/n confirmation** so you can choose to `/model claude-haiku-4-5-20251001` or `/model claude-sonnet-4-6` before proceeding. Crucible cannot detect or change your session model from inside a Skill, so the preview is the closest thing to cost control the plugin offers. The preview text itself is in `skills/run/SKILL.md` and lists the same per-model ranges as the table above.

**v0.1.0 architectural exploration** (worth documenting because it nearly shipped and would have silently broken):

We attempted to move orchestration into a dedicated `coordinator` subagent so the cache-heavy bookkeeping would run at a fixed model tier regardless of the user's session. Two failure modes blocked it:

1. **Haiku-as-coordinator silently impersonated personas.** First verification run on `pytorch-trainer` cost $1.07 total instead of the target $4–6. Looks like a win until the cost split is examined: Sonnet was $0 despite seven personas claiming `model_used: claude-sonnet-4-6` in their saved JSONs, Opus was $0.54 (just main-thread overhead), and 3.3M Haiku cache reads = Haiku reading every persona system prompt and generating outputs that matched the persona's JSON shape from inside its own context — without ever calling the Task tool. The findings were plausible but the plugin was lying about who produced what.

2. **Sonnet-as-coordinator broke user interactivity.** Escalating the coordinator to Sonnet fixed the impersonation discipline (Sonnet did real dispatches, real Sonnet/Opus cost showed up in `/status`), but introduced a different failure: the Profiler is a subagent that must interactively prompt the user (`"I found existing aims. Are these still accurate?"`, `"Proceed with this committee?"`). When the Profiler is dispatched as a sub-subagent (`coordinator → profiler`), nested subagent dispatch loses the user-interaction channel. The Profiler ran, did its work mechanically, and never prompted the user. Cost came in at the $4–6 target but the interactive UX broke.

**v0.1.0 ships main-thread orchestration with the cost-preview prompt** instead. The cost-vs-orchestrator-model coupling stays, but the user is warned and can opt to switch model before the run.

**Worth noting: Haiku as the main-thread orchestrator works** (verification on `pytorch-trainer`, 2026-05-12: $3.26 total cost, real Sonnet ($1.04) and Opus ($1.42) subagent dispatches measured, no impersonation). The impersonation failure mode was specific to Haiku running *inside* a dispatched coordinator subagent, where the SKILL.md `Task(...)` blocks read as workflow descriptions rather than tool invocations. On the main thread Haiku correctly invokes the Task tool. The trade-off is template adherence: Haiku's rendered markdown report improvises section names, abbreviates per-persona findings to one-liners, and may skip the Run Metadata block. Use Haiku for cost-sensitive runs where the executive summary is the primary output; use Sonnet for the best balance of cost and report polish, with the caveat that Sonnet has been measured occasionally improvising the report template too (see CHANGELOG "Known limitations" — a deterministic Python renderer is planned for v0.1.1 to eliminate this).

If a future architecture can solve both subagent interactivity and tool-use discipline simultaneously, the coordinator-subagent pattern is still the right answer — it's recorded in the v0.2.0 roadmap.

**Per-stage cost contribution** (typical run):
- **Orchestrator** (your session model): the dominant variable — Haiku ~$0.80, Sonnet ~$2.50, Opus ~$5
- Profiler (Sonnet 4.6): ~$0.40 — project read + interview + casting
- Stage 1 Haiku peers: ~$0.10
- Stage 1+2 Sonnet reviewers: ~$1–$1.50
- Stage 3 Opus leadership + Aggregator: ~$1.50–$2 — strategic synthesis (the unavoidable Opus floor)

The subagent shares are roughly constant across orchestrator models; the orchestrator share is what scales with your session's tier.

### Variance sources (unchanged from v0.1.0-beta)

- **Within-fixture verbosity variance is the dominant noise source.** One of the three Next.js beta runs wrote a ~30% chattier report — same cast, same scope, ~$1.50 over the others.
- **Cross-project variance is small for similar-sized fixtures.** ML pipelines cast 8 personas (Profiler skips Frontend, Database, Network, Privacy); web/API projects cast 10. Composition shifts substantially per project type.
- **Larger projects will cost more.** Every new file adds to the cache footprint dispatched into each Stage 1/2 persona's prompt. Projects with more files, more languages, or stricter aims will pull a wider cast and bigger payloads. Larger-project cost data (codebases beyond 5–7 files) lands in v0.1.1.

### Plan compatibility

Crucible runs on both **Claude Pro** and **Claude Max**. Both plans support every model the pipeline uses (Haiku 4.5, Sonnet 4.6, Opus 4.7) — there's no per-model gating to worry about. The difference is total budget per 5-hour quota window:

- **Claude Max**: comfortable headroom — roughly 5–10 full-project Sonnet-main reviews per window before quota pressure shows. Plenty of margin for iterative reviewing.
- **Claude Pro**: same pipeline, same models, but the smaller per-window budget runs out faster. A single full-project Sonnet-main review can consume a large fraction of a Pro window. If you hit the limit, you'll be throttled until the window rolls; no Opus-specific cap kicks in separately.

**Practical tip for Pro users**: scope reviews tighter to fit more into each window — a phase review casts ~5 personas vs. ~8–10 for a full-project review, with roughly proportional quota reduction. Or run during a fresh window when quota headroom is maximum.

### Future cost work (v0.2.0+)

The fundamental cost coupling — orchestrator model dominates total cost — is structural to how Skills run today. Two paths could decouple it:

1. **Coordinator subagent with both tool-use discipline AND interactive-passthrough** — see the architectural finding above. The v0.1.0 attempt failed on interactive-passthrough (nested subagents lose user prompts); if Claude Code adds first-class user-prompt forwarding for nested subagents, this becomes the right architecture.
2. **Profiler runs in main thread, post-Profiler runs in subagent** — split the pipeline at the Profiler boundary. Main thread handles the interactive interview; coordinator subagent handles the bookkeeping-heavy Stage 1–4 dispatch + render. Would require splitting the SKILL into two halves. Worth measuring.

Until one of those is verified end-to-end, the cost-preview prompt is the v0.1.0 mitigation: explicit, honest, one-prompt friction.

---

## Configuration

V1 ships with zero required configuration. Optional per-project overrides via `.review/config.yaml`:

```yaml
# .review/config.yaml — all keys optional
casting_overrides:
  always_include:
    - team-security-reviewer
  never_include:
    - team-accessibility-reviewer
model_overrides:
  stage_1: claude-sonnet-4-6   # promote all Stage 1 peers to Sonnet
  stage_3: claude-opus-4-7
report_dir: .review/reports
```

Override behavior is deferred to v0.2.0; v0.1.0 reads the file but does not yet act on it.

---

## Roadmap

### v0.1.0
- Full 23-persona library
- `/crucible:run`, `/crucible:aims`, `/crucible:history`
- Three demo example reports
- Schema + structural validation tests
- Self-hosted marketplace install (`/plugin marketplace add hazarsozer/crucible-cc` + `/plugin install crucible@crucible`)

### v0.1.1 (current)
- Deterministic Python renderer for the final markdown report at `scripts/render_report.py` — replaces v0.1.0's LLM-driven template substitution that drifted across runs (heading text, metadata block style, persona-block structure all varied). Output is now byte-stable; verified by a checked-in golden test against the pytorch-trainer fixture.
- Vendored Jinja2 (BSD-3) + MarkupSafe at `scripts/_vendor/` — no `pip install` or `uv add` required on the user's project; Python 3.8+ is the only runtime dependency.
- Per-persona "WRITE THIS, NOT THAT" examples added to `peer-python-reviewer`, `team-data-ml-reviewer`, and `lead-project-manager` to drop the ~25% lane-discipline slip rate measured on a v0.1.0 verification run.
- Aggregator-summary drift recovered at render time: when `stage_reports.stage_<N>` is stripped to `{persona, score, verdict}` summaries, the renderer re-hydrates from the sibling `stage_<N>/*.json` files written by per-persona dispatches.
- Cost preview externalized to `templates/cost-preview.txt`. The `/crucible:run` cost preview is now `cat`-ed from a file instead of inlined in SKILL.md and printed by the LLM — eliminates the floor-lowering drift observed during the v0.1.1 wet test (Sonnet was rendering `$4.50-7` as `$0.50-7`).

### v0.2.0 (next)
- Persona prompt polish (each persona's quality-review backlog)
- `.review/config.yaml` actively honored
- GitHub PR comment integration via `gh` CLI

### v0.3.0 and beyond
- Adaptive persona generation (Profiler proposes a custom persona when library is insufficient)
- Cost cap / budget enforcement (`--max-cost 0.50`)
- Monorepo / multi-package awareness
- "Devil's advocate" mode for stress-testing consensus
- IDE extension (Cursor, VS Code)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidance on adding a new persona, the persona authoring pattern, and the test harness.

Bug reports, feedback, and persona ideas are very welcome. Open an issue with: plugin version, Claude Code version, the project type Profiler detected, and (if applicable) the casting roster from `.review/runs/<id>/roster.json`.

---

## License

MIT. See [LICENSE](LICENSE).

---

## Author

Built by [Hazar Sozer](https://github.com/hazarsozer) — 4th year AI & Data Engineering student at Istanbul Technical University. Designed and authored across two sessions using Claude Code with the Superpowers brainstorming + writing-plans + subagent-driven-development skills.

If Crucible is useful to you, a star on GitHub helps it find more users. Feedback on LinkedIn or via GitHub issues is the fastest way to influence the v0.2.0 roadmap.
