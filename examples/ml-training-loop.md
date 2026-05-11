# Crucible Review — full project review of pytorch-trainer tabular MLP pipeline

_Review ID: 2026-05-11-1921-full-pytorch-trainer · Generated: 2026-05-11T19:32:20Z · Project: ml-pipeline_

## Final Verdict

**Score:** 3.5/10
**Verdict:** Blocked

Two of the aims document's load-bearing success criteria are falsified by the code as shipped: there is no seed anywhere (reproducibility cannot hold) and no train/val/test split exists (every metric is leakage by construction). team-data-ml-reviewer returned block and lead-project-manager graded aim alignment 2/10 with block, both citing the same two structural gaps. The architect's concerns verdict reinforces this — the pipeline is a single untestable monolith with no seam for splits, seeding, or a metric sink — and peer-quality-engineer's score of 3 confirms there is no test contract pinning any of it down. Security is clean and the codebase is small, but the work cannot meet its own bar until seeding, split, and end-of-training test evaluation land.

## Executive Summary

This is a full-project review of a small PyTorch training pipeline (src/data.py, src/model.py, src/train.py) intended to train a baseline MLP on tabular data with reproducible runs and trustworthy metrics. The aims explicitly call for two load-bearing properties: identical loss curves under a fixed config, and a leakage-free train/val/test split ending in a single test-set accuracy number.

The foundations that exist are sound. team-security-reviewer returned approve with no findings — yaml.safe_load is used correctly, no secrets, no untrusted input paths, no network exposure. The dependency surface is small and current, and the module layout is the right shape to grow into. peer-python-reviewer findings are all medium-severity idiom polish (print vs logging, @torch.no_grad() vs torch.inference_mode(), model.train(False) vs the inference-mode shorthand) — fixable in a single follow-up commit.

The concerns are structural and decisive. No seed is set anywhere in train(), so two runs with the same config produce different weight initialization, shuffles, and loss curves — the reproducibility criterion is unmet by construction. load_full_dataset() returns the undivided TabularDataset with no split, so any accuracy reported would be measured on training rows — the leakage criterion is unmet by construction. There is no end-of-training test evaluation block at all, no val loss logged, and no machine-readable run record. peer-quality-engineer found that the entire training loop, split logic, and predict() are untested. Aim alignment from lead-project-manager is 2/10. The work needs to land seeding, a stratified split, and a final test-set accuracy block before the pipeline can be evaluated against its own success criteria.

## What's Good

- Security surface is clean — team-security-reviewer returned approve with no findings; yaml.safe_load, no secrets, no untrusted input paths.
- Module layout (data.py / model.py / train.py / configs/default.yaml) is the right shape to grow into — the architect's structural concerns are about adding seams, not unwinding the existing structure.
- The dependency surface is small and current; no recognized critical CVEs across the three declared dependencies.
- lead-project-manager confirms scope is on-target: the project is doing the right thing, the gaps are about completeness against its own criteria, not misdirection.

## What's Concerning

- No random seed is set in train() (src/train.py:24,37) — falsifies the 'reproducible runs' success criterion by construction; every run gets different weight init, shuffles, and loss curves.
- load_full_dataset() returns the undivided dataset with no train/val/test split (src/data.py:29-36) — falsifies the 'no leakage' criterion by construction; any accuracy reported is measured on training rows.
- No end-of-training test-set evaluation block exists (src/train.py:33-57) — the 'single accuracy number' success criterion is not implemented at all.
- Test suite is a single 'not None' assertion against the model (tests/test_train.py:8) — the training loop, data loading, split logic, reproducibility contract, and predict() are entirely untested.
- The pipeline is a single function with no seam between data prep, training loop, and evaluation (src/train.py:22-57); every success-criterion fix has to touch train() directly until a Splitter / train_one_epoch / MetricLogger extraction lands.

## Key Notes from the Committee

