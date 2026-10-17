import sys, os, re, struct, ipaddress; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w15'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
PUB = '104.20.23.154'
NAMES = {0: '回显应答', 3: '目的不可达', 5: '重定向', 8: '回显请求', 11: '超时'}
CODES3 = {0: '网络不可达', 1: '主机不可达', 2: '协议不可达', 3: '端口不可达', 4: '需要分片但设置了 DF', 9: '目的网络被管理禁止', 10: '目的主机被管理禁止', 13: '通信被管理禁止'}

def errs(path):
    """抓包 → ICMP 差错报文列表(类型 3 / 11)"""
    out = []
    for ts, ip in read_pcap(path):
        raw = ip.raw; ihl = (raw[0] & 15) * 4
        if raw[9] != 1 or raw[ihl] not in (3, 11): continue
        q = raw[ihl + 8:]
        if len(q) < 20: continue
        qihl = (q[0] & 15) * 4
        out.append(dict(ts=ts, raw=raw, src=socket.inet_ntoa(raw[12:16]), type=raw[ihl], code=raw[ihl + 1], iplen=struct.unpack('>H', raw[2:4])[0], ttl=raw[8], quote=q, qdst=socket.inet_ntoa(q[16:20]), qproto=q[9], qid=struct.unpack('>H', q[4:6])[0], qlen=len(q), qsport=struct.unpack('>H', q[qihl:qihl + 2])[0] if len(q) >= qihl + 2 else None, qdport=struct.unpack('>H', q[qihl + 2:qihl + 4])[0] if len(q) >= qihl + 4 else None))
    return out

def sent_udp(path, dst):
    out = []
    for ts, ip in read_pcap(path):
        raw = ip.raw
        if raw[9] == 17 and socket.inet_ntoa(raw[16:20]) == dst: out.append((ts, raw))
    return out

print('== 一:UDP 发到一个没人监听的端口(127.0.0.1):本机内核回 ICMP 类型 3 代码 3(端口不可达);看这个包的结构,以及应用能不能知道')
r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', 0)); port = r.getsockname()[1]; r.close()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.1', 0)); s.settimeout(1); sp0 = s.getsockname()[1]
with Cap(f'(udp and (port {port} or port {sp0})) or icmp', iface='lo0', write=True) as c:
    s.sendto(b'hello-closed-port', ('127.0.0.1', port))
    try: s.recvfrom(100); res_unc = '收到数据'
    except Exception as e: res_unc = f'没有任何错误({type(e).__name__}:超时)'
    sp = s.getsockname()[1]
    s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s2.settimeout(1); s2.connect(('127.0.0.1', port))
    s2.send(b'hello-connected')
    try: s2.recv(100); res_con = '收到数据'
    except Exception as e: res_con = f'{type(e).__name__}: {e}'
e = errs(c.pcap); out = sent_udp(c.pcap, '127.0.0.1')
print(f'  抓到 {len(out)} 个 UDP 包和 {len(e)} 个 ICMP 差错报文')
for x in e:
    print(f'  ICMP 类型 {x["type"]}({NAMES.get(x["type"])})代码 {x["code"]}({CODES3.get(x["code"])}),IP 总长 {x["iplen"]} = 20 + 8 + 引用 {x["qlen"]} 字节;来自 {x["src"]},引用的原包:目的 {x["qdst"]} 协议 {x["qproto"]}(17 = UDP)源端口 {x["qsport"]} 目的端口 {x["qdport"]}')
orig = out[0][1]; osp = struct.unpack('>H', orig[20:22])[0]
ex = [x for x in e if x['qsport'] == osp][0]; qt = ex['quote']
print(f'  引用的 {len(qt)} 字节(IP 头 20 字节 + UDP 头 8 字节)与发出的原包前 {len(qt)} 字节比较(原包共 {len(orig)} 字节,载荷 {len(orig) - 28} 字节没有被引用):前 {len(qt) - 2} 字节逐字节相同:{qt[:-2] == orig[:len(qt) - 2]};最后 2 个字节是 UDP 校验和字段,原包里抓到 0x{orig[26]:02x}{orig[27]:02x},引用里是 0x{qt[26]:02x}{qt[27]:02x}')
print(f'  应用这一侧:未 connect 的 UDP 套接字 sendto 之后 recvfrom → {res_unc};已 connect 的 UDP 套接字 send 之后 recv → {res_con}')
print('  所以 UDP 想知道对方端口是否关闭,必须 connect 后读错误;ICMP 差错里引用了原包头,内核靠引用的 四元组 找到是哪个套接字')

