import sys, os, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k90')
env = dict(os.environ); env.pop('http_proxy', None); env.pop('https_proxy', None)
print('用 client-go v0.36.1 的 workqueue 包写一个小程序(不需要集群):看去重、同 key 串行、失败重试的指数退避和延迟入队')
r = subprocess.run([str(KT / 'workq' / 'workq')], capture_output=True, text=True, env=env, timeout=60)
n = 0
for l in r.stdout.splitlines():
    if l.startswith('== '):
        n += 1; print(f'== {"一二三四五"[n - 1]}:{l[3:]}')
    elif l.strip(): print('  ' + l)
