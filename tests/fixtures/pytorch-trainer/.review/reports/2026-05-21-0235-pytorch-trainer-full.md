# Crucible Review — pytorch-trainer-full

_Review ID: 2026-05-21-0235-pytorch-trainer-full · Generated: 2026-05-21T02:35:41Z · Project: ml-pipeline (python, yaml / pytorch)_

---

## Verdict

**BLOCKED — 3.0/10**

lead-project-manager returns block with a 2/10 aim alignment because three of four stated success criteria are falsified by construction: no seeds anywhere (reproducibility regressed), load_full_dataset returns the entire dataset with no partitioning (no-leakage split regressed), and train() exits without ever running a test-set accuracy pass (final-accuracy criterion not touched). team-data-ml-reviewer independently reaches the same block verdict citing the leakage-by-construction and unseeded non-determinism. lead-senior-architect's finding that no Experiment boundary owns seed/split/metric capture explains why these omissions cluster — the seam they would attach to does not exist. Perf and style findings (num_workers=0, magic config keys, print() vs logging) are real but secondary; doing them before the rescope would optimize a pipeline that does not deliver what the user asked for.

---

## Executive Summary

This is a small PyTorch training pipeline for a tabular MLP baseline. The stated aims are narrow and specific: reproducible runs, a train/val/test split with no leakage, per-epoch metrics, and a single final test-set accuracy number.

The code that exists is short and readable, and the surface-level hygiene is mostly fine — team-security-reviewer found no hardcoded secrets, no injection sinks, and yaml.safe_load is used correctly. The MLP construction and forward pass work, and the configuration file structure is reasonable. None of the reviewers flagged a structural problem with the modeling choices themselves.

The pipeline as written falsifies three of the four stated success criteria. No seeds are set in TabularDataset, the DataLoader, or weight initialization, so two runs with the same config will not produce matching loss curves. load_full_dataset returns the entire dataset with no partitioning, so every metric reported is leakage by construction — the source file's own docstring acknowledges this. train() exits after the loss loop and never computes a test-set accuracy. lead-project-manager grades aim alignment at 2/10 and recommends a rescope PR; lead-senior-architect calls for an Experiment boundary (seed_everything + make_splits + MetricsSink) before the next run is treated as a result. Hold the perf and style work until the three regressed criteria are closed.

---

## What's Good

- yaml.safe_load is used correctly and no hardcoded secrets, injection sinks, or web-surface risks were found — team-security-reviewer cleared everything except schema validation.
- The MLP construction and forward pass are not flagged as incorrect by any reviewer; the modeling code itself works.
- Configuration is externalized to configs/default.yaml rather than hardcoded in train.py, giving a clean attachment point for the Config dataclass the architect recommends.
- Code surface is small and readable enough that the architect's recommended Experiment seam (seed_everything, make_splits, MetricsSink) can be introduced without restructuring the whole codebase.

---

## What's Concerning

- Reproducibility is falsified by construction — no seeds are set in TabularDataset (np.random.randn/randint), the DataLoader (shuffle=True with no generator), or nn.Linear initialization, so two runs with the same config produce different loss curves.
- No train/val/test split exists — src/data.py:36-46 returns the entire dataset via load_full_dataset, meaning every reported metric is leakage and the 'no leakage' aim is unmet.
- Final test-set accuracy is never computed — train() in src/train.py exits after the loss loop with no test-loader pass, so the fourth stated success criterion is not touched at all.
- No Experiment boundary owns seed, split, or metric capture — the architect notes the three aim commitments cluster as omissions because the seam they would attach to does not exist.
- Test coverage cannot detect regressions on any stated criterion — the lone test asserts MLP() is not None and never touches train.py.
- Secondary but real: DataLoader num_workers=0 with pin_memory=False leaves the RTX 4070 Super idle between batches, costing throughput against the 30-minute budget — defer until correctness lands.

---

## Key Notes

