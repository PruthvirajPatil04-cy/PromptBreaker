"""Budget tracker — the termination guarantee for any loop.

Every unit of spend flows through here. When any cap is hit, exhausted()
returns True and the engine MUST break out and produce a partial report.
There is no unbounded mode.
"""

from __future__ import annotations

import time

from promptbreaker.errors import BudgetExceededError
from promptbreaker.models import RunBudget


class BudgetTracker:
    def __init__(self, budget: RunBudget) -> None:
        self.budget = budget
        self.probes_used = 0
        self.mutations_used: dict[str, int] = {}
        self.tokens_used = 0
        self.cost_used = 0.0
        self._start = time.monotonic()

    # -- consumption --------------------------------------------------------

    def charge_probe(self) -> None:
        self.probes_used += 1

    def charge_mutation(self, probe_id: str) -> int:
        n = self.mutations_used.get(probe_id, 0) + 1
        self.mutations_used[probe_id] = n
        return n

    def charge_tokens(self, tin: int, tout: int) -> None:
        self.tokens_used += tin + tout

    def charge_cost(self, usd: float) -> None:
        self.cost_used += usd

    def remaining_mutations(self, probe_id: str) -> int:
        used = self.mutations_used.get(probe_id, 0)
        return max(0, self.budget.max_mutations_per_probe - used)

    # -- checks -------------------------------------------------------------

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start

    def exhausted(self) -> str | None:
        """Return the reason the budget is exhausted, or None."""
        b = self.budget
        if self.probes_used >= b.max_probes:
            return f"probe cap reached ({b.max_probes})"
        if self.tokens_used >= b.max_tokens:
            return f"token cap reached ({b.max_tokens})"
        if self.cost_used >= b.max_cost_usd:
            return f"cost cap reached (${b.max_cost_usd})"
        if self.elapsed_seconds >= b.timeout_seconds:
            return f"wall-clock timeout reached ({b.timeout_seconds}s)"
        return None

    def assert_not_exhausted(self) -> None:
        reason = self.exhausted()
        if reason:
            raise BudgetExceededError(reason)

    def snapshot(self) -> dict:
        b = self.budget
        return {
            "probes": {"used": self.probes_used, "cap": b.max_probes},
            "tokens": {"used": self.tokens_used, "cap": b.max_tokens},
            "cost_usd": {"used": round(self.cost_used, 4), "cap": b.max_cost_usd},
            "elapsed_s": round(self.elapsed_seconds, 1),
            "timeout_s": b.timeout_seconds,
        }
