from backend.app.agents.context import OrchestrationDomain
from backend.app.agents.specialists.base import DomainSpecialist


class CloudAgent(DomainSpecialist):
    name = "cloud"
    domain = "Cloud"
    domain_enum = OrchestrationDomain.CLOUD
    capabilities = ("resources", "usage", "cost anomalies", "capacity")
    tool_names = ("get_metrics", "get_logs", "run_health_check")
    keywords = ("cloud", "compute", "resource", "usage", "cost", "capacity")
