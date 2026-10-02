from backend.app.agents.context import OrchestrationDomain
from backend.app.agents.specialists.base import DomainSpecialist


class DataAgent(DomainSpecialist):
    name = "data"
    domain = "Data"
    domain_enum = OrchestrationDomain.DATA
    capabilities = ("pipelines", "data quality", "anomalies", "schemas")
    tool_names = ("get_metrics", "get_logs", "inspect_configuration", "run_test")
    keywords = ("data", "pipeline", "quality", "database", "schema")
