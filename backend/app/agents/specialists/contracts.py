from backend.app.agents.context import OrchestrationDomain
from backend.app.agents.specialists.base import DomainSpecialist


class ContractsAgent(DomainSpecialist):
    name = "contracts"
    domain = "Contracts"
    domain_enum = OrchestrationDomain.CONTRACTS
    capabilities = ("obligations", "renewals", "penalties", "expiration")
    tool_names = ("search_documentation", "generate_incident_report")
    keywords = ("contract", "renewal", "obligation", "penalty", "expiration")
