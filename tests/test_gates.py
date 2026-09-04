from eig import GateClass, GateDefinition, GateGraph, GateResult


def test_gate_graph_keeps_warnings_and_not_applicable_nonblocking():
    graph = GateGraph((GateDefinition("warning", GateClass.WARNING, "execution", "Root"), GateDefinition("spread", GateClass.EXECUTION_HARD, "execution", "Root"), GateDefinition("gex", GateClass.INFORMATION_REQUIREMENT, "discovery", "Gamma")))
    execution = graph.evaluate({"warning": GateResult.WARN, "spread": GateResult.PASS}, "execution")
    assert not execution.blocked
    assert len(execution.warnings) == 1
    discovery = graph.evaluate({"gex": GateResult.UNKNOWN}, "discovery")
    assert discovery.blocked
    assert graph.discovery_preserved({"gex": GateResult.UNKNOWN})


def test_gate_graph_requires_gate_owner():
    try:
        GateGraph((GateDefinition("bad", GateClass.WARNING, "discovery", ""),))
    except ValueError as error:
        assert "owner" in str(error)
    else:
        raise AssertionError("ownerless gate accepted")