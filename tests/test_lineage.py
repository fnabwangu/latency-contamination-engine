from eig import Claim, EpistemicType, Provenance, SourceKind, cluster_claims, effective_independent_evidence


def claim(identifier, source, upstream=()):
    return Claim("X", identifier, EpistemicType.HYPOTHESIS, Provenance(source, SourceKind.AGENT, upstream=upstream), id=identifier)


def test_shared_source_and_upstream_are_one_independent_cluster():
    claims = (claim("a", "MACRO", ("e1",)), claim("b", "MACRO", ("e1",)), claim("c", "EP"))
    clusters = cluster_claims(claims)
    assert len(clusters) == 2
    assert effective_independent_evidence(claims) == 2