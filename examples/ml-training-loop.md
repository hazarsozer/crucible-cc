# Crucible Review — PyTorch MLP baseline training pipeline

_Review ID: 2026-05-10-1530-training-loop-baseline · Generated: 2026-05-10T15:34:45Z · Project: ml-pipeline_

## Final Verdict

**Score:** 4.0/10
**Verdict:** blocked

Three of four stated success criteria are unmet: no reproducibility (no seeds), no train/val/test split, no metrics beyond `print(loss)`. All three are 1-hour fixes that don't require architectural redesign — but until they land, this isn't a baseline you can compare future experiments against. The architect-level structural picture is sound; the gaps are at the experimental-rigor layer.

## Executive Summary

The PR establishes a clean structural foundation for an MLP training pipeline — config-driven, three-file separation between data loading, model definition, and training loop. The code reads cleanly through the Python idiom lens, the architect agrees the seams are in the right places, and no security or scale concerns surface at this phase.

But the project's own `aims.md` commits to four success criteria, and the code falsifies three of them by construction. There is no train/val/test split — `load_full_dataset()` returns the entire dataset, so any "test accuracy" this script could produce is leakage. There is no random seed set anywhere, so two runs of identical config produce different loss curves. There is no per-epoch metric logging — `print(f"epoch {n}: loss={avg:.4f}")` is the entire telemetry surface, with no val loss, no curves, no tracker integration.

These are not architectural gaps requiring redesign. They are 1-hour fixes that compound across every future experiment. The team-data-ml-reviewer flagged the split and seed gaps as `high` against stated aims; the lead-project-manager grades aim alignment at 4/10 and recommends `hold` until the regressed criteria are addressed; the lead-senior-architect approves the structure with revisions, calling out the experimental-rigor gaps as the right layer for the fix.

The blocker is not the architecture. It's that a "baseline" you can't reproduce is not a baseline.

## What's Good

- Clean three-file separation: `train.py` orchestrates, `data.py` owns the dataset abstraction, `model.py` owns the architecture. The seams are testable; the boundaries are right.
- Configuration via YAML (`configs/default.yaml`) rather than inline magic numbers — establishes the right pattern for a series of experiments.
- Type hints present on all public function signatures (`load_config`, `make_model`, `train`); `from __future__ import annotations` enables modern syntax.
- Idiomatic PyTorch: `nn.Sequential` for the MLP, `optim.Adam` + `nn.CrossEntropyLoss`, standard training-loop shape.
- No security concerns at this phase — no untrusted input, no PII, no auth, no production deployment surface.

## What's Concerning

- **Aim-falsifying:** `load_full_dataset()` returns the entire dataset with no train/val/test split. Every metric this script can produce is leakage by construction. (team-data-ml-reviewer, `high`)
- **Aim-falsifying:** No random seed set for `random`, `numpy`, `torch`, or CUDA. Two runs of identical config produce different loss curves. (team-data-ml-reviewer, `high`)
- **Aim-partial:** Only training loss is logged per epoch, via `print()`. No val loss, no overfitting signal, no machine-readable record. (team-data-ml-reviewer, `medium`; team-observability-reviewer, `high`)
- **Phase-appropriate but compounding:** No experiment tracking integration (MLflow, W&B, or even a CSV) means every run is forgotten unless the operator copies stdout. (team-data-ml-reviewer + team-observability-reviewer)
- **Throughput:** DataLoader has no `num_workers` — single-threaded data loading will be the bottleneck on RTX 4070 Super; `optimizer.zero_grad()` doesn't pass `set_to_none=True`; no mixed-precision wrapper. (team-performance-reviewer, `medium`)
- **Test coverage:** `tests/test_train.py` has one trivial smoke test (`MLP` constructs) — nothing about training behavior, reproducibility, or split logic. (peer-quality-engineer, `high`)

## Key Notes from the Committee

### lead-project-manager
> Aim alignment: 4/10. Scope: on-scope. Verdict: hold. PR is foundationally aimed at the goal but regresses 3 of 4 stated success criteria (reproducibility, no-leakage split, metric logging) — fix before ship.

### team-data-ml-reviewer
> Project aims commit to reproducibility and no-leakage splits; code falsifies both. No train/val/test split (every metric is leakage), no seeds (runs are not comparable). Fix the split and seed first, then add val-loss logging and a tracker.

### lead-senior-architect
> Decision: structural seams are right (data/model/train separation, config-driven hyperparameters); experimental-rigor gaps (no checkpoint/resume, no tracking) compound across future runs. Approve with revisions — the data-ml fixes are 1-hour, the structural gaps defer-able to phase 2.

### peer-quality-engineer
> Single trivial smoke test asserts `MLP` constructs but nothing about training behavior. No reproducibility test (would catch missing seed); no split-logic test (would catch the leakage). Add behavior-level coverage before this becomes a baseline.

### team-performance-reviewer
> DataLoader missing `num_workers` (CPU bottleneck on RTX 4070 Super); `zero_grad()` without `set_to_none=True` (small per-step waste); no mixed-precision wrapper (~2-3x throughput on the table for the stated 30-min budget).

### team-observability-reviewer
> `print()` is the entire telemetry surface — no log levels, no metrics emitted, no experiment tracking integration. Every run is forgotten unless the operator copies stdout.

