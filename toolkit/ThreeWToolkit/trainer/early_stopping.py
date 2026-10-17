from typing import Literal

import torch
from pydantic import BaseModel, Field, PrivateAttr


class EarlyStoppingConfig(BaseModel):
    """Configuration for validation-based early stopping."""

    patience: int = Field(default=5, ge=1, description="Epochs without improvement.")
    min_delta: float = Field(
        default=0.0, ge=0, description="Minimum validation-loss improvement."
    )
    mode: Literal["min", "max"] = Field(
        default="min", description="Whether lower or higher values are better."
    )
    restore_best_weights: bool = Field(
        default=True, description="Restore model weights from the best epoch."
    )
    _target: type = PrivateAttr(default_factory=lambda: EarlyStopping)


class EarlyStopping:
    """Track a metric and stop training after prolonged non-improvement."""

    def __init__(self, config: EarlyStoppingConfig):
        self.config = config
        self.best_value: float | None = None
        self.bad_epochs = 0
        self.best_state: dict[str, torch.Tensor] | None = None

    def step(self, value: float, model: torch.nn.Module) -> bool:
        """Record a metric and return whether training should stop."""
        improved = self.best_value is None or (
            value < self.best_value - self.config.min_delta
            if self.config.mode == "min"
            else value > self.best_value + self.config.min_delta
        )
        if improved:
            self.best_value = value
            self.bad_epochs = 0
            if self.config.restore_best_weights:
                self.best_state = {
                    key: tensor.detach().cpu().clone()
                    for key, tensor in model.state_dict().items()
                }
        else:
            self.bad_epochs += 1
        return self.bad_epochs >= self.config.patience

    def restore(self, model: torch.nn.Module) -> None:
        """Restore the best model weights, when available."""
        if self.best_state is not None:
            model.load_state_dict(self.best_state)
