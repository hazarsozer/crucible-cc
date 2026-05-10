# pytorch-trainer fixture

Synthetic PyTorch training pipeline for Crucible E2E tests. **Deliberately contains issues** so the persona library has something to find.

## Deliberate gaps

- `src/train.py` — no random seed set (reproducibility gap)
- `src/train.py` — DataLoader has no `num_workers` (slow training)
- `src/train.py` — `optimizer.zero_grad()` called without `set_to_none=True` (perf gap)
- `src/data.py` — no train/val/test split (data integrity gap)
- `src/model.py` — uses deprecated `torch.no_grad()` as decorator
- No experiment tracking, no metric logging
