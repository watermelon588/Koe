# Graph Report - Koe (声)  (2026-10-12)

## Corpus Check
- Corpus is ~13,970 words - fits in a single context window. You may not need a graph.

## Summary
- 288 nodes · 404 edges · 18 communities (14 shown, 4 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 53 edges (avg confidence: 0.85)
- Token cost: 119,251 input · 0 output

## Community Hubs (Navigation)
- Backend Call Relay
- Live Call Flow & Latency
- WhatsApp & GitHub Alerts
- Frontend Dependencies
- Agent Tools & Approval Gate
- TS App Config
- Project Charter & Rules
- Budget, Hosting & Evals
- Phase 0 Smoke Tests
- TS Node Config
- Browser Audio Pipeline
- Mascot & Frontend Design
- Lint Config
- Gemini Models & Fallback
- Mic Worklet
- TS Root Config
- Google OAuth
- Package Root

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 18 edges
2. `compilerOptions` - 15 edges
3. `Tool registry (10 tools max, shared by channels)` - 13 edges
4. `Decision log` - 12 edges
5. `Approval gate (human in the loop)` - 10 edges
6. `Koe Spec (the contract)` - 9 edges
7. `Agent core (agent.py: prompt, tool registry, context builder, text loop)` - 9 edges
8. `Phase 1: live voice call, no tools (current)` - 9 edges
9. `Build log learning journal` - 9 edges
10. `Koe agent instructions (CLAUDE.md)` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Favicon: default Vite purple lightning-bolt logo` --conceptually_related_to--> `Anime mascot (SVG + CSS)`  [AMBIGUOUS]
  frontend/public/favicon.svg → docs/SPEC.md
- `Teaching rule (explain every step, BUILD_LOG entry)` --references--> `Build log learning journal`  [EXTRACTED]
  CLAUDE.md → docs/BUILD_LOG.md
- `Ask-first / never rules for agents` --references--> `Approval gate (human in the loop)`  [EXTRACTED]
  CLAUDE.md → docs/SPEC.md
- `Budget exactly Rs 0, no credit card` --conceptually_related_to--> `Twilio trial limits`  [INFERRED]
  CLAUDE.md → docs/RESEARCH_SOURCES.md
- `Path warning: CJK char and parentheses in folder name` --references--> `Build log learning journal`  [INFERRED]
  CLAUDE.md → docs/BUILD_LOG.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Koe 10-tool registry shared by both channels** — docs_spec_tool_registry, docs_spec_github_review_queue, docs_spec_github_my_prs, docs_spec_github_pr_summary, docs_spec_github_shipped, docs_spec_github_comment, docs_spec_calendar_find_free, docs_spec_calendar_upsert_event, docs_spec_calendar_list, docs_spec_notion_log, docs_spec_sheets_log_hours [EXTRACTED 1.00]
- **Live web call audio pipeline (mic -> Gemini Live -> speaker)** — docs_tech_stack_audioworklet, docs_build_log_raw_pcm16, docs_architecture_voice_call_module, docs_tech_stack_gemini_live_model, docs_build_log_gapless_playback, docs_tech_stack_analysernode, docs_architecture_barge_in [INFERRED 0.85]
- **Approval-gated write flow** — docs_spec_approval_gate, docs_spec_pending_action, docs_architecture_store_module, docs_spec_github_comment, docs_spec_calendar_upsert_event, docs_spec_sheets_log_hours, docs_spec_web_call_channel, docs_spec_whatsapp_channel [EXTRACTED 1.00]

## Communities (18 total, 4 thin omitted)

### Community 0 - "Backend Call Relay"
Cohesion: 0.08
Nodes (8): Settings, health(), call(), _gemini_to_browser(), _mic_to_gemini(), live(), FakeSession, test_call_relays_mic_to_gemini_and_gemini_audio_back()

### Community 1 - "Live Call Flow & Latency"
Cohesion: 0.10
Nodes (27): Path warning: CJK char and parentheses in folder name, Barge-in (flush playback queue on interrupted), config.py (.env via pydantic-settings), Flow A: live web call (latency-critical path), Latency budget (p50 <= 1.5 s speech end -> first audio), main.py (FastAPI app entry), voice_call.py (/ws/call <-> Gemini Live relay), Fail fast on config (Step 2) (+19 more)

### Community 2 - "WhatsApp & GitHub Alerts"
Cohesion: 0.09
Nodes (23): Agent core (agent.py: prompt, tool registry, context builder, text loop), Flow C: GitHub push alert (no LLM), Flow B: WhatsApp voice note, github_hooks.py (verify, dedupe, alert rules), Least-privilege tokens (fine-grained GitHub, limited Google scopes), whatsapp.py (webhook, media download, send), Phase 5: WhatsApp channel + GitHub alerts, Phase 6: shared memory (+15 more)

### Community 3 - "Frontend Dependencies"
Cohesion: 0.07
Nodes (27): dependencies, react, react-dom, devDependencies, oxlint, @types/node, @types/react, @types/react-dom (+19 more)

### Community 4 - "Agent Tools & Approval Gate"
Cohesion: 0.10
Nodes (24): events.py (in-process pub/sub, asyncio.Queue), KOE_ACCESS_TOKEN shared secret on /ws/*, SQLite data model (activity, pending_actions, daily_notes, github_deliveries), store.py (SQLite via stdlib sqlite3), tools/*.py (github, calendar, notion, sheets wrappers), Phase 2: agent core + GitHub read + Calendar + approval gate, Phase 3: dashboard + mascot + live events, Phase 4: PR summaries, shipped, Notion, Sheets (+16 more)

### Community 5 - "TS App Config"
Cohesion: 0.10
Nodes (19): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+11 more)

### Community 6 - "Project Charter & Rules"
Cohesion: 0.15
Nodes (13): Koe agent instructions (CLAUDE.md), Decision log, Phase plan and timeline (~4 weeks), Coordination pain across GitHub/Calendar/Notion/Sheets, Developer founder (primary user), Problem statement, Two channels, one brain, incremental-implementation skill (+5 more)

### Community 7 - "Budget, Hosting & Evals"
Cohesion: 0.12
Nodes (14): Deployment plan (dev: laptop + cloudflared; prod: Azure VM + Vercel), Accepted != delivered (WhatsApp status webhooks), Debugging 'WhatsApp message never arrived' (Step 6), Phase 7: evals, deploy, ship, Success metrics (>=90% accuracy, p50 <=1.5 s, 0 unapproved writes), Azure for Students (backend hosting, no card), Vercel Hobby (frontend hosting), Acceptance criteria (v1 done) (+6 more)

### Community 8 - "Phase 0 Smoke Tests"
Cohesion: 0.18
Nodes (7): calendar(), gemini(), github(), need(), notion(), Skip, whatsapp()

### Community 9 - "TS Node Config"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 10 - "Browser Audio Pipeline"
Cohesion: 0.26
Nodes (6): App(), call(), startMic(), createPlayer(), react, react-dom

### Community 11 - "Mascot & Frontend Design"
Cohesion: 0.28
Nodes (9): Frontend (call panel, mascot, dashboard panels), Mascot design + name (pending, Phase 3), blobatar skill (mascot base), Anime mascot (SVG + CSS), Mascot states (idle, listening, thinking, speaking, happy, error), Web Audio AnalyserNode (mascot mouth), React + TypeScript + Vite, frontend index.html entry (#root -> /src/main.tsx) (+1 more)

### Community 12 - "Lint Config"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 13 - "Gemini Models & Fallback"
Cohesion: 0.40
Nodes (5): Gemini API free tier (unpublished rate limits, data used for training), Rate-limit plan (log 429, back off once, Groq fallback), gemini-3.8-flash (WhatsApp audio, PR summaries), google-genai SDK, Groq fallback (Whisper + gpt-oss)

## Ambiguous Edges - Review These
- `Anime mascot (SVG + CSS)` → `Favicon: default Vite purple lightning-bolt logo`  [AMBIGUOUS]
  frontend/public/favicon.svg · relation: conceptually_related_to

## Knowledge Gaps
- **30 isolated node(s):** `koe`, `@types/node`, `@types/react`, `@types/react-dom`, `oxlint` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 121 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Agent core (agent.py: prompt, tool registry, context builder, text loop)` connect `WhatsApp & GitHub Alerts` to `Live Call Flow & Latency`, `Agent Tools & Approval Gate`, `Project Charter & Rules`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Decision log` (e.g. with `Render free tier rejected` and `Speech-to-speech instead of STT -> LLM -> TTS chain`) actually correct?**
  _`Decision log` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `koe`, `@types/node`, `@types/react` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Backend Call Relay` be split into smaller, more focused modules?**
  _Cohesion score 0.07657657657657657 - nodes in this community are weakly interconnected._
- **Why does `Decision log` connect `Project Charter & Rules` to `Live Call Flow & Latency`, `WhatsApp & GitHub Alerts`, `Mascot & Frontend Design`, `Budget, Hosting & Evals`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Should `Live Call Flow & Latency` be split into smaller, more focused modules?**
  _Cohesion score 0.0967741935483871 - nodes in this community are weakly interconnected._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Anime mascot (SVG + CSS)` and `Favicon: default Vite purple lightning-bolt logo`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._