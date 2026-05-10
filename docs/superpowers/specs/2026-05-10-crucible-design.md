# Crucible — Design Specification

**Status:** Approved (brainstorming output)
**Date:** 2026-05-10
**Name:** Crucible — *Not Another Code Reviewer*
**Author:** Hasan Sozer (`hsozer00@gmail.com`)
**Target distribution:** Public GitHub repo + Claude Code plugin marketplace

---

## 1. Overview

Crucible is a Claude Code plugin that runs a user's code/project through a simulated corporate review pipeline. A Profiler agent reads the project, interviews the user, and casts a 4–8 persona review committee from a 23-persona library. The committee evaluates the work in three sequential stages with isolated parallel reviewers per stage, then a final Aggregator agent synthesizes a holistic verdict and score.

**Tagline:** *Not Another Code Reviewer.*

**One-line pitch:**
> *Crucible — a Claude Code plugin that puts your code through a corporate review pipeline. A Profiler casts the right committee for your project; peers review at the code level, departments hunt for gaps, and leadership grades alignment to your stated aims.*

**Why it doesn't already exist:** Existing review plugins (Anthropic's `code-review`, `pr-review-toolkit`, ECC, wshobson/agents) fan out reviewer agents in parallel with **functional roles** (security, types, perf). None implement: (a) a casting agent that adapts the committee to project type, (b) sequential stage handoff where Stage N+1 reads Stage N's structured findings, or (c) grading against the project's stated aims. The closest existing implementation, `claude-code-staff-engineer` (56 stars), role-plays a hierarchy but does not adapt the cast or grade aim alignment.

---

## 2. Goals & Non-goals

### Goals (v1)
- Public GitHub repo, MIT-licensed, installable as a Claude Code plugin.
- Single command (`/crucible`) end-to-end run: profile → cast → review → synthesize.
- Adaptive committee selection driven by project type detection + user interview.
- Three altitudes of review: code-level (Stage 1), gap-level (Stage 2), strategic (Stage 3).
- Holistic synthesis stage (Stage 4 Aggregator) producing a final score and verdict via Opus reasoning — no math equations.
- Live compact terminal stream during the run + fully detailed markdown report saved to disk.
- 23 personas shipped at v1 release.
- Ship-quality README, demo report examples, contribution guide for adding personas.

