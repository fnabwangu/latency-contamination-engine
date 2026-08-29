import unittest

from latency_contamination_engine import (
    DEFAULT_STRATEGY_UNIVERSE,
    DecisionContext,
    EpistemicType,
    LatencyContaminationGate,
    MultiAgentCoordinator,
    validate_agent_input,
)


class LatencyContaminationGateTest(unittest.TestCase):
    def test_pre_agent_sanitization_locks_strategies_and_quarantines(self):
        ctx = DecisionContext(
            observations={"price": "100"},
            stale_assumptions={"old_vol": "low"},
            inherited_recommendations={"prev_rec": "hold"},
            historical_priors={"bias": "hold_winners"},
        )

        report = LatencyContaminationGate().sanitize_context(ctx)

        self.assertTrue(ctx.latency_contamination_checked)
        self.assertTrue(ctx.strategy_universe_locked)
        self.assertEqual(tuple(ctx.strategy_universe), tuple(DEFAULT_STRATEGY_UNIVERSE))
        self.assertFalse(ctx.previous_recommendations_as_evidence)
        self.assertTrue(report["checked"])
        self.assertEqual(report["quarantined_items"], 2)
        self.assertEqual(report["previous_recommendations_blocked"], 1)

    def test_post_agent_outputs_are_hypotheses_with_provenance(self):
        outputs = LatencyContaminationGate().classify_agent_outputs(
            {"EDGE": "trim", "HEDGE": "hedge"}
        )

        self.assertEqual(len(outputs), 2)
        for item in outputs:
            self.assertEqual(item.epistemic_type, EpistemicType.AGENT_HYPOTHESIS)
            self.assertEqual(item.authority, "NON_FACTUAL")
            self.assertIn(item.source, {"EDGE", "HEDGE"})


class CoordinatorFlowTest(unittest.TestCase):
    def test_coordinator_runs_with_shared_gate_and_flags_disagreement(self):
        ctx = DecisionContext(observations={"price": "101"})
        coordinator = MultiAgentCoordinator()

        result = coordinator.run(
            ctx,
            agent_names=["EDGE", "HEDGE", "Conviction"],
            llm_outputs={"EDGE": "trim", "HEDGE": "hedge", "Conviction": "hold"},
        )

        self.assertTrue(result.latency_report["strategy_set_locked"])
        self.assertEqual(len(result.post_gate_outputs), 3)
        self.assertEqual(len(result.disagreements), 3)

    def test_validate_agent_input_rejects_unsanitized_context(self):
        ctx = DecisionContext(observations={"price": "101"})
        with self.assertRaises(AssertionError):
            validate_agent_input(ctx)


if __name__ == "__main__":
    unittest.main()
