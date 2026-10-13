# Koe (声)

> *Koe* means "voice." A voice-first agent for developer founders: talk to an anime mascot on a live web call, or send a WhatsApp voice note on the move, and Koe handles your **GitHub** (review queue, PR status, PR summaries, what you shipped), **Google Calendar**, **Notion** and **Sheets**, with your approval for anything that matters.

**Status:** live voice, mascot, authenticated dashboard and Phase 4 tools built. A dedicated Notion workspace supports search, previews, tasks, notes, meeting records, approved edits/trash and daily logs. Real Notion/Neon workflow acceptance passed with temporary records; live conversational selection is pending because Gemini returned 503. Other integration acceptance remains separate: [Phase 2](docs/PHASE2_SETUP.md), [Phase 4](docs/PHASE4_SETUP.md), [Notion coverage](docs/NOTION_PLAN.md), [phase plan](docs/PLAN.md).

Storage migrated to **Neon PostgreSQL (Singapore)** on 2026-10-13. Live verification covers atomic approvals, concurrent claims and owner/conversation isolation. `DATABASE_URL` stays in `backend/.env`. Chat, voice notes and push subscriptions also persist in Neon when configured. Browser token entry remains development-only; [the invite-only accounts plan](docs/ACCOUNTS_SPEC.md) is a separate pre-hosting slice. Optional OpenRouter free text fallback is implemented but inactive until a key is supplied; direct Notion controls work without an LLM.

## Docs
- [Problem statement](docs/PROBLEM_STATEMENT.md): who it's for, what it solves, what it doesn't
- [Spec](docs/SPEC.md): the contract (tools, channels, approvals, acceptance criteria)
- [Architecture](docs/ARCHITECTURE.md): components, flows, latency budget
- [Tech stack](docs/TECH_STACK.md): what we use and what we rejected
- [Services and costs](docs/SERVICES_AND_COSTS.md): ₹0 plan, free-tier catches, hosting
- [Plan](docs/PLAN.md): phases and timeline
- [Build log](docs/BUILD_LOG.md): step-by-step learning journal
- [Decisions](docs/DECISIONS.md) · [Skills](docs/SKILLS.md) · [Sources](docs/RESEARCH_SOURCES.md)

*This README becomes the public project page in Phase 7 (demo, metrics, setup).*
