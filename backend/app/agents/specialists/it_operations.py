from backend.app.agents.context import OrchestrationDomain
from backend.app.agents.specialists.base import DomainSpecialist


class ITOperationsAgent(DomainSpecialist):
    name = "it_operations"
    domain = "IT Operations"
    domain_enum = OrchestrationDomain.IT
    capabilities = ("incidents", "logs", "metrics", "deployments", "configuration")
    tool_names = (
        "get_logs",
        "get_metrics",
        "get_recent_deployments",
        "inspect_configuration",
        "run_health_check",
    )
    keywords = ("api", "service", "database", "incident", "deployment", "latency", "error")
