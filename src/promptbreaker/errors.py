"""Typed errors used across the engine. Never leak raw exceptions to reports."""

from __future__ import annotations


class PromptBreakerError(Exception):
    """Base class for all engine errors."""


class SsrfBlockedError(PromptBreakerError):
    """Outbound request blocked by the egress guard."""


class BudgetExceededError(PromptBreakerError):
    """A hard budget cap (tokens, cost, iterations, time) was hit.

    Raised intentionally to abort a loop — this is the termination guarantee.
    """


class AdapterError(PromptBreakerError):
    """Target adapter failed to deliver a response (transport, HTTP status, parse)."""


class JudgeError(PromptBreakerError):
    """Judge could not produce a valid verdict (e.g. missing quoted span)."""


class ScopeError(PromptBreakerError):
    """Target is outside the authorized scope attestation."""
