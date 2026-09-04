from datetime import timedelta

import pytest

from eig import (
    Claim,
    EpistemicIntegrityGate,
    EpistemicType,
    IsolationViolation,
    Provenance,
    SourceKind,
)
from eig.types import utcnow


def make_gate(**kw):
    return EpistemicIntegrityGate(agents=("EDGE", "HEDGE", "EP"), **kw)


def seal_all(gate):
    for agent in ("EDGE", "HEDGE", "EP"):
        gate.seal(agent)


def test_agent_hypothesis_keeps_its_source_label():
    gate = make_gate()
    claim = gate.agent_claim("EDGE", "NBIS", "NBIS rebounds")
    assert claim.label == "AGENT_HYPOTHESIS(source=EDGE)"


def test_agent_cannot_mint_market_data():
    gate = make_gate()
    claim = gate.agent_claim(
        "EDGE", "NBIS", "NBIS rebounds", etype=EpistemicType.MARKET_DATA
    )
    seal_all(gate)
    packet = gate.build_packet()
    accepted = packet.accepted[0]
    assert accepted.id == claim.id
    assert accepted.etype is EpistemicType.HYPOTHESIS
    assert accepted.label == "AGENT_HYPOTHESIS(source=EDGE)"
    assert [f.code for f in packet.demotions] == ["OPINION_LAUNDERING"]


def test_derived_claim_cannot_outrank_weakest_parent():
    gate = make_gate()
    assumption = gate.observe(
        "RATES",
        "cuts priced for Q3",
        source="analyst_note",
        etype=EpistemicType.MARKET_DATA,
    )
    weak = gate.agent_claim("EP", "RATES", "cuts hold", etype=EpistemicType.ASSUMPTION)
    derived = Claim(
        subject="NBIS",
        statement="multiple expands",
        etype=EpistemicType.FACT,
        provenance=Provenance(
            source="synthesis",
            kind=SourceKind.DERIVED,
            upstream=(assumption.id, weak.id),
        ),
    )
    gate.submit(derived)
    seal_all(gate)
    packet = gate.build_packet()
    out = {c.id: c for c in packet.accepted}
    assert out[derived.id].etype is EpistemicType.ASSUMPTION
    assert "AUTHORITY_INFLATION" in {f.code for f in packet.demotions}


def test_previous_cycle_recommendation_cannot_become_fact():
    gate = make_gate()
    old = gate.agent_claim("EDGE", "NBIS", "buy NBIS", etype=EpistemicType.HYPOTHESIS)
    seal_all(gate)
    gate.build_packet()

    gate.advance_cycle()
    laundered = Claim(
        subject="NBIS",
        statement="NBIS is a buy",
        etype=EpistemicType.FACT,
        provenance=Provenance(
            source="memory",
            kind=SourceKind.DERIVED,
            cycle=gate.cycle,
            upstream=(old.id,),
        ),
    )
    gate.submit(laundered)
    packet = gate.build_packet()
    quarantined = {q.claim.id: q for q in packet.quarantined}
    assert laundered.id in quarantined
    assert "LATENCY_CONTAMINATION" in {
        f.code for f in quarantined[laundered.id].findings
    }


def test_orphaned_children_are_quarantined_with_their_parent():
    gate = make_gate(require_seal=False)
    bad = Claim(
        subject="NBIS",
        statement="unsourced",
        etype=EpistemicType.PRIOR,
        provenance=Provenance(source="nowhere", kind=SourceKind.DERIVED),
    )
    gate.submit(bad)
    child = Claim(
        subject="NBIS",
        statement="depends on unsourced",
        etype=EpistemicType.HYPOTHESIS,
        provenance=Provenance(
            source="synthesis", kind=SourceKind.DERIVED, upstream=(bad.id,)
        ),
    )
    gate.submit(child)
    packet = gate.build_packet()
    assert {q.claim.id for q in packet.quarantined} == {bad.id, child.id}
    assert packet.accepted == ()


def test_stale_and_expired_market_data():
    gate = make_gate(require_seal=False)
    stale = gate.observe(
        "NBIS",
        "last 38.10",
        source="feed",
        observed_at=utcnow() - timedelta(minutes=8),
        tags=("options_chain",),
    )
    expired = gate.observe(
        "UST10Y",
        "yield 4.21",
        source="feed",
        observed_at=utcnow() - timedelta(days=2),
        tags=("yield_curve",),
    )
    packet = gate.build_packet()
    assert {c.id for c in packet.accepted} == {stale.id}
    assert {f.code for f in packet.flags} == {"STALE_STALE"}
    assert {q.claim.id for q in packet.quarantined} == {expired.id}


