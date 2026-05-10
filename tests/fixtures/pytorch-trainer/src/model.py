"""Tiny MLP for the fixture.

Deliberately broken in places — see fixture README.
"""
from __future__ import annotations

import torch
from torch import nn


class MLP(nn.Module):
    """Plain MLP with two hidden layers."""

    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# BAD: torch.no_grad() as a decorator on an instance method is the deprecated /
# easy-to-misuse pattern. It works, but the modern approach is `with torch.inference_mode():`
# inside the function body, which is faster and clearer about intent.
@torch.no_grad()
def predict(model: MLP, x: torch.Tensor) -> torch.Tensor:
    """Run the model on x without autograd."""
    model.train(False)  # set to inference mode without using the .eval() shorthand
    return model(x).argmax(dim=-1)
