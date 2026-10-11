# ETHICAL_USE

PromptBreaker AI is a **defensive security** tool. These rules are enforced in
code, not just prose:

1. **Authorization attestation required.** A run cannot start without a
   `ScopeAttestation` record naming the target, the authorizing party, and an
   expiry. The engine refuses targets outside the attested scope.
2. **No production use without approval.** Generated attacks must never be
   pointed at systems you do not own or lack written authorization to test.
3. **Auditability.** Every run writes an append-only event log; findings carry
   hashed, HMAC-chained evidence. Nothing is silently dropped.
4. **Human-in-the-loop for Critical.** Critical findings are flagged for human
   review before reports leave the system.
5. **Budgets always terminate.** Mutation loops have hard caps. There is no
   unbounded generation mode.

Violating these terms voids any support and may violate law. You are
responsible for obtaining authorization before every assessment.
