from backend.app.agents.context import OrchestrationDomain
from backend.app.agents.specialists.base import DomainSpecialist


class CustomerSupportAgent(DomainSpecialist):
    name = "support"
    domain = "Customer Support"
    domain_enum = OrchestrationDomain.SUPPORT
    capabilities = ("tickets", "customer issues", "escalation")
    tool_names = ("search_documentation", "run_test")
    keywords = ("support", "ticket", "customer", "case", "escalation")
