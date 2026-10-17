import sys, os, re, struct, collections, threading, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w42'); reset()
FL = [(0x20, 'URG'), (0x10, 'ACK'), (0x08, 'PSH'), (0x04, 'RST'), (0x02, 'SYN'), (0x01, 'FIN')]
def flags(f): return '+'.join(n for b, n in FL if f & b) or '无'
def tcps(path):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:])
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:tl_]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, plen=len(t) - (off >> 4) * 4))
    return out
def trace(fn):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(); port = ls.getsockname()[1]
    with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
        r = fn(ls, port); time.sleep(0.4)
    return tcps(c.pcap), port, r
def E(e): return f'{type(e).__name__}[Errno {e.errno}] {e.strerror}'
def row(P, port, skip_syn=False):
    base = {}
    for p in P:
        d = 'C' if p['dp'] == port else 'S'
        base.setdefault(d, p['seq'])
    return [f'{"客户端" if p["dp"] == port else "服务端"}:{flags(p["fl"])} seq={p["seq"] - base.get("C" if p["dp"] == port else "S", 0)} ack={p["ack"] - base.get("S" if p["dp"] == port else "C", 0) if p["fl"] & 0x10 else 0}' + (f' 载荷{p["plen"]}' if p['plen'] else '') for p in P]

print('== 一:RST 的第一种来源:连接没人监听的端口。看 RST 包的序号 / 确认号怎么填,以及应用得到的错误码')
ls0 = socket.socket(); ls0.bind(('127.0.0.1', 0)); closed = ls0.getsockname()[1]; ls0.close()
with Cap(f'tcp port {closed}', iface='lo0', write=True) as c:
    k = socket.socket()
    try: k.connect(('127.0.0.1', closed)); r = '连上了'
    except OSError as e: r = E(e)
    time.sleep(0.3)
P = tcps(c.pcap); syn = P[0]; rst = P[1]
print(f'  connect 一个没人监听的端口:{r}')
print(f'  SYN:seq={syn["seq"]};回来的包:标志 {flags(rst["fl"])},seq={rst["seq"]},ack={rst["ack"]} = SYN 的 seq + 1:{rst["ack"] == syn["seq"] + 1}——规则:对一个没有连接的 SYN,RST 的序号取 0、确认号取 SYN 序号 + 1(因为 SYN 占一个序号)')

print('== 二:连接已经不存在时再发数据:对端正常 close 了(发了 FIN),我们这边不知道又发数据,对端的 TCP 回 RST;应用依次看到什么')
def f2(ls, port):
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); cn.close(); time.sleep(0.2)
    res = []
    for i in range(3):
        try: k.send(b'x' * 100); res.append(f'send #{i + 1} 成功')
        except OSError as e: res.append(f'send #{i + 1} {E(e)}')
        time.sleep(0.2)
    try: res.append(f'recv → {k.recv(10)!r}')
    except OSError as e: res.append(f'recv {E(e)}')
    return res
P, port, res = trace(f2)
print('  应用依次看到:' + ';'.join(res))
print('  线上:' + ' → '.join(row(P, port)[2:]))
data = [p for p in P if p['plen'] and p['dp'] == port]; rs = [p for p in P if p['fl'] & 4]
if data and rs: print(f'  RST 的序号 {rs[0]["seq"]} = 触发它的数据包的确认号 {data[0]["ack"]}:{rs[0]["seq"] == data[0]["ack"]}——规则:对一个带 ACK 的段,RST 的序号取该段的确认号,这样发送方才会接受它(落在期望序号上)')

print('== 三:RST 会丢数据:服务端先发 5 字节再用 SO_LINGER 0 中止连接。客户端过一会儿 recv,拿到的是数据还是错误')
def f3(ls, port):
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); cn.sendall(b'hello'); time.sleep(0.1); cn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); cn.close(); time.sleep(0.2)
    res = []
    for i in range(2):
        try: res.append(f'recv #{i + 1} → {k.recv(100)!r}')
        except OSError as e: res.append(f'recv #{i + 1} {E(e)}')
    return res
P, port, res = trace(f3)
print('  服务端发了 hello 再中止;客户端(RST 到达之后)依次:' + ';'.join(res))
print('  线上:' + ' → '.join(row(P, port)[2:]))
def f3b(ls, port):
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); cn.sendall(b'hello'); time.sleep(0.1); cn.close(); time.sleep(0.2)
    res = []
    for i in range(2):
        try: res.append(f'recv #{i + 1} → {k.recv(100)!r}')
        except OSError as e: res.append(f'recv #{i + 1} {E(e)}')
    return res
P, port, res = trace(f3b)
print('  对照:服务端发了 hello 再正常 close(FIN);客户端依次:' + ';'.join(res))

print('== 四:连接建立后对端进程“消失”:应用侧的各种错误码,一次列清——ECONNREFUSED、ECONNRESET、EPIPE、ETIMEDOUT 分别在什么时候出现')
tab = []
# ECONNREFUSED
k = socket.socket()
try: k.connect(('127.0.0.1', closed))
except OSError as e: tab.append(('连接没人监听的端口', 'connect', E(e)))
# ECONNRESET on recv (peer abort)
ls = socket.socket(); ls.bind(('127.0.0.1', 0)); ls.listen(); p_ = ls.getsockname()[1]
k = socket.create_connection(('127.0.0.1', p_)); cn, _ = ls.accept(); cn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); cn.close(); time.sleep(0.2)
try: k.recv(10)
except OSError as e: tab.append(('对端 RST 中止后', 'recv', E(e)))
try: k.send(b'x')
except OSError as e: tab.append(('对端 RST 中止后', 'send', E(e)))
# EPIPE after FIN + RST
k = socket.create_connection(('127.0.0.1', p_)); cn, _ = ls.accept(); cn.close(); time.sleep(0.2)
k.send(b'a'); time.sleep(0.2)
try: k.send(b'b')
except OSError as e: tab.append(('对端 close 后我方第二次 send', 'send', E(e)))
# ETIMEDOUT / EHOSTUNREACH via netlab? skip; use connect timeout
k = socket.socket(); k.settimeout(2)
try: k.connect(('104.20.23.154', 81))
except OSError as e: tab.append(('SYN 无回应(设了 2 秒超时)', 'connect', E(e)))
for a, b, c_ in tab: print(f'    {a:<28}{b:<9}→ {c_}')
print('  ECONNREFUSED = 对 SYN 回了 RST;ECONNRESET = 连接已建立后收到 RST;EPIPE = 向已经收到 RST / FIN 的连接再写(默认还会给进程发 SIGPIPE,Python 屏蔽了它);ETIMEDOUT / 超时 = 对方没有任何回应')
