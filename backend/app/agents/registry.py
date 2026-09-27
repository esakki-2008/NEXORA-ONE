"""Explicit specialist registry for the central orchestrator."""

from backend.app.agents.base import AgentDirectory
from backend.app.agents.specialists import (
    CloudAgent,
    ComplianceAgent,
    ContractsAgent,
    CustomerSupportAgent,
    DataAgent,
    ITOperationsAgent,
    RevenueAgent,
    SupplyChainAgent,
)


def build_specialist_directory() -> AgentDirectory:
    directory = AgentDirectory()
    for specialist in (
        ITOperationsAgent(),
        RevenueAgent(),
        CustomerSupportAgent(),
        SupplyChainAgent(),
        ContractsAgent(),
        CloudAgent(),
        DataAgent(),
        ComplianceAgent(),
    ):
        directory.register(specialist)
    return directory


__all__ = ["build_specialist_directory"]
