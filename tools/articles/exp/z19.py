import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z19'); R = {}
def attempt(port, k, timeout=3):
    ok, bad = [], 0
    for i in range(k):
        try: ok.append(client(f'127.0.0.1:{port}', timeout=4))
        except Exception: bad += 1
    return ok, bad
print('== 一:maxClientCnxns=5(按客户端 IP 限制):同一个 IP 依次开 8 个客户端')
n = Node('z19a', 7300, conf={'maxClientCnxns': 5}).start()
ok, bad = attempt(7300, 8); print(f'  成功 {len(ok)} 个,失败(连接超时){bad} 个')
lg = [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l) for l in n.log().splitlines() if 'Too many connections' in l]
print(f'  服务端日志里「Too many connections」共 {len(lg)} 行,例:', lg[0][:100] if lg else '(无)')
R['limit5'] = dict(ok=len(ok), bad=bad, log=lg[:1])
print()
print('== 二:关掉一个已有连接,名额马上空出来:新的客户端能连上')
ok[0].stop(); ok[0].close(); time.sleep(0.5)
try: z = client('127.0.0.1:7300', timeout=4); print('  关闭 1 个后,新客户端连接:成功'); ok.append(z); R['free'] = True
except Exception as e: print('  新客户端连接失败:', type(e).__name__); R['free'] = False
for z in ok[1:]: z.stop()
n.stop()
print()
print('== 三:maxClientCnxns=0 表示不限制:开 80 个客户端')
n = Node('z19b', 7301, conf={'maxClientCnxns': 0}).start()
ok, bad = attempt(7301, 80); print(f'  成功 {len(ok)} 个,失败 {bad} 个;服务端连接数', kv(n.four('mntr')).get('zk_num_alive_connections')); R['unlimited'] = dict(ok=len(ok), bad=bad)
for z in ok: z.stop()
n.stop()
print()
print('== 四:全局连接数上限 zookeeper.maxCnxns(整个服务端,不分 IP;默认 0 = 不限):设成 4,开 8 个客户端')
n = Node('z19c', 7302, conf={'maxClientCnxns': 0}, jvm=['-Dzookeeper.maxCnxns=4']).start()
ok, bad = attempt(7302, 8); print(f'  成功 {len(ok)} 个,失败 {bad} 个')
lg = [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l) for l in n.log().splitlines() if 'maxCnxns' in l or 'Too many' in l]; print('  日志:', [l[:100] for l in lg[:2]]); R['global'] = dict(ok=len(ok), bad=bad, log=[l[:120] for l in lg[:2]])
for z in ok: z.stop()
n.stop(); save('z19', R)
