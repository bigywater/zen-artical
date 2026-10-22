import sys, os, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [p for p in sys.path if os.path.basename(p) != 'exp']          # exp/ 里有 v2.py 等文件,会盖住 nacos SDK 的顶层包 v2
from msl import *
import shutil, subprocess as sp, urllib.parse
tee('v54'); reset()
print('Nacos 的临时实例(ephemeral,gRPC 连接上的客户端登记,服务端靠连接判活)与持久实例(persistent,通过管理 API 登记,服务端主动探活,不会因为没人续约而被删)。Nacos 3.2.4(自己起的单机实例,Java 17),客户端用 nacos-sdk-python 3.2.0(每个临时实例是一个独立的子进程,这样可以真的杀掉、冻住客户端),持久实例用 /nacos/v3/admin/ns/instance。查询用 HTTP 的 /nacos/v3/client/ns/instance/list(客户端看到的视图)和 /nacos/v3/admin/ns/instance/list(管理视图,原始状态)')
shutil.rmtree(TT / 'nacos_v54', ignore_errors=True)
N = Nacos('v54', 8880, 8881).start(); time.sleep(4)
CL = TT / 'v54_client.py'
CL.write_text('''import asyncio, sys, threading
from v2.nacos import NacosNamingService, ClientConfigBuilder, RegisterInstanceParam, DeregisterInstanceParam
srv, svc, ip, port = sys.argv[1:5]
async def main():
    cfg = ClientConfigBuilder().server_address(srv).build(); ns = await NacosNamingService.create_naming_service(cfg)
    await ns.register_instance(request=RegisterInstanceParam(service_name=svc, ip=ip, port=int(port), ephemeral=True))
    print('registered', flush=True)
    loop = asyncio.get_running_loop()
    line = await loop.run_in_executor(None, sys.stdin.readline)
    if line.strip() == 'dereg':
        await ns.deregister_instance(request=DeregisterInstanceParam(service_name=svc, ip=ip, port=int(port), ephemeral=True)); print('deregistered', flush=True); await ns.shutdown()
asyncio.run(main())
''')
def spawn(svc, ip, port):
    p = sp.Popen([sys.executable, str(CL), '127.0.0.1:8880', svc, ip, str(port)], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.STDOUT, text=True, start_new_session=True)
    for _ in range(30):
        line = p.stdout.readline()
        if line.strip() == 'registered': return p
    raise AssertionError('client did not register')
def lst(svc, healthy=False, ns='public'):
    s, d = N.http('GET', '/nacos/v3/client/ns/instance/list', {'serviceName': svc, 'namespaceId': ns, 'healthyOnly': 'true' if healthy else 'false'}, timeout=5.0)
    return (json.loads(d).get('data') or []) if s == 200 else None
def find(svc, ip, port, healthy=False):
    r = lst(svc, healthy)
    if r is None: return None
    return next((i for i in r if i['ip'] == ip and i['port'] == port), False)
def admin_list(svc, healthy=False):
    s, d = N.http('GET', '/nacos/v3/admin/ns/instance/list', {'serviceName': svc, 'healthyOnly': 'true' if healthy else 'false'}, timeout=5.0)
    return (json.loads(d).get('data') or []) if s == 200 else None
def admin_find(svc, ip, port):
    r = admin_list(svc)
    return next((i for i in r if i['ip'] == ip and i['port'] == port), False) if r is not None else None
def poll(pred, timeout, step=0.1):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        try:
            if pred(): return time.perf_counter() - t0
        except Exception: pass
        time.sleep(step)
    return None
def admin(method, path, **kw):
    s, d = N.http(method, path, body=kw, timeout=10.0); return s, d
def reg_persist(svc, ip, port, **kw):
    return admin('POST', '/nacos/v3/admin/ns/instance', serviceName=svc, ip=ip, port=port, ephemeral='false', clusterName='DEFAULT', weight=1, **kw)
F = lambda x, d=1: f'{x:.{d}f} s' if x is not None else '没等到'

# ============ 一 ============
print('== 一:临时实例怎么才算“没了”。每个临时实例是独立的 SDK 客户端子进程;用三种方式让它消失:(a)优雅注销(deregister);(b)SIGKILL 子进程(操作系统关掉它的 TCP 连接);(c)SIGSTOP 子进程(进程被冻住,TCP 连接仍然开着、但没有任何数据)。从动作开始每 0.1 s 查一次实例列表(healthyOnly=false),记录实例从列表里消失的时间,以及中途 healthy 标志有没有变化。(c) 最多等 180 s')
rows = []
for k, mode in enumerate(('优雅注销', 'SIGKILL', 'SIGSTOP')):
    port = 8100 + k; svc = f'e{k}'; t_reg = time.perf_counter(); p = spawn(svc, '10.1.0.1', port)
    t_vis = poll(lambda: find(svc, '10.1.0.1', port), 20) 
    time.sleep(2.0); first = find(svc, '10.1.0.1', port); flags = [first['healthy']] if first else []
    t0 = time.perf_counter()
    if mode == '优雅注销': p.stdin.write('dereg\n'); p.stdin.flush()
    elif mode == 'SIGKILL': os.kill(p.pid, signal.SIGKILL)
    else: os.kill(p.pid, signal.SIGSTOP)
    changes = []; t_gone = None; last = None
    while time.perf_counter() - t0 < (180 if mode == 'SIGSTOP' else 60):
        try: i = find(svc, '10.1.0.1', port)
        except Exception: i = None
        if i is False: t_gone = time.perf_counter() - t0; break
        if i and i['healthy'] != last: changes.append((round(time.perf_counter() - t0, 1), i['healthy'])); last = i['healthy']
        time.sleep(0.1 if mode != 'SIGSTOP' else 0.2)
    rows.append((mode, F(t_vis, 2) if t_vis is not None else '-', F(t_gone, 2) if t_gone is not None else '180 s 内没有消失', ' → '.join(f'{t}s:healthy={h}' for t, h in changes) or '-'))
    try: os.killpg(p.pid, signal.SIGCONT); os.killpg(p.pid, signal.SIGKILL)
    except Exception: pass
