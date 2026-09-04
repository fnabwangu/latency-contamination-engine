from eig import Claim, EpistemicType, Provenance, ProvenanceGraph, ReconciliationStatus, SourceKind, reconcile


def make(identifier, etype):
    return Claim("X", identifier, etype, Provenance("source", SourceKind.FEED), id=identifier, tags=frozenset({"contradiction_group:g", "polarity:positive" if identifier in {"a", "high"} else "polarity:negative"}))


def test_equal_authority_contradiction_remains_unresolved():
    claims = {"a": make("a", EpistemicType.FACT), "b": make("b", EpistemicType.FACT)}
    contradiction = ProvenanceGraph(claims.values()).contradictions()[0]
    result = reconcile(contradiction, claims)
    assert result.status is ReconciliationStatus.UNRESOLVED
    assert result.winner_id is None


def test_higher_authority_claim_can_resolve_contradiction():
    claims = {"high": make("high", EpistemicType.FACT), "low": make("low", EpistemicType.HYPOTHESIS)}
    contradiction = ProvenanceGraph(claims.values()).contradictions()[0]
    assert reconcile(contradiction, claims).winner_id == "high"