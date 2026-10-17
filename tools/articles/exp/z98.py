import sys, os, time, json, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z98'); R = {}
n = Node('z98', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start()
G = HERE.parent / 'gozk' / 'gozk'
p = subprocess.Popen([str(G)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
lines = []
for l in p.stdout:
    l = l.rstrip('\n')
    if l == 'STOP_ZK': n.stop(); p.stdin.write('go\n'); p.stdin.flush()
    elif l == 'STARTING': n.start(wipe=False)
    elif l == 'DONE': break
    else: print(l, flush=True); lines.append(l)
err = p.stderr.read() if p.poll() is not None else ''
if err: print('STDERR', err[-600:])
R['stdout'] = '\n'.join(lines); p.kill(); n.stop(); save('z98', R); os._exit(0)
