"""Tamper-evident evidence chain.

Every artifact is SHA-256 hashed; each hash is HMAC-chained to the previous
one, so removing or editing any evidence row breaks verification for all
downstream artifacts. This is what lets an auditor trust the report.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from promptbreaker.models import Evidence, utcnow


class EvidenceChain:
    def __init__(self, hmac_key: str) -> None:
        if not hmac_key:
            raise ValueError("evidence hmac key must not be empty")
        self._key = hmac_key.encode()
        self._prev = ""

    @staticmethod
    def sha256_of(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def add(self, run_id: str, attempt_id: str, payload: dict, *, kind: str = "attempt") -> Evidence:
        digest = self.sha256_of(payload)
        message = f"{digest}:{self._prev}".encode()
        mac = hmac.new(self._key, message, hashlib.sha256).hexdigest()
        # Row ID must be unique per run: two runs against a deterministic
        # target hash identical payloads, so the digest alone collides.
        # Integrity lives in sha256 + the HMAC chain, not in this ID.
        ev = Evidence(
            id=f"ev-{run_id[4:]}-{attempt_id}", run_id=run_id, attempt_id=attempt_id,
            kind=kind, sha256=digest, prev_hmac=self._prev, hmac=mac,
            created_at=utcnow(),
        )
        self._prev = mac
        return ev

    def verify_chain(self, evidence: list[Evidence]) -> bool:
        """Recompute the whole chain. Any edit/drop/reorder fails."""
        prev = ""
        for ev in evidence:
            if ev.prev_hmac != prev:
                return False
            message = f"{ev.sha256}:{prev}".encode()
            if not hmac.compare_digest(ev.hmac, hmac.new(self._key, message, hashlib.sha256).hexdigest()):
                return False
            prev = ev.hmac
        return True
