import sys, time, os, signal, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import client
from kazoo.recipe.lock import Lock
port, name, tmo, logf = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
z = client(f'127.0.0.1:{port}', timeout=tmo); lk = Lock(z, '/lk', name)
def log(msg): open(logf, 'a').write(f'{time.time():.3f} {name} {msg}\n')
lk.acquire(); log('ACQUIRED'); st = []
z.add_listener(lambda s: (st.append(str(s)), log('STATE ' + str(s))))
time.sleep(float(sys.argv[5]) if len(sys.argv) > 5 else 300)
log(f'STILL_THINKS_HELD is_acquired={lk.is_acquired}')
