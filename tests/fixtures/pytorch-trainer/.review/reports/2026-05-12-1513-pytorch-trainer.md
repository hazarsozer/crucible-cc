# Crucible Review — pytorch-trainer

_Review ID: 2026-05-12-1513-pytorch-trainer · Generated: 2026-05-12T15:13:43+00:00 · Project: ml-pipeline (python, yaml / pytorch, numpy)_

---

## Verdict

**BLOCKED — 3.0/10**

The pipeline regresses three of four stated success criteria from aims.md: no seeding anywhere (reproducibility falsified), `load_full_dataset` returns the entire dataset with no train/val/test partition (every metric is leakage by construction), and `train.py` exits without a test-set evaluation. `team-data-ml-reviewer` returned block (score 3) and `lead-project-manager` returned block with aim alignment 2/10; `lead-senior-architect` frames these as symptoms of a missing Experiment boundary. `peer-quality-engineer`'s block (score 2) is the test-side mirror. The fixes are surgical (~55 lines) but the current shape cannot produce a trustworthy metric.

---

## Executive Summary

Full-project review of a small PyTorch tabular-classification trainer (`src/train.py`, `src/model.py`, `src/data.py`, `tests/test_train.py`, `configs/default.yaml`). The user's stated goal is a reproducible baseline MLP with trustworthy train/val/test metrics; distributed training, hyperparameter search, and serving are explicit non-goals.

The code that exists is small, structurally clean, and largely idiomatic Python. `team-security-reviewer` found no real attack surface (`yaml.safe_load` is used correctly, no secrets, no network calls). `peer-readability-engineer` flagged that the structure is small with no deep nesting or long functions, and `team-performance-reviewer` noted that the dominant perf gaps (`num_workers=0`, `zero_grad` without `set_to_none`, per-getitem tensor conversion) are mechanical one-line fixes.

The block is on aim alignment, not code quality. Three of four stated success criteria are unmet by construction: no random seeds are set anywhere (different loss curves each run); `load_full_dataset` returns the entire dataset with no held-out partition (every metric is in-sample fit); and `train.py` prints train loss only — no val loss per epoch, no persistent metric log, no test-set accuracy at exit. `lead-senior-architect` frames these as four symptoms of a missing Experiment boundary, and `lead-project-manager` grades aim alignment at 2/10 with the recommendation to block-and-rescope around ~55 lines of surgical changes. The performance fixes should sequence after the reproducibility work.

---

## What's Good

- Security surface is clean — `team-security-reviewer` found `yaml.safe_load` used correctly, no secrets, no PII, no network calls; only a speculative medium on `cfg_path` validation.
- Code structure is small and readable — `peer-readability-engineer` reports no deep nesting, no long functions, and a structurally clean codebase whose main flaw is naming that masks intentional gaps.
- Identified performance gaps are mechanical one-line fixes — `num_workers`, `set_to_none=True`, and pre-converting dataset tensors at construction are all surgical changes per `team-performance-reviewer`.
- The aims document is well-captured and unambiguous — `lead-project-manager` confirms the rescope is about pipeline contents, not drifted user intent.

---

## What's Concerning

- **Reproducibility falsified:** no seeds are set anywhere (Python random, numpy, torch, cuda, DataLoader generator all unseeded) — two runs with the same config produce different loss curves. (`src/train.py:33-37`, `src/data.py:13-17`)
- **Data leakage by construction:** `load_full_dataset` returns the entire dataset with no train/val/test partition, so every accuracy number reported is pure in-sample fit. (`src/data.py:29-36`)
- **Test-set evaluation never runs** — `train.py` exits after the training loop with no `test_loader` pass and no final accuracy number. (`src/train.py:55-66`)
- **Per-epoch metric logging is partial and ephemeral:** only train loss is printed via `print()`, no val loss is computed, and no run artifact is persisted. (`src/train.py:47-50, 55-66`)
- **Test suite is effectively absent:** the single existing assertion checks that MLP can be instantiated; the training loop, data pipeline, reproducibility contract, and split integrity have zero coverage — `peer-quality-engineer` returned block (score 2).
- **Architectural shape blocks the fixes:** `lead-senior-architect` notes there is no Experiment boundary owning seeding, splits, and evaluation in one place, and no testable seams for the tests the QA reviewer wants to write.

---

## Key Notes

📋 **lead-project-manager:** "Aim alignment: 2/10. Pipeline regresses 3 of 4 stated success criteria — no seeds, no split, no per-epoch metrics file, no test final-accuracy. Nothing it produces can be trusted."

