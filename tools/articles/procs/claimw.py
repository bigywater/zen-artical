import sys, os, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import client
from kazoo.exceptions import NodeExistsError, NoNodeError
port, name, logf = sys.argv[1], sys.argv[2], sys.argv[3]
z = client(f'127.0.0.1:{port}', timeout=3)
def log(m): open(logf, 'a').write(f'{time.time():.3f} {name} {m}\n')
log('UP')
idle = 0
while idle < 6000:
    todo = sorted(set(z.get_children('/tasks')) - set(z.get_children('/done'))); random.shuffle(todo)
    did = False
    for t in todo:
        try: z.create(f'/claims/{t}', name.encode(), ephemeral=True)
        except NodeExistsError: continue
        if z.exists(f'/done/{t}'):
            z.delete(f'/claims/{t}'); continue
        log(f'START {t}'); time.sleep(3.0 if t.startswith('slow') else 0.01)
        z.create(f'/done/{t}', name.encode()); log(f'END {t}')
        try: z.delete(f'/claims/{t}')
        except NoNodeError: pass
        did = True
    idle = 0 if did else idle + 1
    time.sleep(0.05)
