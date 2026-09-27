from backend.app.agents.context import OrchestrationDomain
from backend.app.agents.specialists.base import DomainSpecialist


class RevenueAgent(DomainSpecialist):
    name = "revenue"
    domain = "Revenue"
    domain_enum = OrchestrationDomain.REVENUE
    capabilities = ("payments", "billing", "checkout", "revenue impact")
    tool_names = (
        "get_logs",
        "get_metrics",
        "get_recent_deployments",
        "run_health_check",
        "run_test",
    )
    keywords = ("payment", "billing", "checkout", "revenue", "charge")
