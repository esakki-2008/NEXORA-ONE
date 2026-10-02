from backend.app.agents.context import OrchestrationDomain
from backend.app.agents.specialists.base import DomainSpecialist


class SupplyChainAgent(DomainSpecialist):
    name = "supply_chain"
    domain = "Supply Chain"
    domain_enum = OrchestrationDomain.SUPPLY_CHAIN
    capabilities = ("suppliers", "inventory", "shipments", "orders")
    tool_names = ("get_metrics", "search_documentation", "run_health_check")
    keywords = ("supplier", "inventory", "shipment", "warehouse", "order")
