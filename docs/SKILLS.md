# Skills to use: Koe (声)

These are Claude Code skills installed for the user (index: `~/.claude/skills/my-skills/SKILL.md`). Load the matching skill with the Skill tool **before** starting that kind of work, and tell the user which ones you loaded.

## Every session
| Skill | When |
|---|---|
| `using-agent-skills` | Session start: pick the right skills for the work |
| `incremental-implementation` | Every build step: thin, verifiable slices |
| `ponytail` (always on) | Simplest working solution; no unrequested abstractions |

## By phase
| Phase | Skills | Why |
|---|---|---|
| Planning / any scope change | `spec-driven-development`, `planning-and-task-breakdown` | Update SPEC first, then tasks |
| 0 Setup | `git-workflow-and-versioning`, `context-engineering` | Repo hygiene, keep CLAUDE.md useful |
| 1 Live voice | `source-driven-development`, `debugging-and-error-recovery`, `performance-optimization` | Gemini Live and Web Audio must match official docs; audio bugs need root-causing; latency is the product |
| 2 Agent core + tools | `api-and-interface-design`, `test-driven-development`, `claude-api`* | Tool schemas are an interface; approval gate and time math must be tested |
| 3 Dashboard + mascot | `frontend-ui-engineering`, `impeccable`, `design-taste-frontend`, `emil-design-eng`, `animate`, `blobatar` | UI quality, mascot motion states, avatar base |
| 4 GitHub/Notion/Sheets | `source-driven-development`, `test-driven-development` | API correctness |
| 5 WhatsApp + webhooks | `security-and-hardening`, `source-driven-development` | Signature verification, allow-list, untrusted input |
| 6 Memory | `context-engineering` | What goes into each session's context |
| 7 Evals / deploy / launch | `observability-and-instrumentation`, `dataviz`, `shipping-and-launch`, `documentation-and-adrs`, `brag` | Metrics, latency charts, deploy checklist, README/ADRs, demo video |
| Before every commit of a phase | `code-review-and-quality`, `ponytail-review`, `security-review` | Catch bugs, bloat, leaks |

\* `claude-api` covers general tool-use and agent-loop patterns, but this project uses **Gemini**. Always check Google's own docs for Gemini specifics (RESEARCH_SOURCES.md).

## Output style for teaching
The user wants to learn each step. Ask at the first build session: **Learning** (Claude leaves small `TODO(human)` parts for the user) or **Explanatory** (Claude writes the code and adds insight notes). Either way, follow the CLAUDE.md teaching rule and BUILD_LOG.md.
