import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w58'); reset()
def pkts(path, lo, hi):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:])
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, plen=tl_ - ihl - (off >> 4) * 4))
    return out
FLN = {0x02: 'SYN', 0x12: 'SYN+ACK', 0x10: 'ACK', 0x18: 'PSH+ACK', 0x11: 'FIN+ACK', 0x04: 'RST', 0x14: 'RST+ACK'}
def dedup(P):
    seen = set(); out = []
    for p in P:
        key = (p['sp'], p['dp'], p['seq'], p['fl'], p['plen'])
        if key in seen: continue
        seen.add(key); out.append(p)
    return out
def states(*ports):
    txt = sysout('netstat', '-an', '-p', 'tcp'); res = []
    for ln in txt.splitlines():
        f = ln.split()
        if len(f) >= 6 and f[0].startswith('tcp') and any(f'127.0.0.1.{p}' in f[3] or f'127.0.0.1.{p}' in f[4] for p in ports): res.append((f[3].split('.')[-1], f[4].split('.')[-1], f[5]))
    return res

print('== 一:自连接:一个套接字 bind 到端口 P,再 connect 到它自己的地址(127.0.0.1:P),没有任何监听者。按 TCP 规范这能成功(同时打开的特例:SYN 发给自己,自己当作对端的 SYN 收下)。在 macOS 上试四种写法,同时抓包看有没有 SYN 发出')
def self_try(nm, mk):
    P0 = lab_port(); k = mk(P0)
    with Cap(f'tcp port {P0}', iface='lo0', write=True, snaplen=96) as c:
        k.settimeout(3); err = k.connect_ex(('127.0.0.1', P0)); time.sleep(0.3)
    Pk = pkts(c.pcap, 0, 0); k.close()
    print(f'  {nm:<34}:connect_ex = {errno.errorcode.get(err, err)};线上抓到的 TCP 包 {len(Pk)} 个')
def mk_plain(P0):
    k = socket.socket(); k.bind(('127.0.0.1', P0)); return k
def mk_reuse(P0):
    k = socket.socket(); k.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); k.bind(('127.0.0.1', P0)); return k
def mk_any(P0):
    k = socket.socket(); k.bind(('0.0.0.0', P0)); return k
def mk_reuseport(P0):
    k = socket.socket(); k.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1); k.bind(('127.0.0.1', P0)); return k
for nm, mk in (('bind 127.0.0.1:P 再 connect 自己', mk_plain), ('加 SO_REUSEADDR', mk_reuse), ('加 SO_REUSEPORT', mk_reuseport), ('bind 0.0.0.0:P 再 connect 127.0.0.1:P', mk_any)): self_try(nm, mk)
print('  四种写法 macOS 都直接返回 EINVAL,没有发出任何 SYN:内核在 connect 里就拒绝了“源地址端口 = 目的地址端口”的自连接')

print('== 二:同时打开:两个套接字各 bind 一个固定端口,在同一时刻互相 connect。lo0 用 netlab 加每方向 150 ms 延迟,让两个 SYN 在路上交叉。抓包并看中途的状态')
def simul(delay):
    a = socket.socket(); b = socket.socket(); pa = lab_port(); a.bind(('127.0.0.1', pa)); pb = lab_port(); b.bind(('127.0.0.1', pb))
    bar = threading.Barrier(2); res = {}
    def go(nm, s, peer):
        s.settimeout(8); bar.wait(); t0 = time.time()
        try: s.connect(('127.0.0.1', peer)); res[nm] = (0, time.time() - t0)
        except OSError as e: res[nm] = (e.errno, time.time() - t0)
    ta = threading.Thread(target=go, args=('a', a, pb)); tb = threading.Thread(target=go, args=('b', b, pa)); ta.start(); tb.start()
    mid = None
    if delay >= 100: time.sleep(delay / 1000 * 1.2); mid = states(pa, pb)
    ta.join(); tb.join(); time.sleep(0.2)
    return a, b, pa, pb, res, mid
