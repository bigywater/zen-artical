import sys, os, time, json, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z97'); R = {}
n = Node('z97', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start()
CUR = HERE.parent / 'curator'; CP = f'{CUR}/lib/*:{CUR}'; J_ = ['java', '-Dfile.encoding=UTF-8', '-Dstdout.encoding=UTF-8', '-cp', CP]
p = subprocess.Popen(J_ + ['Z97'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
lines = []
for l in p.stdout:
    l = l.rstrip('\n')
    if l == 'STOP_ZK':
        n.stop(); p.stdin.write('go\n'); p.stdin.flush(); time.sleep(1.5); n.start(wipe=False)
    elif l == 'DONE_ONE':
        time.sleep(1.0); p.stdin.write('go\n'); p.stdin.flush()
    else: print(l, flush=True); lines.append(l)
R['stdout'] = '\n'.join(lines); n.stop(); save('z97', R); os._exit(0)
