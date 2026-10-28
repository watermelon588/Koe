"""Read-only diagnosis of the configured database addresses; no addresses or credentials printed."""
import concurrent.futures
import json
import logging
import socket
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from koe import store
import psycopg
logging.disable(logging.CRITICAL)
options=store.connection_options()
if '--direct-tls' in sys.argv:
    options['sslnegotiation']='direct'
if '--ssl-only' in sys.argv:
    options['gssencmode']='disable'
addresses=list(dict.fromkeys((row[0],row[4][0]) for row in socket.getaddrinfo(options['host'],options.get('port',5432),type=socket.SOCK_STREAM)))
print(json.dumps({'resolved_addresses':len(addresses),'families':[family for family,_ in addresses]}),flush=True)
def check(item):
    index,(family,address)=item
    started=time.perf_counter()
    result={'address_index':index,'family':family}
    try:
        with socket.create_connection((address,int(options.get('port',5432))),timeout=3):
            result['tcp']=True
        with psycopg.connect(**{**options,'hostaddr':address,'connect_timeout':3}) as con:
            con.read_only=True
            con.execute("set local statement_timeout='3000ms'")
            result['query']=con.execute('select 1').fetchone()[0]==1
    except Exception as exc:
        result['exception_type']=type(exc).__name__
    result['elapsed_ms']=round((time.perf_counter()-started)*1000)
    print(json.dumps(result),flush=True)
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results=list(pool.map(check,enumerate(addresses)))
Path(__file__).with_name('repairs').mkdir(exist_ok=True)
Path(__file__).with_name('repairs').joinpath('network-ssl-only-results.json' if '--ssl-only' in sys.argv else 'network-direct-results.json' if '--direct-tls' in sys.argv else 'network-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