### lead-project-manager
> Aim alignment: 2/10. Scope: on-scope. Verdict: hold. PR falsifies both primary success criteria — no seed (reproducibility), no split (trustworthy metrics). Foundations are there but the project as shipped cannot meet its own bar.

### team-data-ml-reviewer
> Project aims commit to reproducible runs and no-leakage splits; code falsifies both. No train/val/test split exists (every metric is leakage by construction) and no seed is set (runs are not comparable). Neither success criterion can be evaluated from runs this code produces.

### lead-senior-architect
> The pipeline conflates data loading, splitting, training loop, and evaluation into one untestable monolith with no seed boundary or metric sink; recommend extracting a thin Splitter + Trainer + MetricLogger seam before adding val/test logic.

### peer-quality-engineer
> The test suite is a single smoke test that asserts MLP() is not None. The training loop, data loading, split logic, reproducibility contract, and predict() are entirely untested.

### team-performance-reviewer
> DataLoader runs with num_workers=0 (GPU starved by serial CPU loading); no random seed breaks reproducibility; zero_grad without set_to_none=True adds unnecessary overhead.

### lead-project-manager
> Seeding closes criterion (a) with ~5 lines, split closes criterion (b) with ~20 lines — together move alignment from 2/10 to ~7/10. Sequence: (1) seeding + split + test-set evaluation; (2) val logging + experiment tracking; (3) idiom/perf cleanup. Do not bundle.

## Stage 0 — Profiler

### Project profile
- **Type:** ml-pipeline
- **Languages:** python
- **Frameworks:** torch, numpy
- **Datastores:** (none)

### Review scope
- **Kind:** full
- **Description:** full project review of pytorch-trainer tabular MLP pipeline
- **Files:** src/data.py, src/model.py, src/train.py, tests/test_train.py, configs/default.yaml, pyproject.toml

### Casting reasoning
Pure Python ML pipeline importing torch and numpy — no web frontend, no database, no API surface. peer-python-reviewer covers all four .py source files by extension; peer-quality-engineer covers the same set plus the smoke test. team-data-ml-reviewer is the central Stage 2 lens. team-performance-reviewer casts because training performance is explicitly a success constraint (30-minute budget). team-security-reviewer casts as default. Both leadership personas receive the full project.

## Stage 1 — Peer Review

### peer-python-reviewer (claude-haiku-4-5-20251001)

**Verdict:** concerns · **Score:** 6/10

> print() in reusable train() function should use logging; predict() uses deprecated @torch.no_grad() decorator pattern; model.train(False) should be replaced with the standard inference-mode shorthand.

#### Findings

- **[medium]** Use logging instead of print() for training metrics — `src/train.py:54-55`
  - The train() function emits per-epoch metrics via print(). This is a library-level reusable function, so print() output cannot be silenced, redirected, or captured by callers.
  - **Suggestion:** Add logger = logging.getLogger(__name__) at module top. Replace print statements with logger.info(...) calls.

- **[medium]** Use torch.inference_mode() instead of @torch.no_grad() decorator — `src/model.py:23`
  - The predict() function uses @torch.no_grad() as a decorator, which is the deprecated pattern. The modern idiomatic approach is the torch.inference_mode() context manager inside the function body.
  - **Suggestion:** Remove the @torch.no_grad() decorator. Inside the function body, set model to inference mode and wrap the model invocation with the torch.inference_mode() context manager.

- **[medium]** Use model.eval() shorthand instead of model.train(False) — `src/model.py:25`
  - model.train(False) works but is non-idiomatic. Standard PyTorch convention is model.eval() which is immediately recognizable to any PyTorch programmer.
  - **Suggestion:** Replace model.train(False) with model.eval() — same effect, standard PyTorch idiom.

#### Stage handoff notes
Critical gaps (no random seed, no train/val/test split, no DataLoader num_workers) belong to team-data-ml-reviewer and team-performance-reviewer per casting reasoning. No wildcard imports, no bare excepts, no resource leaks.

### peer-quality-engineer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 3/10