table(rows, ['让它消失的方式', '子进程登记完成后到列表里可见', '动作到列表里消失', '期间 healthy 标志的变化(相对动作时刻)'])

# ============ 二 ============
print('== 二:持久实例由服务端探活,不会因为没人续约就消失。用管理 API 登记 127.0.0.1:端口(服务端默认对服务做 TCP 探测);本进程在该端口上开一个 TCP 监听来当“实例”。用管理 API 的列表看原始 healthy。(a)监听一直在时 healthy;(b)关掉监听后多久 healthy 变 false、实例是否还在列表里;(c)实例保持挂着 60 s 后还在不在;(d)重新开监听后多久 healthy 恢复。另外登记一个从头到尾没人监听的实例,看初始 healthy 和多久变 false')
S = Svc(lambda h: h.reply(200), 'p'); lp = S.port
s, d = reg_persist('p1', '127.0.0.1', lp); print(f'  登记持久实例 p1(端口 {lp}):HTTP {s} {d.decode()[:80]}')
i0 = admin_find('p1', '127.0.0.1', lp); print(f'  登记后立刻查:ephemeral={i0["ephemeral"]},healthy={i0["healthy"]}')
time.sleep(12); i1 = admin_find('p1', '127.0.0.1', lp); print(f'  监听一直开着,12 s 后:healthy={i1["healthy"]}')
S.stop(); t0 = time.perf_counter()
t_unh = poll(lambda: admin_find('p1', '127.0.0.1', lp)['healthy'] is False, 90, 0.2)
all_ = admin_list('p1', False); hy = admin_list('p1', True); cl = lst('p1', True)
print(f'  关掉监听后:healthy 变 false 用了 {F(t_unh)};此时管理 API healthyOnly=false 返回 {len(all_)} 个、healthyOnly=true 返回 {len(hy)} 个;客户端 API(healthyOnly=true)返回 {len(cl)} 个,其中 healthy={[i["healthy"] for i in cl]}')
time.sleep(60); i2 = admin_find('p1', '127.0.0.1', lp); print(f'  再等 60 s(共离开约 {time.perf_counter() - t0:.0f} s):实例{"仍在列表里" if i2 else "已经被删除"}' + (f',healthy={i2["healthy"]}' if i2 else ''))
S2 = Svc(lambda h: h.reply(200), 'p', port=lp); t0 = time.perf_counter()
t_back = poll(lambda: admin_find('p1', '127.0.0.1', lp)['healthy'] is True, 90, 0.2); print(f'  重新监听同一个端口后:healthy 恢复用了 {F(t_back)}'); S2.stop()
dead = free_port(); reg_persist('p2', '127.0.0.1', dead); i = admin_find('p2', '127.0.0.1', dead); init_h = i['healthy']
t_unh2 = poll(lambda: admin_find('p2', '127.0.0.1', dead)['healthy'] is False, 90, 0.2)
print(f'  从头没人监听的实例 p2:登记后立刻查 healthy={init_h};变 false 用了 {F(t_unh2)}(从登记后第一次查询算起)')

# ============ 三 ============
print('== 三:保护阈值(protectThreshold)。服务 prot 有 5 个持久实例(各自有监听);停掉其中 4 个的监听,等管理视图里 4 个都变成 unhealthy。然后依次把服务的保护阈值设成 0、0.1、0.2、0.5、再回 0(PUT /nacos/v3/admin/ns/service),每次等 2 s,比较:管理 API 里 unhealthy 的数量、客户端 API 里看到的 unhealthy 数量,以及两个 API 用 healthyOnly=true 查返回几个')
socks = []
for k in range(5):
    sv = Svc(lambda h: h.reply(200), 'pr'); socks.append(sv); reg_persist('prot', '127.0.0.1', sv.port)
