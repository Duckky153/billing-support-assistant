"""Local audit integrity, detail redaction, and concurrent append regressions."""

from __future__ import annotations

from relay.audit import GENESIS_HASH, AuditLog, redact, verify_chain


def test_concurrent_append_is_atomic(monkeypatch) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import suppress
    from threading import Event

    import relay.audit as audit_module

    entered, release, second_started = Event(), Event(), Event()
    original = audit_module._hash_payload

    def slow_first_hash(payload):
        if payload["ticket_id"] == "first":
            entered.set()
            assert release.wait(2)
        return original(payload)

    monkeypatch.setattr(audit_module, "_hash_payload", slow_first_hash)
    log = AuditLog()

    def append(ticket_id):
        if ticket_id == "second":
            second_started.set()
        return log.append(
            ticket_id=ticket_id,
            customer_id="cus_1",
            kind="resolved",
            action_type="answer",
            verdict="allow",
            code="answer_ok",
            grounded=True,
            detail={},
            timestamp="2025-01-31",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(append, "first")
        assert entered.wait(2)
        second = pool.submit(append, "second")
        assert second_started.wait(2)
        # An unlocked append can finish while the first hash is paused.
        with suppress(TimeoutError):
            second.result(timeout=0.05)
        release.set()
        first.result()
        second.result()
    assert verify_chain(log.records)
    assert [r.seq for r in log.records] == [0, 1]


def test_readers_cannot_mutate_stored_audit_details() -> None:
    log = _log()
    log.records[0].detail["amount_cents"] = "999"
    assert verify_chain(log.records)
    assert log.records[0].detail["amount_cents"] == "2000"


def test_append_itself_drops_non_allowlisted_detail_fields() -> None:
    log = AuditLog()
    record = log.append(
        ticket_id="t",
        customer_id="c",
        kind="resolved",
        action_type="answer",
        verdict="allow",
        code="answer_ok",
        grounded=True,
        detail={"email": "ada@example.com", "amount_cents": "20"},
        timestamp="2025-01-31",
    )
    assert record.detail == {"amount_cents": "20"}


def _log() -> AuditLog:
    log = AuditLog()
    log.append(
        ticket_id="tkt_1",
        customer_id="cus_1",
        kind="resolved",
        action_type="refund",
        verdict="allow",
        code="refund_ok",
        grounded=True,
        detail={"amount_cents": "2000", "invoice_id": "in_1"},
        timestamp="2025-01-31T00:00:00+00:00",
    )
    log.append(
        ticket_id="tkt_2",
        customer_id="cus_2",
        kind="escalated",
        action_type="refund",
        verdict="escalate",
        code="refund_exceeds_cap",
        grounded=True,
        detail={"amount_cents": "999999"},
        timestamp="2025-01-31T00:01:00+00:00",
    )
    return log


def test_first_record_has_genesis_prev_and_seq_zero() -> None:
    log = _log()
    first = log.records[0]
    assert first.seq == 0
    assert first.prev_hash == GENESIS_HASH


def test_records_chain_by_hash() -> None:
    log = _log()
    assert log.records[1].prev_hash == log.records[0].hash
    assert log.records[1].seq == 1


def test_verify_intact_chain_is_true() -> None:
    log = _log()
    assert verify_chain(log.records) is True


def test_verify_detects_a_tampered_record() -> None:
    log = _log()
    # Flip a recorded amount without recomputing the hash → chain must break.
    tampered = list(log.records)
    tampered[0] = tampered[0].model_copy(
        update={"detail": {"amount_cents": "1", "invoice_id": "in_1"}}
    )
    assert verify_chain(tampered) is False


def test_verify_detects_a_dropped_record() -> None:
    log = _log()
    assert verify_chain([log.records[1]]) is False  # seq jumps / prev mismatch


def test_jsonl_roundtrips_and_still_verifies() -> None:
    log = _log()
    text = log.to_jsonl()
    restored = AuditLog.from_jsonl(text)
    assert [r.hash for r in restored.records] == [r.hash for r in log.records]
    assert verify_chain(restored.records) is True


def test_redact_drops_pii_and_keeps_allowlisted_fields() -> None:
    out = redact(
        {
            "email": "ada@example.com",  # PII — dropped
            "body": "my card number is ...",  # raw ticket text — dropped
            "name": "Ada",  # PII — dropped
            "amount_cents": 2000,  # safe — kept, stringified
            "invoice_id": "in_1",  # safe — kept
            "gate_code": "refund_ok",  # safe — kept
        }
    )
    assert out == {"amount_cents": "2000", "invoice_id": "in_1", "gate_code": "refund_ok"}


def test_redact_stringifies_all_values() -> None:
    out = redact({"grounded": True, "amount_cents": 50})
    assert out == {"grounded": "True", "amount_cents": "50"}
