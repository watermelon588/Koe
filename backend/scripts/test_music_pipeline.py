"""Run isolated OAuth/playback and two-window voice E2E suites with managed servers.

Example: python -m scripts.test_music_pipeline --node-modules <directory containing playwright>
Never starts the normal backend or uses hosted storage/provider credentials.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


def wait_ready(url, process):
    deadline = time.monotonic() + 45
    with httpx.Client(timeout=2, trust_env=False) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('A test server exited; inspect the test-only server logs.')
            try:
                if client.get(url).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(.2)
    raise RuntimeError('A test server did not become ready.')


def main():
    # Windows console code pages may not represent the workspace's Japanese name.
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node-modules', default=os.getenv('KOE_E2E_NODE_MODULES'))
    parser.add_argument('--frontend-port', type=int, default=5176)
    parser.add_argument('--backend-port', type=int, default=8002)
    args = parser.parse_args()
    if not args.node_modules or not (Path(args.node_modules) / 'playwright/index.mjs').is_file():
        parser.error('Provide an existing directory containing playwright with --node-modules.')
    if not all(1024 <= port <= 65535 for port in (args.frontend_port, args.backend_port)):
        parser.error('Use distinct unprivileged local ports.')
    if args.frontend_port == args.backend_port:
        parser.error('Frontend and backend ports must differ.')
    node = shutil.which('node')
    if not node:
        parser.error('Node.js is required.')
    backend = Path(__file__).resolve().parents[1]
    frontend = backend.parent / 'frontend'
    origin, fixture = f'http://127.0.0.1:{args.frontend_port}', f'http://127.0.0.1:{args.backend_port}'
    env = {**os.environ, 'KOE_BACKEND': fixture, 'VITE_BACKEND_URL': '', 'KOE_SPOTIFY_E2E': 'true',
           'KOE_E2E_ORIGIN': origin, 'KOE_E2E_FIXTURE': fixture, 'KOE_E2E_NODE_MODULES': str(Path(args.node_modules).resolve())}
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    processes = []
    with tempfile.TemporaryDirectory(prefix='koe-pipeline-logs-') as directory:
        with (Path(directory) / 'backend.log').open('w', encoding='utf-8') as server_log, (Path(directory) / 'frontend.log').open('w', encoding='utf-8') as web_log:
            try:
                server = subprocess.Popen([sys.executable, 'tests/spotify_e2e_server.py', '--port', str(args.backend_port), '--origin', origin],
                    cwd=backend, env=env, stdout=server_log, stderr=subprocess.STDOUT, creationflags=flags)
                processes.append(server)
                web = subprocess.Popen([node, str(frontend / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', str(args.frontend_port), '--strictPort'],
                    cwd=frontend, env=env, stdout=web_log, stderr=subprocess.STDOUT, creationflags=flags)
                processes.append(web)
                wait_ready(fixture + '/__e2e/state', server)
                wait_ready(origin, web)
                for suite in ('spotify_e2e_browser.mjs', 'spotify_voice_e2e_browser.mjs'):
                    result = subprocess.run([node, str(backend / 'tests' / suite)], cwd=backend, env=env,
                        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=240, creationflags=flags)
                    print(result.stdout, flush=True)
                    if result.stderr:
                        print(result.stderr, file=sys.stderr, flush=True)
                    result.check_returncode()
            finally:
                # Only processes started by this runner are stopped; existing app/test servers are untouched.
                for process in reversed(processes):
                    if process.poll() is None:
                        if os.name == 'nt':
                            # The venv launcher may own a Python child holding the log file open.
                            # Stop only this runner's process tree, before TemporaryDirectory cleanup.
                            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                capture_output=True, timeout=10, creationflags=flags)
                        else:
                            process.terminate()
                        try:
                            process.wait(timeout=8)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=8)
    print('PASS complete isolated music pipeline. Reports: backend/data/spotify-e2e-browser and spotify-voice-e2e-browser.')


if __name__ == '__main__':
    main()