print('== 二:TCP 发到没人监听的端口用 RST 拒绝,而不是 ICMP;再比较“拒绝”和“丢弃”对应用的差别——被拒绝的 connect 立刻失败,被丢弃的要等到超时')
r = socket.socket(); r.bind(('127.0.0.1', 0)); port = r.getsockname()[1]; r.close()
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    t0 = time.time(); k = socket.socket(); k.settimeout(3)
    try: k.connect(('127.0.0.1', port)); er = '连上了'
    except Exception as ex: er = f'{type(ex).__name__}: {ex}'
    dt = (time.time() - t0) * 1000
print(f'  lo0 上 connect 一个没人监听的 TCP 端口:{er},用时 {dt:.2f} ms;抓到 {c.count} 个包:')
show(c.lines, 6, 130)
print(f'  其中 ICMP 包 {sum(1 for l in c.lines if "ICMP" in l)} 个——TCP 的拒绝是 RST,不是 ICMP')
with Cap(f'host {gw} and tcp port 81', iface='en0', write=True) as c:
    k = socket.socket(); k.settimeout(3)
    try: k.connect((gw, 81))
    except Exception: pass
    k.close()
print('  默认网关 81 端口的 connect 在线上是这样的(en0,地址已遮盖):')
show([priv(l) for l in c.lines], 6, 150)
print('  第一个 SYN 带 ECN 标志(SEW),网关用 RST 拒绝;1 秒后 macOS 又发一个 SYN,这次 ECN 标志去掉了(S),再被 RST 拒绝,connect 才报 Connection refused——所以被拒绝用了约 1 秒;重发是不是 ECN 协商失败后的回退,没有进一步验证')
with Cap(f'host {PUB} and tcp port 81', iface='en0', write=True) as c:
    k = socket.socket(); k.settimeout(3)
    try: k.connect((PUB, 81))
    except Exception: pass
    k.close()
sy = [l for l in norm(c.lines) if 'Flags [S' in l and f'{PUB}.81:' in l]
print(f'  公网主机 81 端口:3 秒内共发出 {len(sy)} 个 SYN({" / ".join(l.split()[0] for l in sy)} ms),收到该主机的包 {sum(1 for l in c.lines if f"{PUB}.81 >" in l)} 个——没有任何回应(被防火墙丢弃),connect 一直等到超时')
rows = []
for name, ip_, p in (('默认网关的 81 端口', gw, 81), ('公网某主机的 81 端口', PUB, 81), ('公网某主机的 80 端口(对照:有服务)', PUB, 80)):
    ts_ = []
    for _ in range(3):
        k = socket.socket(); k.settimeout(3); t0 = time.time()
        try: k.connect((ip_, p)); er = '连上了'
        except Exception as ex: er = type(ex).__name__ + (': ' + str(ex) if ex.args and not isinstance(ex, socket.timeout) else '')
        ts_.append((time.time() - t0) * 1000); k.close()
    rows.append((name, er, ts_))
    print(f'  {name}:3 次 connect 结果「{er}」,用时 ' + ' / '.join(f'{x:.0f}' for x in ts_) + ' ms')

print('== 三:往各种目的地发 UDP(端口 33435,没人监听),看谁回 ICMP 差错、回的是哪种;不回的也是一种结果')
cands = [('默认网关', gw), ('远端私有地址 10.x', '10.10.10.77'), ('私有地址 172.31.x', '172.31.255.1'), ('运营商级 NAT 地址段 100.64.x', '100.64.0.1'), ('链路本地 169.254.x', '169.254.1.1'), ('保留地址 240.0.0.1', '240.0.0.1'), ('文档地址 198.51.100.7', '198.51.100.7'), ('文档地址 203.0.113.9', '203.0.113.9'), ('文档地址 192.0.2.1', '192.0.2.1'), ('公网 DNS 服务器 A', '8.8.8.8'), ('公网 DNS 服务器 B', '1.1.1.1'), ('公网 Web 主机', PUB)]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
with Cap('icmp or (udp and dst port 33435)', iface='en0', write=True) as c:
    for nm, d in cands:
        try: s.sendto(b'x' * 12, (d, 33435))
        except Exception as ex: print('   sendto 失败', nm, ex)
        time.sleep(0.4)
    time.sleep(2.5)
