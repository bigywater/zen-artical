import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
tee('w102'); reset()
OP = {1: 'RRQ', 2: 'WRQ', 3: 'DATA', 4: 'ACK', 5: 'ERROR', 6: 'OACK'}
FILES = {'small.txt': (b'0123456789' * 200)[:2000], 'big.bin': os.urandom(100000)}
wire = []
def describe(p):
    op = struct.unpack('>H', p[:2])[0]
    if op in (1, 2): parts = p[2:].split(b'\0'); return f'{OP[op]} 文件={parts[0].decode()} 模式={parts[1].decode()}' + (' 选项=' + str([x.decode() for x in parts[2:-1]]) if len(parts) > 3 else '')
    if op == 3: return f'DATA 块号={struct.unpack(">H", p[2:4])[0]} 数据={len(p) - 4} 字节'
    if op == 4: return f'ACK 块号={struct.unpack(">H", p[2:4])[0]}'
    if op == 5: return f'ERROR 码={struct.unpack(">H", p[2:4])[0]} 信息={p[4:-1].decode()!r}'
    if op == 6: return 'OACK 选项=' + str([x.decode() for x in p[2:].split(b"\0")[:-1]])
    return '?'
def serve_rrq(addr, req, sock69, stop, log):
    parts = req[2:].split(b'\0'); fname = parts[0].decode(); opts = {parts[i].decode().lower(): parts[i + 1].decode() for i in range(2, len(parts) - 1, 2)} if len(parts) > 3 else {}
    tid = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); tid.bind(('127.0.0.1', lab_port())); tid.settimeout(0.6); log.append(('TID', tid.getsockname()[1]))
    def send(p): wire.append(('S→C', tid.getsockname()[1], addr[1], p)); tid.sendto(p, addr)
    if fname not in FILES: send(struct.pack('>HH', 5, 1) + b'File not found\0'); return
    data = FILES[fname]; bs = 512
    if 'blksize' in opts:
        bs = int(opts['blksize']); oack = struct.pack('>H', 6) + b'blksize\0' + str(bs).encode() + b'\0'
        for tries in range(6):
            send(oack)
            try: a, ra = tid.recvfrom(65535); wire.append(('C→S', ra[1], tid.getsockname()[1], a)); 
            except socket.timeout: continue
            if struct.unpack('>HH', a[:4]) == (4, 0): break
    blocks = [data[i:i + bs] for i in range(0, len(data), bs)]
    if len(data) % bs == 0: blocks.append(b'')
    for n, blk in enumerate(blocks, 1):
        pkt = struct.pack('>HH', 3, n & 0xffff) + blk
        for tries in range(8):
            send(pkt)
            try:
                a, ra = tid.recvfrom(65535); wire.append(('C→S', ra[1], tid.getsockname()[1], a))
                if ra != addr: tid.sendto(struct.pack('>HH', 5, 5) + b'Unknown transfer ID\0', ra); continue
                if struct.unpack('>HH', a[:4]) == (4, n & 0xffff): break
            except socket.timeout: log.append(('重传', n))
    tid.close()
def tftp_server(port, stop, log):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.1', port)); s.settimeout(0.3)
    while not stop[0]:
        try: d, a = s.recvfrom(65535)
        except socket.timeout: continue
        wire.append(('C→S', a[1], port, d))
        if struct.unpack('>H', d[:2])[0] == 1: threading.Thread(target=serve_rrq, args=(a, d, s, stop, log), daemon=True).start()
    s.close()
def get(port, fname, blksize=None, tmo=1.0, maxretry=10):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(tmo); req = struct.pack('>H', 1) + fname.encode() + b'\0octet\0' + (b'blksize\0' + str(blksize).encode() + b'\0' if blksize else b'')
    wire.append(('C→S', s.getsockname()[1] if False else 0, port, req)); t0 = time.time(); s.sendto(req, ('127.0.0.1', port)); out = b''; srv = None; expect = 1; retries = 0; last = req; bs = 512; stats = {'timeouts': 0, 'blocks': 0}
    while True:
        try: d, a = s.recvfrom(65535)
        except socket.timeout:
            stats['timeouts'] += 1; retries += 1
            if retries > maxretry: return None, time.time() - t0, stats
            s.sendto(last, srv or ('127.0.0.1', port)); continue
        retries = 0; op = struct.unpack('>H', d[:2])[0]
        if srv is None: srv = a
        if a != srv: s.sendto(struct.pack('>HH', 5, 5) + b'Unknown transfer ID\0', a); continue
        if op == 5: return ('ERR', struct.unpack('>H', d[2:4])[0], d[4:-1].decode()), time.time() - t0, stats
        if op == 6:
            bs = int(d[2:].split(b'\0')[1]); last = struct.pack('>HH', 4, 0); s.sendto(last, srv); continue
        if op == 3:
            n = struct.unpack('>H', d[2:4])[0]
            if n == expect & 0xffff:
                out += d[4:]; stats['blocks'] += 1; last = struct.pack('>HH', 4, n); s.sendto(last, srv); expect += 1
                if len(d) - 4 < bs: return out, time.time() - t0, stats
            else: s.sendto(last, srv)
