#!/usr/bin/env python
"""Measure judge accuracy against the golden dataset.

Prefilter cases are checked locally (no model needed). LLM cases are sent to
the configured judge endpoint (PB_JUDGE_BASE_URL, default local Ollama), so
run this wherever the judge model is up:

    .venv/bin/python scripts/calibrate_judge.py            # full calibration
    .venv/bin/python scripts/calibrate_judge.py --prefilter-only

Exit code 0 = judge is calibrated. Non-zero = drift, do not ship.

The pytest gate (tests/test_judge_calibration.py) always runs the prefilter
half in CI; this script is the half that needs a live model.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from promptbreaker.config import settings  # noqa: E402
from promptbreaker.judge.calibration import load_golden  # noqa: E402
from promptbreaker.judge.core import LlmJudge, prefilter  # noqa: E402


async def main(prefilter_only: bool, min_llm_accuracy: float) -> int:
    cases = load_golden()
    judge = LlmJudge(settings.judge_base_url, settings.judge_api_key, settings.judge_model)
    rows: list[tuple[str, str, str, str, bool]] = []  # id, engine, expected, got, ok

    for case in cases:
        probe = case.as_probe()
        got = prefilter(probe, case.response)
        if case.engine == "prefilter":
            verdict = got.verdict.value if got else "ABSTAIN"
            rows.append((case.id, "prefilter", case.expected, verdict,
                         verdict == case.expected))
            continue
        # ambiguous case: rules must abstain, model decides
        if got is not None:
            rows.append((case.id, "llm(skipped)", case.expected,
                         f"prefilter-guessed:{got.verdict.value}", False))
            continue
        if prefilter_only:
            rows.append((case.id, "llm(skipped)", case.expected, "skipped", True))
            continue
        try:
            verdict = (await judge.judge(probe, case.response)).verdict.value
        except Exception as exc:  # noqa: BLE001 — a judge failure IS a miss
            verdict = f"ERROR({str(exc)[:60]})"
        rows.append((case.id, "llm", case.expected, verdict, verdict == case.expected))

    width = max(len(r[0]) for r in rows)
    for cid, engine, expected, got, ok in rows:
        mark = "PASS" if ok else "MISS"
        print(f"[{mark}] {cid:<{width}}  {engine:<12} expected={expected:<8} got={got}")

    pre = [r for r in rows if r[1] == "prefilter"]
    llm = [r for r in rows if r[1] == "llm"]
    pre_acc = sum(r[4] for r in pre) / len(pre) if pre else 1.0
    llm_acc = sum(r[4] for r in llm) / len(llm) if llm else None

    print(f"\nprefilter accuracy: {pre_acc:.0%} ({sum(r[4] for r in pre)}/{len(pre)})")
    if llm_acc is not None:
        print(f"llm judge accuracy: {llm_acc:.0%} ({sum(r[4] for r in llm)}/{len(llm)}) "
              f"[threshold {min_llm_accuracy:.0%}]")

    if pre_acc < 1.0:
        print("\nRESULT: FAIL — prefilter regressed on a golden verdict")
        return 1
    if llm_acc is not None and llm_acc < min_llm_accuracy:
        print("\nRESULT: FAIL — LLM judge below accuracy threshold")
        return 1
    print("\nRESULT: OK — judge is calibrated")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prefilter-only", action="store_true",
                    help="skip the LLM half (no model required)")
    ap.add_argument("--min-llm-accuracy", type=float, default=0.7,
                    help="required accuracy for the LLM judge (default 0.7)")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.prefilter_only, args.min_llm_accuracy)))
