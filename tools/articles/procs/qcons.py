import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import client
from kazoo.recipe.queue import LockingQueue
port, name, tmo, logf, hold = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], float(sys.argv[5])
z = client(f'127.0.0.1:{port}', timeout=tmo); q = LockingQueue(z, '/lq')
def log(m): open(logf, 'a').write(f'{time.time():.3f} {name} {m}\n')
while True:
    item = q.get(timeout=2)
    if item is None: continue
    log(f'GOT {item.decode()}'); time.sleep(hold)
    q.consume(); log(f'ACK {item.decode()}')