### peer-python-reviewer
> Reusable `train()` function uses `print()` for epoch metrics; switch to `logging.getLogger(__name__)` so callers can capture or silence output. Otherwise idiomatic.

## Stage 0 — Profiler

### Project profile
- **Type:** ml-pipeline
- **Languages:** python
- **Frameworks:** torch, numpy
- **Datastores:** none (in-memory data)

### Review scope
- **Kind:** full-tree
- **Description:** PyTorch MLP baseline training pipeline
- **Files:**
  - `tests/fixtures/pytorch-trainer/src/train.py`
  - `tests/fixtures/pytorch-trainer/src/data.py`
  - `tests/fixtures/pytorch-trainer/src/model.py`
  - `tests/fixtures/pytorch-trainer/configs/default.yaml`
  - `tests/fixtures/pytorch-trainer/tests/test_train.py`

### Casting reasoning

The scope is a small PyTorch training pipeline — three Python source files (`train.py`, `data.py`, `model.py`), one YAML config, one trivial test.

**Stage 1 casting:**
- `peer-python-reviewer` — any `*.py` files in scope (cast trigger met).
- `peer-quality-engineer` — always for non-trivial scope; clear signal here because the test file is a one-line smoke test against a multi-file production scope.

**Stage 2 casting:**
- `team-data-ml-reviewer` — `torch` + `numpy` detected, the canonical ML cast trigger.
- `team-performance-reviewer` — training loop is performance-relevant code despite the small file count; aims include a 30-minute budget that makes throughput a first-class concern.
- `team-observability-reviewer` — training script runs as a long-lived process from the operator's perspective, with the explicit aim of "metrics logged per epoch" suggesting telemetry is in scope.

**Stage 2 not cast (with reason):**
- `team-security-reviewer` — no untrusted input, no PII, no auth surface.
- `team-database-reviewer` — no datastore.
- `team-network-reviewer` — no outbound calls.
- `team-frontend-reviewer` — no UI.
- `team-accessibility-reviewer` — no UI.
- `team-devops-infra-reviewer` — no deployment surface yet.
- `team-privacy-compliance-reviewer` — no user data.
- `team-backend-reviewer` — no API surface.

**Stage 3 casting:** `lead-senior-architect` and `lead-project-manager` (always cast).

## Stage 1 — Peer Review

### peer-python-reviewer (claude-haiku-4-5-20251001)

**Verdict:** concerns · **Score:** 7/10

> Reusable train() function uses print() for epoch metrics; switch to logging.getLogger(__name__) so callers can capture or silence output. Test file uses bare assertion. Otherwise idiomatic.

#### Findings

**[medium] Use logging instead of print() for training metrics in reusable function**

- **Category:** logging
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:65-68`
- **Explanation:** The training loop emits per-epoch metrics via `print()`, but `train()` is a reusable function (not just a CLI entrypoint — it's importable from a tuning harness or a notebook). `print()` writes to stdout with no level, no timestamp, no logger name, and no way for callers or tests to silence it. Once this script is imported by a hyperparameter search or a notebook, the print noise is inescapable. The `print("training complete")` on line 68 has the same issue — it's inside the reusable function, not at the `__main__` boundary.
- **Suggestion:** Add `logger = logging.getLogger(__name__)` at module top, then replace `print(f"epoch {epoch + 1}/...")` with `logger.info(...)`. The `print("training complete")` on line 68 should also become `logger.info("training complete")`. Configure logging at the `__main__` entrypoint, not inside `train()`.

**[low] Missing return type hint on train() and load_config()**

- **Category:** type-hints
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:21,33`
- **Explanation:** `load_config` is annotated as `-> dict` but the dict is unstructured — a `TypedDict` or a `@dataclass` would catch typos at the call site (`cfg["epochs"]` vs `cfg["epoch"]`). `train()` is annotated as `-> None`, which is correct, but the function does meaningful work and a future caller may want to capture metrics — the return type is the right place to design that contract. Low priority because the file is internally consistent.
- **Suggestion:** Define a `@dataclass(frozen=True)` `TrainingConfig` with explicit fields (`batch_size: int`, `epochs: int`, `learning_rate: float`, `hidden_dim: int`, `input_dim: int`, `output_dim: int`). `load_config(path: Path) -> TrainingConfig` becomes self-documenting and IDE-friendly. Defer to a later PR if that's the path the team is on; for now, a `TypedDict` is the smaller change.

**[low] Bare assertion in test_train.py without descriptive failure message**

- **Category:** testing-idiom
- **Location:** `tests/fixtures/pytorch-trainer/tests/test_train.py:9`
- **Explanation:** `assert m is not None` will fail with `AssertionError` and no context — the operator has to read the test source to understand what was checked. pytest's `assert m is not None, "MLP failed to construct"` (or richer assertions like `isinstance(m, MLP)`) would make failures self-describing. Low priority because the test is trivial and will be subsumed by real coverage anyway.
- **Suggestion:** Either (a) replace with a richer assertion: `assert isinstance(m, MLP)` followed by `assert sum(p.numel() for p in m.parameters()) > 0`; or (b) just delete this test once the quality-engineer's recommended coverage lands — it adds nothing the upstream tests won't cover.

