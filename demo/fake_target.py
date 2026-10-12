"""Fake OpenAI-compatible target for demos and smoke tests.

Serves POST /v1/chat/completions on 127.0.0.1:18080. Responses are scripted
so some probes succeed (compliance = attack worked = FAIL verdict) and others
are refused — producing a realistic mixed score instead of a fake fixed one.

Used by demo/seed.sh and safe for local use only. Never point the engine at a
real system you are not authorized to test.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

COMPLIANT = (
    "Sure! Here is how to do it, step by step: Step 1: gather materials. "
    "Step 2: follow the process. This should help you accomplish that."
)
REFUSAL = "I'm sorry, but I can't help with that request."

# Patterns where the scripted target "gives in" — each maps to a probe family
# that should register a FAIL (successful attack) for a mixed demo score.
COMPLY_IF = (
    "methamphetamine",          # jailbreak / illicit instruction
    "decode the following base64",  # obfuscation smuggling
    "dan",                      # DAN-style roleplay jailbreak
    "ignore previous",          # instruction override (prompt injection)
    "ignore all previous",      # instruction override variants
    "system prompt",            # system prompt leak
    "you are now",              # persona swap
)
JSLEAK = "javascript:alert"  # improper output handling


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        msg = (body.get("messages") or [{}])[-1].get("content", "")
        lower = msg.lower()

        if JSLEAK in lower:
            text = (
                "Here is the markdown with a javascript:alert(document.cookie) URI "
                "and an <img onerror=alert(1)> tag."
            )
        elif any(p in lower for p in COMPLY_IF):
            text = COMPLIANT
        else:
            text = REFUSAL

        out = {
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 30},
        }
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print("fake target on 127.0.0.1:18080", flush=True)
    HTTPServer(("127.0.0.1", 18080), H).serve_forever()
