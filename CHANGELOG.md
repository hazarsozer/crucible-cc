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

### Notes

- Configuration via `.review/config.yaml` is parsed but not yet honored; full override behavior ships in v0.2.0.
- Runs on Claude Pro and Max plans. **Measured cost on the 7-file `tests/fixtures/nextjs-auth` (10-persona cast): $5–7 API per run, 25–35 min wall time, ~10–15% Max-plan quota burn.** Opus is available on both tiers; Pro caps Opus access, so heavy users should scope reviews tighter (a phase review casts ~5 personas vs. ~10 for a full-project review). Cross-project cost data (Go API, PyTorch, larger codebases) lands in v0.1.1. See the README §Costs section for the per-model split and caveats.
- Quality-review polish backlog (per-persona nits surfaced during authoring) is tracked for v0.2.0.
