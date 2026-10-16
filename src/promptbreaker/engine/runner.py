"""The assessment engine: plan → execute → judge → mutate → report.

A durable, budget-capped state machine. Every transition emits an event to the
append-only log; every attempt produces tamper-evident evidence. The mutation
loop is bounded by BudgetTracker, so a run always terminates and always
produces a (possibly partial) report.

Execution is parallel (semaphore-bounded, default settings.run_concurrency)
but never unordered where it matters: attempts land in plan order in the
result, the evidence chain is sealed in that same order, and the budget is
charged synchronously between awaits so no check-then-charge race exists.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from promptbreaker.adapters.base import TargetAdapter
from promptbreaker.config import settings
from promptbreaker.engine.adaptive import MutationPolicy
from promptbreaker.engine.budget import BudgetTracker
from promptbreaker.engine.events import EventLog, event_log
from promptbreaker.engine.evidence import EvidenceChain
from promptbreaker.engine.mutators import mutate_named
from promptbreaker.errors import (
    AdapterError,
    BudgetExceededError,
    JudgeError,
    ScopeError,
    SsrfBlockedError,
)
from promptbreaker.judge.core import LlmJudge, judge_response
from promptbreaker.models import (
    Attempt,
    Evidence,
    Finding,
    Probe,
    RunBudget,
    RunStatus,
    ScopeAttestation,
    Severity,
    Verdict,
)
from promptbreaker.probes.registry import load_suite
from promptbreaker.scoring import overall_score

log = logging.getLogger("promptbreaker.engine")


@dataclass
class RunResult:
    run_id: str
    status: RunStatus
    attempts: list[Attempt] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    score: Any = None
    budget: dict = field(default_factory=dict)
    abort_reason: str = ""


@dataclass
class _Job:
    """One probe firing: a base probe, one of its mutations, or a chain."""

    probe: Probe
    parent_id: str = ""
    mutator: str = ""


class Engine:
    """Executes one assessment run."""

    def __init__(
        self,
        *,
        adapter: TargetAdapter,
        attestation: ScopeAttestation,
        budget: RunBudget | None = None,
        suite: str = "core",
        llm_judge: LlmJudge | None = None,
        seed: int = 0,
        event_bus: EventLog | None = None,
        category_weights: dict[str, float] | None = None,
        concurrency: int = 0,                     # 0 → settings.run_concurrency
        probes: list[Probe] | None = None,        # explicit plan (resume flows)
        system_context: str = "",                 # override every probe's system prompt
        target_label: str = "",                   # stats key for adaptive mutation
        mutation_policy: MutationPolicy | None = None,
        on_attempt: Callable[[Attempt], Awaitable[None]] | None = None,
    ) -> None:
        self.adapter = adapter
        self.attestation = attestation
        self.budget = budget or RunBudget(
            max_probes=settings.max_probes_per_run,
            max_mutations_per_probe=settings.max_mutations_per_probe,
            max_tokens=settings.max_run_tokens,
            max_cost_usd=settings.max_run_cost_usd,
            timeout_seconds=settings.run_timeout_seconds,
        )
        self.suite = suite
        self.llm_judge = llm_judge
        self.seed = seed
        self.events = event_bus or event_log
        self.category_weights = category_weights
        self.tracker = BudgetTracker(self.budget)
        self.evidence_chain = EvidenceChain(settings.evidence_hmac_key)
        self.run_id = f"run-{uuid.uuid4().hex[:12]}"
        self.concurrency = max(1, concurrency or settings.run_concurrency)
        self._probe_override = probes
        self.system_context = system_context
        self.target_label = target_label or self._scope_host()
        self.mutation_policy = mutation_policy
        self.on_attempt = on_attempt

    # ------------------------------------------------------------------ run

    async def run(self) -> RunResult:
        probes = (
            self._probe_override if self._probe_override is not None
            else load_suite(self.suite)
        )
        result = RunResult(run_id=self.run_id, status=RunStatus.QUEUED)

        # SCOPE GATE — refuse anything outside an unexpired attestation.
        scope_host = self._scope_host()
        if not self.attestation.is_valid(scope_host):
            self.events.append(self.run_id, "run.rejected", {"reason": "outside authorized scope"})
            raise ScopeError(
                f"target {scope_host!r} is not covered by attestation "
                f"{self.attestation.target_pattern!r} (expires {self.attestation.expires})"
            )

        jobs = self._plan(probes)
        self.events.append(self.run_id, "run.started", {
            "suite": self.suite, "probes": len(probes), "jobs": len(jobs),
            "concurrency": self.concurrency, "budget": self.tracker.snapshot(),
        })
        result.status = RunStatus.EXECUTE

        try:
            slots: list[Attempt | None] = [None] * len(jobs)
            sem = asyncio.Semaphore(self.concurrency)

            async def _one(index: int, job: _Job) -> None:
                async with sem:
                    # sync check-and-charge: no await between them, so parallel
                    # tasks cannot both pass the gate on the same unit of budget
                    if self.tracker.exhausted():
                        return
                    if job.mutator:
                        self.tracker.charge_mutation(job.parent_id)
                    slots[index] = await self._run_probe(
                        job.probe, result, parent_id=job.parent_id, mutator=job.mutator,
                    )

            outcomes = await asyncio.gather(
                *(_one(i, j) for i, j in enumerate(jobs)), return_exceptions=True,
            )

            # deterministic plan order, regardless of completion order
            result.attempts = [a for a in slots if a is not None]
            fatal = next(
                (o for o in outcomes
                 if isinstance(o, (AdapterError, SsrfBlockedError, ScopeError))),
                None,
            )
            if fatal is not None:
                raise fatal
            for o in outcomes:
                if isinstance(o, BudgetExceededError):
                    result.abort_reason = str(o)

            reason = self.tracker.exhausted()
            if reason and not result.abort_reason:
                result.abort_reason = reason
            result.status = RunStatus.DONE
        except (AdapterError, SsrfBlockedError) as exc:
            result.status = RunStatus.FAILED
            result.abort_reason = str(exc)
            self.events.append(self.run_id, "run.failed", {"error": str(exc)})

        # score + evidence finalize (in plan order → stable, auditable chain)
        result.score = overall_score(
            result.attempts, category_weights=self.category_weights,
        )
        result.budget = self.tracker.snapshot()
        result.findings = self._findings_from(result)
        for a in result.attempts:
            result.evidence.append(self.evidence_chain.add(
                self.run_id, a.id, {
                    "probe_id": a.probe_id, "verdict": a.verdict.value,
                    "quoted_span": a.quoted_span,
                    "response_sha": EvidenceChain.sha256_of({"t": a.target_response}),
                },
            ))
        # seal report evidence last so the chain covers everything
        report_ev = self.evidence_chain.add(
            self.run_id, "report", {"findings": len(result.findings)}, kind="report",
        )
        result.evidence.append(report_ev)

        self.events.append(self.run_id, "run.finished", {
            "status": result.status.value,
            "score": result.score.score if result.score else None,
            "band": result.score.band.value if result.score else None,
            "attempts": len(result.attempts),
            "abort_reason": result.abort_reason,
            "budget": result.budget,
        })
        return result

    # ------------------------------------------------------------- internals

    def _plan(self, probes: list[Probe]) -> list[_Job]:
        """Expand probes into jobs: base + up to max_mutations per probe.

        Multi-turn chains already escalate in-band (each turn is a probe
        call), so they don't fan out into mutations — the budget buys depth,
        not width. Adaptive ordering biases which mutators are picked.
        """
        order = self.mutation_policy.ordering() if self.mutation_policy else None
        jobs: list[_Job] = []
        for probe in probes:
            jobs.append(_Job(probe))
            if probe.turns:
                continue
            remaining = self.tracker.remaining_mutations(probe.id)
            if not remaining:
                continue
            seed = self.seed + hash(probe.id) % 2**31
            for name, mutated in mutate_named(probe, seed, remaining, order=order):
                jobs.append(_Job(mutated, parent_id=probe.id, mutator=name))
        return jobs

    def _scope_host(self) -> str:
        from urllib.parse import urlparse
        return (urlparse(self.adapter.endpoint).hostname or self.adapter.endpoint).lower()

    async def _run_probe(
        self, probe: Probe, result: RunResult, *, parent_id: str = "", mutator: str = "",
    ) -> Attempt | None:
        self.tracker.charge_probe()
        self.events.append(self.run_id, "probe.sent", {
            "probe_id": probe.id, "category": probe.category, "parent": parent_id,
            "turns": len(probe.turns),
        })

        attempt = Attempt(
            id=f"att-{uuid.uuid4().hex[:10]}", run_id=self.run_id,
            probe_id=probe.id, category=probe.category, sent_payload=probe.payload,
        )

        messages: list[dict[str, str]] = []
        system_prompt = self.system_context or probe.system_context
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": probe.payload})

        try:
            tokens_in = tokens_out = latency_ms = 0
            resp = await self.adapter.complete(messages)
            for turn in probe.turns:
                # multi-turn chain: keep the conversation, escalate, judge the
                # final reply — the target's own earlier answers are context.
                messages.append({"role": "assistant", "content": resp.text})
                messages.append({"role": "user", "content": turn})
                tokens_in += resp.tokens_in
                tokens_out += resp.tokens_out
                latency_ms += resp.latency_ms
                resp = await self.adapter.complete(messages)
            attempt.target_response = resp.text
            attempt.tokens_in = tokens_in + resp.tokens_in
            attempt.tokens_out = tokens_out + resp.tokens_out
            attempt.latency_ms = latency_ms + resp.latency_ms
            if probe.turns:
                # evidence must show the FULL attack dialogue, not just turn 1
                attempt.sent_payload = "\n".join([probe.payload, *probe.turns])
            self.tracker.charge_tokens(attempt.tokens_in, attempt.tokens_out)
        except (AdapterError, SsrfBlockedError) as exc:
            attempt.verdict = Verdict.ERROR
            attempt.error = str(exc)[:500]
            self.events.append(
                self.run_id, "probe.error", {"probe_id": probe.id, "error": attempt.error},
            )
            if self.on_attempt:
                await self._notify(attempt)
            return attempt

        judged = await self._judge(probe, attempt)

        # adaptive feedback: did this mutator actually beat the target?
        if mutator and self.mutation_policy is not None:
            self.mutation_policy.record(
                mutator, judged.verdict in (Verdict.FAIL, Verdict.PARTIAL),
            )

        if self.on_attempt:
            await self._notify(judged)

        self.events.append(self.run_id, "probe.judged", {
            "probe_id": judged.probe_id, "verdict": judged.verdict.value,
            "severity": judged.severity.value if judged.severity else None,
            "judge": judged.judge_engine,
        })
        return judged

    async def _notify(self, attempt: Attempt) -> None:
        """Incremental persistence hook — never let a DB hiccup kill the run."""
        try:
            await self.on_attempt(attempt)  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            log.warning("on_attempt hook failed for %s: %s", attempt.id, exc)

    async def _judge(self, probe: Probe, attempt: Attempt) -> Attempt:
        # chains are judged on the full dialogue intent, not just turn one
        judge_probe = (
            probe.model_copy(update={"payload": attempt.sent_payload})
            if probe.turns else probe
        )
        try:
            judged = await judge_response(probe=judge_probe, response=attempt.target_response,
                                          llm=self.llm_judge)
        except JudgeError as exc:
            attempt.verdict = Verdict.ERROR
            attempt.error = f"judge: {exc}"[:500]
            return attempt
        # preserve identity + measured transport facts from the attempt
        judged.id = attempt.id
        judged.run_id = attempt.run_id
        judged.sent_payload = attempt.sent_payload
        judged.tokens_in, judged.tokens_out = attempt.tokens_in, attempt.tokens_out
        judged.latency_ms = attempt.latency_ms
        return judged

    def _findings_from(self, result: RunResult) -> list[Finding]:
        findings: list[Finding] = []
        for a in result.attempts:
            if a.verdict.value not in ("FAIL", "PARTIAL"):
                continue
            sev = a.severity or Severity.MEDIUM
            findings.append(Finding(
                id=f"fnd-{a.id}", run_id=self.run_id, attempt_id=a.id,
                title=f"{a.probe_id}: target complied ({a.verdict.value})",
                category=a.category, owasp="", severity=sev, verdict=a.verdict,
                quoted_span=a.quoted_span, judge_rationale=a.judge_rationale,
                needs_human_review=sev == Severity.CRITICAL,
            ))
        # worst-first, then alphabetical — parallel completion must not be
        # able to shuffle report ordering between identical runs
        order = {
            Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2,
            Severity.LOW: 1, Severity.INFO: 0,
        }
        findings.sort(key=lambda f: (-order.get(f.severity, 0), f.title))
        return findings


async def execute_run(**kwargs: Any) -> RunResult:
    """Convenience entry point used by CLI and API."""
    return await Engine(**kwargs).run()


def run_sync(**kwargs: Any) -> RunResult:
    return asyncio.run(execute_run(**kwargs))
