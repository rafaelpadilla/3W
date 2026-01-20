from pydantic import BaseModel, Field, field_validator
from typing import Literal
from pathlib import Path

from .enums import EventPrefixEnum


class ParquetDatasetConfig(BaseModel):
    """
    Configuration schema for loading a Parquet dataset.
    Defines the dataset location, splits, filtering options, and preprocessing behavior.
    """

    path: str | Path = Field(..., description="Path to the dataset directory or file.")
    split: Literal[None, "train", "val", "test", "list"] = Field(
        default=None,
        description="Dataset split to load. If None, load all available files.",
    )
    file_list: (list[str] | list[Path]) | None = Field(
        default=None,
        description='List of files to load if split=="list". Must be explicitly provided.',
    )
    event_type: list[EventPrefixEnum] | list[str] | None = Field(
        default=None,
        description="Event types to include. (e.g., simulated, real, ...)",
    )
    target_class: list[int] | None = Field(
        default=None,
        description="Event classes to include. (e.g., 0, 1, 2, ...). Loads all classes if `None`.",
    )
    columns: list[str] | None = Field(
        default=None,
        description="Specific data columns to load. Loads all columns if `None`.",
    )
    target_column: str | None = Field(
        default="class",
        description="Target column used for supervised tasks.",
    )
    force_download: bool = Field(
        default=False,
        description="If True, dataset is downloaded even if it already exists. In this case, \
            existing files will be overwritten.",
    )
    files_per_batch: int = Field(
        default=10,
        description="Number of files to load per batch during iteration.",
    )
    shuffle: bool = Field(
        default=False,
        description="If True, shuffle dataset files before loading.",
    )
    clean_data: bool = Field(
        default=True,
        description="If True, apply basic cleaning to the loaded data.",
    )
    seed: int = Field(
        default=2025,
        description="Random seed for reproducibility in shuffling and splits.",
    )
    version: str = Field(
        default="2.0.0",
        description="Dataset version to load. (e.g., 2.0.0, 2.0.1, ...)",
    )

    @field_validator("file_list")
    @classmethod
    def validate_file_list(cls, value, info):
        """
        Ensure that `file_list` is only provided when `split=="list"`.
        Raise a ValueError otherwise.
        """
        split = info.data.get("split")
        if split == "list" and value is None:
            raise ValueError('file_list must be provided if split is "list".')
        elif split != "list" and value is not None:
            raise ValueError(f'file_list must not be provided if split="{split}".')
        return value

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value):
        """
        Ensure that all event types are valid string values of EventPrefixEnum.
        Raise a ValueError if an unknown type is provided.
        """
        if value is not None:
            valid_strs = {e.value for e in EventPrefixEnum}
            if not isinstance(value, list) or not all(
                isinstance(event_type_item, str) for event_type_item in value
            ):
                raise TypeError("event_type must be a list of str.")
            for event_type_item in value:
                if event_type_item not in valid_strs:
                    raise ValueError(f"Unknown event_type: {event_type_item}")
        return value
