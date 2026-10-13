# Problem statement: Koe (声)

## The one-liner
> **Developers who run agencies or startups lose hours every day to small coordination work across GitHub, Calendar, Notion and Sheets. Koe is a voice-first agent that does this work for them: a live call with an anime mascot when they're at their desk, and WhatsApp voice notes when they're on the move. One brain and one memory sit behind both, the user approves every action that affects others, and booking accuracy and latency are measured.**

## Who it's for
**Primary user: the developer founder**, someone like Rohit. A developer who also runs things: a small agency, a startup, freelance clients, while studying. A typical day:
- pushes PRs, reviews teammates' PRs, watches CI;
- hosts and joins meetings, attends classes and live sessions;
- logs what got done (for clients, invoices, standups);
- is often away from the laptop: walking, commuting, between classes.

It's single-user: one person, their own accounts. No teams or public signup. Owner-only sign-in will replace development token entry before hosting; see AUTH_FLOW.md.

## The pain, concretely
| Moment | What happens today | Cost |
|---|---|---|
| "What's waiting on me in GitHub?" | Open GitHub, click through notifications, PRs and CI runs | 10–15 min of context switching, several times a day |
| "Book a call with Rahul at 7." | Open Calendar, find a gap, create the event, invite | 2–3 min, impossible while walking |
| "Is PR #42 safe to approve?" | Read the diff, files and description | 10+ min per PR |
| "What did I ship today?" | Rebuild it from memory and git log | Skipped, so hours go unbilled and standups are vague |
| "CI failed on my PR" | Found out hours later | Blocked teammates |

Existing options are either **generic assistants** that don't know GitHub (Siri, Google Assistant), **text-only bots**, or **paid tools**. None is voice-first, GitHub-centric, on WhatsApp *and* the web, and free.

## What Koe does
1. **GitHub is the core.**
   - Review queue, status of my PRs (CI, approvals, conflicts), plain-English PR summaries with a risk note, "what did I ship today/this week", stale PRs.
   - Comments on PRs after the user approves.
   - **Push alerts** from GitHub webhooks to WhatsApp: CI failed, review requested, PR merged.
2. **Calendar:** find free slots, book or move meetings (after approval), block review or focus time.
3. **Notion and Sheets:** daily dev log written automatically from GitHub activity, and hours per client logged to a timesheet.
4. **Two channels, one brain:**
   - **Web call** (at the desk): a live, interruptible voice conversation with an animated anime mascot, while a dashboard shows every action live.
   - **WhatsApp** (on the move): voice notes or text in, short replies out, alerts pushed.

## How we'll know it works (success metrics)
| Metric | Target |
|---|---|
| Booking accuracy on the eval suite (right slot, no double-booking, correct timezone) | ≥ 90% |
| Tool-choice accuracy (picks the right tool for the request) | ≥ 90% |
| Web call: user stops talking → first audio from the agent | p50 ≤ 1.5 s |
| WhatsApp: voice note received → reply delivered | p50 ≤ 4 s |
| Write actions executed without approval | **0** |

Targets are goals, not promises. We report real measurements honestly, even if they miss.

## Not doing (and why)
| Not doing | Why |
|---|---|
| Phone-network calls (Twilio and similar) | Costs money or expires; the user has no card |
| Site uptime monitoring | Dropped by the user: polling wastes free-tier resources; GitHub webhooks are event-driven |
| Merging PRs by voice | One misheard word ships broken code |
| Multi-user signup, teams | Personal agent; owner-only sign-in is a separate required pre-hosting slice |
| Email (Gmail) | Keeps the tool count small; possible v2 |
| Mobile app | WhatsApp *is* the mobile app |
| LangGraph / multi-agent orchestration | One agent with about 9 tools doesn't need it (see TECH_STACK) |
| Video, screen sharing | Out of scope |

## Why this is a strong portfolio project
- **Real-time systems:** streaming audio, barge-in (interrupting the agent), latency engineering, all measured.
- **Agent engineering:** tool design, an approval gate, shared memory across channels, an eval suite with accuracy numbers.
- **Integrations:** OAuth (Google), webhooks (GitHub, Meta), REST APIs (Notion, WhatsApp Cloud API).
- **It's something the builder actually uses every day**, so the demo is honest.
