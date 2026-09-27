from backend.app.agents.context import OrchestrationDomain
from backend.app.agents.specialists.base import DomainSpecialist


class ComplianceAgent(DomainSpecialist):
    name = "compliance"
    domain = "Compliance"
    domain_enum = OrchestrationDomain.COMPLIANCE
    capabilities = ("controls", "evidence", "gaps", "audit")
    tool_names = ("search_documentation", "generate_incident_report")
    keywords = ("compliance", "control", "audit", "policy", "regulatory")