🤖 **team-data-ml-reviewer:** "Project aims commit to reproducibility and no-leakage splits; code falsifies both. No train/val/test split (every metric is leakage), no seeds anywhere (runs are not comparable), and no val loss logged. No metric this script produces can be trusted."

🏗️ **lead-senior-architect:** "Pipeline has no experiment boundary (no seed, no split, no eval, no metric log) and no testable seams; the aims' success criteria are structurally unreachable from this shape. Recommend introducing an Experiment/Split/Tracker boundary before further iteration."

👨‍💻 **peer-quality-engineer:** "The test suite contains exactly one assertion — that MLP can be instantiated — leaving the training loop, data pipeline, reproducibility contract, and all success criteria completely untested."

⚡ **team-performance-reviewer:** "DataLoader with num_workers=0 leaves the GPU idle during every batch load — the dominant throughput bottleneck for the 30-minute wall-clock constraint. Both this and zero_grad without set_to_none=True are mechanical one-line fixes."

📋 **lead-project-manager:** "Performance findings are off-aim relative to the missing reproducibility and split work. Sequence: reproducibility + split + test accuracy first; metrics persistence second; defer perf nits to follow-up."

---

## Stage Reports

### Stage 1 — Peer Code Review

| Persona | Score | Verdict |
|---|---|---|
| peer-python-reviewer | 6/10 | concerns |
| peer-quality-engineer | 2/10 | block |
| peer-readability-engineer | 7/10 | concerns |

**peer-python-reviewer** (6/10 · concerns)

> "Production-like function uses print() for metrics; inference helper uses deprecated torch.no_grad() decorator; TabularDataset reinitializes random state on every instantiation, breaking reproducibility."

- **[medium]** `src/train.py:54` — Use `logging` instead of `print()` for epoch metrics in reusable `train()` function
- **[medium]** `src/model.py:21` — Use `torch.inference_mode()` context manager instead of `@torch.no_grad()` decorator
- **[medium]** `src/data.py:13-17` — `TabularDataset` reinitializes random state on every instantiation, breaking reproducibility
- **[low]** `src/model.py:27` — Use `.eval()` shorthand instead of `model.train(False)`

---

**peer-quality-engineer** (2/10 · block)

> "The test suite contains exactly one assertion — that MLP can be instantiated — leaving the training loop, data pipeline, reproducibility contract, and all success criteria completely untested."

- **[critical]** `src/train.py:1-58` — Reproducibility criterion has zero test coverage; no test verifies two identical runs produce the same loss curve
- **[critical]** `src/data.py:29-32` — Train/val/test split criterion has zero test coverage; no test asserts split existence or zero leakage
- **[high]** `src/train.py:27-54` — The training loop has no test of any kind
- **[high]** `src/train.py:47-50` — Per-epoch metric logging and final test-set accuracy are untested stated success criteria
- **[medium]** `tests/test_train.py:6-8` — Only existing test asserts `not None` rather than verifying any behavioral contract
- **[medium]** `src/data.py:18-19` — `TabularDataset` uses unseeded numpy random calls, making every test non-deterministic

---

**peer-readability-engineer** (7/10 · concerns)

> "load_full_dataset() name obscures missing split; train() lacks docstring; function names mask incomplete responsibility."

- **[high]** `src/data.py:23` — `load_full_dataset()` name obscures missing train/val/test split responsibility
- **[high]** `src/train.py:30` — `train()` function lacks docstring and hides multiple concerns
- **[medium]** `src/train.py:21` — `make_model()` is a thin wrapper; consider inlining or naming more precisely
- **[medium]** `src/data.py:10` — `TabularDataset` name should signal synthetic data generation
- **[low]** `src/model.py:23` — `predict()` helper has no context about when to use it

---

### Stage 2 — Cross-functional Review

| Persona | Score | Verdict |
|---|---|---|
| team-security-reviewer | 7/10 | concerns |
| team-data-ml-reviewer | 3/10 | block |
| team-performance-reviewer | 5/10 | concerns |

**team-security-reviewer** (7/10 · concerns)

> "yaml.safe_load used correctly; no secrets. Medium: cfg_path unvalidated, enabling arbitrary file read if ever user-controlled."

- **[medium]** `src/train.py:11-12` — `cfg_path` accepted without validation; path traversal risk if caller ever supplies user-controlled input. Suggest: resolve the path and assert `is_relative_to(Path('configs').resolve())` before reading.

---

**team-data-ml-reviewer** (3/10 · block)

> "No split (all metrics are leakage), no seeds (runs not comparable), no val loss. Nothing this script produces can be trusted."