### Non-goals (v1)
- GitHub PR comment integration. (v2 candidate.)
- Web dashboard / UI. (v2.)
- Adaptive persona generation at runtime (e.g. spawning custom personas the library doesn't have). (v2.)
- Multi-repo / monorepo-aware reviews. (v2.)
- Cost-cap / budget enforcement. (v2.)
- Localized / multilingual reviews. (Out of scope.)

---

## 3. Architecture

### 3.1 Stage Diagram

```
                User: /crucible from project dir
                            │
                            ▼
 STAGE 0  ┌──────────────────────────────────────┐
   ░░░    │  PROFILER agent  (Sonnet 4.6)         │
          │  • Reads project files (tree, README, │
          │    CLAUDE.md, package manifests)      │
          │  • Interviews user about aims         │
          │  • Auto-creates .review/aims.md       │
          │  • Auto-updates .gitignore            │
          │  • Asks scope: full / phase / files   │
          │  • Casts the committee from library   │
          │  • Partitions diff per persona        │
          └──────────────────┬────────────────────┘
                             │ casting roster (JSON)
                             │ + project profile + aims
                             │ + diff partitions
                             ▼
 STAGE 1  ┌──────────────────────────────────────┐
   ███    │  PEER engineers — parallel, isolated │
          │  Haiku 4.5 / Sonnet 4.6 × 3–5         │
          │  per-persona model assignment by      │
          │  reasoning load (see §3.3)            │
          │  Code-level: language idioms, bugs,   │
          │  quality, readability                 │
          └──────────────────┬────────────────────┘
                             │ stage-1 findings (JSON array)
                             ▼
 STAGE 2  ┌──────────────────────────────────────┐
   ███    │  CROSS-FUNCTIONAL — parallel,         │
          │  isolated within stage                │
          │  Sonnet 4.6  ×  2–4 personas          │
          │  Gap-level: read stage-1 findings +   │
          │  diff, look for domain gaps           │
          └──────────────────┬────────────────────┘
                             │ stage-1 + stage-2 findings
                             ▼
 STAGE 3  ┌──────────────────────────────────────┐
   ███    │  LEADERSHIP — parallel                │
          │  Opus 4.7  ×  2 (Architect + PM)      │
          │  Strategic: ADR verdict, aim          │
          │  alignment, scope discipline          │
          └──────────────────┬────────────────────┘
                             │ all stage findings
                             │ + casting roster
                             │ + aims snapshot
                             ▼
 STAGE 4  ┌──────────────────────────────────────┐
   ███    │  AGGREGATOR agent  (Opus 4.7)         │
          │  • Synthesizes holistic score         │
          │  • Synthesizes overall verdict        │
          │  • Writes executive summary           │
          │  • Curates key persona quotes         │
          │  • Compiles full markdown report      │
          └──────────────────┬────────────────────┘
                             │
                             ▼
              Live terminal stream (compact)
              + .review/reports/<id>.md (detailed)
```

### 3.2 Stage Invariants
- **Within a stage**, personas run in parallel and **never see each other's findings**. Strict isolation per scope.
- **Across stages**, handoff is via structured JSON written by the orchestrator skill. Personas in Stage N read all completed reports from Stages 1..N-1.
- **File partitioning** is computed by the Profiler in the casting roster. Each persona only receives its assigned file set, plus prior-stage findings (text only, no source repetition).
- **No mechanical roll-up.** Per-persona scores and verdicts are raw signal in the final report. The single overall score and verdict are reasoned by the Stage 4 Aggregator.

### 3.3 Model Tiering Rationale

Model assignment is **per-persona, not per-stage uniform**. Reasoning load varies meaningfully within Stage 1 (e.g. Rust borrow-checker analysis is much harder than SQL pattern review), so each persona is tiered to the smallest model that handles its workload well.

**Bookend agents:**

| Agent | Model | Reasoning |
|---|---|---|
| Profiler (Stage 0) | Sonnet 4.6 | Strong tool use (file reading) + interview ergonomics + project-type inference. Opus overkill, Haiku too weak. |
| Aggregator (Stage 4) | Opus 4.7 | Holistic synthesis of 7–11 reports + aims; non-mathematical reasoning over conflicting signals. |

**Stage 1 peers — mixed Haiku/Sonnet by reasoning load:**

| Persona | Model | Reasoning load |
|---|---|---|
| Python Reviewer | Haiku 4.5 | Pattern-rich, mostly rule-based |
| TypeScript Reviewer | Sonnet 4.6 | Generics, conditional types, async correctness — needs real reasoning |
| Go Reviewer | Haiku 4.5 | Idiomatic + simple concurrency patterns |
| Rust Reviewer | Sonnet 4.6 | Ownership, lifetimes, unsafe — reasoning-heavy |
| Java/Kotlin Reviewer | Sonnet 4.6 | Concurrency, JVM internals, Spring/Android complexity |
| C/C++ Reviewer | Sonnet 4.6 | Memory safety, undefined behavior, template metaprogramming |
| Swift Reviewer | Haiku 4.5 | Swift idioms — mostly pattern-recognition |
| SQL Reviewer | Haiku 4.5 | Schema/query patterns, mostly rule-based |
| Quality Engineer | Sonnet 4.6 | Reasoning about *absence* (missing tests, uncovered edges) is genuinely hard |
| Readability Engineer | Haiku 4.5 | Naming + structure + function size — local pattern matching |

Stage 1 ratio: 5 Sonnet + 5 Haiku.

**Stages 2 & 3:**

| Stage | Model | Reasoning |
|---|---|---|
| Stage 2 cross-functional (all 11) | Sonnet 4.6 | Gap-finding requires synthesis across files + understanding of prior findings. |
| Stage 3 leadership (Architect + PM) | Opus 4.7 | Strategic judgment, ADR-quality reasoning, aim alignment grading. |

**Cost estimate per review** (rough, API rates, assuming a typical cast of 4 peers / 3 teams / 2 leaders):
- 1 Sonnet Profiler: ~$0.05
- ~2 Haiku peers: ~$0.02
- ~2 Sonnet peers: ~$0.10
- 3 Sonnet teams: ~$0.15
- 2 Opus leaders: ~$0.30
- 1 Opus aggregator: ~$0.20
- **Total: ~$0.82 per review** at API rates; comfortably within Claude Max usage budget.

---

## 4. Plugin File Structure

```
crucible/
├── .claude-plugin/
│   └── plugin.json                              # manifest
├── README.md                                    # public face: pitch, install, demo
├── LICENSE                                      # MIT
├── CONTRIBUTING.md                              # how to add personas
├── CHANGELOG.md
├── examples/
│   ├── nextjs-auth-refactor.md                  # demo report on a sample PR
│   ├── ml-training-loop.md                      # demo on a PyTorch change
│   └── go-api-service.md                        # demo on a Go service
├── skills/
│   ├── crucible/
│   │   └── SKILL.md                             # main entry: /crucible
│   ├── crucible-aims-edit/
│   │   └── SKILL.md                             # /crucible-aims (refresh aims)
│   └── crucible-history/
│       └── SKILL.md                             # /crucible-history (list past reports)
├── agents/
│   ├── profiler.md                              # Stage 0 — Sonnet 4.6
│   ├── aggregator.md                            # Stage 4 — Opus 4.7
│   ├── peers/                                   # Stage 1 — mixed Haiku 4.5 / Sonnet 4.6
│   │   ├── python-reviewer.md                   # Haiku 4.5
│   │   ├── typescript-reviewer.md               # Sonnet 4.6
│   │   ├── go-reviewer.md                       # Haiku 4.5
│   │   ├── rust-reviewer.md                     # Sonnet 4.6
│   │   ├── java-kotlin-reviewer.md              # Sonnet 4.6
│   │   ├── c-cpp-reviewer.md                    # Sonnet 4.6
│   │   ├── swift-reviewer.md                    # Haiku 4.5
│   │   ├── sql-reviewer.md                      # Haiku 4.5
│   │   ├── quality-engineer.md                  # Sonnet 4.6
│   │   └── readability-engineer.md              # Haiku 4.5
│   ├── teams/                                   # Stage 2 — all Sonnet 4.6
│   │   ├── security-reviewer.md
│   │   ├── frontend-reviewer.md
│   │   ├── backend-reviewer.md
│   │   ├── network-reviewer.md
│   │   ├── database-reviewer.md
│   │   ├── devops-infra-reviewer.md
│   │   ├── performance-reviewer.md
│   │   ├── accessibility-reviewer.md
│   │   ├── observability-reviewer.md
│   │   ├── privacy-compliance-reviewer.md
│   │   └── data-ml-reviewer.md
│   └── leadership/                              # Stage 3 — both Opus 4.7
│       ├── senior-architect.md
│       └── project-manager.md
├── templates/
│   ├── persona-protocol.md                      # shared contract referenced by every persona
│   ├── aims.md.tpl                              # Profiler scaffolds .review/aims.md
│   └── report.md.tpl                            # report skeleton aggregator fills
└── schemas/
    ├── casting-roster.schema.json
    ├── persona-finding.schema.json
    └── final-report.schema.json
```

**File count:** 42 files (1 manifest + 4 docs/meta including LICENSE + 3 examples + 3 skills + 25 agents + 3 templates + 3 schemas).

### 4.1 Persona file size and shared protocol

Persona prompts are the heart of the plugin and need real depth. A v1 persona file targets **~250–400 lines**, broken down approximately as:

| Section | Approx. lines |
|---|---|
| YAML frontmatter (name, description, stage, model, casting-trigger) | ~10 |
| Identity + lens (who you are, what you care about) | 30–50 |
| In-scope concerns (each with concrete guidance) | 80–150 |
| Out-of-scope (what to delegate to other personas — prevents overlap) | 10–20 |
| Input contract (what you receive: aims, scope files, prior-stage findings) | ~20 |
| Output contract (JSON schema with worked example) | ~40 |
| Reasoning approach (how to read code, weigh severity, write findings) | 30–50 |
| Constraints (line citations, max findings, JSON-only output) | ~15 |
| Anti-patterns (don't repeat other personas' work, don't hallucinate, etc.) | 15–25 |
| Few-shot example (one good finding, one bad finding to avoid) | 30–50 |

To keep prompts DRY, **`templates/persona-protocol.md`** holds the universal contract — JSON output schema details, severity rubric, file-citation format, length limits, anti-patterns shared across all personas. Each persona file references this protocol; persona-specific content (identity, lens, in-scope concerns, examples) stays in the persona file. This keeps total prompt content manageable (~6,400 lines of authored prompt across 25 personas + 1 protocol) while preserving per-persona depth.

---

## 5. Persona Library (23 personas, v1)

### 5.1 Stage 1 — Peers (10 personas, mixed Haiku 4.5 / Sonnet 4.6)

**Language reviewers** (file-extension-driven casting):
| Persona | Model | Casts when | Lens |
|---|---|---|---|
| Python Reviewer | Haiku 4.5 | `.py` files present | PEP 8, idioms, type hints, common pitfalls |
| TypeScript Reviewer | Sonnet 4.6 | `.ts`/`.tsx`/`.js`/`.jsx` | Type safety, async correctness, idioms |
| Go Reviewer | Haiku 4.5 | `.go` | Idiomatic Go, error handling, concurrency |
| Rust Reviewer | Sonnet 4.6 | `.rs` | Ownership, lifetimes, idiomatic patterns |
| Java/Kotlin Reviewer | Sonnet 4.6 | `.java`/`.kt`/`.kts` | JVM idioms, Spring/Android patterns |
| C/C++ Reviewer | Sonnet 4.6 | `.c`/`.cpp`/`.h`/`.hpp` | Memory safety, modern C++ idioms |
| Swift Reviewer | Haiku 4.5 | `.swift` | Swift idioms, iOS patterns |
| SQL Reviewer | Haiku 4.5 | `.sql` or migration files | Schema, query quality, indexing |

**Universal concerns** (always in scope):
| Persona | Model | Lens |
|---|---|---|
| Quality Engineer | Sonnet 4.6 | Test coverage, edge cases, missing assertions |
| Readability Engineer | Haiku 4.5 | Naming, structure, comment quality, function size |

### 5.2 Stage 2 — Cross-functional (11 personas, Sonnet 4.6)

| Persona | Lens | Casting trigger |
|---|---|---|
| Security Reviewer | Auth, input handling, secrets, injection, OWASP | Always (high-signal default) |
| Frontend Reviewer | UI/UX bugs, state, rendering, framework patterns | Frontend code detected |
| Backend Reviewer | Server logic, request handling, error paths | Backend code detected |
| Network Reviewer | API contracts, retries, timeouts, idempotency | Network/HTTP code detected |
| Database Reviewer | Schema, queries, migrations, indexing, transactions | Database code/migrations detected |
| DevOps/Infra Reviewer | Deployment, CI/CD, secrets management, IaC | CI/CD or infra files detected |
| Performance Reviewer | Cross-system bottlenecks, capacity, hot paths | Always when scope > 5 files |
| Accessibility Reviewer | a11y, WCAG, semantic HTML, ARIA | Frontend with HTML/JSX |
| Observability Reviewer | Logging, metrics, tracing | Long-running services |
| Privacy/Compliance Reviewer | PII handling, data retention, GDPR-style concerns | Auth, user data, or healthcare detected |
| Data/ML Reviewer | Data quality, model training, evaluation, reproducibility | ML frameworks detected |

### 5.3 Stage 3 — Leadership (2 personas, Opus 4.7, always cast)

| Persona | Lens | Output style |
|---|---|---|
| Senior Systems Architect | Structural coherence, boundaries, technical debt, improvement paths | ADR-style verdict (Context / Decision / Consequences) |
| Project / Product Manager | Aim alignment, scope discipline (in/out), prioritization | Aim alignment grade + scope memo |

---

## 6. Profiler Workflow (Stage 0 in detail)

### 6.1 Linear flow
1. **Read project signals** (in parallel): file tree, `README.md`, `CLAUDE.md`/`AGENTS.md`, language manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, etc.), recent commit messages (`git log --oneline -20` if git).
2. **Detect project type** — one of: `web-app`, `api`, `ml-pipeline`, `cli`, `library`, `mobile`, `data-pipeline`, `mixed`. Record evidence.
3. **Check for existing aims** at `.review/aims.md`:
   - **Exists** → display contents to user, ask "Still accurate?" → if yes, proceed; if no, refresh interactively.
   - **Missing** → run interview (next step).
4. **Run interview** (~3–5 questions, adaptive):
   - "I see this looks like a {detected_type}. Is that right?"
   - "What's the overarching goal of this project?"
   - "What does success look like — what would make you say it's working?"
   - "What's explicitly out of scope?"
   - (Conditional) "Any compliance / regulatory constraints I should know about?"
5. **Write `.review/aims.md`** from the template (see §7).
6. **Update `.gitignore`** if `.git/` exists and `.review/` is not already ignored. (Idempotent.)
7. **Ask review scope**:
   - (a) Full project — review all source files
   - (b) A phase / feature — user describes; Profiler scopes to relevant files
   - (c) Specific files / directories — user lists paths
   - (d) Branch diff — review changes on current branch vs `main`
8. **Cast the committee** from the library based on detected project type, languages, and review scope. Partition files per persona.
9. **Display casting roster** to user: "Here's who'll be reviewing — {names}. Reasoning: {one-paragraph}. Proceed?"
10. **Write casting roster JSON** for orchestrator and exit.

### 6.2 Profiler outputs
- `.review/aims.md` (markdown, user-readable, durable)
- Casting roster JSON (transient; passed to orchestrator)

---

## 7. `.review/aims.md` Template

```markdown
# Project Aims
_Generated by Crucible on {date}. Edit anytime; re-run `/crucible` to refresh._

## What this project is
{one-paragraph description Profiler infers and user confirms}

## Goal
{user's stated overarching goal}

## Success criteria
- {criterion 1}
- {criterion 2}
- {criterion 3}

## Non-goals / out of scope
- {explicit non-goal 1}
- {explicit non-goal 2}

## Tech stack (detected)
- **Languages:** {list}
- **Frameworks:** {list}
- **Datastores:** {list}
- **Deployment:** {if known}

## Project type
{web-app | api | ml-pipeline | cli | library | mobile | data-pipeline | mixed}

## Constraints
- {compliance, performance, team-size, etc., if user mentioned any}

---
_Last refreshed: {timestamp}_
```

---

## 8. Cross-stage Data Schemas

### 8.1 Casting Roster (`schemas/casting-roster.schema.json`)
```json
{
  "review_id": "2026-05-10-1430-auth-refactor",
  "started_at": "2026-05-10T14:30:00Z",
  "project_profile": {
    "type": "web-app",
    "languages": ["typescript", "sql"],
    "frameworks": ["nextjs", "prisma"],
    "datastores": ["postgres"]
  },
  "review_scope": {
    "kind": "phase",
    "description": "auth module rewrite",
    "files": ["app/auth/**", "prisma/migrations/2026*.sql"],
    "diff_source": "branch:auth-rewrite vs main"
  },
  "aims_snapshot_path": ".review/aims.md",
  "casting": {
    "stage_1": [
      { "persona": "typescript-reviewer", "files": ["app/auth/*.ts", "app/auth/*.tsx"] },
      { "persona": "sql-reviewer", "files": ["prisma/migrations/2026*.sql"] },
      { "persona": "quality-engineer", "files": ["app/auth/**", "tests/auth/**"] }
    ],
    "stage_2": [
      { "persona": "security-reviewer", "files": ["app/auth/**"] },
      { "persona": "backend-reviewer", "files": ["app/auth/**", "app/api/**"] },
      { "persona": "database-reviewer", "files": ["prisma/**"] }
    ],
    "stage_3": [
      { "persona": "senior-architect", "files": "all" },
      { "persona": "project-manager", "files": "all" }
    ]
  },
  "casting_reasoning": "TypeScript-first project with Prisma SQL migrations; security-sensitive (auth)..."
}
```

### 8.2 Persona Finding (`schemas/persona-finding.schema.json`)
```json
{
  "persona": "security-reviewer",
  "stage": 2,
  "model_used": "claude-sonnet-4-6",
  "started_at": "2026-05-10T14:33:12Z",
  "completed_at": "2026-05-10T14:34:05Z",
  "scope_assessed": ["app/auth/login.ts", "app/auth/session.ts"],
  "verdict": "concerns",
  "score": 6,
  "summary_quote": "Move session storage to httpOnly cookies before merge — current localStorage approach exposes tokens to XSS.",
  "findings": [
    {
      "severity": "high",
      "category": "security",
      "title": "Session token stored in localStorage",
      "location": "app/auth/session.ts:42",
      "explanation": "...",
      "suggestion": "..."
    }
  ],
  "stage_handoff_notes": "Architect should weigh in on session storage strategy; PM should consider rollout impact."
}
```

### 8.3 Final Report (`schemas/final-report.schema.json`)
Output of the Aggregator. Used by both the terminal stream and the saved markdown report.

```json
{
  "review_id": "2026-05-10-1430-auth-refactor",
  "completed_at": "2026-05-10T14:38:22Z",
  "final_score": 7.1,
  "final_verdict": "conditional_approval",
  "verdict_reasoning": "Strong technical execution; one high-severity security gap blocks 'production-ready' status...",
  "executive_summary": "...",
  "what_is_good": ["...", "..."],
  "what_is_concerning": ["...", "..."],
  "key_quotes": [
    { "persona": "security-reviewer", "quote": "..." },
    { "persona": "senior-architect", "quote": "..." }
  ],
  "stage_reports": {
    "stage_1": [/* full PersonaFinding objects */],
    "stage_2": [/* ... */],
    "stage_3": [/* ... */]
  },
  "aims_snapshot": "...",
  "casting_roster": {/* see 8.1 */},
  "metadata": {
    "plugin_version": "0.1.0",
    "wall_clock_seconds": 312,
    "models_used": ["sonnet-4-6", "haiku-4-5", "opus-4-7"],
    "estimated_cost_usd": 0.74
  }
}
```

---

## 9. Aggregator Behavior (Stage 4)

The Aggregator is an Opus 4.7 subagent that produces the final report by **reasoning, not arithmetic**.

### 9.1 Inputs
- All Stage 1, 2, 3 persona findings (full JSON)
- Casting roster JSON
- `.review/aims.md` snapshot
- Run metadata (timing, models used)

### 9.2 Reasoning instructions (paraphrased; full prompt lives in `agents/aggregator.md`)
- Read all findings; weight by severity, evidence quality, and stage altitude — but use judgment, not formulas.
- Strategic findings (Stage 3) generally outweigh micro findings (Stage 1) when computing the final number, but a Stage 1 finding flagged as `critical` is decisive.
- Per-persona scores and verdicts are raw signal — synthesize the holistic number and verdict; do not average.
- Curate 3–5 "what's good" highlights and 3–5 "what's concerning" highlights drawn from across stages.
- Pick 4–6 `summary_quote` strings to feature as "key notes" — prefer the most actionable + most surprising findings.
- Write a 2–3 paragraph executive summary connecting the dots.

### 9.3 Outputs
- Final report JSON (per §8.3)
- Compact terminal stream rendering
- Detailed markdown report saved to `.review/reports/{review_id}.md`

---

## 10. Output Formats

### 10.1 Live terminal stream (compact)

Streams as each stage completes. Persona-level lines appear as their subagents finish — parallel, so order may interleave.

```
🔥 Crucible — Project Review Pipeline

[Stage 0] Profiler reading project...
  ✓ Detected: Next.js + Prisma web app (TypeScript, SQL)
  ✓ Aims: .review/aims.md (created)
  ✓ Scope: auth module rewrite — 8 files

  Casting committee:
    Stage 1 → typescript-reviewer, sql-reviewer, quality-engineer
    Stage 2 → security-reviewer, backend-reviewer, database-reviewer
    Stage 3 → senior-architect, project-manager

[Stage 1] Peer code review (3 reviewers, parallel)...
  ✓ typescript-reviewer ........ 7/10 concerns (4 findings)
  ✓ sql-reviewer ............... 9/10 approve  (1 finding)
  ✓ quality-engineer ........... 5/10 concerns (6 findings — low test coverage)

[Stage 2] Cross-functional (3 reviewers, parallel)...
  ✓ security-reviewer .......... 6/10 concerns (2 high)
  ✓ backend-reviewer ........... 7/10 concerns (3 medium)
  ✓ database-reviewer .......... 8/10 approve  (1 finding)

[Stage 3] Leadership (2 reviewers, parallel)...
  ✓ senior-architect ........... ADR: approved with conditions
  ✓ project-manager ............ aim alignment: 8/10

[Stage 4] Aggregator synthesizing...

──────────────────────────────────────────────────
📊 FINAL VERDICT: 7.1/10 — Conditional Approval
──────────────────────────────────────────────────

What's good:
  • SQL migrations are clean and reversible
  • Backend API contracts well-defined
  • Database schema strong

What's concerning:
  • Session tokens in localStorage (security)
  • Auth tests cover only happy paths (quality)
  • No rate limiting on /login (security)

Key notes:
  🛡️  security-reviewer: "Move session storage to httpOnly cookies before merge."
  🏗️  senior-architect: "Auth boundary is right; storage decision is a 1-day fix."
  📊 project-manager: "Phase aim achieved; one security gap blocks 'production-ready'."

📁 Full report: .review/reports/2026-05-10-1430-auth-refactor.md
   Wall-clock: 5m 12s · Estimated cost: $0.74
```

### 10.2 Saved markdown report (fully detailed)

The report contains:

1. **Header** — review_id, date, project type, scope, commit SHA (if git)
2. **Final Verdict** — score, verdict, aggregator's reasoning
3. **Executive Summary** — 2–3 paragraphs
4. **What's Good** — bullet list (curated)
5. **What's Concerning** — bullet list (curated)
6. **Key Notes** — 4–6 featured quotes with persona attribution
7. **Stage 0 — Profiler** — full project profile, scope decision, casting reasoning
8. **Stage 1 — Peer Review** — every persona's full report (verdict, score, all findings, handoff notes)
9. **Stage 2 — Cross-functional** — same depth
10. **Stage 3 — Leadership** — Architect ADR + PM aim-alignment memo, full text
11. **Aims Snapshot** — verbatim copy of `.review/aims.md` at review time
12. **Run Metadata** — plugin version, wall-clock, models, cost estimate

The report is the durable artifact — every persona's reasoning is preserved, not just summary quotes. Suitable for pasting into a PR, archiving, or sharing as a portfolio piece.

---

## 11. Plugin Commands

| Command | Skill | Purpose |
|---|---|---|
| `/crucible` | `skills/crucible` | Run the full pipeline. Profiler decides whether to interview or reuse aims. |
| `/crucible-aims` | `skills/crucible-aims-edit` | Force-refresh `.review/aims.md` (re-runs Profiler interview without running review). |
| `/crucible-history` | `skills/crucible-history` | List past reviews from `.review/reports/`, optionally show summary of one. |

---

## 12. Edge Cases & Failure Modes

| Scenario | Behavior |
|---|---|
| Subagent fails mid-stage (timeout, model error) | Orchestrator marks that persona as `skipped`, logs error, proceeds. Aggregator notes the gap and reduces confidence accordingly. |
| Empty diff (user wants review of current state, no branch) | Profiler asks user: "Review current files as-is?" — yes proceeds with full file content as `diff`. |
| Non-git project | Skip `.gitignore` step. `.review/` still created. |
| Git but `.gitignore` already lists `.review/` | No-op. |
| `.review/aims.md` exists but malformed | Profiler shows raw content + offers to re-interview from scratch. |
| User cancels mid-stage (Ctrl-C) | Orchestrator catches, writes partial report to `.review/reports/<id>-PARTIAL.md` with completed stages. |
| No language matched in Stage 1 cast (rare; e.g. all-config-file PR) | Profiler casts only `quality-engineer` + `readability-engineer` for Stage 1, notes the limitation. |
| Detected project type is `mixed` and ambiguous | Profiler asks user to pick the dominant type explicitly. |
| Diff exceeds reasonable size (e.g. >5000 lines) | Profiler warns user, recommends scoping to a phase, but allows continuation if user insists. |
| User has no Opus access (Pro tier) | Plugin detects and falls back: Stage 3 + Aggregator on Sonnet 4.6. README documents the fallback. |
| Persona returns invalid JSON | Orchestrator retries once with stricter format prompt; if still invalid, marks as `failed_format` and proceeds. |

---

## 13. Configuration

V1 ships zero required configuration. Optional per-project overrides via `.review/config.yaml`:

```yaml
# .review/config.yaml — all keys optional
casting_overrides:
  always_include:
    - security-reviewer
  never_include:
    - accessibility-reviewer
model_overrides:
  stage_1: claude-sonnet-4-6   # promote peers to Sonnet
  stage_3: claude-opus-4-7
report_dir: .review/reports
```

If absent, defaults apply.

---

## 14. Testing Strategy

### 14.1 Persona unit tests
Each persona file has a companion fixture: a small synthetic diff with known issues. The persona is invoked against the fixture and the response is checked for: (a) valid JSON conforming to schema, (b) catching the expected high-severity findings, (c) verdict matches expectation.

### 14.2 End-to-end tests
Three fixture projects under `tests/fixtures/`:
- `nextjs-auth/` — TypeScript + Prisma, deliberate security gap
- `pytorch-trainer/` — Python ML, deliberate reproducibility gap
- `go-api/` — Go service, deliberate concurrency gap

Each fixture has an expected `.review/reports/EXPECTED.md` (golden file). E2E test runs `/crucible` programmatically and diffs against the golden, allowing for stochastic variance in narrative text but checking structural / schema invariants.

### 14.3 CI
GitHub Actions workflow:
- Schema validation on all JSON examples
- Markdown lint on all `.md` files
- Persona prompt linting (custom script: checks frontmatter, output protocol section presence, model spec)
- E2E test on the three fixtures (one per language family) — gated by Anthropic API key secret; allowed to fail on PRs from forks.

---

## 15. Distribution Plan

### 15.1 Release sequence
1. **Pre-public** — develop in private repo, dogfood on 3–5 personal projects, fix obvious bugs.
2. **Public release v0.1.0** — push to GitHub, tag, write LinkedIn post with demo report screenshot.
3. **Submit to official marketplace** — `claude.ai/settings/plugins/submit`.
4. **Submit to community lists** — `ComposioHQ/awesome-claude-plugins` PR, Reddit `r/ClaudeAI` and `r/ClaudeCode` post.
5. **Iterate** — collect issues, ship v0.2.0 within 2 weeks of v0.1.0 with the most-requested fix or persona.

### 15.2 LinkedIn / GitHub README pitch
Lead with what's unique (adaptive cast, three altitudes, aim alignment), include a screenshot of the terminal stream, link a sample report. Frame as "I built this as a portfolio project to learn the Claude Code plugin system."

### 15.3 License
MIT. Maximizes reuse and reduces friction for adoption.

---

## 16. V1 Scope vs. V2 Ideas

### V1 (this spec)
- 23 personas
- 3 commands (`/crucible`, `/crucible-aims`, `/crucible-history`)
- Local terminal stream + saved markdown report
- 3 fixture projects + E2E tests
- README, CONTRIBUTING, demo reports

### V2 candidates (not in this spec)
- GitHub PR comment integration (`gh pr comment` from aggregator)
- Web dashboard (read `.review/reports/` and render history)
- Adaptive persona generation (Profiler proposes a custom persona when library is insufficient)
- Cost cap / budget enforcement (`--max-cost 0.50`)
- Monorepo / multi-package awareness
- "Devil's advocate" mode (one persona per stage adopts a contrarian stance to stress-test consensus)
- IDE extension (Cursor, VS Code)

---

## 17. Open Assumptions

- **Plugin name:** Locked — `crucible`. Tagline: *Not Another Code Reviewer*.
- **License:** MIT recommended; not yet explicitly chosen.
- **Repo name:** `crucible` (matches plugin name).
- **Existing reviewer agents in Claude Code's bundled set** (e.g. `python-reviewer`, `go-reviewer`) are NOT depended on; Crucible ships its own agent definitions to be self-contained.
- **User's API tier** assumed to support Opus 4.7. Fallback path documented (§12) but not heavily tested in v1.
- **The `gh` CLI** is not required for v1 (no GitHub PR integration in v1 scope).

---

## 18. Open Questions for Implementation Plan

These are deferred to the implementation-plan stage, not blockers for the spec:
- Exact subagent dispatch syntax inside the orchestrator skill (does it Task-tool out, or use a different mechanism?)
- Whether to use streaming responses for the terminal display, or render after each stage completes (vs. true intra-persona streaming)
- Test fixture diff size — how big should each fixture be to exercise the personas without bloating CI?
- Concrete persona prompt template — one shared template with persona-specific overrides, or fully custom per persona?

---

_End of design spec._
