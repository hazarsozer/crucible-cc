"""Trivial smoke test for the training script.

Quality engineer should flag the absence of meaningful tests.
"""
from src.model import MLP


def test_model_constructs() -> None:
    m = MLP(input_dim=32, hidden_dim=128, output_dim=10)
    assert m is not None