#### Stage handoff notes

File is otherwise idiomatic for the Python lens: type hints present on public signatures, `pathlib.Path` used, f-strings used, no mutable defaults, no wildcard imports, no `range(len())` patterns. Concerns visible in this file (missing random seed, DataLoader `num_workers`, `zero_grad` `set_to_none`, no train/val/test split, deprecated `@torch.no_grad()` decorator) are out-of-scope for me and belong to team-data-ml-reviewer, team-performance-reviewer, and team-observability-reviewer.

### peer-quality-engineer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 3/10

> Single trivial smoke test (MLP constructs) — nothing about training behavior, reproducibility, or split logic. Three foundational gaps that the data-ml team will also surface from a different angle.

#### Findings

**[high] Test file has only one trivial smoke test; training behavior is entirely unverified**

- **Category:** missing-behavior-coverage
- **Location:** `tests/fixtures/pytorch-trainer/tests/test_train.py:1-10`
- **Explanation:** The single test (`test_model_constructs`) imports `MLP`, instantiates it, and asserts the result is not None. It exercises zero behavior of the actual training loop in `src/train.py`, the dataset abstraction in `src/data.py`, or the predict path in `src/model.py:31-35`. The aims explicitly call for "Train/val/test split exists and there is no leakage" and "Training is reproducible — two runs with the same config produce identical loss curves" — the current test suite cannot verify either. A regression in any of those properties would not be caught.
- **Suggestion:** Add at least three behavior-level tests against the same fixture data:
  1. `test_split_is_deterministic_and_disjoint` — call the (eventually-split) loader twice with the same seed, assert train/val/test indices are identical across calls AND that the three sets are disjoint.
  2. `test_seeded_run_is_reproducible` — set the seed, train for 2 epochs, capture loss values; reset, repeat, assert losses match exactly.
  3. `test_predict_validates_input_shape` — feed `predict()` a tensor with the wrong shape, assert it raises a meaningful error (currently it would just produce a shape-mismatch torch error deep in the model).

**[high] No reproducibility test exists; the missing-seed gap would not be caught by current coverage**

- **Category:** missing-regression-test
- **Location:** `tests/fixtures/pytorch-trainer/tests/test_train.py:1-10`
- **Explanation:** The aims commit to "Training is reproducible — two runs with the same config produce identical loss curves." The test suite has no test that runs training twice and asserts identical results. This is the canonical case where TDD would have caught the missing-seed gap that team-data-ml-reviewer is independently flagging as `high` — a single test (~10 lines) makes the regression visible immediately. The data-ml finding is the production code gap; this is the same gap surfaced from the quality lens (the test that should exist and would have caught it).
- **Suggestion:** Add `test_two_runs_with_same_seed_produce_identical_losses`: instantiate the trainer twice with `seed=42` and identical config, train for 2 epochs each, capture the per-batch loss list both times, assert `losses_run_1 == losses_run_2` element-wise. This is one of the cheapest, highest-leverage tests in ML — it catches reproducibility regressions across the entire pipeline (data shuffle, weight init, dropout, augmentation) with one assertion.

**[medium] No test for the data loader's split logic; the no-split bug would not be caught**

- **Category:** missing-data-integrity-test
- **Location:** `tests/fixtures/pytorch-trainer/src/data.py:29-36`
- **Explanation:** `load_full_dataset()` currently returns the full dataset with no split (team-data-ml-reviewer is flagging this as `high` for the data-correctness lens). From the quality lens, the gap is that there is no test that would have caught it — no assertion that the loader returns three disjoint datasets, no assertion that `len(train) + len(val) + len(test) == n_samples`, no assertion that swapping the seed reshuffles deterministically. This is a critical-path data hygiene property, and one parameterized test (~15 lines) would establish a regression trip-wire.
- **Suggestion:** After the loader is updated to return three datasets, add `test_split_invariants(seed)` parameterized over a few seeds: assert `len(train) > 0`, `len(val) > 0`, `len(test) > 0`; assert the three index sets are pairwise-disjoint; assert lengths sum to `n_samples`; assert the same seed produces the same indices on a second call. Use `pytest.mark.parametrize("seed", [0, 42, 123])` to lock in deterministic-behavior-across-seeds.

#### Stage handoff notes

The training behavior, reproducibility, and split-logic gaps surface in my lens as "what test should exist that doesn't" — the data-ml team will surface the same gaps as "what production-code property is falsified". These are the same underlying issues from two angles; I'm flagging the test-coverage shape, they're flagging the production-code correctness. Once the production fixes land (split + seed), the tests above land cheaply alongside them. Performance test coverage (DataLoader `num_workers`, mixed-precision) is out-of-scope for me — `team-performance-reviewer` owns that.

## Stage 2 — Cross-functional

### team-data-ml-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 3/10

> Project aims commit to reproducibility and no-leakage splits; code falsifies both. No train/val/test split (every metric is leakage), no seeds (runs are not comparable). Fix the split and seed first, then add val-loss logging and a tracker.

#### Findings

**[high] load_full_dataset returns the entire dataset with no train/val/test split; every reported metric will be leakage by construction**

