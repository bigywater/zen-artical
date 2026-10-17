import sys, os, time, json, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z96'); R = {}
n = Node('z96', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start()
CUR = HERE.parent / 'curator'; CP = f'{CUR}/lib/*:{CUR}'; J_ = ['java', '-Dfile.encoding=UTF-8', '-Dstdout.encoding=UTF-8', '-cp', CP]
r = subprocess.run(J_ + ['Z96'], capture_output=True, text=True, timeout=250); out_ = r.stdout.rstrip(); print(out_)
if r.returncode: print('EXIT', r.returncode, r.stderr[-800:])
R['stdout'] = out_; n.stop(); save('z96', R); os._exit(0)
