"""Disposable LOCAL PostgreSQL parity. Never uses DATABASE_URL from .env.

Requires local initdb/pg_ctl binaries; no remote database or owner account changes.
"""
import asyncio
import os
import shutil
import socket
import subprocess
from uuid import uuid4
from pathlib import Path

import psycopg
import pytest

from koe import connections, db, spotify_service as sp, spotify_store as journal, store
from koe.config import settings


def test_saved_approval_display_queries_hydrate_without_private_args(postgres):
    with psycopg.connect(**postgres, autocommit=True) as con:
        for migration in sorted((Path(__file__).resolve().parents[1] / 'migrations').glob('*.sql')):
            con.execute(migration.read_text(encoding='utf-8'), prepare=False)

    async def scenario():
        session = str(uuid4())
        action = await store.propose(session, 'app', 'sheets_add_columns', {
            'columns': ['Billable'], 'sheet_name': 'Timesheet', 'spreadsheet_id': 'sheet',
            'private_guard': 'must-stay-server-side'}, 'Complete exact audit')
        saved = await store.dashboard_read()
        assert saved['pending'][0]['display']['title'] == 'Add column Billable'
        await store.claim(action['id'], session, False)
        history = await store.dashboard_read()
        assert history['pending'] == []
        assert history['activity'][0]['summary'] == 'rejected'
        assert history['activity'][0]['display']['title'] == 'Add column Billable'
        assert history['activity'][0]['audit_summary'] == 'Complete exact audit'
        previews = await store.action_previews([action['id']])
        assert previews[action['id']]['display']['title'] == 'Add column Billable'
        assert 'must-stay-server-side' not in str([saved, history, previews])

    asyncio.run(scenario())


@pytest.fixture
def postgres(monkeypatch, tmp_path):
    initdb = shutil.which("initdb")
    pg_ctl = shutil.which("pg_ctl")
    if not initdb or not pg_ctl:
        pytest.skip("Disposable PostgreSQL test requires local initdb and pg_ctl")
    data = tmp_path / "postgres"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def run(*args):
        # PostgreSQL inherits pipe handles on Windows; a captured pg_ctl pipe
        # can stay open for the server's lifetime even after pg_ctl exits.
        output = tmp_path / "command.log"
        with output.open("wb") as log:
            result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, timeout=45, creationflags=flags)
        assert result.returncode == 0, output.read_text(errors="replace")

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    run(initdb, "-D", str(data), "-U", "spotify_test", "--auth=trust", "--no-locale", "--encoding=UTF8")
    options = {"host": "127.0.0.1", "port": port, "user": "spotify_test", "dbname": "postgres", "connect_timeout": 5}
    monkeypatch.setattr(settings, "database_url", f"postgresql://spotify_test@127.0.0.1:{port}/postgres?sslmode=require")
    monkeypatch.setattr(store, "connection_options", lambda: options)
    monkeypatch.setattr(db, "_neon", None)
    try:
        run(pg_ctl, "-D", str(data), "-l", str(tmp_path / "postgres.log"), "-o", f"-h 127.0.0.1 -p {port}", "-w", "start")
        yield options
    finally:
        if db._neon is not None:
            db._neon.close()
            db._neon = None
        if (data / "postmaster.pid").exists():
            run(pg_ctl, "-D", str(data), "-m", "immediate", "-w", "stop")


def test_all_migrations_replay_with_spotify_and_old_connections_and_atomic_claim(postgres, monkeypatch):
    migrations = sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql"))
    with psycopg.connect(**postgres, autocommit=True) as con:
        for migration in migrations:
            con.execute(migration.read_text(encoding="utf-8"), prepare=False)
        for provider in ("google", "github", "notion", "gemini", "spotify"):
            con.execute("insert into koe_connections (owner_id,provider,token_enc,created,updated) values (%s,%s,%s,%s,%s)",
                        ("migration-owner", provider, "encrypted-placeholder", "now", "now"))
        con.execute("insert into koe_music_mutations (owner_id,connection_id,request_id,body_hash,operation,state,evidence_enc,created,updated) "
                    "values ('migration-owner','generation','request','hash','add','sent','encrypted','now','now')")
        for migration in migrations:
            con.execute(migration.read_text(encoding="utf-8"), prepare=False)
        assert con.execute("select count(*) from koe_connections").fetchone()[0] == 5
        assert con.execute("select state from koe_music_mutations").fetchone()[0] == "sent"
        policies = con.execute("select relrowsecurity from pg_class where relname in ('koe_music_mutations','koe_spotify_flows')").fetchall()
        assert policies == [(True,), (True,)]
        assert con.execute("select has_table_privilege('public','koe_music_mutations','select')").fetchone()[0] is False
    # Exercise the actual Neon DB branch using the disposable PostgreSQL connection.
    rows = asyncio.run(db.sql("update koe_music_mutations set state='confirmed' where owner_id=%s and request_id=%s "
                              "and state='sent' returning request_id", "migration-owner", "request"))
    assert rows == [{"request_id": "request"}]
    assert asyncio.run(db.sql("update koe_music_mutations set state='confirmed' where owner_id=%s and request_id=%s "
                             "and state='sent' returning request_id", "migration-owner", "request")) == []
    monkeypatch.setattr(settings, "koe_secret_key", "postgres-test-secret-key-longer-than-32-characters")
    connections.save("journal-owner", "spotify", "Spotify", sp.SCOPES, {
        "connection_id": "generation", "refresh_token": "private-refresh"})

    async def exercise_journal():
        body = {"connection_id": "generation", "request_id": "intent", "uri": "spotify:track:" + "t" * 22}
        ticket, replay = await journal.prepare("journal-owner", body, "add", {"playlist_id": "p" * 22})
        assert replay is None

        async def provider():
            return {"snapshot_id": "verified"}

        result = await journal.send(ticket, provider)
        _, replay = await journal.prepare("journal-owner", body, "add", {"playlist_id": "p" * 22})
        assert replay == result and result["state"] == "confirmed"
        await sp.sql("insert into koe_spotify_flows (state_hash,owner_id,session_hash,cookie_hash,redirect_uri,expires) "
                     "values ('state','owner','session','cookie','redirect','2099-01-01')")
        query = "update koe_spotify_flows set consumed='now' where state_hash='state' and consumed is null returning state_hash"
        assert await sp.sql(query) == [{"state_hash": "state"}]
        assert await sp.sql(query) == []
    asyncio.run(exercise_journal())
