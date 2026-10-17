import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import client
from kazoo.exceptions import NodeExistsError
port, name, logf, t0, n = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), int(sys.argv[5])
z = client(f'127.0.0.1:{port}', timeout=3); z.ensure_path('/cron')
for k in range(n):
    d = t0 + k - time.time()
    if d > 0: time.sleep(d)
    try: z.create(f'/cron/tick-{k:03d}', name.encode()); open(logf, 'a').write(f'{time.time():.3f} {name} RUN {k}\n')
    except NodeExistsError: pass
