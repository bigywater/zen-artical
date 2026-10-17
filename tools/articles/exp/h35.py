import sys, os, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import tee
tee('h35')
r = subprocess.run(['go', 'run', './cmd/h35'], cwd=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'grpcgo'), capture_output=True, text=True, timeout=300)
print(r.stdout, end='')
if r.returncode: print('ERROR', r.stderr[-2000:])
