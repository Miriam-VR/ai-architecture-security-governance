"""Typed contracts for the three read-only maintenance tools."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

EQ_ID = r"^[A-Z]{1,3}-\d{2,4}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EquipmentArgs(_Strict):
    equipment_id: str = Field(pattern=EQ_ID)


class HistoryArgs(_Strict):
    equipment_id: str = Field(pattern=EQ_ID)
    limit: int = Field(default=5, ge=1, le=20)


class EquipmentInfo(BaseModel):
    equipment_id: str
    plant_id: str
    type: str
    model: str
    criticality: str
    location: str
    next_maintenance: str | None = None


class SensorReading(BaseModel):
    sensor: str
    value: float
    unit: str
    quality: str
    timestamp: str


class SensorReadings(BaseModel):
    equipment_id: str
    readings: list[SensorReading]


class FailureRecord(BaseModel):
    failure_id: str
    root_cause: str
    confirmed_cause: str
    symptoms: list[str]
    date: str


class FailureHistory(BaseModel):
    equipment_id: str
    failures: list[FailureRecord]


TOOL_ARGS: dict[str, type[BaseModel]] = {
    "get_equipment_info": EquipmentArgs,
    "get_sensor_readings": EquipmentArgs,
    "get_failure_history": HistoryArgs,
}
TOOL_RESULTS: dict[str, type[BaseModel]] = {
    "get_equipment_info": EquipmentInfo,
    "get_sensor_readings": SensorReadings,
    "get_failure_history": FailureHistory,
}
TOOL_DESCRIPTIONS = {
    "get_equipment_info": "Model, criticality, location and scheduled maintenance of an equipment.",
    "get_sensor_readings": "Latest simulated temperature, vibration and pressure readings.",
    "get_failure_history": "Previous failures of an equipment (confirmed causes).",
}
