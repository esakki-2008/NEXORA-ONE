"""Structured ShopFlow simulator records used by future investigation phases."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import Severity


class SimulatorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SimulatedIncident(SimulatorModel):
    scenario_id: str
    title: str
    description: str
    severity: Severity
    service: str
    created_at: datetime


class ServiceSnapshot(SimulatorModel):
    name: str
    status: Literal["healthy", "degraded", "down"]
    version: str | None = None


class DeploymentSnapshot(SimulatorModel):
    id: UUID = Field(default_factory=uuid4)
    service: str
    version: str
    status: Literal["successful", "failed", "rolled_back", "active"]
    deployed_at: datetime
    change_summary: str


class ConfigurationSnapshot(SimulatorModel):
    service: str
    key: str
    value: Any
    expected_value: Any | None = None
    updated_at: datetime
    updated_by: str


class MetricSnapshot(SimulatorModel):
    service: str
    name: str
    value: float
    unit: str
    observed_at: datetime


class LogSnapshot(SimulatorModel):
    id: UUID = Field(default_factory=uuid4)
    service: str
    level: Literal["INFO", "WARN", "ERROR"]
    message: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransactionSnapshot(SimulatorModel):
    id: UUID = Field(default_factory=uuid4)
    service: str
    status: Literal["succeeded", "failed", "pending"]
    amount: float = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    timestamp: datetime
    failure_reason: str | None = None


class ShopFlowState(SimulatorModel):
    company: Literal["ShopFlow"] = "ShopFlow"
    services: list[ServiceSnapshot]
    deployments: list[DeploymentSnapshot]
    configurations: list[ConfigurationSnapshot]
    metrics: list[MetricSnapshot]
    logs: list[LogSnapshot]
    transactions: list[TransactionSnapshot]


class ScenarioFixture(SimulatorModel):
    scenario_id: str
    name: str
    description: str
    incident: SimulatedIncident
    state: ShopFlowState
