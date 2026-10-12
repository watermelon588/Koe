# Koe (声): instructions for AI agents

> Koe (声) means "voice" in Japanese. It's a voice-first personal agent for a developer founder: a **live web call with an anime mascot**, plus **WhatsApp voice notes**, both driving **GitHub, Google Calendar, Notion and Google Sheets**.
> These docs are the ground truth. They're living documents: change the doc first, then the code, and log every decision in [docs/DECISIONS.md](docs/DECISIONS.md).

## Read before doing anything

| Order | File | What it gives you |
|---|---|---|
| 1 | [docs/PROBLEM_STATEMENT.md](docs/PROBLEM_STATEMENT.md) | Who it's for, what pain it solves, what we're *not* doing |
| 2 | [docs/SPEC.md](docs/SPEC.md) | **The contract**: tools, channels, approvals, limits, acceptance criteria |
| 3 | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data flows, latency budget, repo layout |
| 4 | [docs/TECH_STACK.md](docs/TECH_STACK.md) | Every library and service, and why |
| 5 | [docs/SERVICES_AND_COSTS.md](docs/SERVICES_AND_COSTS.md) | Free tiers, their catches, hosting plan (budget is ₹0) |
| 6 | [docs/PLAN.md](docs/PLAN.md) | Phases, timeline, the current phase |
| 7 | [docs/SKILLS.md](docs/SKILLS.md) | Which Claude Code skills to load for which work |
| — | [docs/BUILD_LOG.md](docs/BUILD_LOG.md) | Learning journal: append an entry for every step |
| — | [docs/DECISIONS.md](docs/DECISIONS.md) | Decision log |
| — | [docs/RESEARCH_SOURCES.md](docs/RESEARCH_SOURCES.md) | Every link behind every claim |

If two docs disagree, **SPEC.md wins**. Fix the other doc to match.

## About the user
- Rohit is a student in India (timezone **Asia/Kolkata**), learning AI agents and voice. **Budget is exactly ₹0, and there's no credit card.** Never suggest a paid service or a service that needs a card without flagging it.
- He wants to **understand everything that gets built**. See the teaching rule below.
- He likes anime. The mascot is anime-styled (see SPEC §6).

## Teaching rule (mandatory)
The user wants to learn every concept, not just get code. For **every step**:
1. Before coding: say in 2–3 lines what you're about to build and why.
2. After coding: append an entry to `docs/BUILD_LOG.md` using the template there. It covers files touched, what each does, the core concept in plain English, how it connects to the rest, how to try it, and a one-line "interview line".
3. In chat, keep it short; the full explanation lives in the build log.
4. Ask the user whether to use the **Learning** output style (Claude leaves small `TODO(human)` pieces for the user to write) or **Explanatory** (Claude writes everything and explains). This hasn't been decided yet; ask at the start of the first build session and record the answer in DECISIONS.md.

## Working rules
- **Build in phase order** ([docs/PLAN.md](docs/PLAN.md)), one thin slice at a time. Each slice ends with something runnable and verified.
- **Keep it simple.** No LangGraph, no Node server, no extra frameworks (see TECH_STACK "Rejected"). No classes or abstractions the spec doesn't need. Use the standard library first.
- **Ask first** before: adding a dependency not in TECH_STACK.md · adding or changing a tool · anything that sends messages to real people · anything that touches hosting or accounts.
- **Never:** commit `.env`, tokens or `credentials.json` · let the agent merge PRs · let write actions skip the approval gate (SPEC §5) · invent API behavior. Check the official docs (links in RESEARCH_SOURCES.md) and cite them in a comment when it's non-obvious.
- **Verify with evidence:** run it, test it, measure it. Latency and accuracy numbers come only from real measurements.
- **Free-tier facts change.** Re-check model IDs, rate limits and prices against official pages when you first use them, and update SERVICES_AND_COSTS.md if they've changed.

## Path warning
The project folder name contains `声` and parentheses: `Koe (声)`. Always quote paths. If a tool chokes on the path (some build tools do), tell the user. Renaming the folder to `koe` is the fallback.

## Commands (once scaffolded; Phase 0 creates these)
```bash
# backend (from backend/)
uv sync
uv run uvicorn koe.main:app --reload --timeout-graceful-shutdown 2 --port 8000
uv run pytest -q
# frontend (from frontend/)
npm install
npm run dev
# public URL for webhooks (dev)
cloudflared tunnel --url http://localhost:8000
# evals (from backend/)
uv run python -m evals.run
```
