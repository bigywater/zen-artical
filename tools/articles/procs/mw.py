import sys, time, os, threading, json, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import client
from kazoo.recipe.election import Election
from kazoo.exceptions import NodeExistsError, NoNodeError
role, port, name, tmo, logf = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
z = client(f'127.0.0.1:{port}', timeout=tmo)
def log(m): open(logf, 'a').write(f'{time.time():.3f} {name} {m}\n')
if role == 'worker':
    z.create(f'/workers/{name}', b'', ephemeral=True); z.ensure_path(f'/assign/{name}'); log('WORKER_UP')
    while True:
        kids = z.get_children(f'/assign/{name}')
        if not kids: time.sleep(0.03); continue
        for t in sorted(kids):
            try: payload = z.get(f'/assign/{name}/{t}')[0]
            except NoNodeError: continue
            time.sleep(0.03)
            try: z.create(f'/done/{t}', name.encode()); log(f'DONE {t}')
            except NodeExistsError: log(f'DUPLICATE {t}')
            try: z.delete(f'/assign/{name}/{t}')
            except NoNodeError: pass
else:
    el = Election(z, '/master-election', name)
    def master():
        log('MASTER_START'); known = set()
        while True:
            workers = sorted(z.get_children('/workers'))
            for dead in known - set(workers):
                moved = 0
                for t in z.get_children(f'/assign/{dead}') if z.exists(f'/assign/{dead}') else []:
                    try:
                        tx = z.transaction(); tx.create(f'/tasks/{t}', b''); tx.delete(f'/assign/{dead}/{t}'); tx.commit(); moved += 1
                    except Exception: pass
                try: z.delete(f'/assign/{dead}', recursive=True)
                except Exception: pass
                log(f'WORKER_LOST {dead} requeued={moved}')
            for w in set(workers) - known: log(f'WORKER_SEEN {w}')
            known = set(workers)
            if workers:
                tasks = sorted(z.get_children('/tasks'))
                for i, t in enumerate(tasks):
                    w = workers[hash(t) % len(workers)]
                    try:
                        tx = z.transaction(); tx.delete(f'/tasks/{t}'); tx.create(f'/assign/{w}/{t}', b''); tx.commit()
                    except Exception: pass
            time.sleep(0.1)
    el.run(master)