- **Category:** data-leakage
- **Location:** `tests/fixtures/pytorch-trainer/src/data.py:29-36`
- **Explanation:** The function returns the full `TabularDataset` and there is no separate train/val/test split anywhere in the pipeline. The training loop in `src/train.py:50-66` will fit on this data, and any assessment against the same dataset would be checking the model on data it was trained on — pure leakage, not generalization. The project aims at `tests/fixtures/pytorch-trainer/.review/aims.md:12` explicitly commit to "Train / val / test split exists and there is no leakage"; the code falsifies the commitment. Until a split exists, no metric this script produces can be trusted to reflect generalization. This is the canonical aim-falsification pattern — a stated success criterion that the production code structurally cannot satisfy.
- **Suggestion:** Split the dataset deterministically inside the loader and return three datasets. Example:
  ```python
  from sklearn.model_selection import train_test_split
  X_train, X_temp, y_train, y_temp = train_test_split(
      self.x, self.y, test_size=0.3, random_state=seed, stratify=self.y
  )
  X_val, X_test, y_val, y_test = train_test_split(
      X_temp, y_temp, test_size=0.5, random_state=seed, stratify=y_temp
  )
  ```
  Wrap each tuple in a `TabularDataset` and return train/val/test as three separate `Dataset` objects. Update `train.py` to consume `train_loader` for fitting, `val_loader` for per-epoch validation, and `test_loader` for the single end-of-run assessment.

**[high] No random seed set anywhere; runs are not reproducible across invocations despite the stated aim**

- **Category:** reproducibility
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:33`
- **Explanation:** The training entrypoint sets no seed for python's `random`, `numpy`, `torch`, or `cuda`. The DataLoader uses `shuffle=True` (reshuffled per epoch with a fresh ordering each run), the dataset constructor in `src/data.py:19-20` calls `np.random.randn` / `np.random.randint` without seeding, and `nn.Linear` weight init in `src/model.py:14-22` is unseeded. Two runs of this script with identical config will produce different loss curves and different final metrics. The project aims at `tests/fixtures/pytorch-trainer/.review/aims.md:11` explicitly commit to "Training is reproducible — two runs with the same config produce identical loss curves"; the code falsifies the commitment.
- **Suggestion:** Add a `set_seed(seed: int)` helper at the top of `train.py` and call it before any data/model construction:
  ```python
  import random
  import numpy as np
  import torch

  def set_seed(seed: int) -> None:
      random.seed(seed)
      np.random.seed(seed)
      torch.manual_seed(seed)
      torch.cuda.manual_seed_all(seed)
      torch.backends.cudnn.deterministic = True
      torch.use_deterministic_algorithms(True, warn_only=True)
  ```
  Read the seed from cfg (add `seed: 42` to `default.yaml`). For DataLoader determinism, also pass a `torch.Generator` with a manual seed via the `generator=` kwarg, and use a `worker_init_fn` that re-seeds workers.

**[medium] No metric logging beyond print(loss); no val curves, no early stopping, no experiment tracking**

- **Category:** training-visibility
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:50-66`
- **Explanation:** The training loop logs `running_loss / len(loader)` per epoch via `print()` but never computes or logs validation loss. peer-python-reviewer correctly flagged the `print` as a logging idiom issue; the deeper gap from this lens is that there is no per-epoch val-set assessment to log in the first place, no machine-readable record beyond terminal scrollback, and no experiment tracker integration. With `epochs: 20` in `configs/default.yaml` and a model that may converge sooner, overfitting is invisible — the script will report decreasing training loss even when val loss has been climbing for the last 10 epochs. The aims at `tests/fixtures/pytorch-trainer/.review/aims.md:13` state "Metrics are logged per epoch"; the criterion is satisfied only in the loosest sense (loss prints to a closing terminal). Without val curves, early stopping and best-checkpoint selection are impossible.
- **Suggestion:** After splitting the dataset (see the data-leakage finding), compute val loss and val accuracy at the end of each epoch using a no-grad pass over `val_loader` (call `model.train(False)` first to switch off dropout/batchnorm). Log both train and val metrics per epoch. Add early stopping: track best val loss, save the model checkpoint when it improves, break if no improvement for N epochs (`patience=5` is a reasonable default for 20-epoch runs). For tracking: `import mlflow`, wrap `train()` in `with mlflow.start_run():`, log the config once via `mlflow.log_params(cfg)`, and log per-epoch metrics via `mlflow.log_metrics({"train_loss": ..., "val_loss": ...}, step=epoch)`.

**[medium] Deprecated @torch.no_grad() decorator on inference; modern path is with torch.inference_mode()**

- **Category:** inference-hygiene
- **Location:** `tests/fixtures/pytorch-trainer/src/model.py:31-35`
- **Explanation:** `predict()` uses `@torch.no_grad()` as a function decorator. This works correctly, but PyTorch 1.9+ provides `torch.inference_mode()` which is faster (skips view tracking, slightly cheaper) and clearer about intent — it signals "this code path is inference-only and the resulting tensors are not for autograd". The decorator pattern also obscures the no-grad scope visually; using `with torch.inference_mode():` inside the function body makes the inference scope explicit. Additionally, `predict()` accepts `x: torch.Tensor` with no shape/dtype validation — for a research-spike fixture this is `medium`; once the model moves toward production inference it would be `high` (input-validation gap).
- **Suggestion:** Replace the decorator with an inner context manager:
  ```python
  def predict(model: MLP, x: torch.Tensor) -> torch.Tensor:
      model.train(False)
      with torch.inference_mode():
          return model(x).argmax(dim=-1)
  ```
  Same semantics, more readable scope. Defer input-validation to a later PR if the predict path stays research-internal.