time.sleep(3)
for sv in socks[:4]: sv.stop()
t_4 = poll(lambda: sum(1 for i in admin_list('prot') if not i['healthy']) == 4, 90, 0.2)
print(f'  4 个实例停掉监听后,{F(t_4)} 在管理视图里全部变成 unhealthy;服务的 protectThreshold 初始值:{json.loads(N.http("GET", "/nacos/v3/admin/ns/service", {"serviceName": "prot"})[1])["data"].get("protectThreshold")}')
rows = []
for th in (None, 0.1, 0.2, 0.5, 0.0):
    sc = ''
    if th is not None: s, d = admin('PUT', '/nacos/v3/admin/ns/service', serviceName='prot', protectThreshold=th); sc = f'(PUT HTTP {s})'; time.sleep(2.0)
    cur = json.loads(N.http('GET', '/nacos/v3/admin/ns/service', {'serviceName': 'prot'})[1])['data'].get('protectThreshold')
    a = admin_list('prot'); c = lst('prot', False); ch = lst('prot', True); ah = admin_list('prot', True)
    rows.append((f'{cur}{sc}', f'{sum(1 for i in a if not i["healthy"])} / {len(a)}', f'{sum(1 for i in c if not i["healthy"])} / {len(c)}', len(ch), len(ah)))
table(rows, ['protectThreshold', '管理视图 unhealthy / 总数', '客户端视图 unhealthy / 总数', '客户端 API healthyOnly=true 返回', '管理 API healthyOnly=true 返回'])
print('  健康比例 = 1 / 5 = 0.2。客户端视图在阈值不低于这个比例时把所有实例都报成 healthy(包括实际上已经停了的 4 个),低于时才如实返回;/nacos/v3/client/ns/instance/list 这一版对 healthyOnly 参数没有做过滤(本次实测,返回数与 false 时相同),管理 API 的 healthyOnly=true 则只返回原始状态为 healthy 的')
for sv in socks[4:]: sv.stop()

# ============ 四 ============
print('== 四:同一个服务里混用临时和持久实例,以及 Nacos 重启之后。(a)服务 mix 里先有一个临时实例,再用管理 API 登记一个持久实例;反过来,服务 mix2 先有持久实例,再用 SDK 登记临时实例;(b)Nacos 被 SIGKILL 后重启:服务 keep(持久,监听开着)与服务 eph(临时,SDK 客户端子进程一直活着)各自多久重新出现在列表里')
pm = spawn('mix', '10.2.0.1', 8201)
sm, dm = reg_persist('mix', '127.0.0.1', free_port())
print(f'  (a1)服务里已经有临时实例,再登记持久实例:HTTP {sm} {dm.decode()[:230]!r}')
reg_persist('mix2', '127.0.0.1', free_port())
async def reg_eph_late():
    from v2.nacos import NacosNamingService, ClientConfigBuilder, RegisterInstanceParam
    ns = await NacosNamingService.create_naming_service(ClientConfigBuilder().server_address('127.0.0.1:8880').build())
    try: await ns.register_instance(request=RegisterInstanceParam(service_name='mix2', ip='10.2.0.2', port=8202, ephemeral=True)); return 'ok'
    except Exception as e: return f'{type(e).__name__}: {str(e)[:150]}'
r = asyncio.run(reg_eph_late())
print(f'  (a2)服务里已经有持久实例,再用 SDK 登记临时实例:{r}')
print(f'       两个服务的最终内容:mix → {[(i["ip"], i["ephemeral"]) for i in lst("mix")]};mix2 → {[(i["ip"], i["ephemeral"]) for i in lst("mix2")]}')
SK = Svc(lambda h: h.reply(200), 'k'); reg_persist('keep', '127.0.0.1', SK.port); pe = spawn('eph', '10.3.0.1', 8301); time.sleep(8)
assert admin_find('keep', '127.0.0.1', SK.port) and find('eph', '10.3.0.1', 8301)
N.kill(); time.sleep(1.0); t_start = time.perf_counter(); N.start(wait=False)
t_up = poll(lambda: N.http('GET', '/nacos/v3/client/ns/instance/list', {'serviceName': 'keep'}, timeout=1.0)[0] == 200, 120, 0.2)
seen_keep = []
tk = poll(lambda: (seen_keep.append(admin_find('keep', '127.0.0.1', SK.port)) or seen_keep[-1]), 60, 0.2)
first_h = seen_keep[-1]['healthy'] if tk is not None else None
th_ = poll(lambda: (lambda x: x and x['healthy'])(admin_find('keep', '127.0.0.1', SK.port)), 60, 0.2)
te = poll(lambda: find('eph', '10.3.0.1', 8301), 120, 0.2)
print(f'  Nacos 被 SIGKILL 后重启(从启动命令算起):HTTP 接口可用 {F(t_up)};之后持久实例 keep 在列表里出现用了 {F(tk)}(刚出现时 healthy={first_h},healthy 为 true 用了 {F(th_)});临时实例 eph(SDK 客户端子进程一直活着)重新出现用了 {F(te)}(以上都从接口可用的时刻开始算)')
for p in (pm, pe):
    try: os.killpg(p.pid, signal.SIGKILL)
    except Exception: pass
SK.stop(); N.stop()
print('ERRORS', dict(ERRORS))
