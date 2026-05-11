# Changelog

All notable changes to Crucible are documented here.

## [0.1.0] — 2026-05-10

First public release.

### Added

- **5-stage corporate review pipeline** orchestrated by `/crucible:run`:
  - Stage 0 — **Profiler** (Sonnet 4.6): reads project, interviews user, writes `.review/aims.md`, casts the committee.
  - Stage 1 — **Peer Code Review** (mixed Haiku 4.5 / Sonnet 4.6): 10 personas covering Python, TypeScript, Go, Rust, Java/Kotlin, C/C++, Swift, SQL, plus universal Quality and Readability engineers.
  - Stage 2 — **Cross-functional Gap Review** (Sonnet 4.6): 11 domain reviewers — Security, Frontend, Backend, Network, Database, DevOps/Infra, Performance, Accessibility, Observability, Privacy/Compliance, Data/ML.
  - Stage 3 — **Leadership** (Opus 4.7): Senior Systems Architect (ADR verdict) + Project Manager (aim alignment grade).
  - Stage 4 — **Aggregator** (Opus 4.7): Opus-reasoned holistic synthesis. No mathematical averaging.
- **Adaptive committee casting**: the Profiler picks personas based on project type, languages, frameworks, and review scope. Files are partitioned per persona using extension-based rules for Stage 1 and domain-based semantic rules for Stage 2.
- **Project-aim grading**: the `lead-project-manager` persona reads `.review/aims.md` (interactively written by the Profiler) and grades the change against the user's stated success criteria. Distinguishes Crucible from every other code-review plugin.
- **Sequential stage handoff**: Stage 2 reads Stage 1's structured findings; Stage 3 reads both; Aggregator reads everything plus the aims snapshot. No parallel-fan-out without context.
- **Per-persona model tiering** by reasoning load: Haiku 4.5 for pattern-rich language reviewers; Sonnet 4.6 for reasoning-heavy reviewers; Opus 4.7 for strategic synthesis.
- **Three commands**:
  - `/crucible:run` — full pipeline run
  - `/crucible:aims` — refresh `.review/aims.md` interactively (Profiler in interview-only mode)
  - `/crucible:history` — list and view past reviews
- **Three example reports** under `examples/` covering the included test fixtures (Next.js auth, PyTorch trainer, Go API).
- **Test infrastructure** under `tests/`: JSON-schema validation, persona-frontmatter linting, persona library completeness check, structural integrity tests, persona output validation (gated), and live E2E test (gated by `RUN_LIVE_E2E=1`).
- **Three test fixtures** under `tests/fixtures/` with deliberate gaps for the personas to find: nextjs-auth (security + quality + DB), pytorch-trainer (ML reproducibility + observability), go-api (concurrency + observability + production-readiness).
- **GitHub Actions CI** running lint + schema + structure tests on every push and PR.
- **MIT license**, full README with pipeline diagram, CONTRIBUTING guide, and persona authoring pattern.

### Fixed

- **Profiler now uses the cwd passed in its prompt as the project root**, not `git rev-parse --show-toplevel`. Affects nested projects (a fixture inside a parent repo, a monorepo package, an `examples/foo/` subdirectory): previously the Profiler read the parent repo's README and unfiltered git history, identifying the parent as the project under review instead of the cwd. Symptom: running `/crucible:run` from `tests/fixtures/nextjs-auth` made the Profiler ask "What's the overarching goal of this 23-persona code review pipeline plugin?" instead of recognizing the Next.js auth project.
- **Profiler `.gitignore` update step (step 7) now triggers only when `.git/` is a directory directly inside the project root**, not when the project is anywhere inside a git work tree. Previously, nested projects got a redundant fixture-level `.gitignore` while the parent's `.gitignore` already owned `.review/` policy.
- **Orchestrator now captures `project_root` via `pwd` in Setup and substitutes a literal absolute path into the Profiler dispatch prompt**, instead of relying on the model to interpret a `<absolute path of the user's project>` placeholder. The placeholder approach worked for the nextjs-auth fixture (the Profiler still found the cwd-relative `.review/aims.md` by accident), but failed on the go-api fixture: the Profiler identified the project as Crucible itself (auto-suggesting "Pre-release audit … publishing to the Claude Code plugin marketplace" as the review goal). Same nested-project bug family as the two above.

### Notes

- Configuration via `.review/config.yaml` is parsed but not yet honored; full override behavior ships in v0.2.0.
- Persona output schema (`schemas/persona-finding.schema.json`) `summary_quote` raised from `maxLength: 280` to `500`, and `Finding.title` from `120` to `160`. Aligned to observed real-run outputs (real Sonnet/Opus personas routinely produce 280–330 char headlines).
- `examples/nextjs-auth-refactor.md` and `examples/go-api-service.md` are real Crucible outputs from measured runs on the bundled fixtures (2/10 blocked and 2.5/10 blocked respectively). `examples/ml-training-loop.md` remains a hand-written preview until v0.1.1 measurements land.
- Runs on Claude Pro and Max plans. **Measured cost across `tests/fixtures/{nextjs-auth, go-api}` (5–7 files each, 10-persona cast): $5–7 API per run (median $5.40 across 4 runs), 23–35 min wall time, ~10–15% Max-plan quota burn.** Cross-project variance is small for similar-sized fixtures; within-fixture verbosity variance is the dominant noise source. Opus is available on both tiers; Pro caps Opus access, so heavy users should scope reviews tighter (a phase review casts ~5 personas vs. ~10 for a full-project review). Larger-project cost data (PyTorch fixture, codebases beyond 5–7 files) lands in v0.1.1. See the README §Costs section for the per-model split and caveats.
- Quality-review polish backlog (per-persona nits surfaced during authoring) is tracked for v0.2.0.