with lossy(loss=0, delay=150, bw=0):
    with Cap('tcp portrange 9400-9499', iface='lo0', write=True, snaplen=96) as c:
        a, b, pa, pb, res, mid = simul(150); time.sleep(0.3)
    print(f'  两个 connect 的结果:a → {res["a"][0]}({res["a"][1] * 1000:.0f} ms),b → {res["b"][0]}({res["b"][1] * 1000:.0f} ms)(0 = 成功)')
    print(f'  中途(约 180 ms 时)netstat 里的状态:{mid}')
    Pk = [p for p in dedup(pkts(c.pcap, 0, 0)) if {p['sp'], p['dp']} == {pa, pb}]; t0 = Pk[0]['ts']
    print('  线上的包(去重,端口 A 与 B):')
    for p in Pk: print(f'    +{(p["ts"] - t0) * 1000:7.1f} ms  {"A" if p["sp"] == pa else "B"}→{"B" if p["sp"] == pa else "A"}  {FLN.get(p["fl"], hex(p["fl"])):<8} 载荷 {p["plen"]} 字节')
    try: a.sendall(b'from a'); b.settimeout(2); print(f'  连上之后 a 发的数据,b 收到:{b.recv(20)!r}')
    except OSError as e: print(f'  连上之后收发出错:{e}')
a.close(); b.close()

print('== 三:同时打开成功的条件:两个 connect 必须几乎同时发出。无延迟(lo0 本身)重复 20 次,多少次成功?加 150 ms 延迟又是多少?')
def trial(delay):
    a, b, pa, pb, res, _ = simul(delay if delay < 100 else 0)
    ok = res['a'][0] == 0 and res['b'][0] == 0; a.close(); b.close(); return ok, (res['a'][0], res['b'][0])
for dl in (0, 150):
    oks = []; errs = []
    if dl:
        with lossy(loss=0, delay=dl, bw=0):
            for i in range(20):
                ok, e = trial(0); oks.append(ok); errs.append(e)
    else:
        for i in range(20):
            ok, e = trial(0); oks.append(ok); errs.append(e)
    from collections import Counter
    print(f'  延迟 {dl} ms:20 次里两端都连上 {sum(oks)} 次;失败时的 (a, b) 错误码:{dict(Counter(e for ok, e in zip(oks, errs) if not ok))}(61 = ECONNREFUSED)')

print('== 四:自连接是怎么“意外”发生的:客户端不 bind,connect 到本机一个没人监听、又落在临时端口范围里的端口,内核给客户端挑的源端口恰好等于目标端口,就会自连接(在允许自连接的系统上)。先看范围,再做 60000 次,看 macOS 怎么处理')
print('  ' + sysout('sysctl', 'net.inet.ip.portrange.first').strip() + ';' + sysout('sysctl', 'net.inet.ip.portrange.last').strip())
first = int(sysout('sysctl', '-n', 'net.inet.ip.portrange.first')); last = int(sysout('sysctl', '-n', 'net.inet.ip.portrange.last'))
target = (first + last) // 2; hits = 0; res4 = {}; einval_ports = []; t0 = time.time(); N = 60000
for i in range(N):
    s = socket.socket()
    try: s.connect(('127.0.0.1', target)); hits += 1
    except OSError as e:
        res4[errno.errorcode.get(e.errno, e.errno)] = res4.get(errno.errorcode.get(e.errno, e.errno), 0) + 1
        if e.errno == errno.EINVAL:
            try: einval_ports.append(s.getsockname()[1])
            except OSError: einval_ports.append(None)
    finally: s.close()
print(f'  目标端口 {target}(临时端口范围 {first}–{last},共 {last - first + 1} 个端口):{N} 次 connect,结果 {res4},成功(自连接){hits} 次;用时 {time.time() - t0:.1f} 秒')
print(f'  EINVAL 的那几次,内核挑的源端口分别是 {einval_ports}(目标端口 {target});每次的理论概率约 1/{last - first + 1},{N} 次的期望值 {N / (last - first + 1):.1f} 次')
