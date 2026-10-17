import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
tee('w104'); reset()
PT = {1: 'CONNECT', 2: 'CONNACK', 3: 'PUBLISH', 4: 'PUBACK', 5: 'PUBREC', 6: 'PUBREL', 7: 'PUBCOMP', 8: 'SUBSCRIBE', 9: 'SUBACK', 12: 'PINGREQ', 13: 'PINGRESP', 14: 'DISCONNECT'}
def enc_len(n):
    out = bytearray()
    while True:
        b = n % 128; n //= 128
        if n: b |= 0x80
        out.append(b)
        if not n: return bytes(out)
def dec_len(rd):
    m = 1; v = 0
    while True:
        b = rd(1)[0]; v += (b & 127) * m; m *= 128
        if not b & 128: return v
def estr(s): b = s.encode(); return struct.pack('>H', len(b)) + b
def pkt(first, body): return bytes([first]) + enc_len(len(body)) + body
def read_pkt(s):
    def rd(n):
        b = b''
        while len(b) < n:
            d = s.recv(n - len(b))
            if not d: raise EOFError()
            b += d
        return b
    f = rd(1)[0]; n = dec_len(rd); return f, rd(n)
hx = lambda b: ' '.join(f'{x:02x}' for x in b)
# ---- 迷你 MQTT 3.1.1 代理 ----
subs = {}; retained = {}; lock = threading.Lock(); events = []; drop_next_puback = [False]
def topic_match(flt, t):
    fp = flt.split('/'); tp = t.split('/')
    for i, f in enumerate(fp):
        if f == '#': return True
        if i >= len(tp): return False
        if f != '+' and f != tp[i]: return False
    return len(fp) == len(tp)
def deliver(topic, payload, qos=0, retain=False):
    with lock:
        targets = [(c, q) for c, flts in subs.items() for f, q in flts.items() if topic_match(f, topic)]
    for c, q in targets:
        try:
            qq = min(q, qos); body = estr(topic) + (struct.pack('>H', 1) if qq else b'') + payload; c.sendall(pkt(0x30 | (qq << 1) | (1 if retain else 0), body))
        except Exception: pass
def handle(c):
    will = None; clean = False; ka = 0; last = [time.time()]; pubrel = {}
    c.settimeout(None)
    def watchdog():
        while True:
            time.sleep(0.2)
            if ka and time.time() - last[0] > ka * 1.5:
                events.append(('超时断开', round(time.time() - last[0], 2))); 
                try: c.shutdown(socket.SHUT_RDWR)
                except Exception: pass
                return
    try:
        while True:
            f, body = read_pkt(c); last[0] = time.time(); t = f >> 4
            if t == 1:
                i = 2 + struct.unpack('>H', body[:2])[0]; level = body[i]; flags = body[i + 1]; ka = struct.unpack('>H', body[i + 2:i + 4])[0]; j = i + 4
                cl = struct.unpack('>H', body[j:j + 2])[0]; cid = body[j + 2:j + 2 + cl].decode(); j += 2 + cl
                if flags & 4:
                    tl_ = struct.unpack('>H', body[j:j + 2])[0]; wt = body[j + 2:j + 2 + tl_].decode(); j += 2 + tl_; ml = struct.unpack('>H', body[j:j + 2])[0]; wm = body[j + 2:j + 2 + ml]; will = (wt, wm)
                events.append(('CONNECT', cid, level, flags, ka)); c.sendall(bytes([0x20, 2, 0, 0]))
                if ka: threading.Thread(target=watchdog, daemon=True).start()
            elif t == 8:
                pid = struct.unpack('>H', body[:2])[0]; j = 2; rcs = []
                while j < len(body):
                    tl_ = struct.unpack('>H', body[j:j + 2])[0]; flt = body[j + 2:j + 2 + tl_].decode(); q = body[j + 2 + tl_]; j += 3 + tl_
                    with lock: subs.setdefault(c, {})[flt] = q
                    rcs.append(q)
                c.sendall(pkt(0x90, struct.pack('>H', pid) + bytes(rcs)))
                for rt, (rp, rq) in list(retained.items()):
                    if any(topic_match(f_, rt) for f_ in subs[c]): c.sendall(pkt(0x31, estr(rt) + rp))
            elif t == 3:
                qos = (f >> 1) & 3; retain = f & 1; tl_ = struct.unpack('>H', body[:2])[0]; topic = body[2:2 + tl_].decode(); j = 2 + tl_; pid = None
                if qos: pid = struct.unpack('>H', body[j:j + 2])[0]; j += 2
                payload = body[j:]
                if retain: retained[topic] = (payload, qos) if payload else retained.pop(topic, None) or (b'', 0)
                if qos == 1:
                    events.append(('PUBLISH QoS1', pid, bool(f & 8)))
                    if drop_next_puback[0]: drop_next_puback[0] = False; events.append(('故意不回 PUBACK', pid))
                    else: c.sendall(bytes([0x40, 2]) + struct.pack('>H', pid))
                    if not (f & 8) or True: deliver(topic, payload, qos)
                elif qos == 2: c.sendall(bytes([0x50, 2]) + struct.pack('>H', pid)); pubrel[pid] = (topic, payload)
                else: deliver(topic, payload, 0, False)
            elif t == 6:
                pid = struct.unpack('>H', body[:2])[0]; c.sendall(bytes([0x70, 2]) + struct.pack('>H', pid))
                if pid in pubrel: tp, pl = pubrel.pop(pid); deliver(tp, pl, 0)
            elif t == 12: c.sendall(bytes([0xD0, 0]))
            elif t == 14: clean = True; break
    except Exception: pass
    finally:
        with lock: subs.pop(c, None)
        if will and not clean: events.append(('遗嘱触发', will[0])); deliver(will[0], will[1], 0)
        try: c.close()
        except Exception: pass