📋 **lead-project-manager:** "Aim alignment: 2/10. Pipeline falsifies 3 of 4 stated success criteria (reproducibility, no-leakage split, final test accuracy) — nothing produced can be trusted against the user's own bar."

🤖 **team-data-ml-reviewer:** "Project aims commit to reproducibility and no-leakage splits; code falsifies both. No train/val/test split (every metric is leakage by construction), no seeds anywhere (runs are not comparable). Neither success criterion can be evaluated from the runs this code produces."

🏗️ **lead-senior-architect:** "The pipeline has no Experiment boundary that owns seed, split, and metric capture; aims-stated reproducibility and no-leakage commitments are structurally unreachable without one. Recommend extracting an Experiment seam (Splits + Seeder + MetricsSink) before the next training run is treated as a result."

👨‍💻 **peer-quality-engineer:** "Only one smoke test exists for the entire ML pipeline. Reproducibility (the primary success criterion) is completely untested, the training loop has zero coverage, and the data split gap has no regression fixture."

⚡ **team-performance-reviewer:** "DataLoader num_workers=0 pins CPU-bound data loading to the main thread, leaving the GPU idle between batches — this is the primary throughput bottleneck on a 30-minute budget."

🛡️ **team-security-reviewer:** "YAML config loaded without schema validation. No hardcoded secrets, no injection sinks, no web surface. One medium finding; all else is clean for this lens."

---

## Stage Reports

### Stage 1 — Peer Code Review

| Persona | Score | Verdict |
|---|---|---|
| peer-python-reviewer | 6/10 | concerns |
| peer-quality-engineer | 3/10 | concerns |
| peer-readability-engineer | 6/10 | concerns |

**peer-python-reviewer** (6/10 · concerns)

> "Reusable train() function uses print() for epoch metrics instead of logging; missing type hints on load_config return."

- **[medium]** `src/train.py:61` — Use logging instead of print() for epoch metrics
- **[medium]** `src/train.py:20` — Missing return type annotation on load_config function
- **[medium]** `src/model.py:21` — Bare function predict() outside class should be moved inside MLP
- **[low]** `src/model.py:26` — Use model.eval() instead of model.train(False) for semantic clarity
- **[low]** `src/train.py:43` — Validate config path at function entry for clearer error messages

---

**peer-quality-engineer** (3/10 · concerns)

> "Only one smoke test exists for the entire ML pipeline. Reproducibility is completely untested, the training loop has zero coverage, and the data split gap has no regression fixture."

- **[high]** `src/train.py:28-56` — Training loop, optimizer step, and loss computation are entirely untested
- **[high]** `src/train.py:28-56` — Reproducibility — the primary success criterion — has no test
- **[medium]** `src/data.py:36-46` — Data split absence has no test; train/val/test correctness is unverified
- **[medium]** `tests/test_train.py:8-11` — The only test asserts is not None — it proves nothing about model behavior
- **[low]** `src/data.py:20-24` — No test for non-determinism in TabularDataset

---

**peer-readability-engineer** (6/10 · concerns)

> "Three structural readability issues: magic config keys; deprecated @torch.no_grad() decorator; hollow smoke test."

- **[medium]** `src/train.py:23-35` — Magic config keys scattered across train.py; extract named constants
- **[medium]** `src/model.py:23` — Deprecated @torch.no_grad() decorator obscures inference intent; use context manager
- **[medium]** `tests/test_train.py:6-8` — Test suite is a hollow smoke test with no real assertion substance

---

### Stage 2 — Cross-functional Review

| Persona | Score | Verdict |
|---|---|---|
| team-security-reviewer | 7/10 | concerns |
| team-data-ml-reviewer | 3/10 | block |
| team-performance-reviewer | 5/10 | concerns |

**team-security-reviewer** (7/10 · concerns)

> "YAML config loaded without schema validation. No hardcoded secrets, no injection sinks, no web surface. One medium finding; all else is clean."

