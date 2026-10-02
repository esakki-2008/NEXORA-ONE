from backend.app.models.enums import Severity
from backend.app.simulator.scenarios import ScenarioNotFoundError, ShopFlowSimulator


def test_all_shopflow_scenarios_load_structured_data() -> None:
    simulator = ShopFlowSimulator()
    summaries = simulator.list_scenarios()

    assert len(summaries) == 5
    assert {summary.scenario_id for summary in summaries} == {
        "payment-failure",
        "database-failure",
        "latency-spike",
        "bad-deployment",
        "configuration-mismatch",
    }

    for summary in summaries:
        fixture = simulator.load_scenario(summary.scenario_id)
        assert fixture.state.company == "ShopFlow"
        assert fixture.incident.severity in Severity
        assert fixture.incident.scenario_id == summary.scenario_id
        assert fixture.state.services


def test_payment_failure_contains_correlatable_observations() -> None:
    fixture = ShopFlowSimulator().load_scenario("payment-failure")

    assert fixture.state.deployments
    assert fixture.state.configurations
    assert fixture.state.logs
    assert fixture.state.transactions
    assert any(metric.name == "payment.failure_rate" for metric in fixture.state.metrics)


def test_unknown_scenario_is_not_silently_created() -> None:
    try:
        ShopFlowSimulator().load_scenario("does-not-exist")
    except ScenarioNotFoundError:
        pass
    else:
        raise AssertionError("unknown scenarios must be rejected")