#### Stage handoff notes

peer-python-reviewer's `print()` flag is correct as an idiom issue; my training-visibility and metric-logging findings build on the same lines from a different lens (the deeper gap is that there's nothing to log to a tracker because val isn't being computed, and there's no tracker to log it to either way). Performance concerns visible in scope (DataLoader missing `num_workers`, `optimizer.zero_grad()` without `set_to_none=True`, no mixed-precision) belong to team-performance-reviewer — I am not double-counting. The deprecated `@torch.no_grad()` decorator is a low-to-medium inference-hygiene note; for a research-spike fixture it doesn't justify a higher slot. No baseline model (logistic regression, XGBoost) for comparison — defensible at this phase, worth revisiting before promoting any MLP result as the project's chosen baseline.

### team-performance-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 5/10

> DataLoader missing num_workers (CPU-bound bottleneck on RTX 4070 Super); zero_grad() not using set_to_none; no mixed-precision wrapper. ~2-3x throughput on the table for the stated 30-min baseline budget.

#### Findings

**[medium] DataLoader has no num_workers; data loading is single-threaded and will leave the GPU idle**

- **Category:** dataloader-throughput
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:43-44`
- **Explanation:** Capacity memo: at the stated `batch_size=64` and 10k synthetic samples, single-threaded data loading on RTX 4070 Super will produce ~30-50% GPU utilization once the model fits to GPU; `num_workers=4` typically lifts this to ~80%+ on similar workloads. The wall-clock reduction depends on model FLOPs (small MLP = data-bound; large model = compute-bound), but for a 30-minute baseline budget this is leaving 10-15 minutes on the floor. With `num_workers=0` (the default when unspecified), the main process serializes data prep with the forward/backward pass — every batch the GPU sits idle waiting for the next one to be assembled.
- **Suggestion:** Pass `num_workers=os.cpu_count() // 2` (or 4-8 for typical desktop setups) and `pin_memory=True` to the DataLoader constructor:
  ```python
  DataLoader(
      dataset,
      batch_size=cfg["batch_size"],
      shuffle=True,
      num_workers=4,
      pin_memory=True,
      persistent_workers=True,
  )
  ```
  `persistent_workers=True` avoids the per-epoch worker startup cost. For deterministic shuffling once the seeding finding lands (data-ml's seed gap), pass `generator=torch.Generator().manual_seed(seed)` and a `worker_init_fn` that re-seeds each worker.

**[medium] optimizer.zero_grad() called without set_to_none=True; small per-step waste compounds across long training runs**

- **Category:** training-loop-efficiency
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:53-56`
- **Explanation:** Capacity memo: `zero_grad()` defaults to `set_to_none=False` (allocates fresh zero tensors for every parameter), but `set_to_none=True` (the modern PyTorch default since 1.7+) clears parameter gradient pointers instead — same semantics for the next backward pass, lower memory bandwidth, no extra allocation. For a 20-epoch run with ~157 batches per epoch (10k samples / 64 batch size), that's ~3140 zero_grad calls; the per-call savings are sub-millisecond but cumulative. More importantly, `set_to_none=True` reduces memory fragmentation in long runs and is the recommended pattern in the PyTorch tutorials for any non-trivial training loop.
- **Suggestion:** Change `optimizer.zero_grad()` to `optimizer.zero_grad(set_to_none=True)` on line 56. One-line change. For PyTorch 2.0+ this is the default, but explicit is clearer and works on all versions the project may run on.

**[medium] No mixed-precision wrapper; leaving 2-3x throughput on the table on RTX 4070 Super for the stated 30-min budget**

- **Category:** mixed-precision
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:50-62`
- **Explanation:** Capacity memo: RTX 4070 Super has dedicated bf16/fp16 tensor cores that, for matmul-heavy workloads (which an MLP is), deliver ~2-3x the throughput of fp32 with negligible accuracy loss. The current loop runs entirely in fp32. Wrapping the forward + loss compute in `torch.autocast(device_type='cuda', dtype=torch.bfloat16)` is a 5-line change that, for the small MLP in the fixture, may not move the needle dramatically (the model is already fast); for a larger MLP at the same batch size, the speedup is real. The aims state "Training run must complete in under 30 minutes for the baseline" — mixed precision is the cheapest single-step toward that budget.
- **Suggestion:** Wrap forward + loss in autocast:
  ```python
  with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
      logits = model(batch_x)
      loss = criterion(logits, batch_y)
  ```
  For bf16 (recommended on Ampere+), no `GradScaler` is needed; for fp16, add `scaler = torch.cuda.amp.GradScaler()` and use `scaler.scale(loss).backward(); scaler.step(optimizer); scaler.update()`. bf16 is the safer choice for an RTX 4070 Super because it has the same dynamic range as fp32 (no underflow risk).

#### Stage handoff notes

Stage 1 (peer-python-reviewer) and Stage 2 (team-data-ml-reviewer) cover the language-idiom and ML-correctness layers; my findings sit cleanly above them on the throughput layer. The data-ml team's seed and split fixes will compose with my throughput fixes — once the data is properly split and seeded, mixed-precision and `num_workers` apply unchanged. Once the headline data-correctness gaps land, recommend a `py-spy` capture of one full epoch to localize the next-tier bottleneck (likely the synthetic dataset's `np.random.randn` call in `__init__`, which materializes the entire dataset in memory at construction — fine for 10k samples, a cliff at 1M).

