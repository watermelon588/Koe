"""Authenticated Notion workspace; deterministic operations, no model required."""
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictBool

from koe import agent, events, notion_service, store
from koe.app_channel import authorized
from koe.config import settings

router = APIRouter(prefix='/api/notion', dependencies=[Depends(authorized)])


class Proposal(BaseModel):
    tool: Literal['notion_save', 'notion_archive', 'notion_add_properties']
    args: dict = Field(default_factory=dict)


class Decision(BaseModel):
    approve: StrictBool


class Setup(BaseModel):
    confirm: StrictBool


async def checked(operation):
    try:
        return await operation
    except notion_service.NotionError as exc:
        return JSONResponse(status_code=400, content={'detail': str(exc), 'code': exc.code, 'hint': exc.hint})
    except store.StoreError as exc:
        raise HTTPException(503, str(exc)) from None


async def context():
    # Stable owner-scoped UI conversation survives server restart; no other call/chat can approve it.
    session = str(uuid5(NAMESPACE_URL, 'koe:notion-workspace:' + settings.koe_owner_id))
    ctx = agent.Conversation('app', session_id=session)
    ctx.pending = await store.pending_for_session(session)
    ctx.approval_ready = bool(ctx.pending)
    return ctx


def public_pending(ctx):
    return ({k: ctx.pending[k] for k in ('id', 'summary', 'expires_ts')} if ctx.pending else None)


@router.get('/status')
async def status():
    return await checked(notion_service.status())


@router.get('/schema')
async def schema():
    return await checked(notion_service.schema_fields())


@router.get('/activity')
async def activity():
    return {'activity': await checked(store.notion_activity())}


@router.get('/records')
async def records(query: str = Query('', max_length=200), kind: str = '', cursor: str = Query('', max_length=500)):
    return await checked(notion_service.read(query=query, kind=kind, cursor=cursor))


@router.get('/records/{page_id}')
async def detail(page_id: str):
    return await checked(notion_service.read(page_id=page_id))


@router.post('/setup')
async def setup(body: Setup):
    if not body.confirm:
        raise HTTPException(400, 'Confirm adding the missing workflow properties first.')
    result = await checked(notion_service.setup())
    if isinstance(result, JSONResponse):
        return result
    events.publish('tool', name='notion_setup', phase='end', result=result, ok=True, channel='app')
    session = str(uuid5(NAMESPACE_URL, 'koe:notion-workspace:' + settings.koe_owner_id))
    await store.record_best_effort('app', session, 'tool', 'notion_setup', {'result': result})
    return result


@router.get('/pending')
async def pending():
    ctx = await checked(context())
    return {'pending_action': public_pending(ctx)}


@router.post('/proposals')
async def propose(body: Proposal):
    async with notion_service.lock():
        ctx = await checked(context())
        result = await agent.run_tool(body.tool, body.args, context=ctx)
        return result


@router.post('/approvals/{action_id}')
async def decide(action_id: str, body: Decision):
    # agent.confirm validates original context/action ID; store.claim is atomic across duplicate requests.
    ctx = await checked(context())
    result = await agent.confirm(ctx, body.approve, action_id)
    return {'result': result, 'pending_action': public_pending(ctx)}
