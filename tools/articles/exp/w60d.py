import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tfo_common import *
tee('w60d'); reset()
LAB = os.path.abspath('wtmp_lab'); PORT = 7000
def sh(*a, t=120):
    r = subprocess.run(['docker', *a], capture_output=True, text=True, timeout=t); return (r.stdout + r.stderr).strip()
def ex(c, cmd, t=120): return sh('exec', c, 'sh', '-c', cmd, t=t)
def conns(P, port):
    out = []
    for p in syns(P, port):
        sa = [q for q in P if q['sp'] == port and q['dp'] == p['sp'] and q['fl'] & 0x12 == 0x12]
        out.append((p, sa[0] if sa else None))
    return out
def ck(p, kind=34):
    d = p['optd'].get(kind, b''); return d.hex()[:8] if len(d) >= 8 else '-'
def desc(i, p, sa):
    s = f'    第 {i} 个:SYN 载荷 {p["plen"]} 字节,TFO 选项长度 {topt(p) or "无"},cookie 前 4 字节 {ck(p)}'
    if sa is None: return s + ';没有 SYN+ACK'
    acc = ',数据被接受' if p['plen'] and sa['ack'] - p['seq'] == p['plen'] + 1 else (',数据没被接受(ack = seq + 1)' if p['plen'] else '')
    return s + f';SYN+ACK 的 TFO 选项 {ck(sa) if 34 in sa["optd"] else "无"}{acc}'
def cap_start(name): ex('tc', f'rm -f /tmp/{name}.pcap'); sh('exec', '-d', 'tc', 'tcpdump', '-U', '-i', 'eth0', '-w', f'/tmp/{name}.pcap', 'tcp', 'and', 'portrange', '7000-7001'); time.sleep(1)
def cap_stop(name):
    time.sleep(0.8); ex('tc', 'pkill tcpdump'); time.sleep(0.5); sh('cp', f'tc:/tmp/{name}.pcap', f'wtmp/{name}.pcap'); return dd(tcp_pkts(f'wtmp/{name}.pcap', True))
def cli(mode, port, n, tag, gap=0.3):
    out = ex('tc', f'python3 /lab/tfo_cli.py {mode} 172.31.9.10 {port} {n} {gap} {tag}', t=300)
    return [l.split()[1] for l in out.split('\n') if l.strip()]
def cleanup():
    for c in ('ts', 'tc'): sh('rm', '-f', c)
    sh('network', 'rm', 'tfonet')
