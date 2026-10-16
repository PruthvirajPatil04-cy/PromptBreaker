"""Append-only run event log.

Events are the durable source of truth. SSE is a view over this log (with
Last-Event-ID replay), and the audit trail comes free. The engine never
mutates past events.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RunEvent:
    seq: int
    run_id: str
    type: str          # run.started | probe.sent | probe.judged | run.finished | ...
    payload: dict = field(default_factory=dict)
    ts: str = field(default_factory=_now_iso)

    def to_sse(self) -> dict:
        return {"id": str(self.seq), "event": self.type, "data": self.payload}

    def to_json(self) -> str:
        return json.dumps(
            {"seq": self.seq, "run_id": self.run_id, "type": self.type,
             "payload": self.payload, "ts": self.ts},
            default=str,
        )


class EventLog:
    """In-memory event log with subscriber fan-out.

    The API's SSE endpoint replays from `since` and then subscribes, so a
    reconnecting client never loses events. Persistence to Postgres/SQLite is
    handled by store/; this class owns ordering and fan-out only.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[RunEvent]] = {}
        self._seq: dict[str, int] = {}
        self._subs: dict[str, list[Callable[[RunEvent], None]]] = {}

    def append(self, run_id: str, type_: str, payload: dict | None = None) -> RunEvent:
        seq = self._seq.get(run_id, 0) + 1
        self._seq[run_id] = seq
        ev = RunEvent(seq=seq, run_id=run_id, type=type_, payload=payload or {})
        self._events.setdefault(run_id, []).append(ev)
        for cb in self._subs.get(run_id, []):
            cb(ev)
        return ev

    def since(self, run_id: str, last_seq: int = 0) -> list[RunEvent]:
        return [e for e in self._events.get(run_id, []) if e.seq > last_seq]

    def subscribe(self, run_id: str, cb: Callable[[RunEvent], None]) -> Callable[[], None]:
        self._subs.setdefault(run_id, []).append(cb)

        def unsubscribe() -> None:
            if cb in self._subs.get(run_id, []):
                self._subs[run_id].remove(cb)

        return unsubscribe

    def all(self, run_id: str) -> list[RunEvent]:
        return list(self._events.get(run_id, []))


# process-wide default log (the API and engine share it)
event_log = EventLog()

