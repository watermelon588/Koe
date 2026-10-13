"""A bounded Gemini text/tool loop shared by the CLI, future WhatsApp and evals.
https://ai.google.dev/gemini-api/docs/function-calling
"""
import logging

from google import genai
from google.genai import errors, types

from koe import agent, gemini, store, events, text_fallback
from koe.config import settings

MAX_TOOL_ROUNDS = 8
log = logging.getLogger("koe.text_agent")


def approval_text(result: dict) -> str:
    if result.get("status") == "executed":
        if result.get('cancelled'):
            return f"Cancelled Calendar {result.get('scope', 'event')}: {result.get('title', 'Approved event')}. Guest cancellation notifications requested."
        text = f"Saved: {result.get('title', 'Approved action')}. {result.get('url', '')}".strip()
        conference = result.get('conference') or {}
        state = conference.get('status')
        if state == 'success' and conference.get('url'):
            text += ' Meet: ' + conference['url']
        elif state in ('pending', 'failure', 'unavailable'):
            text += f' Meet status: {state}. The event is saved; read it again to check the link. Do not recreate the event.'
        return text
    if result.get("status") == "rejected":
        return "Cancelled. Nothing was changed."
    error = result.get("error", {})
    return f"{error.get('message', 'The action failed.')} {error.get('hint', '')}".strip()


def _reply(text: str, context: agent.Conversation) -> dict:
    if context.pending:
        text += f"\nPending: {context.pending['summary']}. Confirm with yes or cancel with no."
        context.approval_ready = True
    return {"text": text, "pending_action": context.pending}


async def chat(text: str, history: list, context: agent.Conversation, client: genai.Client | None = None,
               seen: list | None = None) -> dict:
    """One turn. Without `client`, Gemini runs through gemini.py's model/key fallbacks (the app, WhatsApp);
    tests and scripts may pass one client. `seen` (optional) collects (tool, args, result) for the app's live workspace."""
    text = text.strip()[:2000]
    if not text:
        return {"text": "Please enter a message."}
    history.append(types.Content(role="user", parts=[types.Part.from_text(text=text)]))
    store.record_later(context.channel, context.session_id, "message", text, {"role": "user"})
    decision = agent.confirmation(text)
    if decision is not None and context.pending:
        result = await agent.confirm(context, decision)
        reply = approval_text(result)
        history.append(types.Content(role="model", parts=[types.Part.from_text(text=reply)]))
        return {"text": reply, "approval_result": result}
    try:
        provider, model = 'gemini', None
        for round_index in range(MAX_TOOL_ROUNDS):
            if provider == 'openrouter':
                response = await text_fallback.generate(history)
            else:
                try:
                    # Later rounds prefer the model that started the turn but may still fall back: measured
                    # 2026-10-13, a tool turn begun on gemini-3.6-flash (with thought signatures) finished fine on
                    # gemini-3.5-flash and gemini-3-flash-preview. Tools never re-run either way.
                    response, model = await gemini.generate(
                        contents=history, models=list(dict.fromkeys([model, *gemini.text_models()])) if model else None, only=client,
                        config={"system_instruction": agent.system_prompt(),
                                "tools": [{"function_declarations": agent.declarations()}],
                                "automatic_function_calling": {"disable": True}})
                    if round_index == 0 and model != settings.gemini_text_model:
                        events.publish('model', provider='gemini', message=f'{settings.gemini_text_model} is busy; using {model}.')
                except errors.APIError as exc:
                    # Only switch before this turn has executed any tools. Never restart/replay a turn.
                    if round_index != 0 or exc.code not in {429, *gemini.OVERLOADED} or not settings.openrouter_api_key:
                        raise
                    response = await text_fallback.generate(history)
                    provider = 'openrouter'
                    events.publish('model', provider=provider, message='Using the configured free backup text provider.')
            content = response.candidates[0].content if response.candidates else None
            if not content or not content.parts:
                return _reply("The model returned no answer. Please try again.", context)
            # Preserve the actual model Content, including thought signatures, across tool rounds.
            history.append(content)
            calls = [p.function_call for p in content.parts if p.function_call]
            if not calls:
                reply = "".join(p.text for p in content.parts if p.text and not p.thought) or "The model returned no answer."
                result = _reply(reply, context)
                store.record_later(context.channel, context.session_id, "message", result["text"], {"role": "koe"})
                return result
            parts = []
            for fc in calls:
                result = await agent.run_tool(fc.name, fc.args, context=context)
                if seen is not None:
                    seen.append((fc.name, fc.args, result))
                parts.append(types.Part(function_response=types.FunctionResponse(name=fc.name, id=fc.id, response=result)))
            history.append(types.Content(role="user", parts=parts))
    except text_fallback.FallbackError:
        return _reply('Gemini and the free backup text model are unavailable. You can still manage records from the Notion workspace. No tools were replayed.', context)
    except errors.APIError as exc:
        log.warning("model call failed: %s %s", exc.code, exc.status)
        if exc.code in {429, *gemini.OVERLOADED}:  # temporary provider availability, including exhausted fallbacks
            return _reply("Gemini is busy right now. Please try again in a minute. No approval was inferred.", context)
        return _reply("The model could not complete this turn. No approval was inferred.", context)
    except Exception:
        log.exception("text turn failed")
        return _reply("The model could not complete this turn. No approval was inferred.", context)
    return _reply("Stopped after eight tool rounds. Please narrow the request.", context)