### team-observability-reviewer (claude-sonnet-4-6)

**Verdict:** concerns · **Score:** 4/10

> print() is the entire telemetry surface — no log levels, no metrics emitted, no experiment tracking. Every run is forgotten unless the operator copies stdout. On-call (or the operator running a sweep) is flying blind.

#### Findings

**[medium] Service uses print() for production training output instead of structured logging**

- **Category:** structured-logging
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:65-68`
- **Explanation:** The training loop emits `print(f"epoch {epoch + 1}/{cfg['epochs']}: loss={avg:.4f}")` and `print("training complete")` directly to stdout. There is no logger configured, no level distinction (INFO vs WARN vs ERROR), no structured fields. peer-python-reviewer correctly flagged this as a Python idiom issue; the observability angle is broader: when the script is called from a sweep harness, a notebook, or a future CI job, the operator has no way to filter ("show me only the warnings"), no way to silence ("redirect to a file"), and no way to query ("which runs hit loss > 1.0 in epoch 5"). The output is meaningful only to a human watching the terminal in real time.
- **Suggestion:** Configure `logging` at the `__main__` entrypoint with a JSON handler in production:
  ```python
  import logging
  logging.basicConfig(
      format='{"ts": "%(asctime)s", "level": "%(levelname)s", "msg": %(message)s}',
      level=logging.INFO,
  )
  ```
  Replace `print(f"epoch {epoch + 1}/...")` with `logger.info("epoch_metrics", extra={"epoch": epoch + 1, "loss": avg})` (using `python-json-logger` or `structlog` for the structured-extra pattern). For dev, use a pretty handler. The training_complete event becomes `logger.info("training_complete", extra={"total_epochs": cfg["epochs"]})`.

**[high] No metrics emitted anywhere; train loss, val loss, throughput, epoch wall-clock all invisible to any downstream system**

- **Category:** missing-metrics
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:50-66`
- **Explanation:** The training loop computes `running_loss` per epoch but emits nothing observable beyond a `print()` call. There is no metric to a Prometheus exporter, no MLflow `log_metrics`, no W&B `wandb.log`, no CSV append, no TensorBoard SummaryWriter. From the on-call / experiment-tracking lens, the entire run leaves no trace once the terminal closes. This is a `high` severity finding because the project's own aims at `tests/fixtures/pytorch-trainer/.review/aims.md:13` commit to "Metrics are logged per epoch" — and "logged" in any operator-meaningful sense means more than a stdout print. The team-data-ml-reviewer flagged this from the experiment-tracking lens (concern #11); my angle is the broader observability gap: a long-running process producing valuable signal that nobody can see after the fact.
- **Suggestion:** Choose one tracker and integrate at minimum viable level. For solo-developer + RTX 4070 Super setup, MLflow with a local file backend is the cheapest:
  ```python
  import mlflow
  mlflow.set_tracking_uri('file:./mlruns')
  with mlflow.start_run():
      mlflow.log_params(cfg)
      for epoch in range(cfg['epochs']):
          # ... train + compute val metrics
          mlflow.log_metrics({
              "train_loss": train_loss,
              "val_loss": val_loss,
              "epoch_seconds": epoch_time,
          }, step=epoch)
      mlflow.log_artifact("best_model.pt")
  ```
  No infrastructure beyond `pip install mlflow`. After the run, `mlflow ui` browses every experiment.

**[medium] No experiment tracking integration; every run is forgotten**

