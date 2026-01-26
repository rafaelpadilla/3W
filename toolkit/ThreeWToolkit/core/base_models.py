from abc import ABC

from pydantic import BaseModel, Field, field_validator

from ..core.enums import ModelTypeEnum


class ModelsConfig(BaseModel):
    model_type: ModelTypeEnum | str = Field(..., description="Type of model to use.")
    random_seed: int | None = Field(42, description="Random seed for reproducibility.")

    @field_validator("model_type")
    @classmethod
    def check_model_type(cls, value, info):
        valid_types = {e for e in ModelTypeEnum}
        valid_strs = {e.value for e in ModelTypeEnum}
        if value is None:
            raise ValueError("model_type is required.")
        if value not in valid_types and value not in valid_strs:
            raise NotImplementedError(f"`model_type` {value} not implemented yet.")
        return value


class BaseModels(ABC):
    def __init__(self, config: ModelsConfig):
        """
        Base model class constructor.

        Args:
            config (ModelsConfig): Configuration object with model parameters.
        """
        super().__init__()
        self.config = config
