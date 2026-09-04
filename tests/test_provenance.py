from eig import Claim, EpistemicType, Provenance, ProvenanceGraph, SourceKind


def claim(identifier, upstream=(), tags=()):
    return Claim("NBIS", identifier, EpistemicType.HYPOTHESIS, Provenance("agent", SourceKind.AGENT, upstream=upstream), tags=frozenset(tags), id=identifier)


def test_provenance_graph_detects_cycles_and_dangling_links():
    graph = ProvenanceGraph((claim("a", ("b",)), claim("b", ("a",)), claim("c", ("missing",))))
    findings = graph.validate()
    assert {finding.code for finding in findings} == {"PROVENANCE_CYCLE", "DANGLING_PROVENANCE"}


def test_contradictions_are_opt_in_and_subject_scoped():
    graph = ProvenanceGraph((claim("positive", tags=("contradiction_group:g", "polarity:positive")), claim("negative", tags=("contradiction_group:g", "polarity:negative"))))
    contradictions = graph.contradictions()
    assert len(contradictions) == 1
    assert contradictions[0].left_id == "positive"


def test_provenance_graph_exposes_multi_hop_cycle_decay():
    graph = ProvenanceGraph((claim("old"), claim("new", ("old",))))
    assert graph.ancestor_cycles("new") == (0,)
    assert graph.temporally_stale("new", current_cycle=2, max_cycle_lag=1)