def serve(port, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=handle, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
port = lab_port(); stop = [False]; serve(port, stop)
def connect(cid, ka=60, will=None, clean=True):
    s = socket.create_connection(('127.0.0.1', port)); s.settimeout(5); flags = (2 if clean else 0) | ((4 | (1 << 3)) if will else 0)
    body = estr('MQTT') + bytes([4, flags]) + struct.pack('>H', ka) + estr(cid) + ((estr(will[0]) + struct.pack('>H', len(will[1])) + will[1]) if will else b'')
    p = pkt(0x10, body); s.sendall(p); r = read_pkt(s); return s, p, r
def subscribe(s, flt, qos=0, pid=1):
    p = pkt(0x82, struct.pack('>H', pid) + estr(flt) + bytes([qos])); s.sendall(p); return p, read_pkt(s)

print('== 一:MQTT 的报文只有 14 种,固定头 = 1 字节(高 4 位类型 + 低 4 位标志)+ 1~4 字节的“剩余长度”。手工连本机迷你代理:CONNECT / CONNACK、SUBSCRIBE / SUBACK')
s, p, r = connect('w104-client', ka=60)
print(f'  CONNECT({len(p)} 字节):{hx(p)}')
print(f'    = {p[0]:02x}(类型 1 = CONNECT,标志 0)| {p[1]:02x}(剩余长度 {p[1]})| 00 04 "MQTT"(协议名)| 04(协议级别 4 = MQTT 3.1.1)| 02(连接标志:Clean Session)| 00 3c(保活 60 秒)| 00 0c "w104-client"(客户端标识)')
print(f'  CONNACK({len(bytes([r[0], 2]) + r[1])} 字节):{hx(bytes([r[0], len(r[1])]) + r[1])} = 类型 2(CONNACK)| 剩余长度 2 | 00(会话存在标志 0)| 00(返回码 0 = 接受)')
p2, r2 = subscribe(s, 'sensors/+/temp', 1)
print(f'  SUBSCRIBE({len(p2)} 字节):{hx(p2)}:82 = 类型 8,标志必须是 0010;包标识 00 01;主题过滤器 "sensors/+/temp";请求的 QoS 01。SUBACK:{hx(bytes([r2[0], len(r2[1])]) + r2[1])}(类型 9,包标识 1,授予的 QoS 1)')

print('== 二:PUBLISH 一条消息要多少字节?QoS 0:固定头 + 主题(2 字节长度 + 主题名)+ 载荷;没有应答。剩余长度的变长编码:≤127 一个字节,≤16383 两个字节')
pub, _, _ = connect('w104-pub'); sub, _, _ = connect('w104-sub'); subscribe(sub, 'sensors/room1/temp', 0)
p = pkt(0x30, estr('sensors/room1/temp') + b'21.5'); pub.sendall(p); rf, rb = read_pkt(sub)
print(f'  发布者发出(QoS 0,{len(p)} 字节):{hx(p)}:30 = PUBLISH,QoS 0 | {p[1]:02x} 剩余长度 {p[1]} | 00 12 + 18 字节主题 "sensors/room1/temp" | 4 字节载荷 "21.5"')
print(f'  订阅者收到({len(rb) + 2} 字节):类型 {PT[rf >> 4]},主题 {rb[2:2 + struct.unpack(">H", rb[:2])[0]].decode()!r},载荷 {rb[2 + struct.unpack(">H", rb[:2])[0]:]!r};单条消息的总开销 = 固定头 2 + 主题长度字段 2 = 4 字节,再加主题名本身 18 字节(MQTT 没有“头部压缩”,主题名每次都要带)')
for n in (100, 127, 128, 16383, 16384):
    pl = b'x' * n; body = estr('t') + pl; print(f'    载荷 {n:>5} 字节:剩余长度 {len(body):>6} → 编码成 {len(enc_len(len(body)))} 字节({hx(enc_len(len(body)))});整个包 {1 + len(enc_len(len(body))) + len(body)} 字节')
pub.close(); sub.close()

print('== 三:QoS 1(至少一次):PUBLISH 带包标识,收到方回 PUBACK;没收到 PUBACK 发送方要用 DUP 标志重发。让代理故意不回第一次的 PUBACK')
events.clear(); drop_next_puback[0] = True
pub, _, _ = connect('w104-q1'); pid = 7; body = estr('q1/topic') + struct.pack('>H', pid) + b'payload'; first = pkt(0x32, body); t0 = time.time(); pub.sendall(first); pub.settimeout(1.0)
try: pub.recv(10); got = '收到了 PUBACK'
except socket.timeout: got = '1 秒内没有收到 PUBACK'
dup = pkt(0x3A, body); pub.sendall(dup); pub.settimeout(3); ack = read_pkt(pub); dt = time.time() - t0
print(f'  第一次 PUBLISH:{hx(first)}(32 = QoS 1,DUP 0);代理故意不回;客户端{got}')
print(f'  重发 PUBLISH:{hx(dup)}(3A = QoS 1 + DUP 1,包标识仍是 {pid});代理回 PUBACK {hx(bytes([ack[0], len(ack[1])]) + ack[1])}(类型 4,包标识 {struct.unpack(">H", ack[1])[0]})')
print(f'  代理看到的 QoS1 PUBLISH 事件:{[e for e in events if e[0].startswith("PUBLISH") or e[0].startswith("故意")]}——同一个包标识被收到了两次,所以 QoS 1 是“至少一次”,接收方可能看到重复')
pub.close()

print('== 四:QoS 2(恰好一次):四步握手 PUBLISH → PUBREC → PUBREL → PUBCOMP,接收方在 PUBREL 之后才投递,所以不会重复')
sub, _, _ = connect('w104-q2sub'); subscribe(sub, 'q2/topic', 0); pub, _, _ = connect('w104-q2')
steps_ = []
pub.sendall(pkt(0x34, estr('q2/topic') + struct.pack('>H', 9) + b'exactly once')); steps_.append(('C→S', 'PUBLISH QoS2 pid=9'))
f, b = read_pkt(pub); steps_.append(('S→C', f'{PT[f >> 4]} pid={struct.unpack(">H", b)[0]}'))
sub.settimeout(0.5)
try: sub.recv(100); early = '订阅者在 PUBREL 之前就收到了(不应该)'
except socket.timeout: early = '订阅者此时还没收到消息(代理在等 PUBREL)'
pub.sendall(bytes([0x62, 2]) + struct.pack('>H', 9)); steps_.append(('C→S', 'PUBREL pid=9'))
f, b = read_pkt(pub); steps_.append(('S→C', f'{PT[f >> 4]} pid={struct.unpack(">H", b)[0]}'))
sub.settimeout(3); sf, sb = read_pkt(sub)
for who, d in steps_: print(f'    {who}  {d}')
print(f'  {early};PUBREL 之后订阅者收到:主题 {sb[2:2 + struct.unpack(">H", sb[:2])[0]].decode()!r},载荷 {sb[2 + struct.unpack(">H", sb[:2])[0]:]!r}。QoS 2 用 4 个包(2 个往返)换来“恰好一次”,开销是 QoS 0 的 4 倍')
pub.close(); sub.close()

print('== 五:保活与遗嘱:客户端声明保活 2 秒,不发任何包;代理在 1.5 倍保活时间(3 秒)后断开它,并发布它的“遗嘱”消息。对比正常 DISCONNECT')
events.clear(); watcher, _, _ = connect('w104-watch'); subscribe(watcher, 'clients/status', 0)
dead, _, _ = connect('w104-dead', ka=2, will=('clients/status', b'w104-dead went offline')); t0 = time.time()
watcher.settimeout(6)
try: wf, wb = read_pkt(watcher); dt = time.time() - t0; wt = f'订阅者在 {dt:.1f} 秒后收到遗嘱:主题 {wb[2:2 + struct.unpack(">H", wb[:2])[0]].decode()!r},载荷 {wb[2 + struct.unpack(">H", wb[:2])[0]:]!r}'
except Exception as e: wt = f'没有收到遗嘱 {type(e).__name__}'
print(f'  不发任何包、保活 2 秒 → {wt};代理记录:{[e for e in events if e[0] in ("超时断开", "遗嘱触发")]}')
ok, _, _ = connect('w104-ok', ka=60, will=('clients/status', b'w104-ok went offline')); ok.sendall(bytes([0xE0, 0])); time.sleep(0.5); ok.close()
watcher.settimeout(1.5)
try: read_pkt(watcher); print('  正常 DISCONNECT(e0 00)的客户端:订阅者仍收到了遗嘱(不应该)')
except Exception: print('  正常 DISCONNECT(e0 00,2 字节)的客户端:订阅者没有收到遗嘱——遗嘱只在“非正常断开”时发布')
ps, _, _ = connect('w104-ping', ka=2); t0 = time.time(); ps.sendall(bytes([0xC0, 0])); pr = ps.recv(10); print(f'  PINGREQ c0 00 → PINGRESP {hx(pr)}(各 2 字节,{(time.time() - t0) * 1000:.1f} ms):客户端在空闲时每隔保活时间发一次它来证明自己还活着')
print('== 六:保留消息:发布时带 RETAIN 标志,代理会存下最后一条,以后订阅的人立刻收到(不用等下一次发布)')
pub, _, _ = connect('w104-ret'); pub.sendall(pkt(0x31, estr('home/door') + b'closed')); time.sleep(0.3)
late, _, _ = connect('w104-late'); t0 = time.time(); subscribe(late, 'home/door', 0); late.settimeout(2); lf, lb = read_pkt(late)
print(f'  先发布 retain 消息 home/door = closed(31 = PUBLISH, RETAIN 1)。之后才来订阅的客户端,SUBACK 之后立刻收到:类型 {PT[lf >> 4]},保留位 {lf & 1},载荷 {lb[2 + struct.unpack(">H", lb[:2])[0]:]!r}(订阅完 {(time.time() - t0) * 1000:.1f} ms 内);用途:设备的“最新状态”')
stop[0] = True
