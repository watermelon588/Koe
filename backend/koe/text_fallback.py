"""Optional free OpenRouter text/tool provider. Never executes tools itself.

https://openrouter.ai/docs/guides/features/tool-calling
https://openrouter.ai/docs/guides/routing/routers/free-router
"""
import json
from types import SimpleNamespace

import httpx
from google.genai import types

from koe import agent
from koe.config import settings


class FallbackError(Exception):
    pass


def messages(history, connection_state=None):
    result = [{'role': 'system', 'content': agent.system_prompt(connection_state)}]
    pending = []
    for i, content in enumerate(history):
        parts = content.parts or []
        calls = [p.function_call for p in parts if p.function_call]
        responses = [p.function_response for p in parts if p.function_response]
        text = ''.join(p.text for p in parts if p.text and not p.thought)
        if responses:
            for response in responses:
                index = next((j for j, c in enumerate(pending) if c[1] == response.name), None)
                call_id = pending.pop(index)[0] if index is not None else response.id
                if not call_id:
                    raise FallbackError('Conversation tool history cannot be safely transferred.')
                result.append({'role': 'tool', 'tool_call_id': call_id, 'content': json.dumps(response.response)})
        elif calls:
            tool_calls = []
            for j, call in enumerate(calls):
                call_id = call.id or f'call_{i}_{j}'
                pending.append((call_id, call.name))
                tool_calls.append({'id': call_id, 'type': 'function', 'function': {'name': call.name, 'arguments': json.dumps(call.args or {})}})
            result.append({'role': 'assistant', 'content': text or None, 'tool_calls': tool_calls})
        elif text:
            result.append({'role': 'assistant' if content.role == 'model' else 'user', 'content': text})
    return result


async def generate(history):
    model = settings.openrouter_model
    if not settings.openrouter_api_key or not (model == 'openrouter/free' or model.endswith(':free')):
        raise FallbackError('A free backup text model is not configured.')
    tools = [{'type': 'function', 'function': {'name': name, 'description': tool.description, 'parameters': tool.parameters}}
             for name, tool in agent.TOOLS.items()]
    try:
        connection_state = await agent.connection_status()
        async with httpx.AsyncClient(timeout=35, trust_env=False) as api:
            response = await api.post('https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': 'Bearer ' + settings.openrouter_api_key},
                json={'model': model, 'messages': messages(history, connection_state), 'tools': tools, 'max_tokens': 1800})
            response.raise_for_status()
            data = response.json()
        message = data['choices'][0]['message']
        if not isinstance(message, dict):
            raise ValueError()
        parts = []
        if isinstance(message.get('content'), str) and message['content']:
            parts.append(types.Part.from_text(text=message['content']))
        calls = message.get('tool_calls') or []
        if not isinstance(calls, list) or len(calls) > 8:
            raise ValueError()
        for call in calls:
            fn = call['function']
            args = json.loads(fn['arguments'])
            if fn['name'] not in agent.TOOLS or not isinstance(args, dict) or not isinstance(call.get('id'), str):
                raise ValueError()
            parts.append(types.Part(function_call=types.FunctionCall(name=fn['name'], args=args, id=call['id'])))
        if not parts:
            raise ValueError()
        return SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role='model', parts=parts))])
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError):
        raise FallbackError('The backup text provider is unavailable or returned an invalid answer. No tools were replayed.') from None
