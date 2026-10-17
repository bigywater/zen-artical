import sys, os, time, json, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z92'); R = {}
n = Node('z92', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start()
CUR = HERE.parent / 'curator'
r = subprocess.run(['java', '-Dfile.encoding=UTF-8', '-Dstdout.encoding=UTF-8', '-cp', f'{CUR}/lib/*:{CUR}', 'Z92', str(n.p.pid)], capture_output=True, text=True, timeout=240)
print(r.stdout.rstrip()); 
if r.returncode: print('EXIT', r.returncode, r.stderr[-800:])
R['stdout'] = r.stdout
n.stop(); save('z92', R); os._exit(0)
