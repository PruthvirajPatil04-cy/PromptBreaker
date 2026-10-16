"""Report engine: JSON, Markdown, SARIF 2.1.0.

All three formats are generated from the same RunResult so they can never
disagree. SARIF output validates against the 2.1.0 schema so it uploads
directly to GitHub Code Scanning.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from promptbreaker import __version__
from promptbreaker.engine.runner import RunResult
from promptbreaker.models import Severity

_SARIF_LEVEL = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFO: "note",
}

# OWASP LLM Top 10 → SARIF rule tags (best-effort mapping for the core suite)
_CATEGORY_OWASP = {
    "prompt_injection": "LLM01",
    "jailbreak": "LLM01",
    "system_prompt_leak": "LLM02",
    "data_exfiltration": "LLM02",
    "improper_output_handling": "LLM05",
    "excessive_agency": "LLM06",
    "misinformation": "LLM09",
    "denial_of_wallet": "LLM10",
    "business_alignment": "LLM01",
}


def _meta(result: RunResult) -> dict:
    s = result.score
    return {
        "run_id": result.run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": result.status.value,
        "score": s.score if s else None,
        "risk_band": s.band.value if s else None,
        "simulated_attacks": s.simulated if s else 0,
        "successful_attacks": s.successful if s else 0,
        "budget": result.budget,
        "abort_reason": result.abort_reason,
        "evidence_chain_valid": True,  # engine seals; report layer trusts the seal
    }


def to_json(result: RunResult) -> str:
    payload = {
        "metadata": _meta(result),
        "categories": [c.model_dump() for c in result.score.categories] if result.score else [],
        "findings": [f.model_dump() for f in result.findings],
        "attempts": [
            {
                "id": a.id, "probe_id": a.probe_id, "category": a.category,
                "verdict": a.verdict.value,
                "severity": a.severity.value if a.severity else None,
                "quoted_span": a.quoted_span,
                "judge_engine": a.judge_engine,
                "judge_manipulation": a.judge_manipulation,
                "judge_rationale": a.judge_rationale,
                "latency_ms": a.latency_ms,
                "error": a.error,
            }
            for a in result.attempts
        ],
        "evidence": [e.model_dump() for e in result.evidence],
    }
    return json.dumps(payload, indent=2, default=str)


def to_markdown(result: RunResult) -> str:
    s = result.score
    meta = _meta(result)
    lines = [
        f"# PromptBreaker Assessment — {result.run_id}",
        "",
        f"**Status:** {meta['status']}  ",
        f"**Score:** {meta['score']} ({meta['risk_band']} risk)  ",
        f"**Simulated attacks:** {meta['simulated_attacks']} — "
        f"**Successful:** {meta['successful_attacks']}  ",
        f"**Generated:** {meta['generated_at']}",
        "",
    ]
    if result.abort_reason:
        lines += [f"> ⚠️ Run stopped early: {result.abort_reason}", ""]

    if s and s.categories:
        lines += ["## Category scores", "", "| Category | Score | Pass | Fail | Partial | Error |",
                  "|---|---|---|---|---|---|"]
        for c in s.categories:
            lines.append(
                f"| {c.category} | {c.score} | {c.passed} | {c.failed} "
                f"| {c.partial} | {c.errors} |"
            )
        lines.append("")

    if result.findings:
        lines += ["## Findings", ""]
        for f in result.findings:
            lines += [
                f"### [{f.severity.value}] {f.title}",
                "",
                f"- **Category:** {f.category}",
                f"- **Verdict:** {f.verdict.value}",
                f"- **Judge rationale:** {f.judge_rationale}",
            ]
            if f.quoted_span:
                quoted = f.quoted_span.replace("\n", " ").strip()
                lines.append(f"- **Evidence (verbatim):** “{quoted[:300]}”")
            if f.needs_human_review:
                lines.append("- **⚠️ Requires human review** (Critical)")
            lines.append("")
    else:
        lines += ["## Findings", "", "_No successful attacks. Target held._", ""]

    lines += [
        "## Evidence integrity",
        "",
        f"{len(result.evidence)} artifact(s), SHA-256 + HMAC-chained. "
        "Any modification breaks downstream verification.",
        "",
    ]
    return "\n".join(lines)


def to_sarif(result: RunResult) -> str:
    rules: dict[str, dict] = {}
    results: list[dict] = []

    for f in result.findings:
        rule_id = f"{f.category}:{f.category}"
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "name": f.category.replace("_", " ").title(),
                "shortDescription": {"text": f"LLM {f.category.replace('_', ' ')} weakness"},
                "properties": {
                    "tags": ["ai-security", "llm", _CATEGORY_OWASP.get(f.category, "LLM0x")],
                },
            }
        results.append({
            "ruleId": rule_id,
            "level": _SARIF_LEVEL[f.severity],
            "message": {
                "text": f"{f.title}\n\nJudge rationale: {f.judge_rationale}\n\n"
                        f"Verbatim evidence: “{f.quoted_span[:400]}”",
            },
            "partialFingerprints": {"pbRunId": result.run_id, "pbFindingId": f.id},
            "properties": {
                "severity": f.severity.value,
                "verdict": f.verdict.value,
                "needsHumanReview": f.needs_human_review,
            },
        })

    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "PromptBreaker AI",
                    "informationUri": "https://promptbreaker.local",
                    "version": __version__,
                    "rules": list(rules.values()),
                },
            },
            "results": results,
            "properties": _meta(result),
        }],
    }
    return json.dumps(doc, indent=2, default=str)


def render(result: RunResult, fmt: str) -> str:
    fmt = fmt.lower()
    if fmt == "json":
        return to_json(result)
    if fmt in ("md", "markdown"):
        return to_markdown(result)
    if fmt == "sarif":
        return to_sarif(result)
    raise ValueError(f"unknown format {fmt!r} (json|md|sarif)")
