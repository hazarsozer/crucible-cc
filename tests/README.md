# Crucible test suite

Two layers:

## Standard tests (no API calls, no cost)

```bash
uv run pytest
```

These cover:
- JSON schema validity + example validation
- Persona frontmatter linting (every shipped persona)
- Persona library completeness
- Plugin structural integrity (orchestrator references, skill frontmatter, plugin manifest)
- Template marker hygiene
- Example reports presence

Runs in well under a second on a typical laptop. CI runs this layer on every push.

## Live E2E test (real API calls, ~$1-2 per run)

```bash
RUN_LIVE_E2E=1 uv run pytest tests/test_e2e.py::test_crucible_runs_on_nextjs_fixture
```

Requires:
- `claude` CLI on PATH
- This plugin installed locally (`claude --plugin-dir <repo-root>` or marketplace install)
- `ANTHROPIC_API_KEY` exported
- ~5–10 minutes per fixture
- ~$1–2 per fixture in API tokens

The live test asserts only structural invariants (sections present in the
generated report); content is stochastic. Run before any release tag.

## Adding fixture outputs for ongoing validation

After a successful live run, the orchestrator saves persona outputs under
`tests/fixtures/<fixture>/.review/runs/<id>/stage_<N>/<persona>.json`. These
are NOT committed by default (the `.review/` directory is gitignored except
for the aims files), but you can keep them locally for repeated
`test_all_persona_outputs_validate` runs.