- **[medium]** `src/train.py:20-22` — yaml.safe_load used correctly but config dict consumed with no schema validation

---

**team-data-ml-reviewer** (3/10 · block)

> "Project aims commit to reproducibility and no-leakage splits; code falsifies both. No train/val/test split (every metric is leakage by construction), no seeds anywhere (runs are not comparable)."

- **[high]** `src/data.py:36-46` — load_full_dataset returns the entire dataset with no train/val/test split; every reported metric is leakage by construction
- **[high]** `src/train.py:33` — No random seed set anywhere; two runs with the same config produce different metrics
- **[medium]** `src/train.py:57-65` — Only training loss is recorded per epoch; no val loss, so overfitting is invisible
- **[medium]** `src/train.py:33-68` — No experiment tracking integration; metrics exist only in terminal scrollback
- **[low]** `src/model.py:23-29` — predict() uses deprecated decorator pattern and model.train(False) instead of canonical inference-mode pattern

---

**team-performance-reviewer** (5/10 · concerns)

> "DataLoader num_workers=0 pins CPU-bound data loading to the main thread, leaving the GPU idle between batches — the primary throughput bottleneck on a 30-minute budget."

- **[high]** `src/train.py:51` — DataLoader num_workers=0 serialises data loading with forward pass, leaving GPU idle between batches
- **[medium]** `src/data.py:19-20` — TabularDataset regenerates synthetic data on every instantiation rather than pinning the array once
- **[low]** `src/train.py:56` — optimizer.zero_grad() without set_to_none=True allocates zero-filled gradient tensors each step

---

### Stage 3 — Leadership

| Persona | Score | Verdict |
|---|---|---|
| lead-senior-architect | 4/10 | concerns |
| lead-project-manager | 2/10 | block |

**lead-senior-architect** (4/10 · concerns)

> "The pipeline has no Experiment boundary that owns seed, split, and metric capture; aims-stated reproducibility and no-leakage commitments are structurally unreachable without one."

- **[high]** `src/train.py:33-71` — No Experiment boundary owns seed, split, and metric capture — the three aim commitments are scattered as missing concerns across train.py and data.py
- **[medium]** `src/train.py:20-42` — Config is consumed as a raw dict via magic string keys at every callsite — the schema lives implicitly in default.yaml

---

**lead-project-manager** (2/10 · block)

> "Aim alignment: 2/10. Scope: on-scope. Verdict: rescope. Pipeline falsifies 3 of 4 stated success criteria (reproducibility, no-leakage split, final test accuracy) — nothing produced can be trusted against the user's own bar."

- **[critical]** `tests/fixtures/pytorch-trainer/.review/aims.md:9-14` — Pipeline regresses three of four stated success criteria; the work as-shipped cannot satisfy the user's stated bar
- **[high]** `tests/fixtures/pytorch-trainer/.review/aims.md:9-12` — Highest-leverage work is reproducibility + split + final-eval, not the perf optimizations or code-style nits
- **[medium]** `tests/fixtures/pytorch-trainer/.review/aims.md:9-14` — Existing test coverage cannot detect regressions on any stated success criterion

---

## Aims Snapshot

> # Project Aims
> _Generated by Crucible on 2026-05-10._
>
> Train a baseline MLP on tabular data with reproducible runs and trustworthy metrics.
>
> Success criteria:
> - Training is reproducible — two runs with the same config produce identical loss curves.
> - Train / val / test split exists and there is no leakage.
> - Metrics are logged per epoch.
> - A test set evaluation runs at the end and produces a single accuracy number.

---

## Committee

**Stage 1:** peer-python-reviewer, peer-quality-engineer, peer-readability-engineer

**Stage 2:** team-security-reviewer, team-data-ml-reviewer, team-performance-reviewer

**Stage 3:** lead-senior-architect, lead-project-manager

_Models used: claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-7 · Plugin: v0.1.1_
