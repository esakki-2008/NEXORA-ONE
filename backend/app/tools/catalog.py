"""Future tool metadata; no tool is executable in Phase 1."""

from backend.app.models.enums import RiskLevel
from backend.app.tools.contracts import ToolDefinition
from backend.app.tools.registry import ToolCatalog

FOUNDATION_TOOL_DEFINITIONS = (
    ToolDefinition(
        name="get_logs",
        description="Read bounded, time-windowed logs for an allow-listed service.",
        input_schema={"type": "object", "required": ["service", "since"]},
        output_schema={"type": "array", "items": {"type": "object"}},
        risk_level=RiskLevel.READ_ONLY,
        requires_approval=False,
    ),
    ToolDefinition(
        name="get_metrics",
        description="Read approved metrics for an allow-listed service.",
        input_schema={"type": "object", "required": ["service", "metric", "since"]},
        output_schema={"type": "array", "items": {"type": "object"}},
        risk_level=RiskLevel.READ_ONLY,
        requires_approval=False,
    ),
    ToolDefinition(
        name="get_recent_deployments",
        description="Read deployment records for an allow-listed service.",
        input_schema={"type": "object", "required": ["service"]},
        output_schema={"type": "array", "items": {"type": "object"}},
        risk_level=RiskLevel.READ_ONLY,
        requires_approval=False,
    ),
    ToolDefinition(
        name="inspect_configuration",
        description="Read approved configuration keys without exposing secrets.",
        input_schema={"type": "object", "required": ["service", "keys"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.READ_ONLY,
        requires_approval=False,
    ),
    ToolDefinition(
        name="search_documentation",
        description="Search an approved documentation corpus.",
        input_schema={"type": "object", "required": ["query"]},
        output_schema={"type": "array", "items": {"type": "object"}},
        risk_level=RiskLevel.READ_ONLY,
        requires_approval=False,
    ),
    ToolDefinition(
        name="run_health_check",
        description="Run a named, allow-listed service health check.",
        input_schema={"type": "object", "required": ["service", "check"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.READ_ONLY,
        requires_approval=False,
    ),
    ToolDefinition(
        name="run_test",
        description="Run a named test from an allow-listed test catalog.",
        input_schema={"type": "object", "required": ["test_id"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.LOW,
        requires_approval=False,
    ),
    ToolDefinition(
        name="create_remediation_plan",
        description="Create a structured remediation proposal without executing it.",
        input_schema={"type": "object", "required": ["incident_id", "steps"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.LOW,
        requires_approval=False,
    ),
    ToolDefinition(
        name="execute_safe_action",
        description="Execute one explicitly allow-listed reversible action after approval.",
        input_schema={"type": "object", "required": ["action_id", "parameters"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.HIGH,
        requires_approval=True,
    ),
    ToolDefinition(
        name="verify_resolution",
        description="Run a structured verification check against a known incident.",
        input_schema={"type": "object", "required": ["incident_id", "checks"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.READ_ONLY,
        requires_approval=False,
    ),
    ToolDefinition(
        name="generate_incident_report",
        description="Assemble a report from recorded evidence, actions, and verification.",
        input_schema={"type": "object", "required": ["incident_id"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.LOW,
        requires_approval=False,
    ),
)

FOUNDATION_TOOL_CATALOG = ToolCatalog(FOUNDATION_TOOL_DEFINITIONS)
