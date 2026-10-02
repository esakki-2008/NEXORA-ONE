"""Check that the public OpenAPI contract contains the critical route paths."""

from __future__ import annotations

from backend.app.main import create_app

REQUIRED_ROUTES: tuple[tuple[str, str], ...] = (
    ("GET", "/health"),
    ("GET", "/api/ai/health"),
    ("POST", "/api/ai/test"),
    ("POST", "/api/ai/analyze"),
    ("GET", "/api/ai/activity"),
    ("GET", "/api/simulator/scenarios"),
    ("GET", "/api/simulator/scenarios/{scenario_id}"),
    ("POST", "/api/incidents"),
    ("GET", "/api/incidents/{incident_id}"),
    ("GET", "/api/incidents/{incident_id}/report"),
    ("POST", "/api/investigations/incidents/{incident_id}/start"),
    ("POST", "/api/actions"),
    ("GET", "/api/actions/registry"),
    ("POST", "/api/actions/{action_id}/approve"),
    ("POST", "/api/actions/{action_id}/execute"),
    ("POST", "/api/actions/{action_id}/rollback"),
    ("GET", "/api/actions/{action_id}/verification"),
    ("GET", "/api/actions/{action_id}/audit"),
    ("GET", "/api/verification"),
    ("POST", "/api/verification/{verification_id}/retry"),
    ("GET", "/api/verification/{verification_id}/timeline"),
    ("GET", "/api/security/session"),
)


def main() -> None:
    schema = create_app().openapi()
    paths = schema.get("paths", {})
    missing = [
        f"{method} {path}"
        for method, path in REQUIRED_ROUTES
        if path not in paths or method.lower() not in paths[path]
    ]
    if missing:
        raise SystemExit("OpenAPI route check failed: " + ", ".join(missing))
    print(
        f"OpenAPI route check passed: {len(paths)} paths; "
        f"{len(REQUIRED_ROUTES)} critical routes checked."
    )


if __name__ == "__main__":
    main()
