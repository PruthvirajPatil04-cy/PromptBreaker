"""The assessment engine: plan → execute → judge → mutate → report.

A durable, budget-capped state machine. Every transition emits an event to the
append-only log; every attempt produces tamper-evident evidence. The mutation
loop is bounded by BudgetTracker, so a run always terminates and always
produces a (possibly partial) report.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from promptbreaker.adapters.base import TargetAdapter
from promptbreaker.config import settings
from promptbreaker.engine.budget import BudgetTracker
from promptbreaker.engine.events import EventLog, event_log
from promptbreaker.engine.evidence import EvidenceChain
from promptbreaker.engine.mutators import mutate
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

    # ------------------------------------------------------------------ run

    async def run(self) -> RunResult:
        probes = load_suite(self.suite)
        result = RunResult(run_id=self.run_id, status=RunStatus.QUEUED)

        # SCOPE GATE — refuse anything outside an unexpired attestation.
        scope_host = self._scope_host()
        if not self.attestation.is_valid(scope_host):
            self.events.append(self.run_id, "run.rejected", {"reason": "outside authorized scope"})
            raise ScopeError(
                f"target {scope_host!r} is not covered by attestation "
                f"{self.attestation.target_pattern!r} (expires {self.attestation.expires})"
            )

        self.events.append(self.run_id, "run.started", {
            "suite": self.suite, "probes": len(probes), "budget": self.tracker.snapshot(),
        })
        result.status = RunStatus.EXECUTE

        try:
            for probe in probes:
                if self.tracker.exhausted():
                    break
                await self._run_probe(probe, result)
                # bounded mutation loop — terminates by construction
                remaining = self.tracker.remaining_mutations(probe.id)
                if remaining and not self.tracker.exhausted():
                    for mutated in mutate(probe, self.seed + hash(probe.id) % 2**31, remaining):
                        if self.tracker.exhausted():
                            break
                        await self._run_probe(mutated, result, parent_id=probe.id)

            result.status = RunStatus.DONE
        except BudgetExceededError as exc:
            result.status = RunStatus.DONE
            result.abort_reason = str(exc)
        except (AdapterError, SsrfBlockedError) as exc:
            result.status = RunStatus.FAILED
            result.abort_reason = str(exc)
            self.events.append(self.run_id, "run.failed", {"error": str(exc)})

        # score + evidence finalize
        result.score = overall_score(
            result.attempts, category_weights=self.category_weights,
        )
        result.budget = self.tracker.snapshot()
        result.findings = self._findings_from(result)
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

    def _scope_host(self) -> str:
        from urllib.parse import urlparse
        return (urlparse(self.adapter.endpoint).hostname or self.adapter.endpoint).lower()

    async def _run_probe(self, probe: Probe, result: RunResult, *, parent_id: str = "") -> None:
        self.tracker.charge_probe()
        self.events.append(self.run_id, "probe.sent", {
            "probe_id": probe.id, "category": probe.category, "parent": parent_id,
        })

        attempt = Attempt(
            id=f"att-{uuid.uuid4().hex[:10]}", run_id=self.run_id,
            probe_id=probe.id, category=probe.category, sent_payload=probe.payload,
        )

        messages = []
        if probe.system_context:
            messages.append({"role": "system", "content": probe.system_context})
        messages.append({"role": "user", "content": probe.payload})

        try:
            resp = await self.adapter.complete(messages)
            attempt.target_response = resp.text
            attempt.tokens_in, attempt.tokens_out = resp.tokens_in, resp.tokens_out
            attempt.latency_ms = resp.latency_ms
            self.tracker.charge_tokens(resp.tokens_in, resp.tokens_out)
        except (AdapterError, SsrfBlockedError) as exc:
            attempt.verdict = Verdict.ERROR
            attempt.error = str(exc)[:500]
            self.events.append(
                self.run_id, "probe.error", {"probe_id": probe.id, "error": attempt.error}
            )
            result.attempts.append(attempt)
            return

        judged = await self._judge(probe, attempt)
        result.attempts.append(judged)

        ev = self.evidence_chain.add(self.run_id, judged.id, {
            "probe_id": judged.probe_id, "verdict": judged.verdict.value,
            "quoted_span": judged.quoted_span, "response_sha": EvidenceChain.sha256_of(
                {"t": judged.target_response}),
        })
        result.evidence.append(ev)

        self.events.append(self.run_id, "probe.judged", {
            "probe_id": judged.probe_id, "verdict": judged.verdict.value,
            "severity": judged.severity.value if judged.severity else None,
        })

    async def _judge(self, probe: Probe, attempt: Attempt) -> Attempt:
        try:
            judged = await judge_response(probe, attempt.target_response, llm=self.llm_judge)
        except JudgeError as exc:
            attempt.verdict = Verdict.ERROR
            attempt.error = f"judge: {exc}"[:500]
            return attempt
        # preserve identity + measured transport facts from the attempt
        judged.id = attempt.id
        judged.run_id = attempt.run_id
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
        # worst-first
        order = {
            Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2,
            Severity.LOW: 1, Severity.INFO: 0,
        }
        findings.sort(key=lambda f: order.get(f.severity, 0), reverse=True)
        return findings


async def execute_run(**kwargs: Any) -> RunResult:
    """Convenience entry point used by CLI and API."""
    return await Engine(**kwargs).run()


def run_sync(**kwargs: Any) -> RunResult:
    return asyncio.run(execute_run(**kwargs))
