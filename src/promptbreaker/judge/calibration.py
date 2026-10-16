"""Judge calibration — the golden dataset gate.

The prefilter is deterministic, so its accuracy against the golden set is a
hard CI gate (tests/test_judge_calibration.py): a signature change that
breaks a known verdict fails the build before it ships.

The LLM judge needs a live model, so its accuracy is MEASURED, never
assumed: run scripts/calibrate_judge.py against a running Ollama (or
PB_CALIBRATE_LLM=1 in an environment that has one). A judge that drifts
below threshold fails that run.

Golden cases live next to this module (golden.jsonl) so they ship with the
package and stay versioned with the signatures they test.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from promptbreaker.models import Probe, Severity

GOLDEN_PATH = Path(__file__).parent / "golden.jsonl"


@dataclass(frozen=True)
class GoldenCase:
    """One known (probe, response) pair with the verdict a correct judge
    must produce."""

    id: str
    engine: str              # prefilter = rules decide; llm = rules must abstain
    probe_category: str
    severity_if_failed: str
    payload: str
    response: str
    expected: str            # PASS | FAIL | PARTIAL
    note: str = ""

    def as_probe(self) -> Probe:
        return Probe(
            id=self.id, name=self.id, category=self.probe_category,
            payload=self.payload,
            severity_if_failed=Severity(self.severity_if_failed),
        )


def load_golden(path: Path = GOLDEN_PATH) -> list[GoldenCase]:
    cases = [
        GoldenCase(**json.loads(line))
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("golden set has duplicate case ids")
    return cases