> The test suite is a single smoke test that asserts MLP() is not None. The training loop, data loading, split logic, reproducibility contract, and predict() are entirely untested.

#### Findings

- **[high]** train() has no tests at all — the pipeline's core contract is unverified — `src/train.py:1`
  - The entire training entry point — config loading, DataLoader construction, forward pass, loss computation, per-epoch logging — is exercised by zero tests. None of the stated success criteria properties are asserted anywhere.
  - **Suggestion:** Add tests for train() with minimal config (2 epochs, small batch), a determinism test with fixed seed asserting identical final losses, and a config round-trip test.

- **[high]** load_full_dataset() returns undivided data with no test asserting split existence — `src/data.py:29`
  - No test asserts that distinct splits exist or that train and test indices are disjoint.
  - **Suggestion:** Once split is implemented, add tests asserting: len(train)+len(val)+len(test)==total; train_indices.isdisjoint(test_indices); train_indices.isdisjoint(val_indices).

- **[medium]** predict() is completely untested — output shape and dtype contract unverified — `src/model.py:29`
  - No test verifies output shape, dtype, or value range for predict().
  - **Suggestion:** Add test asserting output shape (batch_size,), dtype int64, all values in range [0, output_dim).

- **[medium]** The only existing test asserts 'not None' — provides no signal about correctness — `tests/test_train.py:8`
  - test_model_constructs() asserts m is not None. Any object would pass this assertion.
  - **Suggestion:** Replace with: forward pass shape test m(torch.randn(4, 32)).shape == (4, 10); parameter count nonzero check.

- **[medium]** No test for TabularDataset boundary behavior — `src/data.py:14`
  - No tests check __len__, __getitem__ at boundaries, or that out-of-bounds raises IndexError.
  - **Suggestion:** Add parametrized boundary test for indices 0 and n-1; negative test asserting ds[n] raises IndexError.

#### Stage handoff notes
Until the training loop produces a deterministic split and a final accuracy number, there is not a stable contract to write tests against; QE work should follow the criteria PR, not precede it.

## Stage 2 — Cross-functional

### team-security-reviewer (claude-sonnet-4-6)

**Verdict:** approve · **Score:** 9/10

> No exploitable security issues in scope. yaml.safe_load is used correctly. No secrets, no untrusted input paths, no injection vectors, no network exposure. This is a local-only ML pipeline with a minimal attack surface.

#### Findings

(none)

#### Stage handoff notes
Security surface is minimal and clean for this scope. yaml.safe_load is the correct choice — arbitrary object deserialization is not possible. No secrets or credentials in source or config. The three declared dependencies are current major versions with no recognized critical CVEs; recommend adding pip-audit or Dependabot for ongoing hygiene.

### team-performance-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 6/10

> DataLoader runs with num_workers=0 (single-threaded CPU data loading serialized with GPU compute); no random seed breaks reproducibility (stated success criterion); zero_grad without set_to_none=True adds unnecessary gradient tensor overhead each step.

#### Findings

- **[high]** DataLoader num_workers=0 — CPU data prep serialized with GPU compute — `src/train.py:30`
  - With num_workers=0, all numpy-to-tensor conversion is serial with GPU compute. For 10k samples at batch_size=64, 20 epochs = 3140 forward/backward passes each waiting on serial CPU loading. Setting num_workers=4 enables prefetching — the next batch is prepared in a background worker while the GPU processes the current one.
  - **Suggestion:** Pass num_workers=4 and pin_memory=True to the DataLoader constructor. Expose both as config keys in default.yaml.

- **[high]** No random seed set — reproducibility success criterion is unmet — `src/train.py:24`
  - Without seeding torch, numpy, and Python's random module, every run starts from different weight initialization and shuffles data in a different order. No meaningful comparison between runs is possible.
  - **Suggestion:** Seed all RNGs at top of train(). Add seed: 42 to default.yaml. Pass generator=torch.Generator().manual_seed(seed) to DataLoader.

