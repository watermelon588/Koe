"""Compare encrypted connection negotiation on one configured address; read-only."""
import json
import socket
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from koe import store
import psycopg
options=store.connection_options()
options['hostaddr']=next(row[4][0] for row in socket.getaddrinfo(options['host'],options.get('port',5432),type=socket.SOCK_STREAM) if row[0]==socket.AF_INET)
options['connect_timeout']=3
results=[]
for mode,extra in [('original',{}),('ssl_only',{'gssencmode':'disable'}),('direct_tls',{'sslnegotiation':'direct'}),('direct_ssl_only',{'sslnegotiation':'direct','gssencmode':'disable'})]:
    started=time.perf_counter()
    result={'mode':mode}
    try:
        with psycopg.connect(**{**options,**extra}) as con:
            con.read_only=True
            con.execute("set local statement_timeout='3000ms'")
            result['query']=con.execute('select 1').fetchone()[0]==1
    except Exception as exc:
        result['exception_type']=type(exc).__name__
    result['elapsed_ms']=round((time.perf_counter()-started)*1000)
    results.append(result)
    print(json.dumps(result),flush=True)
Path(__file__).with_name('repairs').joinpath('database-transport-ab.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
