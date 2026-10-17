import sys, os, re, time, json, datetime, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k89')
cn, _ = up('main'); wait_nodes_ready()
NS = ns('k89')
env = dict(os.environ); env.pop('http_proxy', None); env.pop('https_proxy', None)
print(f'集群 {cn};用 client-go v0.36.1 写一个很小的 informer 程序(ConfigMap,resync 10 秒),在客户端包一层 RoundTripper 数它发出的 HTTP 请求')
r = subprocess.run([str(KT / 'informer' / 'informer'), str(kcfg(cn)), NS], capture_output=True, text=True, env=env, timeout=120)
L = [l for l in r.stdout.splitlines() if l.strip()]
if r.returncode != 0: print(r.stderr[-500:])
def sec(title, pred):
    print(f'== {title}')
    for l in L:
        if pred(l): print('  ' + l)
sec('一:启动——一次带 sendInitialEvents 的 WATCH 灌满缓存,之后读缓存不再请求 API Server', lambda l: 'HasSynced' in l or '第一个 WATCH' in l or ('ADD' in l and 'pre-' in l) or '本地缓存' in l or '直接向' in l)
sec('二:事件——WATCH 推送变化,回调拿到旧值和新值', lambda l: ('ADD' in l and 'live' in l) or 'UPDATE' in l or 'DELETE' in l or 'lister 里已经' in l or '事件回调累计' in l)
sec('三:resync——没有变化也会周期性回调 UpdateFunc', lambda l: '又过 25 秒' in l or '全程请求数' in l)
k('delete', 'ns', NS, '--wait=false')
