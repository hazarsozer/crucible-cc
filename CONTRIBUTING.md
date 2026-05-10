# Contributing to Crucible

Thanks for considering a contribution. Crucible is opinionated about persona quality — adding a persona is more than dropping a markdown file.

## Adding a persona

1. Read `templates/persona-protocol.md` first. Personas MUST conform.
2. Pick a stage (1, 2, or 3) and decide the model tier based on reasoning load.
3. Follow the structure documented in `docs/superpowers/plans/2026-05-10-crucible.md` § "Persona Authoring Pattern".
4. Run `uv run python scripts/lint_personas.py agents/<your-file>.md` to validate frontmatter.
5. Add a smoke-test scenario for the persona on at least one fixture under `tests/fixtures/`.
6. Open a PR with a sample finding the persona produced on the fixture.

## Reporting bugs

Open a GitHub issue with: plugin version, Claude Code version, the project type Profiler detected, and the casting roster (saved to `.review/reports/<id>.md` runs include this).
