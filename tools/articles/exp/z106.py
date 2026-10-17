import sys, os, time, json, re, subprocess, signal, urllib.request, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z106'); R = {}
n = Node('z106', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
JAR = HERE.parent / 'spring' / 'target' / 'zkdemo-1.jar'; WD = ZDATA / 'z106'; WD.mkdir(exist_ok=True)
def app(port, extra=()):
    f = WD / f'app{port}.log'; p = subprocess.Popen(['java', '-Xmx256m', '-jar', str(JAR), f'--server.port={port}', *extra], stdout=open(f, 'w'), stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 90:
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/hello', timeout=1); return p
        except Exception: time.sleep(0.3)
    raise TimeoutError(f.read_text()[-800:])
def http(port, path):
    try: return urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=2).read().decode()
    except Exception as e: return 'ERR ' + type(e).__name__
def tree(p, d=0, out_=None):
    out_ = [] if out_ is None else out_
    for k in sorted(z.get_children(p)):
        q = p.rstrip('/') + '/' + k
        if q.startswith('/zookeeper'): continue
        st = z.exists(q); out_.append(('  ' * d + k)[:80] + ('  [临时节点]' if st.ephemeralOwner else '')); tree(q, d + 1, out_)
    return out_
print('== 一:启动一个 Spring Boot 3.3.5 + Spring Cloud 2023.0.4(spring-cloud-starter-zookeeper-discovery / -config)应用 demo-svc,ZooKeeper 里出现什么')
a = app(7971); time.sleep(2)
print('\n'.join('  ' + l for l in tree('/'))); R['tree'] = tree('/')
kid = z.get_children('/services/demo-svc')[0]; d = z.get(f'/services/demo-svc/{kid}')[0].decode(); print('  /services/demo-svc/<uuid> 的数据:', d[:700]); R['inst'] = d
print('  应用自己看到的 /services:', http(7971, '/services'), '| /instances/demo-svc:', http(7971, '/instances/demo-svc'))
print()
print('== 二:再起一个实例(端口 7972),两个应用各自看到的实例列表;然后 kill -9 其中一个,另一个的 DiscoveryClient 多久把它去掉')
b = app(7972); time.sleep(3)
print('  两个应用与 ZooKeeper 之间会话的协商超时(cons 的 to=):', sorted({re.search(r'to=(\d+)', l).group(1) for l in n.four('cons').splitlines() if 'to=' in l and 'sid=0x' in l}), '(tickTime=1000 时服务端 maxSessionTimeout = 20000)')
print('  7971 看到:', http(7971, '/instances/demo-svc')); print('  7972 看到:', http(7972, '/instances/demo-svc'))
tk = time.time(); b.kill(); t_zk = t_app = None
def count(): return len(json.loads(http(7971, '/instances/demo-svc')) if not http(7971, '/instances/demo-svc').startswith('ERR') else [])
while time.time() - tk < 90 and (t_zk is None or t_app is None):
    if t_zk is None and len(z.get_children('/services/demo-svc')) == 1: t_zk = time.time() - tk
    if t_app is None and count() == 1: t_app = time.time() - tk
    time.sleep(0.2)
print(f'  kill -9 后:ZooKeeper 里的节点 {t_zk:.1f} s 后消失;7971 的 DiscoveryClient 在 {t_app:.1f} s 后只剩 1 个实例')
R['kill'] = dict(zk=t_zk, app=t_app)
print()
print('== 三:配置中心:在 ZooKeeper 里建 /config/demo-svc/demo.msg(应用启动后才建),/cfg 多久反映;再改;再建全局默认 /config/application/demo.msg 看优先级')
print('  建之前 /cfg =', http(7971, '/cfg')); z.ensure_path('/config/demo-svc'); t0 = time.time(); z.create('/config/demo-svc/demo.msg', b'v1')
def wait_val(port, v, to=30):
    t0_ = time.time()
    while time.time() - t0_ < to:
        if http(port, '/cfg') == v: return time.time() - t0_
        time.sleep(0.02)
    return None
l1 = wait_val(7971, 'v1'); print(f'  新建节点后 /cfg 变成 v1:{(l1 * 1000):.0f} ms' if l1 is not None else '  新建节点后 30 s 内 /cfg 没有变化')
t0 = time.time(); z.set('/config/demo-svc/demo.msg', b'v2'); l2 = wait_val(7971, 'v2'); print(f'  改成 v2:{(l2 * 1000):.0f} ms' if l2 is not None else '  改成 v2 后 30 s 内没有变化')
R['cfg'] = dict(create_ms=l1 * 1000 if l1 else None, set_ms=l2 * 1000 if l2 else None)
z.ensure_path('/config/application'); z.create('/config/application/demo.msg', b'GLOBAL'); time.sleep(2)
print('  应用运行中再建 /config/application/demo.msg=GLOBAL 后 /cfg =', http(7971, '/cfg'), '(不能说明优先级:这个全局目录在应用启动时并不存在,可能根本没有被监听)')
a.kill(); time.sleep(1); a = app(7971); time.sleep(1)
R['prio'] = http(7971, '/cfg'); print('  重启应用后(此时 /config/application/demo.msg=GLOBAL 与 /config/demo-svc/demo.msg=v2 同时存在)/cfg =', R['prio'], '(优先级:' + ('应用专属配置压过全局' if R['prio'] == 'v2' else '全局压过应用专属' if R['prio'] == 'GLOBAL' else '?') + ')')
print('  /config 的树:'); print('\n'.join('    ' + l for l in tree('/config')))
a.kill(); z.stop(); n.stop(); save('z106', R); os._exit(0)
