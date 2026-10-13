"""Secret-free deployment/configuration diagnostics. No provider or database calls."""
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Response

from koe import auth, gemini, identity, store
from koe.config import settings

router = APIRouter(prefix='/api/backend', dependencies=[Depends(auth.http_owner)])


def revision():
    # https://render.com/docs/environment-variables#render_git_commit
    value = os.getenv('RENDER_GIT_COMMIT', '')
    return value.lower() if re.fullmatch(r'[0-9a-fA-F]{7,40}', value) else 'unknown'


@router.get('/status')
async def status(response: Response):
    if not identity.is_owner():
        raise HTTPException(403, 'Backend diagnostics are available to the owner only.')
    response.headers['Cache-Control'] = 'no-store'
    return {'revision': revision(), 'configuration': {
        'gemini_primary_configured': bool(settings.gemini_api_key),
        'gemini_secondary_configured': bool(settings.gemini_api_key_2),
        'openrouter_configured': bool(settings.openrouter_api_key),
        'openrouter_free_model': settings.openrouter_model == 'openrouter/free' or settings.openrouter_model.endswith(':free'),
        'notion_configured': bool(settings.notion_token and (settings.notion_database_id or settings.notion_data_source_id)),
        'neon_configured': store.configured(),
    }, 'limits': {'gemini_attempt_ms': gemini.TIMEOUT_MS, 'gemini_generation_seconds': gemini.GENERATION_SECONDS,
                  'audit_backlog_capacity': store.MAX_BACKGROUND},
        'audit_pending': len(store._background),
        'note': 'Configuration presence only; this does not verify provider availability or remaining quota.'}
