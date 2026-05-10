"""Training entry point for the toy MLP.

Deliberately broken in places — see fixture README.
- No random seed set (reproducibility gap).
- DataLoader has no num_workers.
- optimizer.zero_grad() called without set_to_none=True (perf nit).
"""
from __future__ import annotations

from pathlib import Path

import torch
import yaml
from torch import nn, optim
from torch.utils.data import DataLoader

from src.data import load_full_dataset
from src.model import MLP


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def make_model(cfg: dict) -> MLP:
    return MLP(
        input_dim=cfg["input_dim"],
        hidden_dim=cfg["hidden_dim"],
        output_dim=cfg["output_dim"],
    )


def train(cfg_path: str = "configs/default.yaml") -> None:
    cfg = load_config(Path(cfg_path))

    # BAD: no random seed for python / numpy / torch / cuda. Two runs of this
    # script will produce different metrics. The Data/ML persona should flag
    # this loudly as a reproducibility gap.

    dataset = load_full_dataset()

    # BAD: DataLoader has no num_workers. With a real dataset this means
    # the GPU is idle while the CPU is loading the next batch.
    loader = DataLoader(dataset, batch_size=cfg["batch_size"], shuffle=True)

    model = make_model(cfg)
    optimizer = optim.Adam(model.parameters(), lr=cfg["learning_rate"])
    criterion = nn.CrossEntropyLoss()

    for epoch in range(cfg["epochs"]):
        running_loss = 0.0
        for batch_x, batch_y in loader:
            # BAD: zero_grad() without set_to_none=True allocates fresh zero
            # tensors instead of just clearing pointers — small per-step waste
            # that adds up over a long training run.
            optimizer.zero_grad()

            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        avg = running_loss / len(loader)
        print(f"epoch {epoch + 1}/{cfg['epochs']}: loss={avg:.4f}")

    print("training complete")


if __name__ == "__main__":
    train()