- **[medium]** optimizer.zero_grad() without set_to_none=True — `src/train.py:36`
  - Default zero_grad() fills each parameter's .grad tensor with zeros rather than releasing it. set_to_none=True deallocates .grad entirely, reducing peak memory and eliminating the zero-fill pass.
  - **Suggestion:** Change optimizer.zero_grad() to optimizer.zero_grad(set_to_none=True). One-token change with no behavioral downside.

#### Stage handoff notes
The no-random-seed finding overlaps with team-data-ml-reviewer's reproducibility finding but from a different angle: seed is a runtime-state concern, not a test-coverage concern. Once a proper split is added, the num_workers and pin_memory config keys should apply to all three DataLoader instantiations.

### team-data-ml-reviewer (claude-sonnet-4-6)

**Verdict:** block · **Score:** 3/10

> Project aims commit to reproducible runs and no-leakage splits; code falsifies both. No train/val/test split exists (every metric is leakage by construction) and no seed is set (runs are not comparable). Neither success criterion can be evaluated from runs this code produces.

#### Findings

- **[high]** No train/val/test split; every reported metric is leakage by construction — `src/data.py:29-36`
  - The function returns the full TabularDataset and there is no split anywhere in the pipeline. Any accuracy computed would be evaluated on rows the model was trained on. The project aims explicitly commit to 'Train/val/test split exists and there is no leakage' — the code falsifies this by construction.
  - **Suggestion:** Add split_dataset() returning (train_ds, val_ds, test_ds) with 70/15/15 split, stratified by class, seeded. Update train.py to use train_loader for gradient updates, val_loader for per-epoch val loss, and test_loader for a single held-out evaluation at the end.

- **[high]** No random seed is set anywhere; two runs produce different loss curves — `src/train.py:37`
  - No seed before any stochastic component: TabularDataset generates different data each run, DataLoader shuffle differs, nn.Linear weight init differs. The project aims commit to 'identical loss curves'; the code falsifies this by construction.
  - **Suggestion:** Add set_seed(seed) called at top of train(): random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed); cudnn.deterministic = True. Add seed: 42 to configs/default.yaml.

- **[medium]** Only training loss logged per epoch; overfitting invisible for the 20-epoch run — `src/train.py:50-55`
  - No val set exists, so no val loss is computed. With 20 epochs on a 10k-sample dataset, the model may overfit well before epoch 20 with no visible signal.
  - **Suggestion:** After adding the split, add a per-epoch val pass using torch.inference_mode(). Log both train_loss and val_loss. Add early stopping with patience=5.

- **[medium]** No experiment tracking; metrics only in terminal scrollback — `src/train.py:33-57`
  - All metrics are written via print(). No machine-readable record of any run persists. Two runs of different configs cannot be compared after the fact.
  - **Suggestion:** Add MLflow with mlruns local storage. Log params once, metrics per epoch.

- **[medium]** No end-of-training test-set evaluation; success criterion not implemented — `src/train.py:33-57`
  - train() ends with print('training complete') and no evaluation of any kind. There is no test_loader, no accuracy computation, no final metric.
  - **Suggestion:** After the training loop, add a final test-set pass using torch.inference_mode() computing correct/total over test_loader; print the accuracy. Must run exactly once after all training is complete.

#### Stage handoff notes
The two high findings together constitute grounds for block: both primary success criteria are falsified by the code as written. Any metric the current script produces is neither reproducible nor trustworthy.

## Stage 3 — Leadership

### lead-senior-architect (claude-opus-4-7)

**Verdict:** concerns · **Score:** 6/10

> Decision: the pipeline conflates data loading, splitting, training loop, and evaluation into one untestable monolith with no seed boundary or metric sink; recommend extracting a thin Splitter + Trainer + MetricLogger seam before adding val/test logic.

#### Findings

