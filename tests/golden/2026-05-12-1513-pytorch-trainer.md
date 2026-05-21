# Crucible Review — pytorch-trainer

_Review ID: 2026-05-12-1513-pytorch-trainer · Generated: 2026-05-12T15:13:43+00:00 · Project: ml-pipeline (python, yaml / pytorch, numpy)_

---

## Verdict

**BLOCKED — 3.0/10**

The pipeline regresses three of four stated success criteria from aims.md: no seeding anywhere (reproducibility falsified), load_full_dataset returns the entire dataset with no train/val/test partition (every metric is leakage by construction), and train.py exits without a test-set evaluation. team-data-ml-reviewer returned block (score 3) and lead-project-manager returned block with aim alignment 2/10; lead-senior-architect frames these as symptoms of a missing Experiment boundary. peer-quality-engineer's block (score 2) is the test-side mirror. The fixes are surgical (~55 lines) but the current shape cannot produce a trustworthy metric.

---

## Executive Summary

Full-project review of a small PyTorch tabular-classification trainer. Goal: reproducible baseline MLP with trustworthy metrics.

The code is small, structurally clean, and largely idiomatic Python. team-security-reviewer found no real attack surface. peer-readability-engineer notes no deep nesting or long functions. team-performance-reviewer notes dominant perf gaps are mechanical one-line fixes.

The block is on aim alignment, not code quality. Three of four stated success criteria are unmet by construction: no random seeds set anywhere (different loss curves each run), load_full_dataset returns entire dataset with no held-out partition (every metric is in-sample fit), and train.py prints train loss only with no test-set accuracy at exit. lead-senior-architect frames these as four symptoms of a missing Experiment boundary. lead-project-manager grades aim alignment at 2/10 and recommends block-and-rescope (~55 lines: seeding utility, load_splits, test-set pass). Performance fixes should sequence after reproducibility work.

---

## What's Good

- Security surface is clean — yaml.safe_load used correctly, no secrets, no PII, no network calls.
- Code structure is small and readable — no deep nesting, no long functions, structurally clean.
- Identified performance gaps are mechanical one-line fixes — num_workers, set_to_none=True, tensor pre-conversion.
- The aims document is well-captured and unambiguous.

---

## What's Concerning

- Reproducibility falsified: no seeds set anywhere — two runs with the same config produce different loss curves.
- Data leakage by construction: load_full_dataset returns entire dataset with no split; every metric is in-sample fit.
- Test-set accuracy never computed — train.py exits after training with no test_loader pass.
- Per-epoch metric logging is partial and ephemeral: only train loss printed, no val loss, no persistent artifact.
- Test suite effectively absent: single test asserts MLP constructs; all success criteria have zero coverage.
- Architectural shape blocks fixes: no Experiment boundary owning seeding, splits, and evaluation in one place.

---

## Key Notes

📋 **lead-project-manager:** "Aim alignment: 2/10. Pipeline regresses 3 of 4 stated success criteria — no seeds, no split, no per-epoch metrics file, no test final-accuracy. Nothing it produces can be trusted."

🤖 **team-data-ml-reviewer:** "Project aims commit to reproducibility and no-leakage splits; code falsifies both. No train/val/test split (every metric is leakage), no seeds anywhere (runs are not comparable), and no val loss logged."

🏗️ **lead-senior-architect:** "Pipeline has no experiment boundary (no seed, no split, no eval, no metric log) and no testable seams; the aims' success criteria are structurally unreachable from this shape."

👨‍💻 **peer-quality-engineer:** "The test suite contains exactly one assertion — that MLP can be instantiated — leaving the training loop, data pipeline, reproducibility contract, and all success criteria completely untested."

⚡ **team-performance-reviewer:** "DataLoader with num_workers=0 leaves the GPU idle during every batch load — the dominant throughput bottleneck for the 30-minute wall-clock constraint."

📋 **lead-project-manager:** "Performance findings are off-aim relative to the missing reproducibility and split work. Sequence: reproducibility + split + test accuracy first; perf nits after."

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

- **[medium]** `src/train.py:54-55` — Use logging instead of print() for epoch metrics in reusable train() function
- **[medium]** `src/model.py:21` — Use torch.inference_mode() context manager instead of @torch.no_grad() decorator
- **[medium]** `src/data.py:13-17` — TabularDataset reinitializes random state on every instantiation, breaking reproducibility
- **[low]** `src/model.py:27` — Use .eval() shorthand instead of model.train(False) for clarity

---

**peer-quality-engineer** (2/10 · block)

> "The test suite contains exactly one assertion — that MLP can be instantiated — leaving the training loop, data pipeline, reproducibility contract, and all success criteria completely untested. The aims state reproducibility and split integrity as the core goals; neither has a single test."

- **[critical]** `src/train.py:1-58` — Reproducibility is the primary success criterion and has zero test coverage; no test verifies two identical runs produce the same loss curve
- **[critical]** `src/data.py:29-32` — Train/val/test split is a stated success criterion; load_full_dataset returns no split and there is no test asserting split existence or zero leakage
- **[high]** `src/train.py:27-54` — The training loop has no test of any kind; epoch loss logging, optimizer step, and forward pass are all untested code paths
- **[high]** `src/train.py:47-50` — Per-epoch metric logging and final test-set accuracy are stated success criteria with no corresponding assertion in the suite
- **[medium]** `tests/test_train.py:6-8` — The only existing test asserts result is not None rather than verifying any behavioral contract of MLP
- **[medium]** `src/data.py:18-19` — TabularDataset uses unseeded numpy random calls at construction time, making every test that touches data non-deterministic

