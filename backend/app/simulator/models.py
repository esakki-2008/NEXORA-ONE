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
    id: UUID = Field(default_factory=uuid4)
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


class SupportSnapshot(SimulatorModel):
    """Synthetic customer-support observations for controlled demonstrations."""

    source_id: str = Field(min_length=3, max_length=120)
    ticket_volume: int = Field(ge=0)
    unresolved_tickets: int = Field(ge=0)
    escalation_rate: float = Field(ge=0, le=1)
    response_time_minutes: float = Field(ge=0)
    resolution_time_minutes: float = Field(ge=0)
    sentiment_signal: float = Field(ge=-1, le=1)
    affected_customers: int = Field(ge=0)
    top_issue_categories: list[str] = Field(min_length=1, max_length=12)
    observed_at: datetime


class ShopFlowState(SimulatorModel):
    company: Literal["ShopFlow"] = "ShopFlow"
    services: list[ServiceSnapshot]
    deployments: list[DeploymentSnapshot]
    configurations: list[ConfigurationSnapshot]
    metrics: list[MetricSnapshot]
    logs: list[LogSnapshot]
    transactions: list[TransactionSnapshot]
    support: SupportSnapshot | None = None
    queues: dict[str, int] = Field(
        default_factory=lambda: {
            "payment": 12,
            "checkout": 8,
            "order-processing": 18,
            "fulfillment": 6,
        }
    )
    feature_flags: dict[str, bool] = Field(
        default_factory=lambda: {
            "new_checkout": True,
            "payment_retries": True,
            "express_checkout": True,
            "fraud_screening": True,
        }
    )
    service_capacities: dict[str, int] = Field(
        default_factory=lambda: {
            "Payment Service": 3,
            "Checkout Service": 3,
            "Inventory": 2,
            "Support System": 2,
        }
    )


class ScenarioFixture(SimulatorModel):
    scenario_id: str
    name: str
    description: str
    incident: SimulatedIncident
    state: ShopFlowState