- **[high]** `src/data.py:29-36` — `load_full_dataset` returns entire dataset with no split; every metric is leakage by construction. Suggest: replace with `load_splits()` returning `(train_ds, val_ds, test_ds)` using `train_test_split` with `stratify=y` and a fixed seed.
- **[high]** `src/train.py:33-37` — No random seed set anywhere; two runs with identical config produce different metrics. Suggest: add `set_seed(cfg['seed'])` helper seeding Python random, numpy, torch, and cuda; add `seed: 42` to config.
- **[high]** `src/train.py:55-66` — No validation loss computed or logged per epoch; overfitting is invisible. Suggest: add val_loader pass per epoch, log train_loss and val_loss, add early stopping, run test_loader once at end for final accuracy.
- **[medium]** `src/train.py:33-72` — No experiment tracking; metrics exist only in terminal scrollback. Suggest: add MLflow with local file backend (`mlflow.log_params(cfg)`, `mlflow.log_metrics` per epoch, `tracking_uri='file:./mlruns'`).

---

**team-performance-reviewer** (5/10 · concerns)

> "DataLoader num_workers=0 leaves GPU idle each batch — dominant bottleneck for 30-min constraint."

- **[high]** `src/train.py:33` — `DataLoader` `num_workers=0` serializes CPU loading with GPU compute. Suggest: add `num_workers=cfg.get('num_workers', 2), pin_memory=True` to DataLoader.
- **[medium]** `src/train.py:41` — `optimizer.zero_grad()` without `set_to_none=True` allocates unnecessary zero tensors each step. Suggest: `optimizer.zero_grad(set_to_none=True)` — one-character change, no correctness risk.
- **[medium]** `src/data.py:18-19` — `TabularDataset` converts numpy to tensors on every `__getitem__` call. Suggest: construct `self.x = torch.randn(n_samples, input_dim)` and `self.y = torch.randint(0, n_classes, (n_samples,))` directly in `__init__`.

---

### Stage 3 — Leadership

| Persona | Score | Verdict |
|---|---|---|
| lead-senior-architect | 4/10 | concerns |
| lead-project-manager | 2/10 | block |

**lead-senior-architect** (4/10 · concerns)

> "Pipeline has no Experiment boundary; aims' success criteria are structurally unreachable from this shape."

- **[high]** `src/train.py:22-41` — Pipeline has no Experiment boundary — reproducibility, split, and evaluation are concerns with no owner. All Stage 2 ML findings are symptoms of this single missing boundary. Suggest: introduce `src/experiment.py` with `Experiment(cfg, seed, tracker)` owning `prepare()`, `fit()`, and `evaluate()`. `train.py` becomes a 10-line entry point.
- **[medium]** `tests/test_train.py:1-6` — No testable seams — every aims criterion can only be exercised via the full training run. Suggest: name seams for the tests they enable: `make_splits` (disjointness), `seed_everything` (determinism), `InMemoryTracker` (metric emission), `evaluate()` (float-in-range).
- **[low]** `src/train.py:18-30` — Config schema is implicit — `cfg['key']` reads at multiple call sites with no validation. Suggest: add `src/config.py` with `pydantic.BaseModel` `ExperimentConfig` validated at YAML load time.

---

**lead-project-manager** (2/10 · block)

> "Aim alignment: 2/10. Verdict: rescope. Nothing it produces can be trusted."

- **[critical]** `.review/aims.md:9-14` — Pipeline regresses three of four stated success criteria. Per-criterion: (a) reproducibility — REGRESSED; (b) split/no-leakage — REGRESSED; (c) per-epoch metrics — PARTIAL; (d) test accuracy — NOT TOUCHED. Fix is ~55 lines across three surgical changes.
- **[medium]** `.review/aims.md:19-21` — Performance findings are off-aim relative to missing reproducibility and split work. Sequence: reproducibility + split + test accuracy first; perf nits after.

---

## Aims Snapshot

> A small PyTorch training pipeline exploring a tabular classification baseline. Goal: train a baseline MLP on tabular data with reproducible runs and trustworthy metrics.
>
> **Success criteria:** reproducibility (identical loss curves across runs), train/val/test split with no leakage, per-epoch metric logging, final test accuracy number.
>
> **Non-goals:** distributed training, hyperparameter search, model serving.

---

## Committee

**Stage 1:** peer-python-reviewer, peer-quality-engineer, peer-readability-engineer

**Stage 2:** team-security-reviewer, team-data-ml-reviewer, team-performance-reviewer

**Stage 3:** lead-senior-architect, lead-project-manager

_Models used: claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-7 · Plugin: v0.1.0_
