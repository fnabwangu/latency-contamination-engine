"""Worked example: one reasoning cycle over NBIS with three isolated agents."""

from datetime import timedelta

from eig import Claim, EpistemicIntegrityGate, EpistemicType, Provenance, SourceKind
from eig.types import utcnow


def main() -> None:
    gate = EpistemicIntegrityGate(cycle=7, agents=("EDGE", "HEDGE", "EP"))

    quote = gate.observe(
        "NBIS", "last 38.10", source="polygon", tags=("quote",), value=38.10
    )
    gate.observe(
        "NBIS",
        "30d IV 71%",
        source="tradier",
        tags=("options_chain",),
        observed_at=utcnow() - timedelta(minutes=9),
    )
    gate.observe(
        "UST10Y",
        "yield 4.21",
        source="fred",
        tags=("yield_curve",),
        observed_at=utcnow() - timedelta(days=3),
    )
    gate.observe(
        "PORTFOLIO",
        "NBIS 4.2% of book, no hedge",
        source="broker",
        etype=EpistemicType.USER_STATE,
        kind=SourceKind.SYSTEM_OF_RECORD,
    )

    # Each agent reasons in its own lane. None can see the others yet.
    gate.agent_claim(
        "EDGE", "NBIS", "NBIS rebounds into Q3", upstream=(quote.id,), confidence=0.55
    )
    gate.agent_claim(
        "HEDGE", "NBIS", "tail risk underpriced at 4.2% weight", confidence=0.7
    )
    gate.agent_claim(
        "EP", "NBIS", "no execution edge above 38.50", etype=EpistemicType.AGENT_OPINION
    )

    # An upstream system tries to launder last cycle's call into the fact tier.
    stale_call = gate.agent_claim(
        "EDGE", "NBIS", "buy NBIS", cycle=6, etype=EpistemicType.HYPOTHESIS
    )
    gate.submit(
        Claim(
            subject="NBIS",
            statement="NBIS is a confirmed buy",
            etype=EpistemicType.MARKET_DATA,
            provenance=Provenance(
                source="thesis_cache",
                kind=SourceKind.DERIVED,
                cycle=gate.cycle,
                upstream=(stale_call.id,),
            ),
        )
    )

    for agent in ("EDGE", "HEDGE", "EP"):
        gate.seal(agent)

    packet = gate.build_packet()
    print(packet.summary())


if __name__ == "__main__":
    main()
