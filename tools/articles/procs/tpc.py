import sys, os, time, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import client
from kazoo.exceptions import NodeExistsError, NoNodeError
role, port, name, logf = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]; extra = sys.argv[5:]
z = client(f'127.0.0.1:{port}', timeout=3)
def log(m): open(logf, 'a').write(f'{time.time():.4f} {name} {m}\n')
def wait_node(path):
    ev = threading.Event()
    while True:
        if z.exists(path, watch=lambda e: ev.set()): return
        ev.wait(); ev.clear()
def get_wait(path):
    wait_node(path); return z.get(path)[0].decode()
def decide(txid, parts, timeout):
    t_end = time.time() + timeout; votes = {}
    while time.time() < t_end:
        for p in parts:
            if p not in votes:
                try: votes[p] = z.get(f'/tx/{txid}/votes/{p}')[0].decode()
                except NoNodeError: pass
        if len(votes) == len(parts) or 'no' in votes.values(): break
        time.sleep(0.01)
    return votes
def write_decision(txid, votes, parts):
    d = 'commit' if len(votes) == len(parts) and all(v == 'yes' for v in votes.values()) else 'abort'
    try: z.create(f'/tx/{txid}/decision', d.encode())
    except NodeExistsError: d = z.get(f'/tx/{txid}/decision')[0].decode()
    return d
if role == 'participant':
    z.ensure_path('/tx'); z.create(f'/members/{name}', b'', ephemeral=True, makepath=True); log('UP')
    for txid in extra:
        parts = get_wait(f'/tx/{txid}/prepare').split(',')
        if name not in parts: continue
        log(f'PREPARE {txid}')
        if txid == 'tdie' and name == 'P3': os.kill(os.getpid(), 9)
        time.sleep(0.02)
        v = 'no' if (txid == 'tno' and name == 'P2') else 'yes'
        z.create(f'/tx/{txid}/votes/{name}', v.encode(), makepath=True); log(f'VOTE {txid} {v}')
        d = get_wait(f'/tx/{txid}/decision'); log(f'APPLIED {txid} {d}')
elif role == 'coord':
    txid, parts, mode = extra[0], extra[1].split(','), extra[2]
    z.create(f'/tx/{txid}/prepare', ','.join(parts).encode(), makepath=True); log(f'PREPARE_SENT {txid}')
    votes = decide(txid, parts, 3.0); log(f'VOTES {txid} {votes}')
    if mode == 'stall': log('STALLED'); time.sleep(600)
    log(f'DECISION {txid} {write_decision(txid, votes, parts)}')
elif role == 'recover':
    txid = extra[0]; parts = z.get(f'/tx/{txid}/prepare')[0].decode().split(',')
    if z.exists(f'/tx/{txid}/decision'): log(f'RECOVER_FOUND {z.get(f"/tx/{txid}/decision")[0].decode()}')
    else:
        votes = decide(txid, parts, 0.5); log(f'RECOVER_VOTES {votes}'); log(f'RECOVER_DECISION {write_decision(txid, votes, parts)}')