cleanup()
os.makedirs('wtmp', exist_ok=True)
try:
    print(sh('network', 'create', '--subnet', '172.31.9.0/24', 'tfonet')[:0], end='')
    for nm, ip in (('ts', '172.31.9.10'), ('tc', '172.31.9.11')):
        sh('run', '-d', '--name', nm, '--network', 'tfonet', '--ip', ip, '--cap-add', 'NET_ADMIN', '--sysctl', 'net.ipv4.tcp_fastopen=3', '-v', f'{LAB}:/lab:ro', 'netlab-tfo', 'sleep', '3600')
        ex(nm, 'tc qdisc add dev eth0 root netem delay 50ms')
    kernel = ex('tc', 'uname -r')
    ex('ts', f'(python3 /lab/tfo_srv.py {PORT} /tmp/s.log tfo >/dev/null 2>&1 &) ; (python3 /lab/tfo_srv.py 7001 /tmp/s1.log >/dev/null 2>&1 &)'); time.sleep(1)

    print(f'== 八:Linux 对照(内核 {kernel},两个容器之间每方向加 50 ms 延迟,往返 100 ms,tcp_fastopen = {ex("tc", "cat /proc/sys/net/ipv4/tcp_fastopen")}):客户端 sendto + MSG_FASTOPEN,服务端 listen 前后设 TCP_FASTOPEN。先 4 次普通 connect + send,再 5 次 TFO,然后用 ip tcp_metrics flush 清掉缓存的 cookie,再 2 次 TFO')
    cap_start('a')
    normal = cli('normal', PORT, 4, 'n')
    tfo1 = cli('tfo', PORT, 5, 't')
    print('  清掉缓存前 ip tcp_metrics 里的 TFO 记录:' + ex('tc', 'ip tcp_metrics show | grep -c fo_cookie || true') + ' 条带 fo_cookie')
    ex('tc', 'ip tcp_metrics flush'); print('  清掉后:' + ex('tc', 'ip tcp_metrics show | grep -c fo_cookie || true') + ' 条带 fo_cookie')
    tfo2 = cli('tfo', PORT, 2, 'f')
    P = cap_stop('a')
    print(f'  耗时(ms):普通 connect + send {normal};TFO(第 1 次取 cookie){tfo1};清缓存后 TFO {tfo2}')
    print(f'  普通 4 次中位 {statistics.median(map(float, normal)):.0f} ms;TFO 里 SYN 带数据的 4 次中位 {statistics.median(map(float, tfo1[1:])):.0f} ms')
    print('  每个连接的 SYN(按时间顺序:4 个普通、5 个 TFO、2 个清缓存后):')
    for i, (p, sa) in enumerate(conns(P, PORT), 1): print(desc(i, p, sa))
    print('  服务端收到的数据:' + ex('ts', 'cut -d" " -f2- /tmp/s.log | tr "\\n" " "'))

    print('== 九:Linux 客户端的 cookie 还在缓存里,把它发给一个没开 TFO 的服务端(端口 7001):SYN 带着数据,服务端的内核怎么处理')
    cap_start('b'); t9 = cli('tfo', 7001, 3, 'x'); P = cap_stop('b')
    print(f'  3 次耗时(ms):{t9}')
    for i, (p, sa) in enumerate(conns(P, 7001), 1): print(desc(i, p, sa))
    print('  服务端(7001)收到的数据:' + ex('ts', 'cut -d" " -f2- /tmp/s1.log | tr "\\n" " "'))

    print('== 十:SYN 里的数据会被重放:cookie 无状态,服务端不记得“这个 SYN 来过”。先让客户端用有效 cookie 发一个带 order-0 的 TFO 连接,再把抓到的那个 SYN 原样用原始套接字重发 5 次(间隔 0.5 秒,源地址仍是客户端自己的),看服务端应用一共收到几次')
    ex('ts', ': > /tmp/s.log')
    cli('tfo', PORT, 2, 'warm'); ex('ts', ': > /tmp/s.log')
    NS = "nstat -az TcpExtTCPFastOpenPassive | awk 'NR==2{print $2}'"; n0 = int(ex('ts', NS))
    cap_start('c'); cli('tfo', PORT, 1, 'order-'); P = cap_stop('c')
    syn = [p for p in tcp_pkts('wtmp/c.pcap', True) if p['fl'] & 0x12 == 0x02 and p['dp'] == PORT and p['plen'] > 0][0]
    raw = None
    with open('wtmp/c.pcap', 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type == 0x0800 and isinstance(e.data.data, dpkt.tcp.TCP) and e.data.data.dport == PORT and e.data.data.flags & 0x12 == 0x02 and len(e.data.data.data):
                ipk = e.data; ipk.sum = 0; ipk.data.sum = 0; raw = bytes(ipk); break
    print('  (容器网卡开着发送校验和卸载,抓到的出站包里 TCP 校验和是占位值,直接重发会被服务端丢弃——第一次尝试时服务端计数 TcpInCsumErrors = 2,重发的包没有生效;下面是重新计算校验和之后的结果)')
    print(f'  抓到的 SYN:载荷 {syn["plen"]} 字节,TFO 选项长度 {topt(syn)}')
    ro = ex('tc', f'python3 -c "import socket,time;s=socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_RAW);p=bytes.fromhex(\'{raw.hex()}\')\nfor i in range(5): s.sendto(p,(\'172.31.9.10\',0)); time.sleep(0.5)"')
    time.sleep(1.5); n1 = int(ex('ts', NS)); print(f'  服务端内核计数 TcpExtTCPFastOpenPassive(收到有效 cookie 的 SYN 并建立子连接的次数)增加了 {n1 - n0}(1 次原始 + 重放)')
    log = ex('ts', 'cat /tmp/s.log').split('\n')
    print(f'  服务端应用收到的记录({len(log)} 条):{[l.split(" ", 1)[1] if " " in l else l for l in log]}')
    print(f'  其中应用读到 order-0 的有 {sum(1 for l in log if l.endswith("order-0"))} 次,另有 {sum(1 for l in log if "ERR" in l)} 条是随后收到客户端 RST 的报错(客户端内核没有对应的套接字,对重放引发的 SYN+ACK 回 RST)')

    print('== 十一:中间设备丢弃“带数据的 SYN”(服务端容器上用 iptables 丢弃长度 ≥ 70 字节的 SYN;不带数据的 SYN 约 60 字节,请求 cookie 的约 64 字节):客户端有有效 cookie,连续 5 次 TFO,再看之后的连接')
    ex('tc', 'nstat -n >/dev/null 2>&1; true'); print('  tcp_fastopen_blackhole_timeout_sec = ' + ex('tc', 'cat /proc/sys/net/ipv4/tcp_fastopen_blackhole_timeout_sec'))
    ex('ts', ': > /tmp/s.log')
    ex('ts', f'iptables -A INPUT -p tcp --dport {PORT} --syn -m length --length 70:1500 -j DROP')
    cap_start('d'); t11 = cli('tfo', PORT, 5, 'd', gap=0.3)
    ex('ts', f'iptables -D INPUT -p tcp --dport {PORT} --syn -m length --length 70:1500 -j DROP')
    t11b = cli('tfo', PORT, 3, 'e'); P = cap_stop('d')
    print(f'  丢弃期间 5 次耗时(ms):{t11};撤掉规则后再 3 次:{t11b}')
    by = {}
    for p in tcp_pkts('wtmp/d.pcap', True):
        if p['fl'] & 0x12 == 0x02 and p['dp'] == PORT:
            L = by.setdefault(p['sp'], []); L.append((round(p['ts'], 2), p['plen']))
    for i, L in enumerate(by.values(), 1):
        t0 = L[0][0]; print(f'    第 {i} 个连接的 SYN(相对时间 s / 载荷):' + ', '.join(f'+{t - t0:.1f}s/{pl}B' for t, pl in L))
    print('  客户端内核计数(从本组容器启动起累计,其中第九节的 3 次 + 本节的 5 次 = 8 次 SYN 里的数据没被对端确认):' + ex('tc', 'nstat -az TcpExtTCPFastOpenActiveFail TcpExtTCPFastOpenBlackhole | tr -s " " | cut -d" " -f1,2 | tr "\\n" ";"'))
    print('  服务端收到的数据:' + ex('ts', 'cut -d" " -f2- /tmp/s.log | tr "\\n" " "'))
finally:
    cleanup()