def test_agents_cannot_see_each_other_before_sealing():
    gate = make_gate()
    edge = gate.agent_claim("EDGE", "NBIS", "rebound")
    market = gate.observe("NBIS", "last 38.10", source="feed")

    visible = gate.visible_to("HEDGE")
    assert {c.id for c in visible} == {market.id}
    with pytest.raises(IsolationViolation):
        gate.barrier.read("HEDGE", edge.id)

    with pytest.raises(IsolationViolation):
        gate.agent_claim("HEDGE", "NBIS", "agrees with EDGE", upstream=(edge.id,))

    seal_all(gate)
    assert gate.barrier.released
    assert edge.id in {c.id for c in gate.visible_to("HEDGE")}
    assert gate.barrier.read("HEDGE", edge.id).id == edge.id


def test_packet_requires_all_agents_sealed():
    gate = make_gate()
    gate.agent_claim("EDGE", "NBIS", "rebound")
    gate.seal("EDGE")
    with pytest.raises(IsolationViolation):
        gate.build_packet()
    gate.seal("HEDGE")
    gate.seal("EP")
    assert gate.build_packet().accepted


def test_sealed_agent_cannot_add_claims_before_release():
    gate = make_gate()
    gate.seal("EDGE")
    with pytest.raises(IsolationViolation):
        gate.agent_claim("EDGE", "NBIS", "one more thing")


def test_packet_digest_is_stable_and_content_addressed():
    gate = make_gate(require_seal=False)
    gate.observe("NBIS", "last 38.10", source="feed")
    packet = gate.build_packet()
    assert packet.digest == gate.build_packet().digest
    assert len(packet.digest) == 64


def test_assert_clean_raises_on_quarantine():
    from eig import ContaminatedPacket

    gate = make_gate(require_seal=False)
    gate.observe(
        "UST10Y",
        "yield 4.21",
        source="feed",
        observed_at=utcnow() - timedelta(days=30),
        tags=("yield_curve",),
    )
    with pytest.raises(ContaminatedPacket):
        gate.build_packet().assert_clean()


def test_demotion_cannot_raise_authority():
    claim = Claim(
        subject="X",
        statement="y",
        etype=EpistemicType.HYPOTHESIS,
        provenance=Provenance(source="EDGE", kind=SourceKind.AGENT),
    )
    with pytest.raises(ValueError):
        claim.demoted_to(EpistemicType.FACT)


def test_cyclic_provenance_is_quarantined_by_the_gate():
    gate = make_gate(require_seal=False)
    first = Claim("X", "first", EpistemicType.HYPOTHESIS, Provenance("derived", SourceKind.DERIVED, upstream=("second",)), id="first")
    second = Claim("X", "second", EpistemicType.HYPOTHESIS, Provenance("derived", SourceKind.DERIVED, upstream=("first",)), id="second")
    gate.submit(first)
    gate.submit(second)
    packet = gate.build_packet()
    findings = [finding.code for item in packet.quarantined for finding in item.findings]
    assert "PROVENANCE_CYCLE" in findings


def test_prior_cycle_agent_reasoning_cannot_feed_current_hypothesis():
    gate = make_gate(require_seal=False)
    old = gate.agent_claim("EDGE", "NBIS", "old thesis")
    gate.build_packet()
    gate.advance_cycle()
    current = Claim("NBIS", "synthesis", EpistemicType.HYPOTHESIS, Provenance("synthesis", SourceKind.DERIVED, cycle=gate.cycle, upstream=(old.id,)), id="current")
    gate.submit(current)
    packet = gate.build_packet()
    quarantined = {item.claim.id: item for item in packet.quarantined}
    assert "LATENCY_CONTAMINATION" in {finding.code for finding in quarantined["current"].findings}


def test_packet_surfaces_contradictory_evidence_without_dropping_claims():
    gate = make_gate(require_seal=False)
    gate.submit(Claim("X", "up", EpistemicType.FACT, Provenance("feed-a", SourceKind.FEED), tags=frozenset({"contradiction_group:g", "polarity:positive"}), id="up"))
    gate.submit(Claim("X", "down", EpistemicType.FACT, Provenance("feed-b", SourceKind.FEED), tags=frozenset({"contradiction_group:g", "polarity:negative"}), id="down"))
    packet = gate.build_packet()
    assert {claim.id for claim in packet.accepted} == {"up", "down"}
    assert len(packet.contradictions) == 1
    assert sum(finding.code == "CONTRADICTORY_EVIDENCE" for finding in packet.flags) == 2
