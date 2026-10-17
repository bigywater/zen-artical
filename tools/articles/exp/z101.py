import sys, os, time, json, re, subprocess, signal, urllib.parse, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z101'); R = {}
n = Node('z101', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
D = HERE.parent / 'dubbo'; J_ = ['java', '-Dfile.encoding=UTF-8', '-cp', f'{D}/lib/*:{D}']; WD = ZDATA / 'z101'; WD.mkdir(exist_ok=True)
def prov(port, name, reg=''): 
    f = WD / f'{name}.log'; f.write_text(''); p = subprocess.Popen(J_ + ['Provider', str(port), name] + ([reg] if reg else []), stdout=open(f, 'w'), stderr=subprocess.STDOUT)
    t0 = time.time()
    while 'PROVIDER_UP' not in f.read_text() and time.time() - t0 < 60: time.sleep(0.2)
    return p
def cons(reg=''):
    f = WD / 'cons.log'; f.write_text(''); p = subprocess.Popen(J_ + ['Consumer'] + ([reg] if reg else []), stdout=open(f, 'w'), stderr=subprocess.STDOUT)
    t0 = time.time()
    while 'CONSUMER_UP' not in f.read_text() and time.time() - t0 < 60: time.sleep(0.2)
    return p
def calls(since=0): return [(int(l.split()[0]) / 1000, ' '.join(l.split()[2:])) for l in (WD / 'cons.log').read_text().splitlines() if ' CALL ' in l and int(l.split()[0]) / 1000 >= since]
def tree():
    out_ = []
    def walk(p, d=0):
        for k in sorted(z.get_children(p)):
            q = p.rstrip('/') + '/' + k
            if q.startswith('/zookeeper'): continue
            st = z.exists(q); out_.append(('  ' * d + k)[:96] + ('  [临时节点]' if st.ephemeralOwner else '')); walk(q, d + 1)
    walk('/', 0); return out_
print('== 一:只启动一个 Dubbo 3.3.6 提供者(注册中心 zookeeper://127.0.0.1:7300),ZooKeeper 里出现了什么')
p1 = prov(20881, 'P1'); time.sleep(2)
t1 = tree(); print('\n'.join('  ' + l for l in t1)); R['tree1'] = t1
u = urllib.parse.unquote(z.get_children('/dubbo/Greeter/providers')[0]); print('  接口级节点名 URL 解码后:', u[:300]); R['url'] = u
print('  /services/prov-app 下实例节点的数据:', z.get('/services/prov-app/' + z.get_children('/services/prov-app')[0] + '')[0].decode()[:300])
print('  /dubbo/mapping/Greeter 的数据:', z.get('/dubbo/mapping/Greeter')[0].decode(), '(接口名 → 应用名的映射)')
print()
print('== 二:启动一个消费者:新增的节点,以及它的调用结果')
before = set(t1); c = cons(); time.sleep(3); t2 = tree(); new = [l for l in t2 if l not in before]; print('  消费者启动后新增的节点:', *[('\n    ' + l) for l in new]); R['new'] = new
cl = calls(time.time() - 2); print('  最近的调用:', [x[1] for x in cl[-3:]])
print()
print('== 三:再启动第二个提供者 P2:消费者的负载均衡(100 次调用中各提供者的次数)')
p2 = prov(20882, 'P2'); time.sleep(4); t0 = time.time(); time.sleep(20)
cnt = collections.Counter(re.search(r'from (P\d)', x[1]).group(1) for x in calls(t0) if 'from' in x[1]); print('  20 秒内的调用分布:', dict(cnt)); R['lb'] = dict(cnt)
print('  /dubbo/Greeter/providers 子节点数 =', len(z.get_children('/dubbo/Greeter/providers')))
print()
print('== 四:kill -9 其中一个提供者(P1),消费者(retries=0,不重试)的调用失败多久、多少次;注册中心 session 用默认值')
cons_line = [l for l in n.four('cons').splitlines() if 'sid=' in l]
tk = time.time(); p1.kill(); 
while time.time() - tk < 90 and len(z.get_children('/dubbo/Greeter/providers')) > 1: time.sleep(0.1)
t_rm = time.time() - tk; time.sleep(2); allc = [x for x in calls(tk) if x[0] < tk + t_rm + 1.5]; err = [x for x in allc if x[1].startswith('ERR')]
last_err = max((x[0] for x in err), default=tk) - tk
print(f'  kill -9 后 /dubbo/Greeter/providers 下的 P1 节点在 {t_rm:.1f} s 后消失(Dubbo 默认注册中心 session 60 s,服务端 maxSessionTimeout = 20 × tickTime = 20 s)')
print(f'  这期间消费者共 {len(allc)} 次调用,失败 {len(err)} 次(错误类型 {sorted(set(x[1] for x in err))[:2]})' + (f';最后一次失败在 kill 后 {last_err:.1f} s' if err else ' —— 我的推断(没有进一步验证):进程被 kill -9 时操作系统关闭了它的 TCP 连接,Dubbo 消费者据此不再向它发请求,没有等 ZooKeeper 的通知'))
R['kill_default'] = dict(removed=t_rm, calls=len(allc), err=len(err), last_err=last_err)
print('  节点移除之后的 5 秒内失败次数:', sum(1 for x in calls(tk + t_rm + 1) if x[1].startswith('ERR')))
p2.kill(); c.kill(); time.sleep(3)
print()
print('== 五:注册中心 URL 加 ?session=3000(提供者与消费者都配置),同样 kill -9 P1,重复 3 次(P2 与消费者一直在运行)')
p2 = prov(20882, 'P2', 'session=3000'); c = cons('session=3000'); trials = []
for k in range(3):
    p1 = prov(20881, 'P1', 'session=3000'); time.sleep(5); tk = time.time(); p1.kill()
    while time.time() - tk < 60 and len(z.get_children('/dubbo/Greeter/providers')) > 1: time.sleep(0.05)
    t_rm = time.time() - tk; time.sleep(2); allc = [x for x in calls(tk) if x[0] < tk + t_rm + 1.5]; err = [x for x in allc if x[1].startswith('ERR')]
    trials.append((t_rm, len(allc), len(err))); print(f'  第 {k + 1} 次:P1 节点在 {t_rm:.1f} s 后消失;期间调用 {len(allc)} 次,失败 {len(err)} 次')
R['kill_s3'] = dict(removed=[round(t[0], 1) for t in trials], calls=[t[1] for t in trials], err=[t[2] for t in trials])
print()
print('== 五(续):提供者进程被冻结(SIGSTOP:进程在、TCP 连接保持、但不再响应,也不再向 ZooKeeper 发心跳),session=3000')
p1 = prov(20881, 'P1', 'session=3000'); time.sleep(5); tk = time.time(); p1.send_signal(signal.SIGSTOP)
while time.time() - tk < 60 and len(z.get_children('/dubbo/Greeter/providers')) > 1: time.sleep(0.05)
t_rm = time.time() - tk; time.sleep(2); allc = [x for x in calls(tk) if x[0] < tk + t_rm + 1.5]; err = [x for x in allc if x[1].startswith('ERR')]
print(f'  冻结后 P1 的节点在 {t_rm:.1f} s 后消失;期间消费者调用 {len(allc)} 次,失败 {len(err)} 次(错误类型 {sorted(set(x[1] for x in err))[:2]})')
la = max((x[0] for x in err), default=tk) - tk; print(f'  最后一次失败在冻结后 {la:.1f} s;节点消失之后 3 秒内失败 {sum(1 for x in calls(tk + t_rm) if x[1].startswith("ERR") and x[0] < tk + t_rm + 3)} 次')
R['freeze'] = dict(removed=t_rm, calls=len(allc), err=len(err), last_err=la)
p1.send_signal(signal.SIGCONT); p1.kill()
print()
print('== 六:SIGTERM 正常退出(Dubbo 的 shutdown hook 会先注销):P2 被 SIGTERM,看节点消失时间与失败调用')
p1 = prov(20881, 'P1', 'session=3000'); time.sleep(5); tk = time.time(); p2.send_signal(signal.SIGTERM)
while time.time() - tk < 30 and len(z.get_children('/dubbo/Greeter/providers')) > 1: time.sleep(0.02)
t_rm = time.time() - tk; time.sleep(2); allc = [x for x in calls(tk) if x[0] < tk + 4]; err = [x for x in allc if x[1].startswith('ERR')]
print(f'  SIGTERM 后 P2 的节点 {t_rm:.2f} s 消失;SIGTERM 后 4 秒内消费者调用 {len(allc)} 次,失败 {len(err)} 次')
R['term'] = dict(removed=t_rm, calls=len(allc), err=len(err))
for x in (p1, p2, c):
    try: x.kill()
    except Exception: pass
z.stop(); n.stop(); save('z101', R); os._exit(0)
