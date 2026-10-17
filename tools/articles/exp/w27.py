import sys, os, re, struct, collections, ipaddress, asyncio, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w27'); reset()
IFI = socket.if_nametoindex('en0')
GHOST = ('fe80::dead:beef:7:1234', 80, 0, IFI)

print('== 一:双栈套接字:监听 :: 的服务端能同时收 IPv6 和 IPv4 连接(IPv4 客户端的地址显示成 ::ffff:a.b.c.d),IPV6_V6ONLY=1 时就只收 IPv6')
print('  ' + sysout('sysctl', 'net.inet6.ip6.v6only').strip() + '(0 = 默认双栈)')
for v6only in (0, 1):
    sv = socket.socket(socket.AF_INET6); sv.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, v6only); sv.bind(('::', 0)); sv.listen(); p = sv.getsockname()[1]; sv.settimeout(1)
    peers = []; res = []
    for fam, addr in ((socket.AF_INET6, '::1'), (socket.AF_INET, '127.0.0.1')):
        c = socket.socket(fam); c.settimeout(1)
        try: c.connect((addr, p)); cn, pa = sv.accept(); peers.append((addr, pa[0])); cn.close(); res.append(f'连 {addr} 成功,服务端看到的对端地址是 {pa[0]}')
        except Exception as e: res.append(f'连 {addr} 失败:{type(e).__name__}: {getattr(e, "strerror", e)}')
        c.close()
    print(f'  IPV6_V6ONLY={v6only}:' + ';'.join(res))
print(f'  IPv4 映射地址:::ffff:127.0.0.1 → Python 的 .ipv4_mapped = {ipaddress.IPv6Address("::ffff:127.0.0.1").ipv4_mapped};一个 AF_INET6 的监听套接字因此可以同时服务两种协议')

print('== 二:getaddrinfo 返回的顺序(应用按这个顺序一个个尝试):localhost')
for nm in ('localhost',):
    for flags, fn in ((0, '默认'), (socket.AI_ADDRCONFIG, 'AI_ADDRCONFIG')):
        r = socket.getaddrinfo(nm, 80, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, flags)
        print(f'  getaddrinfo("{nm}") {fn}:' + ' → '.join(('IPv6 ' if x[0] == socket.AF_INET6 else 'IPv4 ') + x[4][0] for x in r))
print('  按 RFC 6724 的默认策略,IPv6 优先;所以连 localhost 时应用先试 ::1,失败(被拒绝)再试 127.0.0.1')

print('== 三:IPv6 一端很慢时的代价:IPv6 监听在 netlab 作用的端口(每个方向加 400 ms 延迟,一次 SYN/SYN-ACK 往返约 800 ms),IPv4 监听在不受影响的端口;顺序回退 vs Happy Eyeballs(IPv4 比 IPv6 晚 250 ms 发起)')
def he_connect(targets, delay, timeout=5):
    """targets: [(family, sockaddr)]。每隔 delay 秒再发起下一个;返回 (第一个成功的下标, 耗时)"""
    t0 = time.time(); ev = threading.Event(); win = []; socks = []; lock = threading.Lock()
    def attempt(i, fam, sa, wait):
        if wait: 
            if ev.wait(wait): return
        s = socket.socket(fam); s.settimeout(timeout); socks.append(s)
        try:
            s.connect(sa)
            with lock:
                if not win: win.append((i, time.time() - t0)); ev.set()
        except Exception: pass
    ths = [threading.Thread(target=attempt, args=(i, f, sa, i * delay), daemon=True) for i, (f, sa) in enumerate(targets)]
    for t in ths: t.start()
    ev.wait(timeout)
    for s in socks:
        try: s.close()
        except Exception: pass
    return win[0] if win else (None, time.time() - t0)
def seq_connect(targets, timeout=5):
    t0 = time.time()
    for i, (f, sa) in enumerate(targets):
        s = socket.socket(f); s.settimeout(timeout)
        try: s.connect(sa); s.close(); return i, time.time() - t0
        except Exception: s.close()
    return None, time.time() - t0
