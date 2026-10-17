import sys, os, re, struct, threading, statistics, errno, selectors; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w59'); reset()
RA, RP = socket.SO_REUSEADDR, socket.SO_REUSEPORT
def E(r): return errno.errorcode.get(r, r)
def mk(opts=(), addr='127.0.0.1', port=0, listen=True, typ=socket.SOCK_STREAM):
    s = socket.socket(socket.AF_INET, typ)
    for o in opts: s.setsockopt(socket.SOL_SOCKET, o, 1)
    s.bind((addr, port))
    if listen and typ == socket.SOCK_STREAM: s.listen()
    return s
def try_bind(opts_a, opts_b, addr_a='127.0.0.1', addr_b='127.0.0.1', listen_a=True, typ=socket.SOCK_STREAM):
    a = mk(opts_a, addr_a, lab_port(), listen_a, typ); port = a.getsockname()[1]
    try:
        b = mk(opts_b, addr_b, port, False, typ); b.close(); r = '成功'
    except OSError as e: r = E(e.errno)
    a.close(); return r
N = lambda o: '+'.join({RA: 'REUSEADDR', RP: 'REUSEPORT'}[x] for x in o) or '都不设'

print('== 一:同一个地址端口能不能被两个套接字 bind。第一个已经 listen;选项在两个套接字上都设置(都不设 / 只 REUSEADDR / 只 REUSEPORT / 两个都设)')
for opts in ((), (RA,), (RP,), (RA, RP)):
    print(f'  两边都设 {N(opts):<20}:第二个 bind 同一个 127.0.0.1:P → {try_bind(opts, opts)}')
print('  只有一边设:')
print(f'  第一个设 REUSEPORT、第二个不设 → {try_bind((RP,), ())};第一个不设、第二个设 REUSEPORT → {try_bind((), (RP,))}')
print(f'  第一个设 REUSEADDR、第二个不设 → {try_bind((RA,), ())};第一个不设、第二个设 REUSEADDR → {try_bind((), (RA,))}')

print('== 二:REUSEADDR 的经典用途:服务端重启时绕过 TIME_WAIT。让服务端先 close,留下 TIME_WAIT,再 bind 同一个端口')
def tw_test(opts):
    ls = mk(opts, '127.0.0.1', lab_port()); port = ls.getsockname()[1]
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); k.sendall(b'x'); cn.recv(10)
    cn.close(); time.sleep(0.2); k.recv(10); k.close(); ls.close(); time.sleep(0.2)
    st = [x[5] for x in [l.split() for l in sysout('netstat', '-an', '-p', 'tcp').splitlines() if f'127.0.0.1.{port} ' in l] if len(x) >= 6]
    try: n = mk(opts, '127.0.0.1', port); r = '成功'; n.close()
    except OSError as e: r = E(e.errno)
    return st, r
for opts in ((), (RA,), (RP,)):
    st, r = tw_test(opts); print(f'  重新 bind 时设 {N(opts):<12}:netstat 里这个端口的状态 {st};新套接字 bind + listen → {r}')

print('== 三:通配地址与具体地址:一个绑 0.0.0.0:P,另一个绑 127.0.0.1:P')
for nm, a, b, oa, ob in (('先 0.0.0.0 后 127.0.0.1,都不设', '0.0.0.0', '127.0.0.1', (), ()), ('先 0.0.0.0 后 127.0.0.1,都设 REUSEADDR', '0.0.0.0', '127.0.0.1', (RA,), (RA,)), ('先 127.0.0.1 后 0.0.0.0,都设 REUSEADDR', '127.0.0.1', '0.0.0.0', (RA,), (RA,)), ('先 0.0.0.0 后 127.0.0.1,都设 REUSEPORT', '0.0.0.0', '127.0.0.1', (RP,), (RP,))):
    print(f'  {nm:<40}→ {try_bind(oa, ob, a, b)}')
w = mk((RA,), '0.0.0.0', lab_port()); port = w.getsockname()[1]; sp = mk((RA,), '127.0.0.1', port)
got = {'通配 0.0.0.0': 0, '具体 127.0.0.1': 0}; sel = selectors.DefaultSelector(); sel.register(w, selectors.EVENT_READ, '通配 0.0.0.0'); sel.register(sp, selectors.EVENT_READ, '具体 127.0.0.1')
for i in range(100):
    k = socket.create_connection(('127.0.0.1', port))
    for key, _ in sel.select(1): key.fileobj.accept()[0].close(); got[key.data] += 1
    k.close()