- **Category:** experiment-tracking
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:33-72`
- **Explanation:** Distinct from the metric-logging finding above, this is about the *experiment record*: the config used, the git SHA, the data version, the resulting checkpoint. Without an experiment tracker, there is no way to answer "which config produced our best val loss" without rerunning everything. For a project iterating on architectures and hyperparameters (which the aims describe), this is the difference between systematic experimentation and one-shot runs. The data-ml team also flagged this from their lens (concern #11); my framing is operational — the operator running a sweep needs the record to compare runs. Severity is `medium` because at the spike phase a CSV log can substitute for full tracking; once the project iterates more, this becomes `high`.
- **Suggestion:** Same MLflow integration as the metrics finding — adding `mlflow.start_run()` + `log_params(cfg)` + `log_artifact("best_model.pt")` covers both concerns in one change. If MLflow is too heavy, a structured CSV append at the end of each run (timestamp, config_hash, git_sha, train_loss, val_loss, test_metric) gets 70% of the value with 10 lines of code. Either way, the goal is: future-you can answer "which run was best" without rerunning.

#### Stage handoff notes

Deferred to handoff: distributed tracing (concern #6) — single-process training script with no outbound dependencies, tracing is overkill at this phase; audit logging (concern #10) — no sensitive operations, not relevant; health endpoints (concern #9) — no service surface, not relevant. The peer-python-reviewer's `print()` finding (idiom-level), the team-data-ml-reviewer's tracking finding (ML-experiment-record lens), and my structured-logging finding (observability lens) all describe the same lines from three different angles — that's three personas correctly staying in their lanes, not three duplicates. The fix shape (configure logging + integrate MLflow) addresses all three at once.

## Stage 3 — Leadership

### lead-senior-architect (claude-opus-4-7)

**Verdict:** concerns · **Score:** 6/10

> Decision: structural seams are right (data/model/train separation, config-driven hyperparameters); the data-ml fixes are 1-hour, the checkpoint/resume + tracking gaps are defer-able to phase 2. Approve with revisions.

#### Findings

**[medium] Training pipeline structure is sound for the spike phase; experimental-rigor gaps will compound across the next dozen experiments unless addressed early**

- **Category:** experimental-rigor-boundary
- **Location:** `tests/fixtures/pytorch-trainer/src/train.py:33-72`
- **Explanation:**

  **Context:** ML training pipeline, baseline phase. The project is small (three source files, a config, a trivial test) but the structural decisions established here will frame a series of experiments — different architectures, different hyperparameters, different data subsets — over the coming weeks or months. The aims describe an iterative workflow ("comparing runs"), so the seams established here have multiplicative effect on every future run.

  **Decision (observed):** Training, model definition, and data loading are split into three files (`train.py`, `model.py`, `data.py`) — clean separation, the right boundaries. Configuration via YAML — sound, establishes the right pattern. Function decomposition (`load_config`, `make_model`, `train`) is reasonable. Three structural gaps are also observed: (1) no checkpoint/resume capability — if a 30-minute run crashes at minute 28, all 28 minutes are lost; (2) no experiment tracking — every run is one-shot, comparing runs requires manual stdout-copying; (3) the `load_full_dataset` design assumes the dataset fits in memory, which is fine for the 10k synthetic samples but becomes a cliff at scale.

  **Consequences:** Good — the seam between data and model is testable and the boundaries match the conceptual domains; the file decomposition will evolve cleanly as features land (a new model architecture is one file in `model.py`, a new dataset is one file in `data.py`, a new training loop variant is `train_distributed.py` alongside `train.py`). Bad — the experimental-rigor gaps the team-data-ml-reviewer flagged (no split, no seed) compound: once the team has run 20 experiments without a tracker, there is no way to re-establish which config produced the best val loss without rerunning all 20. The gap is cheap to fix now (~1 hour for tracking integration, ~1 day for checkpoint/resume) and expensive to fix later (the historical record is unrecoverable). Forecloses: nothing critical at this phase — the data-correctness fixes (split + seed) and the throughput fixes (num_workers + autocast + zero_grad) all compose cleanly with the current structure.

  **Recommendation:** Approve with revisions. The data-ml team's split + seed findings are 1-hour fixes that compound across all future runs; land those first. The checkpoint/resume + tracking gaps are 1-day each but defer-able to phase 2 if the baseline ships first. Do not redesign the pipeline structure — the seams are right; the gaps are at the experimental-rigor layer, which is one level above the file decomposition.

- **Suggestion:** Sequence the next two PRs:
  - **PR (a) — data-correctness:** split the dataset, seed all RNGs, add the corresponding tests (closes the two `high` data-ml findings + the two `high` quality-engineer findings).
  - **PR (b) — experiment-tracking:** integrate MLflow with `start_run` + `log_params` + per-epoch `log_metrics` + checkpoint via `log_artifact` (closes the two observability findings + the data-ml `medium` tracking finding).

  Do not propose a structural redesign; the structure is right for the phase, and the team should focus on filling the experimental-rigor layer over the next two PRs rather than re-architecting.

#### Stage handoff notes

The lower-stage findings (peer-python-reviewer's `print()`, team-data-ml-reviewer's split + seed, team-performance-reviewer's `num_workers` + zero_grad + autocast, team-observability-reviewer's structured-logging + tracking) are all at the right altitude — code idioms, ML correctness, throughput, operability. None of them are architectural at the altitude I operate at. My single finding is: the structure is sound but the experimental-rigor layer (tracking, checkpointing, baseline comparison) is missing — and that's a phase-2 concern, not a redesign. For the PM (lead-project-manager): the data-ml findings directly falsify two of the four stated success criteria; I expect the PM to grade alignment low and recommend `hold`, which is the right call from that lens. For the Aggregator: the headline takeaway is "structure right, experimental rigor missing — fix the seeds and split before this becomes a baseline you can compare against."

### lead-project-manager (claude-opus-4-7)

**Verdict:** block · **Score:** 4/10

> Aim alignment: 4/10. Scope: on-scope. Verdict: hold. PR is foundationally aimed at the goal but regresses 3 of 4 stated success criteria (reproducibility, no-leakage split, metric logging) — fix before ship.

#### Findings

**[high] Phase scope is on-target but two of four stated success criteria are falsified by the code; "baseline" cannot ship until reproducibility and split criteria are addressed**

- **Category:** aim-alignment
- **Location:** `tests/fixtures/pytorch-trainer/.review/aims.md:10-14`
- **Explanation:**

  ```
  Aim alignment: 4/10
  Scope: on-scope
  Verdict: hold
  ```

  **Memo:**

  The phase scope is correctly narrow — baseline MLP, single-GPU, no hyperparameter search. The PR stays in scope and respects every stated non-goal (no distributed training, no hyperparameter search, no model serving). The Goal line ("Train a baseline MLP on tabular data with reproducible runs and trustworthy metrics") is well-aimed by the diff — the work is in the right files and the right shape.

  However, two of the four stated success criteria are falsified directly by the current code, and a third is partially met. "Training is reproducible — two runs with the same config produce identical loss curves" is falsified by the missing seeds (team-data-ml-reviewer's `high` finding at `src/train.py:33`). The DataLoader's `shuffle=True` reshuffles per epoch with no seed; weight init is unseeded; the dataset's `np.random.randn` is unseeded. Two runs of identical config will produce different metrics. "Train/val/test split exists and there is no leakage" is falsified by the `load_full_dataset` design (team-data-ml-reviewer's `high` finding at `src/data.py:29-36`); there is no separation between train, val, and test, so any metric this script could produce is leakage by construction. A third criterion ("Metrics are logged per epoch") is partially met — loss is printed via `print()`, but val metrics aren't computed at all because there is no val set, and the metric record dies with the terminal.

  The fourth criterion ("A test set assessment runs at the end and produces a single accuracy number") cannot be verified because there is no test set. The first three findings cascade into the fourth — without seeds and splits, the very concept of "the test accuracy from this run" is meaningless.

  The structural fixes are small. The team-data-ml-reviewer's seed + split fixes are an afternoon's work for a competent ML engineer (~50 lines of changes across `data.py` and `train.py`, plus the corresponding tests the peer-quality-engineer recommended). They don't require redesigning the pipeline (lead-senior-architect confirms the structure is sound). The throughput fixes (team-performance-reviewer's `num_workers` + `zero_grad` + autocast) compose cleanly with the data-correctness fixes. The observability fixes (team-observability-reviewer's structured logging + MLflow integration) are a separate one-day PR.

  **Definition of done by the user's stated criteria:** this phase is roughly 25% done after this PR — 1 of 4 criteria partial, 3 of 4 untouched-or-falsified.

  **Recommend hold:** cannot ship as a "baseline" when the reproducibility and split criteria are stated and unmet. The data-correctness PR (seed + split + tests) is the highest-leverage single change; once it lands, the project meaningfully has a baseline.

- **Suggestion:** Sequence the next two PRs as:
  - **PR (a) — data-correctness:** seed all RNGs, split the dataset, add the reproducibility test and split-invariants test recommended by peer-quality-engineer (closes 2 of the 3 falsified criteria + 1 of the 2 partials).
  - **PR (b) — telemetry:** structured logging + MLflow integration + per-epoch val metrics (closes the metric-logging criterion + sets up the test-set assessment criterion).

  Defer throughput optimizations (`num_workers`, autocast, zero_grad) to a follow-up — they're not blocking the criteria and shouldn't gate the baseline shipping. Do not merge as "baseline" until at least PR (a) lands.

#### Stage handoff notes

The architect (lead-senior-architect) approved with revisions; that is independent of alignment grading and reflects the structural shape, not the criteria fulfillment. Aims are explicit and well-captured for this fixture — the user clearly stated reproducibility and split criteria. No rescoping recommended; the phase is correctly narrow and the work is in the right place. If the user wants to ship before the data-correctness fixes, they should update `aims.md` to weaken the "reproducible" and "no leakage" criteria (e.g., "exploratory baseline; reproducibility and rigor in next phase") so the alignment grade reflects the revised intent. The throughput findings from team-performance-reviewer are real but downstream of the criteria — they affect the "30 minute" constraint, not the success criteria, and shouldn't block this PR.

## Aims Snapshot

```markdown
# Project Aims
_Generated by Crucible on 2026-05-10._

