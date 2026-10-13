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
        return f"Saved: {result.get('title', 'Approved action')}. {result.get('url', '')}".strip()
    if result.get("status") == "rejected":
        return "Cancelled. Nothing was changed."
    error = result.get("error", {})
    return f"{error.get('message', 'The action failed.')} {error.get('hint', '')}".strip()


def _reply(text: str, context: agent.Conversation) -> dict:
    if context.pending:
        text += f"\nPending: {context.pending['summary']}. Confirm with yes or cancel with no."
        context.approval_ready = True
    return {"text": text, "pending_action": context.pending}


async def chat(text: str, history: list, context: agent.Conversation, client: genai.Client | None = None) -> dict:
    """One turn. Without `client`, Gemini runs through gemini.py's model/key fallbacks (the app, WhatsApp);
    tests and scripts may pass one client."""
    text = text.strip()[:2000]
    if not text:
        return {"text": "Please enter a message."}
    history.append(types.Content(role="user", parts=[types.Part.from_text(text=text)]))
    await store.record_best_effort(context.channel, context.session_id, "message", text, {"role": "user"})
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
                    # Round 0 may fall back across models and keys; later rounds stay on the model that started the
                    # turn (its tool calls and thought signatures are already in the history).
                    response, model = await gemini.generate(
                        contents=history, models=[model] if model else None, only=client,
                        config={"system_instruction": agent.system_prompt(),
                                "tools": [{"function_declarations": agent.declarations()}],
                                "automatic_function_calling": {"disable": True}})
                    if round_index == 0 and model != settings.gemini_text_model:
                        events.publish('model', provider='gemini', message=f'{settings.gemini_text_model} is busy; using {model}.')
                except errors.APIError as exc:
                    # Only switch before this turn has executed any tools. Never restart/replay a turn.
                    if round_index != 0 or exc.code not in {429, 503} or not settings.openrouter_api_key:
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
                await store.record_best_effort(context.channel, context.session_id, "message", result["text"], {"role": "koe"})
                return result
            parts = []
            for fc in calls:
                result = await agent.run_tool(fc.name, fc.args, context=context)
                parts.append(types.Part(function_response=types.FunctionResponse(name=fc.name, id=fc.id, response=result)))
            history.append(types.Content(role="user", parts=parts))
    except text_fallback.FallbackError:
        return _reply('Gemini and the free backup text model are unavailable. You can still manage records from the Notion workspace. No tools were replayed.', context)
    except errors.APIError as exc:
        log.warning("model call failed: %s %s", exc.code, exc.status)
        if exc.code in {429, 503}:  # free-tier rate limit or "high demand": temporary, say so
            return _reply("Gemini is busy right now. Please try again in a minute. No approval was inferred.", context)
        return _reply("The model could not complete this turn. No approval was inferred.", context)
    except Exception:
        log.exception("text turn failed")
        return _reply("The model could not complete this turn. No approval was inferred.", context)
    return _reply("Stopped after eight tool rounds. Please narrow the request.", context)
