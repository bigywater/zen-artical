import sys, os, re, struct, collections, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w40'); reset()

def sample(port):
    """netstat 里和这个端口有关的 TCP 套接字 → {'server': 状态, 'client': 状态, 'listen': ...}"""
    out = {}
    for l in sysout('netstat', '-an', '-p', 'tcp').splitlines():
        p = l.split()
        if len(p) < 6 or not p[0].startswith('tcp4'): continue
        la, fa, st = p[3], p[4], p[5]
        if la.endswith(f'.{port}'):
            out['listen' if st == 'LISTEN' else 'server'] = st
        elif fa.endswith(f'.{port}'): out['client'] = st
    return out
def timeline(port, stop, t0, log, step=0.02):
    last = {}
    while not stop.is_set():
        s_ = sample(port)
        for k_ in set(list(s_) + list(last)):
            v = s_.get(k_, '(无)')
            if last.get(k_) != v: log.append((time.time() - t0, k_, v)); last[k_] = v
        time.sleep(step)
def show(log, names):
    seq = {k_: [] for k_ in names}
    for t, k_, v in log:
        if k_ in seq and (not seq[k_] or seq[k_][-1][1] != v): seq[k_].append((t, v))
    for k_, nm in names.items():
        print(f'    {nm}:' + ' → '.join(f'{v}({t * 1000:.0f} ms)' for t, v in seq[k_]))
    return seq

DELAY = 150
def scenario(title, body, names, delay=DELAY):
    p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen()
    log = []; stop = threading.Event()
    with lossy(loss=0, delay=delay, bw=0):
        t0 = time.time(); th = threading.Thread(target=timeline, args=(p, stop, t0, log)); th.start()
        try: body(ls, p, t0)
        finally:
            time.sleep(0.2); stop.set(); th.join()
    ls.close()
    print(f'  {title}(单向延迟 {delay} ms,往返 {2 * delay} ms;括号里是相对 connect 的时间):')
    return show(log, names)

print('== 一:用 netlab 给回环加 150 ms 单向延迟,把每一步拖慢到 netstat 能抓到,逐个观察 TCP 的 11 个状态(CLOSED 就是 netstat 里没有这一行)')
def b1(ls, p, t0):
    time.sleep(0.1); k = socket.create_connection(('127.0.0.1', p)); cn, _ = ls.accept(); time.sleep(0.5)
    k.close()                      # 客户端先关
    time.sleep(1.0)                # 服务端过了一会儿才关 → 客户端在 FIN_WAIT_2 停留、服务端在 CLOSE_WAIT 停留
    cn.close(); time.sleep(0.8)
s1 = scenario('场景 1:握手、数据、客户端先 close、服务端晚一秒才 close', b1, {'client': '客户端', 'server': '服务端', 'listen': '监听套接字'})
seen1 = collections.Counter(v for t, k_, v in sum(([(t, k_, v) for t, v in s1[k_]] for k_ in s1), []))
print('  这个场景里见到的状态:' + '、'.join(sorted(v for v in seen1 if v != '(无)')))

def b2(ls, p, t0):
    time.sleep(0.1); k = socket.socket(); k.connect(('127.0.0.1', p)); cn, _ = ls.accept(); k.close(); cn.close(); time.sleep(1.5)
s2 = scenario('场景 2:客户端 connect 之后立刻 close,服务端也立刻 close(看 LAST_ACK)', b2, {'client': '客户端', 'server': '服务端'})

def b3(ls, p, t0):
    time.sleep(0.1); k = socket.create_connection(('127.0.0.1', p)); cn, _ = ls.accept(); time.sleep(0.5); b = threading.Barrier(2)
    def cl(s): b.wait(); s.close()
    t1 = threading.Thread(target=cl, args=(k,)); t2 = threading.Thread(target=cl, args=(cn,)); t1.start(); t2.start(); t1.join(); t2.join(); time.sleep(1.2)
s3 = scenario('场景 3:两端同时 close(看 CLOSING)', b3, {'client': '一端', 'server': '另一端'})

print('== 二:状态总表:11 个状态各自在什么时候出现、在 netstat 里怎么看;本机里这 11 个状态里见到了哪些')
ALL = ['CLOSED', 'LISTEN', 'SYN_SENT', 'SYN_RCVD', 'ESTABLISHED', 'FIN_WAIT_1', 'FIN_WAIT_2', 'CLOSE_WAIT', 'CLOSING', 'LAST_ACK', 'TIME_WAIT']
seen = set()
for s_ in (s1, s2, s3):
    for k_, L in s_.items():
        for t, v in L: seen.add(v)
seen.add('LISTEN') if 'listen' in s1 and s1['listen'] else None
WHEN = {'CLOSED': '没有连接(netstat 里没有这一行)', 'LISTEN': '服务端 listen() 之后', 'SYN_SENT': '客户端发出 SYN、等 SYN-ACK', 'SYN_RCVD': '服务端收到 SYN、发出 SYN-ACK、等第三个 ACK', 'ESTABLISHED': '三次握手完成,数据传输阶段', 'FIN_WAIT_1': '主动关闭方发出 FIN、等对方的 ACK', 'FIN_WAIT_2': '主动关闭方的 FIN 已被 ACK,等对方的 FIN', 'CLOSE_WAIT': '被动关闭方收到 FIN、已 ACK,等本端应用 close()', 'CLOSING': '两端同时关闭:发出 FIN 后先收到对方的 FIN', 'LAST_ACK': '被动关闭方发出 FIN、等最后的 ACK', 'TIME_WAIT': '主动关闭方收到对方的 FIN 并回了 ACK,等 2MSL'}
for st in ALL: print(f'    {st:<12}{"本次观察到" if st in seen or st == "CLOSED" else "没抓到":<6} {WHEN[st]}')
print(f'  三个场景里 netstat 抓到了 {len(seen & set(ALL))} 个状态({"、".join(s for s in ALL if s in seen)});CLOSED 本来就是“没有这一行”,算上它是 {len((seen & set(ALL)) | {"CLOSED"})} / 11')

print('== 三:SYN_SENT 与 SYN_RCVD:SYN_SENT 能用一个会丢弃 SYN 的公网地址轻松看到;SYN_RCVD 要靠延迟。服务端收到 SYN 到收到第三个 ACK 之间就是 SYN_RCVD')
k = socket.socket(); k.setblocking(False); k.connect_ex(('104.20.23.154', 81)); time.sleep(0.5)
st = [l.split()[5] for l in sysout('netstat', '-an', '-p', 'tcp').splitlines() if len(l.split()) >= 6 and l.split()[4].startswith('104.20.23.154.81')]
print(f'  非阻塞 connect 到一个丢弃 SYN 的地址,0.5 秒后 netstat 看到的状态:{st}'); k.close()
def b4(ls, p, t0):
    time.sleep(0.1); k = socket.socket(); k.setblocking(False); k.connect_ex(('127.0.0.1', p)); time.sleep(0.7); k.close(); time.sleep(0.5)
s4 = scenario('场景 4:非阻塞 connect,服务端不 accept(accept 与状态无关,握手由内核完成)', b4, {'client': '客户端', 'server': '服务端'})
print('  服务端内核在回了 SYN-ACK 之后到收到客户端第三个 ACK 之前处于 SYN_RCVD;只要握手完成就是 ESTABLISHED——应用有没有调用 accept() 不影响状态,没被 accept 的连接排在全连接队列里(见 backlog 一篇)')
