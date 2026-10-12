# Research sources: Koe (声)

## Phase 2 implementation sources (checked 2026-10-12)
- [Supabase database functions and execution grants](https://supabase.com/docs/guides/database/functions)
- [Supabase API key types and apikey header](https://supabase.com/docs/guides/getting-started/api-keys)
- [Google Calendar Python OAuth quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python)
- [Create Google OAuth credentials](https://developers.google.com/workspace/guides/create-credentials)
- [Calendar permission scopes](https://developers.google.com/workspace/calendar/api/auth)
- [Calendar resource versions and If-Match](https://developers.google.com/workspace/calendar/api/guides/version-resources)
- [Google refresh-token expiration](https://developers.google.com/identity/protocols/oauth2#expiration)
- [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Python zoneinfo and Windows tzdata dependency](https://docs.python.org/3/library/zoneinfo.html)

Links behind the claims in these docs, gathered 2026-10-03 to 2026-10-12. Many are third-party summaries; **official docs win** when they disagree.

## Official docs (build against these)
- Gemini API pricing (free tier, Live models): https://ai.google.dev/gemini-api/docs/pricing
- Live API limits and specs (session length, audio formats): https://firebase.google.com/docs/ai-logic/live-api/limits-and-specs
- Gemini Live API reference (Google Cloud): https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/multimodal-live
- Gemini 2.5 Flash native audio (Live) model page: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-live-api
- WhatsApp Cloud API calling: https://developers.facebook.com/documentation/business-messaging/whatsapp/calling
- WhatsApp Business Platform overview: https://developers.facebook.com/documentation/business-messaging/whatsapp/about-the-platform
- Azure for Students (India): https://azure.microsoft.com/en-in/free/students
- Pipecat (plan B transport): https://github.com/pipecat-ai/pipecat · https://docs.pipecat.ai/overview/introduction
- Twilio trial limits (why we skipped phones): https://support.twilio.com/hc/en-us/articles/360036052753-Twilio-Free-Trial-Limitations · https://www.twilio.com/docs/usage/trials/try-out-voice
- LiveKit phone numbers (inbound-only, US-only): https://docs.livekit.io/telephony/start/phone-numbers/
- Anthropic, "Writing effective tools for agents": https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic, "Building effective agents": https://www.anthropic.com/engineering/building-effective-agents

- Gemini models list: https://ai.google.dev/gemini-api/docs/models
- Gemini Live get started (Python SDK): https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk
- Gemini Live session management (limits, resumption, GoAway): https://ai.google.dev/gemini-api/docs/live-api/session-management
- Gemini rate limits (points to AI Studio): https://ai.google.dev/gemini-api/docs/rate-limits
- GitHub REST, get authenticated user (API version 2026-03-10): https://docs.github.com/en/rest/users/users#get-the-authenticated-user
- Notion, retrieve token's bot user (Notion-Version 2026-03-11): https://developers.notion.com/reference/get-self · https://developers.notion.com/reference/versioning
- Google Calendar Python quickstart (OAuth installed-app flow): https://developers.google.com/workspace/calendar/api/quickstart/python
- WhatsApp Cloud API get started (test number, 24 h window, Graph v23.0): https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started
- GitHub webhook signature (`X-Hub-Signature-256`, test vector used in tests): https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
- GitHub webhook events and payloads: https://docs.github.com/en/webhooks/webhook-events-and-payloads
- WhatsApp Cloud API webhooks (verify handshake, `X-Hub-Signature-256` with the app secret): https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks

*Still to add, when first used:* GitHub REST API (pulls, checks), Google Calendar API (freeBusy, events), Google Sheets API (values.append), Notion API (pages, databases), WhatsApp Cloud API (messages, media, interactive, templates, webhooks), Web Audio `AudioWorklet`.

### Mascot (3D VRM)
- three-vrm (library + examples): https://github.com/pixiv/three-vrm
- VRM 1.0 humanoid bones (required vs optional): https://vrm.dev/en/vrm1/humanoid/
- VRM license terms (sample model `VRM1_Constraint_Twist_Sample.vrm`: redistribution + commercial use allowed, no credit needed): https://vrm.dev/licenses/1.0/
- VRoid Studio (free, commercial use): https://vroid.com/en/studio
- Rejected options: Live2D SDK release license https://live2d.com/en/?p=586 · Rive pricing (free plan can't export `.riv`, third-party review) https://frontdeskreview.com/software/design-tools/rive/

## Costs and free tiers
- Voice agent cost per minute (market context): https://futureagi.com/blog/voice-ai-infrastructure-stack-decision-guide-2026/ · https://softcery.com/ai-voice-agents-calculator
- OpenAI Realtime pricing (comparison): https://openai.com/index/introducing-gpt-realtime/
- Gemini Live free-tier concurrency report: https://discuss.ai.google.dev/t/native-audio-live-free-tier-setup-quota-rejection-below-visible-tpm-which-admission-metric-applies/186840
- Groq free tier: https://www.eesel.ai/blog/groq-pricing
- Deepgram $200 credit: https://costbench.com/software/ai-transcription-apis/deepgram/free-plan/
- WhatsApp pricing and the Oct 2026 change: https://www.wati.io/en/blog/whatsapp-api-pricing-guide/ · https://github.com/robhunter/agentdeals/issues/2671 · https://sleekflow.io/blog/whatsapp-business-price
- Render free tier: https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026 · https://agentdeals.dev/vendor/render
- No-card hosting comparisons: https://snapdeploy.dev/blog/free-backend-hosting-2026-apis-servers · https://zizme.com/8-best-free-backend-deployment-platforms-in-2026-no-card-heroku-alternatives
- Heroku student offer (needs card): https://www.heroku.com/github-students/

## Market context
- Voice AI funding and growth: https://www.landbase.com/blog/fastest-growing-voice-ai-platforms-companies
- Voice engineer hiring (vendor source, directional): https://callsphere.ai/blog/vw9c-ai-voice-engineer-hiring-market-2026-salaries-comp
- WhatsApp voice agent starter (Pipecat + WhatsApp): https://github.com/topics/whatsapp-calling


### Phase 3 dashboard references (2026-10-12)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/): JSON messages, disconnection handling and the single-process limitation of in-memory connection lists.
- [Python asyncio queues](https://docs.python.org/3/library/asyncio-queue.html): bounded queues and nonblocking `put_nowait`/`QueueFull` behavior.
- [Supabase API security](https://supabase.com/docs/guides/api/securing-your-api): restricted backend access; no service key in the browser.

## Phase 4 implementation sources (checked 2026-10-13)
- GitHub [PR metadata and files](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files): pagination and 3,000-file maximum; current REST header 2026-03-10.
- GitHub [search](https://docs.github.com/en/rest/search/search): 1,000-result cap, incomplete_results, authored/merged qualifiers; [commits](https://docs.github.com/en/rest/commits/commits#list-commits): default branch, author and date filters.
- GitHub [PR discussion comments](https://docs.github.com/en/rest/issues/comments#create-an-issue-comment): issue-comment endpoint also covers PRs; Pull requests write permission.
- Google [structured output](https://ai.google.dev/gemini-api/docs/structured-output): Pydantic response schema; local validation and tool-free summarizer.
- Notion [versioning](https://developers.notion.com/reference/versioning), [retrieve database](https://developers.notion.com/reference/retrieve-a-database), [retrieve data source](https://developers.notion.com/reference/retrieve-a-data-source), [query data source](https://developers.notion.com/reference/query-a-data-source), [create page](https://developers.notion.com/reference/post-page), [append blocks](https://developers.notion.com/reference/patch-block-children). The last two HTML pages exceeded the browser fetch limit; read their official .md counterparts directly. Query request_status can mark a capped read incomplete even when has_more is false.
- Sheets [append values](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append) and [ValueInputOption](https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueInputOption): configured A1 range, RAW values and returned updates.updatedRange.