log = []; port = lab_port(); stop = [False]; threading.Thread(target=tftp_server, args=(port, stop, log), daemon=True).start(); time.sleep(0.3)

print('== 一:TFTP 的报文(RFC 1350):只有 5 种,2 字节操作码开头。读一个 2000 字节的文件,逐包看(客户端请求发到服务器的公开端口,服务器却从一个新的端口回答——这就是 TID,传输标识)')
wire.clear(); log.clear(); data, dt, st = get(port, 'small.txt'); time.sleep(0.2)
tid = [x for x in log if x[0] == 'TID'][0][1]
for who, sp, dp, p in wire: print(f'    {who}  {"客户端临时端口" if who == "C→S" and dp == port else "客户端" if who == "C→S" else "服务器 TID"}→ {"服务器 69 端口(此处为 " + str(port) + ")" if dp == port else "服务器 TID " + str(tid) if who == "C→S" else "客户端"}  {len(p):>4} 字节  {describe(p)}')
print(f'  文件 {len(FILES["small.txt"])} 字节 = 3 × 512 + 464:前 3 个 DATA 是 512 字节(满块),最后一个 DATA 只有 464 字节(不足 512)——“不足 512 字节的 DATA 就是传输结束”。如果文件大小恰好是 512 的整数倍,最后要多发一个 0 字节的 DATA')
print(f'  服务器回应用的端口 {tid} 不是请求发往的端口 {port}:服务器为每个传输新开一个端口(TID),后续两边都只认这一对端口;拿别的端口来插话会被回 ERROR 5(Unknown transfer ID)')

print('== 二:错误:请求一个不存在的文件')
wire.clear(); r, dt, st = get(port, 'nope.txt'); print(f'  请求 nope.txt → {r};' + ' ; '.join(describe(p) for who, sp, dp, p in wire if who == 'S→C'))

print('== 三:停等(lock-step):每个 DATA 都要等 ACK 才发下一个。往返 50 ms(netlab 每方向 25 ms)读 100000 字节的文件,块大小 512(默认)与协商 blksize = 1428(RFC 2348 的 OACK)')
for bs in (None, 1428):
    with lossy(loss=0, delay=25, bw=0):
        wire.clear(); r, dt, st = get(port, 'big.bin', blksize=bs); ok = (r == FILES['big.bin'])
    nb = -(-100000 // (bs or 512)) + (1 if 100000 % (bs or 512) == 0 else 0)
    print(f'  块大小 {bs or 512:>4}:共 {nb} 个 DATA 块,耗时 {dt:.2f} 秒,吞吐 {100000 / dt / 1000:.0f} KB/s;内容{"正确" if ok else "不正确"};每个块一个往返 → 理论 {nb} × 0.05 = {nb * 0.05:.2f} 秒' + (f';第一个包是 {describe(wire[1][3])},服务器回 {describe([w for w in wire if w[0] == "S→C"][0][3])}' if bs else ''))
print('  吞吐 ≈ 块大小 ÷ 往返时间(512 ÷ 0.05 = 10 KB/s;1428 ÷ 0.05 ≈ 29 KB/s):TFTP 在有延迟的链路上很慢,因为它每次只允许一个块在路上')

print('== 四:丢包:重传由两端的超时驱动。3% 丢包(netlab 每方向),读 100000 字节(块大小 1428,共 71 个块),看超时次数与耗时')
for loss in (0, 3):
    with lossy(loss=loss, delay=25, bw=0):
        log.clear(); r, dt, st = get(port, 'big.bin', blksize=1428, tmo=0.6); ok = (r == FILES['big.bin'])
    print(f'  丢包 {loss}%:耗时 {dt:.2f} 秒;客户端超时重传 {st["timeouts"]} 次,服务器超时重传 {len([x for x in log if x[0] == "重传"])} 次;内容{"正确" if ok else "不正确(" + str(type(r).__name__) + ")"}')
print('  每丢一个包(DATA 或 ACK)就要等一个完整的超时(0.6 秒)才重传,而正常一个往返只要 0.05 秒——丢包让 TFTP 的耗时按“超时”而不是按“往返”增长')
stop[0] = True