E = errs(c.pcap); got = {}
for x in E: got.setdefault(x['qdst'], []).append(x)
nrep = 0
for nm, d in cands:
    L = got.get(d, [])
    if L:
        x = L[0]; nrep += 1
        who = '目的地自己' if x['src'] == d else ('本机默认网关' if x['src'] == gw else '路径上的另一台设备')
        print(f'  {nm:<24}→ 类型 {x["type"]} 代码 {x["code"]}({CODES3.get(x["code"], "?") if x["type"] == 3 else "超时"}),来自{who},IP 总长 {x["iplen"]}(引用 {x["qlen"]} 字节)')
    else: print(f'  {nm:<24}→ 没有收到任何 ICMP 差错')
rep = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
with Cap('icmp', iface='en0', write=True) as c:
    for _ in range(10): rep.sendto(b'x' * 12, (gw, 33435)); time.sleep(1.0)
    time.sleep(1.5)
gr = [x for x in errs(c.pcap) if x['qdst'] == gw]
print(f'  默认网关再单独试:间隔 1 s 连发 10 个到 33435 端口,收到 ICMP 差错 {len(gr)} 个(类型/代码:{sorted({(x["type"], x["code"]) for x in gr})})——网关不是每次都回')
codes = sorted({(x['type'], x['code']) for x in E})
print(f'  12 个目的地里 {nrep} 个收到了差错报文;出现过的 (类型, 代码):{codes}')

print('== 四:引用的长度因设备而异:同样 40 字节的 UDP 探测,不同跳的路由器各引用了多少字节;并核对引用内容和原包(除 TTL 和校验和外)一致')
rows = []
with Cap('icmp or (udp and dst port 33435)', iface='en0', write=True) as c:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for ttl in (1, 2, 3, 4, 8, 10, 11):
        s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl); s.sendto(b'y' * 12, (PUB, 33435)); time.sleep(0.4)
    time.sleep(2)
E4 = errs(c.pcap); S4 = sent_udp(c.pcap, PUB)
byid = {struct.unpack('>H', r_[4:6])[0]: r_ for ts, r_ in S4}
tb = {}
for x in E4:
    o = byid.get(x['qid'])
    if not o: continue
    ok = len(x['quote']) >= 28 and x['quote'][0:8] == o[0:8] and x['quote'][9:10] == o[9:10] and x['quote'][12:28] == o[12:28]
    full = (x['quote'][20:26] == o[20:26]) if len(x['quote']) == 28 else (x['quote'][20:26] == o[20:26] and x['quote'][28:] == o[28:len(x['quote'])])
    tb[x['type'], x['qlen']] = tb.get((x['type'], x['qlen']), 0) + 1
    print(f'  TTL={o[8]:<2} 的探测:{"Time Exceeded" if x["type"] == 11 else "端口不可达"} 的 IP 总长 {x["iplen"]},引用 {x["qlen"]} 字节;引用的 IP 头(版本/长度/标识/协议/源/目的)与原包相同:{ok};引用的 UDP 头(端口、长度){"" if len(x["quote"]) == 28 else "和载荷"}与原包相同:{full}')
print(f'  各种 (类型, 引用字节数) 出现次数:{tb}')
print('  规范要求至少引用原包的 IP 头 + 8 字节(= 28 字节);更多的话接收方能拿到更多信息')
print(f'  对照第一节:本机内核回端口不可达引用了 {e[0]["qlen"]} 字节;第三节里三台公网主机引用的分别是 {[x["qlen"] for x in E if x["type"] == 3 and x["src"] != gw]} 字节')

print('== 五:不对广播回差错:UDP 发到子网广播地址的一个没人监听的端口,同一网段的所有设备里有没有一个回 ICMP 端口不可达;对照发到单个主机(默认网关)')
bc = [l.split()[-1] for l in sysout('ifconfig', 'en0').splitlines() if 'broadcast' in l][0]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
res5 = []
for nm, d in (('子网广播地址', bc), ('默认网关(单播)', gw)):
    with Cap('icmp', iface='en0', write=True) as c:
        for _ in range(5): s.sendto(b'z' * 12, (d, 33435)); time.sleep(0.3)
        time.sleep(1.5)
    E5 = [x for x in errs(c.pcap) if x['qdst'] == d]
    res5.append((nm, len(E5), len({x['src'] for x in E5})))
    print(f'  发 5 个到{nm}的 33435 端口:收到 ICMP 差错 {len(E5)} 个,来自 {len({x["src"] for x in E5})} 台设备')
print('  规范(RFC 1122 / 1812):不对发给广播 / 组播地址的数据报回 ICMP 差错,否则一个广播会引来整网的回复(广播风暴);也不对 ICMP 差错本身再回差错')