---

**peer-readability-engineer** (7/10 · concerns)

> "load_full_dataset() returns entire dataset with no train/val/test split; train() lacks random seed and docstring; function names mask incomplete responsibility (load_full_dataset should be load_dataset or clarify the 'full' semantic)."

- **[high]** `src/data.py:23` — load_full_dataset() name obscures missing train/val/test split responsibility
- **[high]** `src/train.py:30` — train() function lacks docstring and hides multiple concerns
- **[medium]** `src/train.py:21` — make_model() is a thin wrapper; consider inlining or naming more precisely
- **[medium]** `src/data.py:10` — TabularDataset generates data in __init__; name should signal this is synthetic
- **[low]** `src/model.py:23` — predict() helper in model.py has no context about when to use it

---

### Stage 2 — Cross-functional Review

| Persona | Score | Verdict |
|---|---|---|
| team-security-reviewer | 7/10 | concerns |
| team-data-ml-reviewer | 3/10 | block |
| team-performance-reviewer | 5/10 | concerns |

**team-security-reviewer** (7/10 · concerns)

> "yaml.safe_load is used correctly; no secrets or auth surface present. One medium concern: the config loader silently accepts any YAML file path without validation, enabling arbitrary file reads if cfg_path ever becomes user-controlled."

- **[medium]** `src/train.py:11-12` — cfg_path accepted without validation; arbitrary file read if caller ever supplies user-controlled input

---

**team-data-ml-reviewer** (3/10 · block)

> "Project aims commit to reproducibility and no-leakage splits; code falsifies both. No train/val/test split (every metric is leakage), no seeds anywhere (runs are not comparable), and no val loss logged. No metric this script produces can be trusted."

- **[high]** `src/data.py:29-36` — load_full_dataset returns the entire dataset with no train/val/test split; every reported metric is leakage by construction
- **[high]** `src/train.py:33-37` — No random seed set anywhere; two runs with identical config produce different metrics
- **[high]** `src/train.py:55-66` — No validation loss computed or logged per epoch; overfitting is invisible and the metric logging success criterion is unmet
- **[medium]** `src/train.py:33-72` — No experiment tracking integration; metrics exist only in terminal scrollback and no run record persists

---

**team-performance-reviewer** (5/10 · concerns)

> "DataLoader with num_workers=0 leaves the GPU idle during every batch load — the dominant throughput bottleneck for the 30-minute wall-clock constraint. Zero_grad without set_to_none=True adds avoidable per-step allocation overhead. Both are mechanical one-line fixes."

- **[high]** `src/train.py:33` — DataLoader num_workers=0 serializes CPU data loading with GPU compute, leaving GPU idle each batch
- **[medium]** `src/train.py:41` — optimizer.zero_grad() without set_to_none=True allocates fresh zero tensors every step
- **[medium]** `src/data.py:18-19` — TabularDataset converts numpy arrays to tensors on every __getitem__ call rather than pre-converting at construction time

---

### Stage 3 — Leadership

| Persona | Score | Verdict |
|---|---|---|
| lead-senior-architect | 4/10 | concerns |
| lead-project-manager | 2/10 | block |

**lead-senior-architect** (4/10 · concerns)

> "Decision: pipeline has no experiment boundary (no seed, no split, no eval, no metric log) and no testable seams; the aims' success criteria are structurally unreachable from this shape. Recommend introducing an Experiment/Split/Tracker boundary before further iteration."

- **[high]** `src/train.py:22-41` — Pipeline has no Experiment boundary — reproducibility, split, and evaluation are concerns with no owner
- **[medium]** `tests/test_train.py:1-6` — No testable seams — every aims criterion can only be exercised via the full training run, so the test suite collapses to a smoke test by construction
- **[low]** `src/train.py:18-30` — Config schema is implicit — cfg['key'] reads at multiple call sites with no validation, locking the project into a flat dict shape

---

**lead-project-manager** (2/10 · block)

> "Aim alignment: 2/10. Scope: on-scope. Verdict: rescope. Pipeline regresses 3 of 4 stated success criteria — no seeds, no split, no per-epoch metrics file, no test final-accuracy. Nothing it produces can be trusted."

- **[critical]** `.review/aims.md:9-14` — Pipeline regresses three of four stated success criteria; nothing it produces is trustworthy by the user's own bar
- **[medium]** `.review/aims.md:19-21` — Performance findings are off-aim relative to the missing reproducibility and split work

---

## Aims Snapshot

> A small PyTorch training pipeline for tabular classification. Goal: reproducible runs with trustworthy metrics. Success criteria: reproducibility, train/val/test split (no leakage), per-epoch metrics, final test accuracy number.

---

## Committee

**Stage 1:** peer-python-reviewer, peer-quality-engineer, peer-readability-engineer

**Stage 2:** team-security-reviewer, team-data-ml-reviewer, team-performance-reviewer

**Stage 3:** lead-senior-architect, lead-project-manager

_Models used: claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-7 · Plugin: v0.1.0_
