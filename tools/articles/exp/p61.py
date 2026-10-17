import sys, os, json, gzip, zlib, hashlib, base64, uuid, socket, random, io, collections, datetime, urllib.parse as up; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
sys.path.insert(0, '/private/tmp/claude-501/-Users-w-Desktop-zen/ba230915-496f-4157-87cf-8cee4040b1b9/scratchpad/warc_site')
from warcio.archiveiterator import ArchiveIterator
tee('p61')
d = pdir('p61')
rnd = random.Random(61)
VOC = [''.join(rnd.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(rnd.randint(3, 9))) for _ in range(3000)]
def page(i):
    r = random.Random(i); return ('<html><head><title>page %d</title></head><body>' % i + ' '.join('<p>%s</p>' % ' '.join(r.choice(VOC) for _ in range(12)) for _ in range(180)) + '</body></html>').encode()
def chunked(b, n=4096): return b''.join(b'%x\r\n' % len(b[i:i + n]) + b[i:i + n] + b'\r\n' for i in range(0, len(b), n)) + b'0\r\n\r\n'
def wire(i, kind):
    """kind: plain / gzip / chunked → (整个 HTTP 响应的字节, 去掉 chunked 之后的实体字节)"""
    body = page(i); hd = [('Server', 'x'), ('Content-Type', 'text/html; charset=utf-8')]
    if kind == 'gzip': ent = gzip.compress(body, mtime=0); hd += [('Content-Encoding', 'gzip'), ('Content-Length', len(ent))]; wb = ent
    elif kind == 'chunked': ent = body; hd += [('Transfer-Encoding', 'chunked')]; wb = chunked(body)
    else: ent = body; hd += [('Content-Length', len(body))]; wb = body
    return b'HTTP/1.1 200 OK\r\n' + b''.join(f'{k}: {v}\r\n'.encode() for k, v in hd) + b'\r\n' + wb, ent
def srv(h):
    p = up.urlsplit(h.path).path; i = int(p.split('/')[-1]); kind = p.split('/')[1]
    w, ent = wire(i, kind); head, _, wb = w.partition(b'\r\n\r\n')
    h.wfile.write(w); h.wfile.flush(); h.close_connection = True
