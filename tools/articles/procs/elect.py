import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import client
from kazoo.recipe.election import Election
port, name, tmo, logf = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
z = client(f'127.0.0.1:{port}', timeout=tmo); el = Election(z, '/election', name)
def log(msg): open(logf, 'a').write(f'{time.time():.3f} {name} {msg}\n')
def lead():
    log('LEAD_START')
    n = 0
    while True:
        time.sleep(0.1); log('BEAT')
        if len(sys.argv) > 5 and sys.argv[5] == 'resign' and n > 15: return
        n += 1
el.run(lead)
