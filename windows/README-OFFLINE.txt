PromptBreaker Offline 1.2.0 — fully self-contained desktop app
==============================================================

Double-click PromptBreaker.exe. First launch takes ~10 seconds while the
bundled engine and dashboard start; the window opens on its own.

What runs (all local, nothing leaves this PC)
---------------------------------------------
  127.0.0.1:8000   PromptBreaker engine (bundled Python 3.12 + FastAPI)
  127.0.0.1:3000   dashboard (bundled node.exe, Next standalone)
  127.0.0.1:18081-18088   the 8 demo chatbots (seeded as scan targets)

Everything binds 127.0.0.1 only. Data (SQLite DB + evidence keys) lives in
%LOCALAPPDATA%\PromptBreaker. No WSL, no internet, no account needed.

Judge mode — read this
----------------------
The deterministic prefilter judge always works offline (672/672 mutation
selftest). If this machine runs Ollama with any chat model, the app
auto-detects it and upgrades to the full hybrid judge (prefilter + LLM).
Without Ollama: verdicts the prefilter cannot decide return ERROR
("no LLM judge configured") — the engine never guesses. Install Ollama
(https://ollama.com) and pull a model (e.g. `ollama pull qwen2.5:7b`),
then relaunch PromptBreaker to enable the LLM judge.

Scan targets
------------
The 8 demo chatbots are pre-seeded as targets on first launch (SecureBot,
RecordsClerk, LeakyAssist, YesMan, AutoAgent, InfiniteWriter, CreativeAI,
EvasiveBot). Add any other OpenAI-compatible endpoint via Add Target.

Offline self-test (for judges / CI)
-----------------------------------
Run from cmd.exe:
    PromptBreaker.exe --selftest
Starts the full stack headless, health-checks engine + dashboard +
chatbots, seeds the demo targets, writes PASS/FAIL to selftest.log next to
the exe and exits (0 = pass). Delete selftest.log before a clean demo.

Uninstall
---------
Settings > Apps > "PromptBreaker Offline", or Uninstall.exe in the install
folder. Removes the app; data in %LOCALAPPDATA%\PromptBreaker stays unless
you delete it.

Authorized testing only. Scan systems you own or are explicitly authorized
to assess.