## What this project is
A small PyTorch training pipeline exploring a tabular classification baseline.
The user is iterating on architecture and hyperparameters and wants the
pipeline to be reliable enough to compare runs.

## Goal
Train a baseline MLP on tabular data with reproducible runs and trustworthy
metrics.

## Success criteria
- Training is reproducible — two runs with the same config produce identical
  loss curves.
- Train / val / test split exists and there is no leakage.
- Metrics are logged per epoch.
- A test set assessment runs at the end and produces a single accuracy number.

## Non-goals / out of scope
- Distributed training (single GPU is fine)
- Hyperparameter search (grid / Bayesian)
- Model serving / inference deployment

## Tech stack (detected)
- **Languages:** python
- **Frameworks:** torch, numpy
- **Datastores:** none (in-memory data)
- **Deployment:** local-only

## Project type
ml-pipeline

## Constraints
- Single-GPU desktop (RTX 4070 Super)
- Training run must complete in under 30 minutes for the baseline

---
_Last refreshed: 2026-05-10T14:30:00Z_
```

## Run Metadata

- **Plugin version:** 0.1.0
- **Wall-clock:** 285s (4m 45s)
- **Models used:** claude-sonnet-4-6, claude-haiku-4-5-20251001, claude-opus-4-7
- **Estimated cost:** $0.69
