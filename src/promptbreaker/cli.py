"""PromptBreaker CLI.

Deterministic exit codes for CI gating:
  0 = clean (no finding at or above --fail-on)
  1 = findings at or above threshold  → pipeline fails
  2 = engine/transport error           → pipeline fails, distinct cause
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from promptbreaker import __version__
from promptbreaker.adapters.base import build_adapter
from promptbreaker.config import settings
from promptbreaker.engine.runner import execute_run
from promptbreaker.errors import PromptBreakerError, ScopeError
from promptbreaker.models import RunBudget, ScopeAttestation, Severity
from promptbreaker.report.render import render
from promptbreaker.scoring import meets_severity_threshold

_SEV = {s.value.lower(): s for s in Severity}


def _build_parser(defaults: dict | None = None) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="promptbreaker",
        description="PromptBreaker AI — adversarial assessment for LLM apps (authorized only)",
    )
    p.add_argument("--version", action="version", version=f"promptbreaker {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Run an assessment against an authorized target")
    scan.add_argument("--config", default="", metavar="FILE",
                      help="YAML/JSON scan spec (promptbreaker.yml); CLI flags override it")
    scan.add_argument("--target", default="", help="Target base URL (e.g. http://host/v1)")
    scan.add_argument("--adapter", default="openai", choices=["openai", "ollama", "http"])
    scan.add_argument("--model", default="default")
    scan.add_argument("--api-key", default="")
    scan.add_argument("--suite", default="core")
    scan.add_argument("--format", default="json", choices=["json", "md", "markdown", "sarif"])
    scan.add_argument("--output", default="", help="Write report to file (default: stdout)")
    scan.add_argument("--fail-on", default="High",
                      help="Severity threshold that fails CI (Critical|High|Medium|Low|Info)")
    scan.add_argument("--max-probes", type=int, default=settings.max_probes_per_run)
    scan.add_argument("--allow-private", action="store_true",
                      help="Permit private-range targets (labs only — SSRF guard off)")
    scan.add_argument("--attested-by", default="", help="Authorizer name/email (required)")
    scan.add_argument("--attestation-ref", default="", help="Engagement reference (required)")
    scan.add_argument("--seed", type=int, default=0)

    sub.add_parser("suites", help="List available probe suites")
    if defaults:
        # Defaults live on the SUBparser: argparse subparsers overwrite parent
        # set_defaults values with their own during parse.
        scan.set_defaults(**defaults)
    return p


# promptbreaker.yml keys → argparse dests (multiple aliases where natural)
_CONFIG_KEYS: dict[str, str] = {
    "target": "target", "adapter": "adapter", "model": "model",
    "api_key": "api_key", "api_key_env": "api_key", "suite": "suite",
    "format": "format", "output": "output", "fail_on": "fail_on",
    "max_probes": "max_probes", "allow_private": "allow_private",
    "seed": "seed",
    "attested_by": "attested_by", "authorized_by": "attested_by",
    "attestation_ref": "attestation_ref", "reference": "attestation_ref",
}


def _load_config(path: str) -> dict:
    """Read a scan spec. YAML when PyYAML is present; .json always works."""
    import json as _json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        print(f"ERROR: config file not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    text = p.read_text()
    if p.suffix.lower() == ".json":
        data = _json.loads(text)
    else:
        try:
            import yaml  # noqa: PLC0415 — optional dependency, JSON path works without it
        except ImportError:
            print("ERROR: --config with YAML needs PyYAML (pip install pyyaml)",
                  file=sys.stderr)
            raise SystemExit(2) from None
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        print(f"ERROR: {path} must contain a mapping of scan options", file=sys.stderr)
        raise SystemExit(2)
    unknown = sorted(set(data) - set(_CONFIG_KEYS) - {"comment", "name"})
    if unknown:
        print(f"ERROR: unknown config keys: {', '.join(unknown)}", file=sys.stderr)
        raise SystemExit(2)
    if "api_key_env" in data:
        import os
        env_name = str(data["api_key_env"])
        if not os.environ.get(env_name):
            print(f"ERROR: api_key_env {env_name!r} is not set in the environment",
                  file=sys.stderr)
            raise SystemExit(2)
    return data


def _config_defaults(cfg: dict) -> dict:
    import os

    out: dict = {}
    for key, value in cfg.items():
        dest = _CONFIG_KEYS.get(key)
        if dest is None:
            continue
        if key == "api_key_env":
            value = os.environ[str(value)]
        out[dest] = value
    return out


def _parse(argv: list[str]) -> argparse.Namespace:
    """Parse argv; a --config file seeds defaults, explicit flags win."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "config", ""):
        cfg = _load_config(args.config)
        args = _build_parser(_config_defaults(cfg)).parse_args(argv)
    return args


def _cmd_suites() -> int:
    from promptbreaker.probes.registry import list_suites
    for name in list_suites():
        print(name)
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    if not args.target:
        print("REFUSED: --target (or target: in --config) is required.", file=sys.stderr)
        return 2
    if not args.attested_by or not args.attestation_ref:
        print(
            "REFUSED: --attested-by and --attestation-ref are required.\n"
            "PromptBreaker only runs against targets you are authorized to test. "
            "See ETHICAL_USE.md.",
            file=sys.stderr,
        )
        return 2

    attestation = ScopeAttestation(
        target_pattern=args.target,
        authorized_by=args.attested_by,
        reference=args.attestation_ref,
        expires=datetime.now(UTC) + timedelta(hours=24),
    )

    adapter = build_adapter(
        args.adapter, args.target, allow_private=args.allow_private, model=args.model,
        api_key=args.api_key,
    )
    budget = RunBudget(max_probes=args.max_probes)

    from promptbreaker.judge.core import LlmJudge
    llm = LlmJudge(settings.judge_base_url, settings.judge_api_key, settings.judge_model)

    try:
        result = asyncio.run(execute_run(
            adapter=adapter, attestation=attestation, budget=budget,
            suite=args.suite, llm_judge=llm, seed=args.seed,
        ))
    except ScopeError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except PromptBreakerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    report = render(result, args.format)
    if args.output:
        with open(args.output, "w") as fh:
            fh.write(report)
        print(f"report written: {args.output}", file=sys.stderr)
    else:
        print(report)

    # ---- pipeline gate
    threshold = _SEV.get(args.fail_on.lower())
    if threshold is None:
        print(f"ERROR: invalid --fail-on {args.fail_on!r}", file=sys.stderr)
        return 2

    hits = [f for f in result.findings if meets_severity_threshold(f.severity, threshold)]
    s = result.score
    print(
        f"\nsummary: score={s.score} band={s.band.value} "
        f"simulated={s.simulated} successful={s.successful} "
        f"gate={'>=' + threshold.value}: {len(hits)}",
        file=sys.stderr,
    )
    if result.status.value == "FAILED":
        return 2
    return 1 if hits else 0


def main(argv: list[str] | None = None) -> int:
    args = _parse(list(sys.argv[1:]) if argv is None else list(argv))
    try:
        if args.cmd == "suites":
            return _cmd_suites()
        if args.cmd == "scan":
            return _cmd_scan(args)
    except PromptBreakerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
