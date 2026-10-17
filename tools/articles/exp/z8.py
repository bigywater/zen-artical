import sys, os, time, json, re, subprocess, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.exceptions import NoChildrenForEphemeralsError
tee('z8'); R = {}
n = Node('z8', 7300, conf={'tickTime': 1000}, jvm=['-Dzookeeper.extendedTypesEnabled=true', '-Dznode.container.checkIntervalMs=300']).start()
z = client('127.0.0.1:7300', timeout=6); w = client('127.0.0.1:7300', timeout=6)
print('== 一:持久节点与临时节点的 stat:ephemeralOwner 就是创建者的会话 id')
z.create('/persist', b'p'); z.create('/eph', b'e', ephemeral=True)
sid = z.client_id[0]
print(f'  /persist  ephemeralOwner = {w.get("/persist")[1].ephemeralOwner:#x}'); print(f'  /eph      ephemeralOwner = {w.get("/eph")[1].ephemeralOwner:#x}   创建者会话 id = {sid:#x}   相等: {w.get("/eph")[1].ephemeralOwner == sid}')
R['owner_equal'] = w.get('/eph')[1].ephemeralOwner == sid
print()
print('== 二:临时节点不能有子节点')
try: z.create('/eph/child', b'')
except NoChildrenForEphemeralsError as e: print('  create /eph/child →', type(e).__name__); R['nochild'] = type(e).__name__
print()
print('== 三:客户端正常 close():临时节点什么时候消失?(另一个客户端轮询)')
z2 = client('127.0.0.1:7300', timeout=6); z2.create('/eph-close', b'', ephemeral=True)
t0 = time.perf_counter(); z2.stop(); z2.close()
while w.exists('/eph-close'): time.sleep(0.01)
tclose = (time.perf_counter() - t0) * 1000; print(f'  close() 之后到节点消失:{tclose:.0f} ms'); R['close_ms'] = tclose
print()
print('== 四:客户端进程被 kill -9(没有 close):临时节点要等会话超时(请求 6 s,tickTime=1000 → 协商后的超时见下)')
code = "import sys, time, os; sys.path.insert(0, '.')\nfrom zkl import client\nz = client('127.0.0.1:7300', timeout=6); z.create('/eph-kill', b'', ephemeral=True); print('created', flush=True); os.kill(os.getpid(), 9)\n"
t0 = time.perf_counter(); subprocess.run([sys.executable, '-c', code], cwd=HERE, capture_output=True)
tk = time.perf_counter()
print('  客户端进程被 kill -9 之后立即查询:', 'eph-kill 还在' if w.exists('/eph-kill') else '已消失')
while w.exists('/eph-kill'): time.sleep(0.05)
tgone = (time.perf_counter() - tk) * 1000; to = int(re.search(r'to=(\d+)', n.four('cons')).group(1)) if 'to=' in n.four('cons') else None
print(f'  从进程被杀到节点消失:{tgone:.0f} ms(会话超时 6000 ms)'); R['kill_ms'] = tgone
print()
print('== 五:服务端重启:会话在 snapshot/事务日志里,客户端在超时内重连,临时节点还在')
z3 = client('127.0.0.1:7300', timeout=30); z3.create('/eph-restart', b'', ephemeral=True); sid3 = z3.client_id[0]
n.stop(); n.start(wipe=False); time.sleep(1.5)
ok = z3.exists('/eph-restart') is not None; print('  服务端重启后 /eph-restart 还在:', ok, '| 同一个会话 id:', z3.client_id[0] == sid3); R['restart'] = dict(exists=ok, same=z3.client_id[0] == sid3)
print()
print('== 六:TTL 节点与容器节点(3.6+;需要 -Dzookeeper.extendedTypesEnabled=true)')
seen = {}
def poll():
    while 'gone' not in seen:
        e = w.exists('/ttl1'); t = time.perf_counter()
        if e and 'appear' not in seen: seen['appear'] = t
        if not e and 'appear' in seen: seen['gone'] = t
        time.sleep(0.02)
th = threading.Thread(target=poll); th.start()
out = cli(7300, 'create -t 2000 /ttl1 x'); print('  [zk] create -t 2000 /ttl1 x →', out[0]); th.join(15)
dur = (seen.get('gone', 0) - seen.get('appear', 0)) * 1000
print(f'  轮询看到 /ttl1 存在了 {dur:.0f} ms(TTL = 2000 ms,容器检查间隔被我设成 300 ms)'); R['ttl_ms'] = dur
out = cli(7300, 'create -c /cont', 'create -c /cont/child x'); print('  [zk] create -c /cont →', out[0], '|  create -c /cont/child x →', out[1])
w.delete('/cont/child'); t0 = time.perf_counter()
while w.exists('/cont') and time.perf_counter() - t0 < 10: time.sleep(0.02)
print(f'  容器节点 /cont 在删掉最后一个子节点 {(time.perf_counter() - t0) * 1000:.0f} ms 后被自动删除'); R['container_ms'] = (time.perf_counter() - t0) * 1000
m = Node('z8b', 7301).start()
print('  没有 extendedTypesEnabled 的另一个节点上 create -t 1000 /x →', cli(7301, 'create -t 1000 /x x')[0].splitlines()[0]); R['no_ext'] = cli(7301, 'create -t 1000 /x x')[0].splitlines()[0]; m.stop()
for c in (z, w, z3):
    try: c.stop()
    except Exception: pass
n.stop(); save('z8', R)