def capture(port, path):
    s = socket.create_connection(('127.0.0.1', port)); s.sendall(f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n'.encode()); buf = b''
    while True:
        x = s.recv(65536)
        if not x: break
        buf += x
    s.close(); return buf
def b32sha1(b): return 'sha1:' + base64.b32encode(hashlib.sha1(b).digest()).decode()
def rec(rtype, uri, block, date='2026-10-12T08:00:00Z', extra=(), ctype='application/http; msgtype=response', rid=None):
    h = [('WARC-Type', rtype), ('WARC-Record-ID', f'<urn:uuid:{rid or uuid.uuid4()}>'), ('WARC-Date', date), ('WARC-Target-URI', uri)] + list(extra) + [('Content-Type', ctype), ('Content-Length', len(block))]
    return b'WARC/1.1\r\n' + b''.join(f'{k}: {v}\r\n'.encode() for k, v in h) + b'\r\n' + block + b'\r\n\r\n'
def response_rec(uri, w, payload=None, **kw): return rec('response', uri, w, extra=[('WARC-Block-Digest', b32sha1(w)), ('WARC-Payload-Digest', b32sha1(w.partition(b'\r\n\r\n')[2] if payload is None else payload))], **kw)
def gz_member(b): return gzip.compress(b, 6, mtime=0)

def read1(r, check=False):
    got = next(ArchiveIterator(io.BytesIO(r), check_digests=check)); b = got.content_stream().read()
    return got, b
def count_complete(buf):
    """从未压缩的 WARC 字节流里数完整记录的个数(自己解析 Content-Length)"""
    pos = n = 0
    while True:
        e = buf.find(b'\r\n\r\n', pos)
        if e < 0 or not buf.startswith(b'WARC/', pos): return n, pos
        hl = [l for l in buf[pos:e].split(b'\r\n') if l.lower().startswith(b'content-length:')]
        end = e + 4 + int(hl[0].split(b':')[1]) + 4
        if end > len(buf): return n, pos
        n += 1; pos = end
def walk_members(data):
    """一个个 gzip 成员地走:返回(完整成员个数, 最后一个完整成员的结束偏移)"""
    pos = n = 0; mv = memoryview(data)
    while pos < len(data):
        dz = zlib.decompressobj(31); dz.decompress(mv[pos:])
        if not dz.eof: break
        pos = len(data) - len(dz.unused_data); n += 1
    return n, pos

with Srv(srv) as sv:
    print('== 一:抓一条响应(套接字上收到的字节原样写进记录),用 warcio 1.8.1 读回来核对;三种传输方式')
    for kind in ('plain', 'gzip', 'chunked'):
        path = f'/{kind}/7'; wirebytes = capture(sv.port, path); head, _, wb = wirebytes.partition(b'\r\n\r\n')
        r = response_rec(sv.url(path), wirebytes); got, body = read1(r, True)
        print(f'  {kind:8s} 套接字上收到 {len(wirebytes)} 字节(头 {len(head)+4}、正文 {len(wb)});写成的记录 {len(r)} 字节;warcio 读回:类型 {got.rec_type}、URI 正确 {got.rec_headers.get_header("WARC-Target-URI") == sv.url(path)}、状态 {got.http_headers.get_statuscode()}、content_stream 给出的正文(按头自动去 chunked/gzip)长度 {len(body)},与原 HTML(长度 {len(page(7))})相同:{body == page(7)};warcio 摘要核对:{got.digest_checker.passed}')
    w7, ent7 = wire(7, 'chunked'); r = response_rec('http://x.test/c', w7, ent7); got, body = read1(r, True)
    print(f'  chunked 记录里的 WARC-Payload-Digest 如果改算"去掉分块之后的正文"的摘要:warcio 摘要核对 {got.digest_checker.passed},问题 {list(got.digest_checker.problems)}(它是对头后面的字节原样算的,即分块格式还在的那些字节);我没有去核对规范里对这一点怎么规定)')
    print('== 二:同样的响应(gzip 压缩,响应头有 Content-Encoding: gzip 和 Content-Length),三种写法读回来是不是原样')
    path = '/gzip/9'; wirebytes = capture(sv.port, path); head, _, wb = wirebytes.partition(b'\r\n\r\n'); html = page(9); uri = sv.url(path)
    def describe(blk):
        got, b = read1(response_rec(uri, blk), True); hdr = {k.lower(): v for k, v in got.http_headers.headers}; stored = blk.partition(b'\r\n\r\n')[2]
        return f'warcio 读回 {len(b)} 字节,与原 HTML 相同:{b == html};记录里存的正文 {len(stored)} 字节,头里 Content-Length={hdr.get("content-length")},Content-Encoding={hdr.get("content-encoding")};存的正文与服务器发出的字节相同:{stored == wb}'
    print(f'  (a) 套接字上的字节原样:{describe(wirebytes)}')
    import requests
    s = requests.Session(); resp = s.get(uri); dec = resp.content
    print(f'  (b) requests 的 .content(是解压后的 {len(dec)} 字节)接在原样的头后面:{describe(head + b"\r\n\r\n" + dec)}')
    h2 = b'\r\n'.join(l for l in head.split(b'\r\n') if not l.lower().startswith((b'content-encoding', b'content-length'))) + b'\r\nContent-Length: %d' % len(dec)
    print(f'  (c) 解压后的正文,头里去掉 Content-Encoding、Content-Length 改成解压后的长度:{describe(h2 + b"\r\n\r\n" + dec)}')
    raw = s.get(uri, stream=True).raw.read(decode_content=False)
    print(f'  从 requests 里拿原始字节:stream=True 后 resp.raw.read(decode_content=False) 得到 {len(raw)} 字节,与套接字上的正文相同:{raw == wb}')
    cwire = capture(sv.port, '/chunked/9'); cbody = cwire.partition(b'\r\n\r\n')[2]; cr = s.get(sv.url('/chunked/9'), stream=True)
    print(f'  chunked 的响应:套接字上的正文 {len(cbody)} 字节(含分块格式);requests 的 resp.raw 读出 {len(cr.raw.read(decode_content=False))} 字节(分块格式已经被去掉),而 resp.headers 里仍有 Transfer-Encoding: {cr.headers.get("Transfer-Encoding")}')
    print('== 三:5000 条响应(每条正文约 16 KB HTML,三种传输方式轮流)的存储大小和写入时间')
    N = 5000; kinds = ['plain', 'gzip', 'chunked']; recs = []
    t0 = time.perf_counter()
    for i in range(N):
        k = kinds[i % 3]; w, ent = wire(i, k); recs.append(response_rec(f'http://x.test/{k}/{i}', w))
    tb = time.perf_counter() - t0
    raw_total = sum(len(r) for r in recs); print(f'  构造 {N} 条记录:{tb:.2f} 秒;未压缩 WARC 共 {raw_total / 1048576:.1f} MiB(平均每条 {raw_total // N} 字节;其中 1/3 的正文本来就是 gzip 压缩过的,所以压缩率不高)')
    t0 = time.perf_counter(); open(d / 'a.warc', 'wb').write(b''.join(recs)); t_plain = time.perf_counter() - t0
    t0 = time.perf_counter(); members = [gz_member(r) for r in recs]; open(d / 'b.warc.gz', 'wb').write(b''.join(members)); t_member = time.perf_counter() - t0
    t0 = time.perf_counter(); open(d / 'c.warc.gz', 'wb').write(gzip.compress(b''.join(recs), 6)); t_whole = time.perf_counter() - t0
    for lab, fn, t in (('不压缩 .warc', 'a.warc', t_plain), ('每条记录单独 gzip(.warc.gz)', 'b.warc.gz', t_member), ('整个文件一个 gzip 流', 'c.warc.gz', t_whole)):
        print(f'  {lab:28s} {(d / fn).stat().st_size / 1048576:7.1f} MiB   写入 {t:.2f} 秒')
    try:
        n = sum(1 for _ in ArchiveIterator(open(d / 'c.warc.gz', 'rb'))); msg = f'读到 {n} 条'
    except Exception as e: msg = f'抛出 {type(e).__name__}:{str(e).strip().splitlines()[0][:80]}'
    print(f'  warcio 读整个文件一个 gzip 流的那个文件:{msg}')
    print('== 四:随机读取其中一条:有偏移索引(每条的 offset、长度)和没有索引时要多久')
    offs = []; o = 0
    for m in members: offs.append((o, len(m))); o += len(m)
    rr = random.Random(4); picks = [rr.randrange(N) for _ in range(200)]
    f = open(d / 'b.warc.gz', 'rb'); t0 = time.perf_counter()
    for k in picks: f.seek(offs[k][0]); b = gzip.decompress(f.read(offs[k][1])); assert b == recs[k]
    t_idx = (time.perf_counter() - t0) / len(picks) * 1000
    print(f'  每条单独 gzip + 偏移索引:读 200 次随机记录,平均每次 {t_idx:.3f} 毫秒,读出的字节和写入的完全一致')
    tgt = 3000; target = f'http://x.test/{kinds[tgt % 3]}/{tgt}'; t0 = time.perf_counter(); found = None
    with open(d / 'b.warc.gz', 'rb') as fh:
        for r in ArchiveIterator(fh):
            if r.rec_headers.get_header('WARC-Target-URI') == target: found = True; break
    t_scan = (time.perf_counter() - t0) * 1000
    print(f'  没有索引、按 URL 顺序扫描(warcio 迭代,目标是第 {tgt} 条):{t_scan:.0f} 毫秒({"找到" if found else "没找到"})')
    t0 = time.perf_counter(); data = gzip.decompress(open(d / 'c.warc.gz', 'rb').read()); t_whole_read = (time.perf_counter() - t0) * 1000
    print(f'  整个文件一个 gzip 流:解压整个文件 {t_whole_read:.0f} 毫秒(这里没有测增量解压到某个位置就停的情形)')
    print('== 五:内容重复时用 revisit 记录(只存头和指向第一次记录的引用)')
    full = revis = 0; seen = {}; nrev = 0
    for i in range(N):
        src = i - 7 if i % 10 >= 7 else i; k = kinds[src % 3]; w, ent = wire(src, k); uri = f'http://x.test/{k}/{i}'; pdg = b32sha1(w.partition(b'\r\n\r\n')[2])
        r_full = response_rec(uri, w); g = len(gz_member(r_full)); full += g
        if pdg in seen:
            hd = w.partition(b'\r\n\r\n')[0] + b'\r\n\r\n'
            r_rev = rec('revisit', uri, hd, extra=[('WARC-Profile', 'http://netpreserve.org/warc/1.1/revisit/identical-payload-digest'), ('WARC-Payload-Digest', pdg), ('WARC-Refers-To', seen[pdg])]); revis += len(gz_member(r_rev)); nrev += 1
        else: seen[pdg] = f'<urn:uuid:{uuid.UUID(int=i)}>'; revis += g
    print(f'  {N} 个 URL 里有 {nrev} 个(30%)的正文与前面某个 URL 的字节完全相同(例如同一页面带不同的跟踪参数):全部写完整记录(每条单独 gzip)共 {full / 1048576:.1f} MiB;重复的写成 revisit 记录共 {revis / 1048576:.1f} MiB,省下 {100 - revis * 100 / full:.0f}%')
    print('== 六:写到一半进程被杀(文件被截断在第 3000 条记录中间):能恢复多少条')
    cut = offs[3000][0] + offs[3000][1] // 2
    data = open(d / 'b.warc.gz', 'rb').read()[:cut]; n = 0; st = collections.Counter(); last = None
    for r in ArchiveIterator(io.BytesIO(data), check_digests=True):
        body = r.content_stream().read(); n += 1; st[r.digest_checker.passed] += 1; last = (int(r.rec_headers.get_header('Content-Length')), len(body) + len(r.http_headers.compute_headers_buffer()) if False else None, r.rec_headers.get_header('WARC-Target-URI'))
    print(f'  每条单独 gzip,截断在 {cut / 1048576:.1f} MiB:warcio 顺序读到 {n} 条,没有报错;摘要核对结果的分布 {dict(st)};最后一条是 {last[2]},头里声明的 Content-Length={last[0]}')
    t0 = time.perf_counter(); nm, endpos = walk_members(data); tw = time.perf_counter() - t0
    print(f'  用 zlib 逐个 gzip 成员地走:完整的成员 {nm} 个,最后一个完整成员结束在偏移 {endpos},文件被截断多出 {len(data) - endpos} 字节;把文件截到 {endpos} 就能继续追加(走一遍用了 {tw:.2f} 秒)')
    print(f'  有偏移索引时:第 3000 条在索引里的结束偏移 {offs[3000][0] + offs[3000][1]} 大于文件大小 {len(data)},判定为不完整;前面的记录不受影响')
    whole = open(d / 'c.warc.gz', 'rb').read(); wcut = whole[:len(whole) * 3000 // N]
    dz = zlib.decompressobj(31); pre = dz.decompress(wcut); nc, _ = count_complete(pre)
    print(f'  整个文件一个 gzip 流,同样按位置比例(3000/{N})截断在 {len(wcut) / 1048576:.1f} MiB:zlib 流式解压能得到 {len(pre) / 1048576:.1f} MiB 的未压缩数据,自己解析 Content-Length 数出完整记录 {nc} 条;但 warcio 不认这种文件(见第三节)')
purge()
