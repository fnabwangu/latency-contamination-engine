"""Source-lineage clustering for dependence-aware evidence pooling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .types import Claim


@dataclass(frozen=True)
class LineageCluster:
    cluster_id: str
    claim_ids: tuple[str, ...]
    sources: tuple[str, ...]
    upstream_ids: tuple[str, ...]


def cluster_claims(claims: Iterable[Claim]) -> tuple[LineageCluster, ...]:
    groups: dict[tuple[str, tuple[str, ...]], list[Claim]] = {}
    for claim in claims:
        key = (claim.provenance.source, tuple(sorted(claim.provenance.upstream)))
        groups.setdefault(key, []).append(claim)
    clusters = []
    for index, ((source, upstream), values) in enumerate(sorted(groups.items(), key=lambda item: item[0])):
        clusters.append(LineageCluster(f"lineage-{index + 1}", tuple(value.id for value in values), (source,), upstream))
    return tuple(clusters)


def effective_independent_evidence(claims: Iterable[Claim]) -> int:
    return len(cluster_claims(claims))