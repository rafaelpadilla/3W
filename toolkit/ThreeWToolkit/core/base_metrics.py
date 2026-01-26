import numpy as np
import pandas as pd

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class BaseScoreArgsValidator(BaseModel):
    y_true: np.ndarray | pd.Series | list
    y_pred: np.ndarray | pd.Series | list
    sample_weight: np.ndarray | pd.Series | list | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("y_true", "y_pred", "sample_weight", mode="before")
    @classmethod
    def check_array_like(cls, value, info):
        if info.field_name == "sample_weight" and value is None:
            return value
        if not isinstance(value, (np.ndarray, pd.Series, list)):
            raise TypeError(
                f"'{info.field_name}' must be a np.ndarray, pd.Series or list, got {type(value)}"
            )
        return value

    @model_validator(mode="after")
    def check_shapes(self):
        ytrue_size = len(self.y_true)
        ypred_size = len(self.y_pred)

        if ytrue_size != ypred_size:
            raise ValueError(
                f"'y_true' and 'y_pred' must have the same number of elements "
                f"(received: {ytrue_size} and {ypred_size})"
            )
        if self.sample_weight is not None:
            sample_weight_size = len(self.sample_weight)
            if sample_weight_size != ytrue_size:
                raise ValueError(
                    f"'sample_weight' must have the same number of elements as 'y_true' "
                    f"(received: {sample_weight_size} and {ytrue_size})"
                )
        return self


class LabelsValidator(BaseModel):
    labels: list | None = None

    @field_validator("labels", mode="before")
    @classmethod
    def check_labels(cls, value):
        if value is not None and not isinstance(value, list):
            raise TypeError(f"'labels' must be a list or None, got {type(value)}")
        return value


class PosLabelValidator(BaseModel):
    pos_label: int = 1

    @field_validator("pos_label", mode="before")
    @classmethod
    def check_pos_label(cls, value):
        if not isinstance(value, (int, float)) and value is not None:
            raise TypeError(f"'pos_label' must be a number or None, got {type(value)}")
        return value


class AverageValidator(BaseModel):
    average: str | None = "binary"

    @field_validator("average", mode="before")
    @classmethod
    def check_average(cls, value):
        allowed = {"micro", "macro", "samples", "weighted", "binary", None}
        if value not in allowed:
            raise ValueError(f"'average' must be one of {allowed}, got '{value}'")
        return value


class ZeroDivisionValidator(BaseModel):
    zero_division: str | int = "warn"

    @field_validator("zero_division", mode="before")
    @classmethod
    def check_zero_division(cls, value):
        allowed = {"warn", 0, 1}
        if value not in allowed:
            raise ValueError(f"'zero_division' must be one of {allowed}, got '{value}'")
        return value


class AccuracyScoreConfig(BaseScoreArgsValidator):
    normalize: bool = True

    @field_validator("normalize", mode="before")
    @classmethod
    def check_bool(cls, value):
        if not isinstance(value, bool):
            raise TypeError(
                f"'normalize' must be a boolean, got {type(value)} with value '{value}'"
            )
        return value


class BalancedAccuracyScoreConfig(BaseScoreArgsValidator):
    adjusted: bool = False

    @field_validator("adjusted", mode="before")
    @classmethod
    def check_bool(cls, value):
        if not isinstance(value, bool):
            raise TypeError(
                f"'adjusted' must be a boolean, got {type(value)} with value '{value}'"
            )
        return value


class AveragePrecisionScoreConfig(
    BaseScoreArgsValidator, AverageValidator, PosLabelValidator
):
    @field_validator("average", mode="before")
    @classmethod
    def override_average_options(cls, value):
        allowed = {"micro", "macro", "samples", "weighted", None}
        if value not in allowed:
            raise ValueError(f"'average' must be one of {allowed}, got '{value}'")
        return value


class MultiClassValidator(BaseModel):
    multi_class: str = "raise"

    @field_validator("multi_class", mode="before")
    @classmethod
    def check_multi_class(cls, value):
        allowed = {"raise", "ovr", "ovo"}
        if value not in allowed:
            raise ValueError(f"'multi_class' must be one of {allowed}, got '{value}'")
        return value


class MaxFprValidator(BaseModel):
    max_fpr: float | None = None

    @field_validator("max_fpr", mode="before")
    @classmethod
    def check_max_fpr(cls, value):
        if value is not None and (
            not isinstance(value, (int, float)) or not (0 < value <= 1)
        ):
            raise ValueError(
                f"'max_fpr' must be a float in the range (0, 1], got {value}"
            )
        return value


class PrecisionScoreConfig(
    BaseScoreArgsValidator,
    LabelsValidator,
    PosLabelValidator,
    AverageValidator,
    ZeroDivisionValidator,
):
    pass


class RecallScoreConfig(
    BaseScoreArgsValidator,
    LabelsValidator,
    PosLabelValidator,
    AverageValidator,
    ZeroDivisionValidator,
):
    pass


class F1ScoreConfig(
    BaseScoreArgsValidator,
    LabelsValidator,
    PosLabelValidator,
    AverageValidator,
    ZeroDivisionValidator,
):
    pass


class RocAucScoreConfig(
    BaseScoreArgsValidator,
    AverageValidator,
    MaxFprValidator,
    MultiClassValidator,
    LabelsValidator,
):
    @field_validator("average", mode="before")
    @classmethod
    def override_average_options(cls, value):
        allowed = {"micro", "macro", "samples", "weighted", None}
        if value not in allowed:
            raise ValueError(f"'average' must be one of {allowed}, got '{value}'")
        return value


class MultiOutputValidator(BaseModel):
    multioutput: str = "uniform_average"

    @field_validator("multioutput", mode="before")
    @classmethod
    def check_multioutput(cls, value):
        allowed = {"raw_values", "uniform_average", "variance_weighted"}
        if value not in allowed:
            raise ValueError(f"'multioutput' must be one of {allowed}, got '{value}'")
        return value


class ForceFiniteValidator(BaseModel):
    force_finite: bool = True

    @field_validator("force_finite", mode="before")
    @classmethod
    def check_force_finite(cls, value):
        if not isinstance(value, bool):
            raise TypeError(f"'force_finite' must be a boolean, got {type(value)}")
        return value


class ExplainedVarianceScoreConfig(
    BaseScoreArgsValidator, MultiOutputValidator, ForceFiniteValidator
):
    pass