- **[high]** Pipeline has no seam between data preparation, training loop, and evaluation — success criteria cannot be added without restructuring — `src/train.py:22-57`
  - The current implementation is a 35-line train() function with no Splitter, no Trainer, no Evaluator, no MetricLogger. The peer-quality-engineer's 'no tests' finding and team-data-ml-reviewer's three findings (no split, no val loss, no test assessment) are not four independent gaps — they are four projections of one structural gap: there is no surface to attach split logic, val-loss computation, or final test assessment to without rewriting train(). Every success criterion requires touching train() directly.
  - **Suggestion:** Extract three named seams: (1) prepare_splits(dataset, seed) returning (train_ds, val_ds, test_ds) in data.py; (2) train_one_epoch(model, loader, optimizer, criterion) returning a metrics dict; (3) a MetricLogger protocol with a PrintLogger default.

- **[medium]** Reproducibility is a cross-cutting concern with no owning boundary — `src/train.py:24, src/data.py:13`
  - Reproducibility requires seeding four independent RNGs. NumPy calls in TabularDataset.__init__ happen at dataset construction time and silently bypass any seeding done later in train() unless construction order is carefully managed.
  - **Suggestion:** Create src/repro.py with set_seed(seed) seeding all four RNGs plus cudnn settings, and a seed_worker(worker_id) helper. Refactor TabularDataset to accept an explicit rng: np.random.Generator parameter.

#### Stage handoff notes
My two findings synthesize five Stage 2 findings into one structural ADR plus one cross-cutting concern. The individual per-issue findings should still be fixed; my altitude names the order: extract seams first, then fill in each criterion.

### lead-project-manager (claude-opus-4-7)

**Verdict:** block · **Score:** 2/10

> Aim alignment: 2/10. Scope: on-scope. Verdict: hold. PR falsifies both primary success criteria — no seed (reproducibility), no split (trustworthy metrics). Foundations are there but the project as shipped cannot meet its own bar.

#### Findings

- **[high]** PR ships a training loop but falsifies the two primary success criteria — `.review/aims.md:11-15`
  - Aim alignment: 2/10. Scope is on-target (correct place, respects all non-goals), but both load-bearing success criteria are unmet by construction: unseeded (different weight inits, shuffles, loss curves on every run); no split (all reported metrics are training-set leakage). Val metrics: partial. Test-set final accuracy: not implemented. By the user's own criteria, this phase is roughly 10-15% done.
  - **Suggestion:** Hold until seeding + split + test-set final accuracy land. Then address val logging, experiment tracking, and idiom cleanup as follow-up.

- **[medium]** Highest-leverage next work is seeding + split, not the perf/idiom findings — `.review/aims.md:11-14`
  - Seeding closes criterion (a) with ~5 lines and the split closes criterion (b) with ~20 lines — together move the alignment grade from 2/10 to ~7/10 with one focused PR. The num_workers=0 perf concern is real but the runtime budget is not in danger for a 10k-sample MLP.
  - **Suggestion:** Sequence as: (1) seeding + split + final test accuracy; (2) val metric logging + experiment tracking; (3) idiom/perf cleanup. Do not bundle.

#### Stage handoff notes
team-data-ml-reviewer's block verdict maps one-to-one onto two stated success criteria — the alignment lens fully concurs. peer-quality-engineer's 'no real tests' concern is genuine but downstream: until the training loop produces a deterministic split and a final accuracy number, there is not a stable contract to write tests against. No rescoping recommended — this is an execution gap, not an intent mismatch.

## Aims Snapshot

Train a baseline MLP on tabular data with reproducible runs and trustworthy metrics. Success criteria: reproducibility (identical loss curves), no-leakage train/val/test split, per-epoch metrics logging, final test-set accuracy number. Constraints: single-GPU RTX 4070 Super, training run under 30 minutes for the baseline.

## Run Metadata

- **Plugin version:** 0.1.0
- **Wall-clock:** 1205s
- **Models used:** claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-7

_API cost is not displayed here. Claude Code does not expose token-level pricing to plugin skill scripts, so any number Crucible printed would be a guess. Run `/status` in your Claude Code session to see real API cost for this run._
