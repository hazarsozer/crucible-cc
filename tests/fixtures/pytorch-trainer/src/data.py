"""Tabular dataset loader.

Deliberately broken — no train/val/test split. See fixture README.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


class TabularDataset(Dataset):
    """A toy synthetic tabular dataset."""

    def __init__(self, n_samples: int = 10_000, input_dim: int = 32, n_classes: int = 10) -> None:
        # Synthetic features and labels for the fixture.
        self.x = np.random.randn(n_samples, input_dim).astype(np.float32)
        self.y = np.random.randint(0, n_classes, size=n_samples).astype(np.int64)

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        return torch.from_numpy(self.x[idx]), torch.tensor(self.y[idx])


def load_full_dataset(path: Path | None = None) -> TabularDataset:
    """Returns the entire dataset.

    BAD: there is no train / val / test split here. The training script
    feeds the same data to fit and (would have to) eval. The Data/ML
    persona should flag this as a leakage / integrity gap.
    """
    return TabularDataset()
