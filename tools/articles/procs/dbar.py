import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import client
from kazoo.recipe.barrier import DoubleBarrier
port, name, n, logf, stage = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
z = client(f'127.0.0.1:{port}', timeout=3); b = DoubleBarrier(z, '/dbk', n, identifier=name)
def log(m): open(logf, 'a').write(f'{time.time():.3f} {name} {m}\n')
b.enter(); log('ENTERED')
if stage == 'die_after_enter': time.sleep(300)
time.sleep(0.3); b.leave(); log('LEFT')