print(f'  两个都设 REUSEADDR 时,连 127.0.0.1:P 100 次,被谁接走:{got}(具体地址优先于通配)'); w.close(); sp.close()

print('== 四:REUSEPORT 的负载均衡:4 个监听套接字同绑 127.0.0.1:P,发起 400 个连接,看每个监听者收到几个')
ls_ = [mk((RP,), '127.0.0.1', 0 if i == 0 else port) if False else None for i in range(0)]
port = lab_port(); ls_ = [mk((RP,), '127.0.0.1', port) for i in range(4)]; sel = selectors.DefaultSelector()
for i, s in enumerate(ls_): sel.register(s, selectors.EVENT_READ, i)
cnt = [0] * 4; ks = []
for i in range(400):
    ks.append(socket.create_connection(('127.0.0.1', port)))
    for key, _ in sel.select(1): key.fileobj.accept()[0].close(); cnt[key.data] += 1
for k in ks: k.close()
print(f'  4 个监听者各 accept 到:{cnt}(合计 {sum(cnt)})')
for s in ls_: s.close()

print('== 五:UDP 单播 + REUSEPORT:3 个 UDP 套接字同绑 127.0.0.1:P,一个发送方发 300 个数据报,看各收到几个')
port = lab_port(); us = [mk((RP,), '127.0.0.1', port, False, socket.SOCK_DGRAM) for _ in range(3)]
for u in us: u.setblocking(False)
snd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for i in range(300): snd.sendto(b'd', ('127.0.0.1', port))
time.sleep(0.3); c_ = []
for u in us:
    n = 0
    try:
        while True: u.recv(10); n += 1
    except BlockingIOError: pass
    c_.append(n)
print(f'  3 个 UDP 套接字各收到:{c_}(合计 {sum(c_)}/300)')
snd2 = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(30)]
for s in snd2:
    for i in range(10): s.sendto(b'd', ('127.0.0.1', port))
time.sleep(0.3); c2 = []
for u in us:
    n = 0
    try:
        while True: u.recv(10); n += 1
    except BlockingIOError: pass
    c2.append(n)
print(f'  换成 30 个不同源端口的发送方、各发 10 个(共 300):各收到 {c2}(合计 {sum(c2)}/300)')
for u in us: u.close()

print('== 六:UDP 多播:3 个套接字同绑一个 UDP 端口并加入同一个多播组(239.1.2.3),本机发 10 个多播包,看几个 bind 成功、各收到几个。三种设置:只 REUSEADDR 绑 0.0.0.0、REUSEADDR+REUSEPORT 绑 0.0.0.0、只 REUSEADDR 绑多播组地址本身')
grp = '239.1.2.3'
def udp_port():
    while True:
        p_ = lab_port(); t_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: t_.bind(('0.0.0.0', p_)); t_.close(); return p_
        except OSError: t_.close()
for nm, opts, addr in (('只 REUSEADDR,绑 0.0.0.0', (RA,), '0.0.0.0'), ('REUSEADDR+REUSEPORT,绑 0.0.0.0', (RA, RP), '0.0.0.0'), ('只 REUSEADDR,绑多播组地址', (RA,), grp)):
    port = udp_port(); us = []; rs = []
    for i in range(3):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for o in opts: s.setsockopt(socket.SOL_SOCKET, o, 1)
        try: s.bind((addr, port))
        except OSError as e: rs.append(E(e.errno)); s.close(); continue
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(grp) + socket.inet_aton('127.0.0.1')); s.setblocking(False); us.append(s); rs.append('成功')
    snd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); snd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton('127.0.0.1')); snd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    for i in range(10): snd.sendto(b'm', (grp, port))
    time.sleep(0.3); c3 = []
    for u in us:
        n = 0
        try:
            while True: u.recv(10); n += 1
        except BlockingIOError: pass
        c3.append(n)
    print(f'  {nm:<32}:3 次 bind → {rs};已绑定的套接字各收到 {c3}(共发 10 个)')
    for u in us: u.close()
    snd.close()
