"""Judge calibration gate — the prefilter must match every golden verdict.

These are the zero-false-positive locks for the judge: a signature change
that reclassifies a known response fails here before it can ship. The LLM
judge is measured separately (scripts/calibrate_judge.py) because it needs
a live model — nothing in this file touches the network.
"""

from __future__ import annotations

import pytest

from promptbreaker.judge.calibration import load_golden
from promptbreaker.judge.core import prefilter
from promptbreaker.models import Verdict

CASES = load_golden()


def test_golden_set_is_substantial_and_wellformed():
    assert len(CASES) >= 12, "golden set must cover all verdict families"
    engines = {c.engine for c in CASES}
    assert engines == {"prefilter", "llm"}
    verdicts = {c.expected for c in CASES}
    assert {"PASS", "FAIL", "PARTIAL"} <= verdicts


@pytest.mark.parametrize("case", [c for c in CASES if c.engine == "prefilter"],
                         ids=lambda c: c.id)
def test_prefilter_matches_golden_verdicts(case):
    got = prefilter(case.as_probe(), case.response)
    assert got is not None, f"{case.id}: prefilter must decide this case"
    assert got.verdict == Verdict(case.expected), (
        f"{case.id}: expected {case.expected}, got {got.verdict} — {case.note}"
    )
    if case.expected in ("FAIL", "PARTIAL"):
        # the quoted-span rule: a failing verdict without verbatim evidence
        # is invalid, and the span must appear in the response
        assert got.quoted_span, f"{case.id}: failing verdict lacks quoted evidence"
        assert got.quoted_span in case.response, f"{case.id}: quote is not verbatim"


@pytest.mark.parametrize("case", [c for c in CASES if c.engine == "llm"],
                         ids=lambda c: c.id)
def test_prefilter_abstains_on_llm_cases(case):
    """Ambiguous cases must escalate, never be guessed by rules."""
    got = prefilter(case.as_probe(), case.response)
    assert got is None, (
        f"{case.id}: prefilter guessed {got.verdict} on an ambiguous case "
        f"(correct handling: abstain and escalate to the LLM judge)"
    )


def test_golden_manipulation_case_is_flagged():
    case = next(c for c in CASES if c.id == "gold-009")
    got = prefilter(case.as_probe(), case.response)
    assert got is not None and got.judge_manipulation is True
