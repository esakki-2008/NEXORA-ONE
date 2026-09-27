"""Read-only simulator routes for inspecting structured ShopFlow fixtures."""

from fastapi import APIRouter, HTTPException, Request, status

from backend.app.schemas.incidents import ScenarioSummary
from backend.app.simulator.models import ScenarioFixture
from backend.app.simulator.scenarios import ScenarioNotFoundError, ShopFlowSimulator

router = APIRouter(prefix="/api/simulator", tags=["simulator"])


@router.get("/scenarios", response_model=list[ScenarioSummary], summary="List ShopFlow scenarios")
def list_scenarios(request: Request) -> list[ScenarioSummary]:
    simulator: ShopFlowSimulator = request.app.state.simulator
    return simulator.list_scenarios()


@router.get(
    "/scenarios/{scenario_id}",
    response_model=ScenarioFixture,
    summary="Load a structured ShopFlow scenario",
)
def load_scenario(request: Request, scenario_id: str) -> ScenarioFixture:
    simulator: ShopFlowSimulator = request.app.state.simulator
    try:
        return simulator.load_scenario(scenario_id)
    except ScenarioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario {scenario_id!r} was not found",
        ) from exc