p6 = lab_port(); l6 = socket.socket(socket.AF_INET6); l6.bind(('::1', p6)); l6.listen(50)
l4 = socket.socket(); l4.bind(('127.0.0.1', 0)); l4.listen(50); p4 = l4.getsockname()[1]
T = [(socket.AF_INET6, ('::1', p6)), (socket.AF_INET, ('127.0.0.1', p4))]
r0 = [seq_connect(T)[1] for _ in range(5)]; h0 = [he_connect(T, 0.25) for _ in range(5)]
print(f'  没有延迟时(基线):顺序连接(IPv6 先)用时中位 {statistics.median(r0) * 1000:.2f} ms;Happy Eyeballs 用时中位 {statistics.median(x[1] for x in h0) * 1000:.2f} ms,5 次里 IPv6 赢了 {sum(1 for x in h0 if x[0] == 0)} 次')
with lossy(loss=0, delay=400, bw=0):
    rs = [seq_connect(T) for _ in range(5)]; rh = [he_connect(T, 0.25) for _ in range(5)]
print(f'  IPv6 加了 400 ms 单向延迟:顺序连接(IPv6 先,等它连上才算):用时中位 {statistics.median(x[1] for x in rs) * 1000:.0f} ms,每次最终连上的是{"IPv6" if rs[0][0] == 0 else "IPv4"}')
print(f'  Happy Eyeballs(250 ms 后启动 IPv4):用时中位 {statistics.median(x[1] for x in rh) * 1000:.0f} ms,每次最终连上的是{"IPv4" if all(x[0] == 1 for x in rh) else "IPv6"}(5 次里 IPv4 赢了 {sum(1 for x in rh if x[0] == 1)} 次)')
print('  Happy Eyeballs 不是放弃 IPv6:基线里 IPv6 本来就快,它赢了(IPv4 的尝试没来得及启动或被放弃);只有 IPv6 太慢才让 IPv4 去抢')

print('== 四:IPv6 是黑洞时(真实的):目标是本链路上一个不存在的链路本地地址,TCP 的 SYN 一直发不出去;用 asyncio 的 create_connection,把 getaddrinfo 换成“IPv6 黑洞 + 127.0.0.1”这两项,比较 happy_eyeballs_delay 关闭 / 打开')
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(50); port = srv.getsockname()[1]
async def go(delay, wait):
    loop = asyncio.get_running_loop()
    async def gai(host, port_, **kw): return [(socket.AF_INET6, socket.SOCK_STREAM, 6, '', (GHOST[0], port_, 0, IFI)), (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', port_))]
    loop.getaddrinfo = gai
    t0 = time.time()
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection('dual.example', port, happy_eyeballs_delay=delay), wait)
        fam = w.get_extra_info('peername')[0]; w.close(); return time.time() - t0, fam
    except Exception as e: return time.time() - t0, type(e).__name__
t_none = [asyncio.run(go(None, 5)) for _ in range(2)]
print(f'  happy_eyeballs_delay=None(asyncio 默认,关闭):等待上限 5 秒,结果 {[(round(t, 2), f) for t, f in t_none]}——一直卡在 IPv6 黑洞上,根本没尝试 IPv4(超时 = 5 秒的人为上限)')
t_he = [asyncio.run(go(0.25, 5)) for _ in range(3)]
print(f'  happy_eyeballs_delay=0.25:{[(round(t * 1000), f) for t, f in t_he]}(毫秒,连上的对端地址)——约 250 ms 后启动 IPv4,立刻成功')

print('== 五:启动延迟取不同的值,黑洞时的连接用时(asyncio,每个值 3 次取中位)')
rows = []
for d in (0.05, 0.1, 0.25, 0.5, 1.0):
    ts = [asyncio.run(go(d, 5))[0] for _ in range(3)]; rows.append((d, statistics.median(ts)))
    print(f'  happy_eyeballs_delay={d:<5}→ 连上用时中位 {statistics.median(ts) * 1000:.0f} ms(额外开销 {(statistics.median(ts) - d) * 1000:.1f} ms)')
print('  RFC 8305 的建议:先解析 AAAA 再等 A(解析延迟 50 ms)、连接尝试延迟 250 ms(可根据历史 RTT 在 100 ms 到 2 s 间调整);asyncio 的建议值同样是 0.25')
