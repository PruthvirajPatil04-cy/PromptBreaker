"""Adaptive mutation ordering — the feedback loop between outcomes and tactics.

The algorithmic mutators are pure functions; this policy remembers which ones
actually defeated each target and biases future runs toward them. Two rules
keep it honest:

  * exploration before exploitation — mutators with no data for a target
    always sort ahead of proven ones, so the policy can never lock itself
    into a stale ordering,
  * bounded and deterministic — ordering is a stable sort over rates, so a
    run with the same stats and seed mutates identically.

Stats live in memory while a run executes; the API loads them from the
store before the run and writes them back after (see api/app.py), so the
engine itself never touches persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from promptbreaker.engine.mutators import MUTATOR_NAMES


@dataclass
class MutationPolicy:
    """Per-target mutator effectiveness: wins / tries, keyed by mutator name."""

    stats: dict[str, dict[str, int]] = field(default_factory=dict)  # mutator -> {tries, wins}

    @classmethod
    def from_rows(cls, rows: list[tuple[str, int, int]]) -> MutationPolicy:
        """Build from (mutator, tries, wins) rows as stored by the repo."""
        return cls(stats={
            m: {"tries": int(t), "wins": int(w)} for m, t, w in rows if t or w
        })

    def record(self, mutator: str, won: bool) -> None:
        """One probe fired (try) and whether it defeated the target (win)."""
        slot = self.stats.setdefault(mutator, {"tries": 0, "wins": 0})
        slot["tries"] += 1
        if won:
            slot["wins"] += 1

    def win_rate(self, mutator: str) -> float:
        s = self.stats.get(mutator)
        if not s or not s["tries"]:
            return 0.0
        return s["wins"] / s["tries"]

    def ordering(self) -> list[str]:
        """Mutator names sorted best-first for the next run.

        Unseen mutators (no tries recorded) sort first — the policy must
        explore before it can exploit. Ties break by name so the order is
        fully deterministic.
        """
        return sorted(
            MUTATOR_NAMES,
            key=lambda m: (self.stats.get(m, {}).get("tries", 0) > 0, -self.win_rate(m), m),
        )

    def rows(self) -> list[tuple[str, int, int]]:
        """(mutator, tries, wins) tuples for persistence."""
        return [(m, s["tries"], s["wins"]) for m, s in sorted(self.stats.items())]
