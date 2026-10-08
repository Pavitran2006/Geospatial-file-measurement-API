"""Pydantic response models."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_type: str
    status: str
    crs: str | None
    feature_count: int
    error: str | None
    created_at: datetime


class FeatureOut(BaseModel):
    feature_index: int
    geometry_type: str | None
    geometry: dict[str, Any] | None
    crs: str | None
    properties: dict[str, Any]


class MeasurementValue(BaseModel):
    type: str  # "area" | "length"
    value: float
    unit: str  # "m2" | "m"
    projected_crs: str


class FeatureMeasurementOut(BaseModel):
    feature_index: int
    geometry_type: str | None
    status: str  # OK | NOT_APPLICABLE | UNSUPPORTED | SKIPPED
    measurement: MeasurementValue | None
    note: str | None


class MeasurementSummary(BaseModel):
    total_area_m2: float
    total_length_m: float
    measured_features: int
    unmeasured_features: int


class MeasurementsOut(BaseModel):
    file_id: str
    crs: str | None
    feature_count: int
    limit: int
    offset: int
    summary: MeasurementSummary
    measurements: list[FeatureMeasurementOut]


class FeaturesOut(BaseModel):
    file_id: str
    feature_count: int
    limit: int
    offset: int
    features: list[FeatureOut]
