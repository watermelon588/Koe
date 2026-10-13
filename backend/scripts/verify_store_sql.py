"""Verify the migration on a disposable LOCAL PostgreSQL cluster, never the user's database.

Requires initdb, postgres, pg_ctl and psql on PATH. Run: python -m scripts.verify_store_sql
"""
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4


def main():
    commands = {name: shutil.which(name) for name in ("initdb", "postgres", "pg_ctl", "psql")}
    if not all(commands.values()):
        raise SystemExit("Local PostgreSQL tools are required. This check never connects to Neon.")
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    def run(name, *args, **kwargs):
        return subprocess.run([commands[name], *args], capture_output=True, text=True,
                              check=True, **flags, **kwargs).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="koe-phase2-pg-") as root:
        # TemporaryDirectory owns exactly this freshly created directory; never touch installed clusters.
        data = str(Path(root) / "data")
        run("initdb", "-D", data, "-U", "postgres", "-A", "trust", "--no-locale", "-E", "UTF8")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = str(sock.getsockname()[1])
        with open(Path(root) / "postgres.log", "w") as log:
            server = subprocess.Popen([commands["postgres"], "-D", data, "-p", port, "-h", "127.0.0.1"],
                                      stdout=log, stderr=log, **flags)
            def sql(query):
                return run("psql", "-X", "-h", "127.0.0.1", "-p", port, "-U", "postgres", "-d", "postgres",
                           "-At", "-v", "ON_ERROR_STOP=1", "-c", query)
            try:
                for _ in range(50):
                    try:
                        sql("select 1")
                        break
                    except subprocess.CalledProcessError:
                        time.sleep(0.1)
                sql("create role untrusted;")
                migration = (Path(__file__).resolve().parents[1] / "migrations/001_phase2.sql").read_text(encoding="utf-8")
                sql(migration)
                session = str(uuid4())
                def propose(s=session):
                    return json.loads(sql(f"select public.koe_propose_action('owner','{s}','cli','calendar_upsert_event','{{}}','Call');"))
                action = propose()
                assert propose()["id"] == action["id"], "Same proposal must be idempotent"
                assert "error" in json.loads(sql(f"select public.koe_propose_action('owner','{session}','cli','calendar_upsert_event','{{\"other\":true}}','Different');")), "A different proposal cannot replace a pending action"
                wrong = sql(f"select public.koe_claim_action('other','{session}','{action['id']}',true) is null;")
                assert wrong == "t", "Other owner cannot claim"
                wrong = sql(f"select public.koe_claim_action('owner','{uuid4()}','{action['id']}',true) is null;")
                assert wrong == "t", "Other conversation cannot claim"
                query = f"select public.koe_claim_action('owner','{session}','{action['id']}',true);"
                with ThreadPoolExecutor(max_workers=4) as pool:
                    claims = list(pool.map(lambda _: sql(query), range(4)))
                assert sum(bool(c) for c in claims) == 1, "Exactly one concurrent claim may execute"
                result = json.loads(sql(f"select public.koe_finish_action('owner','{session}','{action['id']}',true,'{{\"id\":\"event\"}}');"))
                assert result["status"] == "executed"
                assert sql(f"select string_agg(summary,',' order by ts,id) from public.koe_activity where payload_json->>'action_id'='{action['id']}';").count("approved") == 1
                expired = propose()
                sql(f"update public.koe_pending_actions set expires_ts=now()-interval '1 second' where id='{expired['id']}';")
                assert json.loads(sql(f"select public.koe_claim_action('owner','{session}','{expired['id']}',true);"))["status"] == "expired"
                rejected = propose()
                assert json.loads(sql(f"select public.koe_claim_action('owner','{session}','{rejected['id']}',false);"))["status"] == "rejected"
                assert not sql(f"select public.koe_claim_action('owner','{session}','{rejected['id']}',true);")
                assert sql("select has_function_privilege('untrusted','public.koe_claim_action(text,uuid,uuid,boolean)','execute');") == "f"
                assert sql("select has_table_privilege('untrusted','public.koe_pending_actions','select');") == "f"
                assert sql("select bool_and(relrowsecurity) from pg_class where relname in ('koe_activity','koe_pending_actions','koe_daily_notes','koe_github_deliveries');") == "t"
                app_session = str(uuid4())
                app_action = json.loads(sql(f"select public.koe_propose_action('owner','{app_session}','app','calendar_upsert_event','{{}}','App proposal');"))
                assert app_action["channel"] == "app", "Installed app proposals must be persisted too"
                assert json.loads(sql(f"select public.koe_claim_action('owner','{app_session}','{app_action['id']}',false);"))["status"] == "rejected"
                sql(migration)  # reapplying must preserve existing actions
                assert sql("select count(*) from public.koe_pending_actions;") == "4"
                print("PASS SQL: migration/reapply, audit, concurrent claims, owner/session isolation, expiry, rejection, RLS/grants")
            finally:
                subprocess.run([commands["pg_ctl"], "-D", data, "-m", "fast", "-w", "stop"],
                               capture_output=True, **flags)
                server.wait(timeout=15)


if __name__ == "__main__":
    main()
