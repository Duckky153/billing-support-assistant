"""Concurrent hash-linked local audit records with allowlisted details.

Append and snapshots are locked. Hashes detect modified records and broken links,
not valid-prefix removal or full chain replacement without a trusted checkpoint.
IDs remain identifiers; real deployments need log access controls.
"""

from __future__ import annotations

import hashlib
import json
import threading

from pydantic import BaseModel, ConfigDict

GENESIS_HASH = "0" * 64

# Only these keys survive redaction. Everything else is dropped. This is an
# allowlist, not a denylist: a new field is invisible to the audit log until
# someone deliberately adds it here.
_ALLOWED_DETAIL_KEYS: frozenset[str] = frozenset(
    {
        "action",
        "intent",
        "verdict",
        "code",
        "gate_code",
        "grounding_code",
        "grounded",
        "amount_cents",
        "invoice_id",
        "subscription_id",
        "resolution",
        "confidence",
    }
)


def redact(raw: dict[str, object]) -> dict[str, str]:
    """Keep only allowlisted, non-PII fields; stringify their values."""
    return {k: str(v) for k, v in raw.items() if k in _ALLOWED_DETAIL_KEYS}


class AuditRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    seq: int
    timestamp: str
    ticket_id: str
    customer_id: str
    kind: str
    action_type: str
    verdict: str
    code: str
    grounded: bool
    detail: dict[str, str]
    prev_hash: str
    hash: str

    def payload(self) -> dict[str, object]:
        """The hashed content — every field except ``hash`` itself."""
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "ticket_id": self.ticket_id,
            "customer_id": self.customer_id,
            "kind": self.kind,
            "action_type": self.action_type,
            "verdict": self.verdict,
            "code": self.code,
            "grounded": self.grounded,
            "detail": self.detail,
            "prev_hash": self.prev_hash,
        }

    def compute_hash(self) -> str:
        return _hash_payload(self.payload())


def _hash_payload(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AuditLog:
    """An in-memory, append-only hash chain of audit records."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []
        self._lock = threading.RLock()

    @property
    def records(self) -> list[AuditRecord]:
        with self._lock:
            return [record.model_copy(deep=True) for record in self._records]

    @property
    def head_hash(self) -> str:
        with self._lock:
            return self._records[-1].hash if self._records else GENESIS_HASH

    def append(
        self,
        *,
        ticket_id: str,
        customer_id: str,
        kind: str,
        action_type: str,
        verdict: str,
        code: str,
        grounded: bool,
        detail: dict[str, str],
        timestamp: str,
    ) -> AuditRecord:
        with self._lock:
            payload = {
                "seq": len(self._records),
                "timestamp": timestamp,
                "ticket_id": ticket_id,
                "customer_id": customer_id,
                "kind": kind,
                "action_type": action_type,
                "verdict": verdict,
                "code": code,
                "grounded": grounded,
                "detail": redact(dict(detail)),
                "prev_hash": self.head_hash,
            }
            record = AuditRecord(hash=_hash_payload(payload), **payload)  # type: ignore[arg-type]
            self._records.append(record)
            return record.model_copy(deep=True)

    def to_jsonl(self) -> str:
        return "\n".join(r.model_dump_json() for r in self.records)

    @classmethod
    def from_jsonl(cls, text: str) -> AuditLog:
        log = cls()
        for line in text.splitlines():
            line = line.strip()
            if line:
                log._records.append(AuditRecord.model_validate_json(line))
        return log


def verify_chain(records: list[AuditRecord]) -> bool:
    """Return True iff the records form an intact, sequential hash chain."""
    prev_hash = GENESIS_HASH
    for expected_seq, record in enumerate(records):
        if record.seq != expected_seq:
            return False
        if record.prev_hash != prev_hash:
            return False
        if record.compute_hash() != record.hash:
            return False
        prev_hash = record.hash
    return True
