"""Bounded read and queue regressions; no live database access."""
import asyncio
import threading
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from fastapi.testclient import TestClient

from koe import db, store
from koe.config import settings
from koe.main import app


def test_history_read_has_a_total_deadline(monkeypatch):
    release = threading.Event()
    calls = []
    def slow_read(query, params):
        calls.append(query)
        release.wait(1)
        return []
    monkeypatch.setattr(db, '_run', slow_read)
    monkeypatch.setattr(db, 'READ_SECONDS', .02, raising=False)
    async def scenario():
        try:
            with pytest.raises(psycopg.OperationalError):
                await db.sql('select * from koe_app_messages')
        finally:
            release.set()
    asyncio.run(scenario())
    assert len(calls) == 1


@pytest.mark.parametrize('module,lock_name', [(db, '_neon_lock'), (store, '_con_lock')])
def test_busy_database_fails_before_sending_another_operation(monkeypatch, module, lock_name):
    lock = threading.Lock()
    lock.acquire()
    timer = threading.Timer(.2, lock.release)
    timer.start()
    monkeypatch.setattr(module, lock_name, lock)
    monkeypatch.setattr(module, 'LOCK_SECONDS', .01, raising=False)
    monkeypatch.setattr(settings, 'database_url', 'postgresql://user:secret@db.invalid/app?sslmode=require')
    sent = []
    monkeypatch.setattr(psycopg, 'connect', lambda **kwargs: sent.append(kwargs))
    try:
        with pytest.raises((psycopg.OperationalError, store.StoreError)):
            if module is db:
                db._run_neon('insert into koe_app_messages values (%s)', ('x',))
            else:
                with store._connection(store.connection_options()):
                    pytest.fail('The database lock was not acquired.')
    finally:
        timer.cancel()
        if lock.locked():
            lock.release()
    assert sent == []


def test_database_errors_are_recoverable_and_never_expose_details(monkeypatch):
    from koe import auth
    async def unavailable(request):
        raise psycopg.OperationalError('private-host private-password private-sql')
    monkeypatch.setattr(auth, 'signed_in_user', unavailable)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/api/connections')
    assert response.status_code == 503
    assert 'private-' not in response.text
    assert response.headers.get('retry-after')


def test_parallel_reads_can_wait_for_a_healthy_cold_connection(monkeypatch):
    started = threading.Event()
    class Connection:
        closed = broken = False
        @contextmanager
        def transaction(self):
            yield
        def execute(self, *args):
            return self
        description = True
        def fetchall(self):
            return [{'ok': True}]
    def connect(**kwargs):
        started.set()
        time.sleep(2.2)  # A healthy cold Neon handshake must fit the queue budget.
        return Connection()
    monkeypatch.setattr(settings, 'database_url', 'postgresql://user:secret@db.invalid/app?sslmode=require')
    monkeypatch.setattr(db, '_neon', None)
    monkeypatch.setattr(db, '_neon_lock', threading.Lock())
    monkeypatch.setattr(psycopg, 'connect', connect)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(db._run_neon, 'select 1', ())
        assert started.wait(1)
        second = pool.submit(db._run_neon, 'select 1', ())
        assert first.result(5) == second.result(5) == [{'ok': True}]
