import pytest
import torch
from ThreeWToolkit.trainer import EarlyStopping, EarlyStoppingConfig


class TestEarlyStopping:
    def test_stops_after_patience(self):
        stopping = EarlyStopping(EarlyStoppingConfig(patience=2))
        model = torch.nn.Linear(1, 1)

        assert not stopping.step(1.0, model)
        assert not stopping.step(1.1, model)
        assert stopping.step(1.2, model)

    def test_restores_best_weights(self):
        stopping = EarlyStopping(EarlyStoppingConfig(patience=2))
        model = torch.nn.Linear(1, 1)
        stopping.step(1.0, model)
        best_weight = model.weight.detach().clone()
        with torch.no_grad():
            model.weight.add_(1.0)

        stopping.restore(model)

        assert torch.equal(model.weight, best_weight)

    def test_rejects_negative_settings(self):
        with pytest.raises(ValueError):
            EarlyStoppingConfig(patience=-1)
