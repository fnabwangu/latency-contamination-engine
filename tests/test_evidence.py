from datetime import timedelta

from eig import EvidenceModality, EvidenceRecord, EvidenceStore
from eig.types import utcnow


def test_evidence_is_content_addressed_and_deduplicated():
    now = utcnow()
    first = EvidenceRecord("feed", now, now, EvidenceModality.STRUCTURED, "NBIS=38.10", candidate_ids=("c1",))
    second = EvidenceRecord("feed", now, now, EvidenceModality.STRUCTURED, "NBIS=38.10", candidate_ids=("c1",))
    store = EvidenceStore()
    assert store.register(first).evidence_id == store.register(second).evidence_id
    assert len(store.records) == 1


def test_evidence_expiry_is_explicit():
    now = utcnow()
    record = EvidenceRecord("filing", now, now, EvidenceModality.FILING, "guidance", candidate_ids=("c1",)).with_ttl(timedelta(minutes=5))
    assert not record.is_expired(now)
    assert record.is_expired(record.expires_at)


def test_evidence_store_counts_independent_sources():
    now = utcnow()
    store = EvidenceStore()
    store.register(EvidenceRecord("feed", now, now, EvidenceModality.TEXT, "one", candidate_ids=("c1",)))
    store.register(EvidenceRecord("feed", now, now, EvidenceModality.TEXT, "two", candidate_ids=("c1",)))
    store.register(EvidenceRecord("filing", now, now, EvidenceModality.TEXT, "three", candidate_ids=("c1",)))
    assert store.independent_count("c1") == 2