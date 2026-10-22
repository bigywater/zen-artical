import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import struct, math
from compression import zstd
tee('v82'); reset()
print('指标的存储与压缩:时序数据怎么编码。(一)我按 Gorilla 论文写的编码器(时间戳用 delta-of-delta,数值用与前一个值的 XOR),先验证能无损还原,再看不同形状的数据每个样本占多少位;(二)Prometheus 3.15.0 真实存下来的 chunk 每个样本占多少字节,和我的编码器在同一批样本上的结果比较;(三)索引占多少。注意:我的是论文版本,Prometheus 的 XOR chunk 在时间戳的位宽等细节上不同,所以两者只能大致对照')
class BW:
    def __init__(self): self.buf = bytearray(); self.nbits = 0
    def bit(self, b):
        if self.nbits % 8 == 0: self.buf.append(0)
        if b: self.buf[-1] |= 1 << (7 - self.nbits % 8)
        self.nbits += 1
    def bits(self, v, n):
        for i in range(n - 1, -1, -1): self.bit((v >> i) & 1)
class BR:
    def __init__(self, buf, nbits): self.buf, self.n, self.i = buf, nbits, 0
    def bit(self): b = (self.buf[self.i // 8] >> (7 - self.i % 8)) & 1; self.i += 1; return b
    def bits(self, n):
        v = 0
        for _ in range(n): v = (v << 1) | self.bit()
        return v
def f2u(x): return struct.unpack('>Q', struct.pack('>d', x))[0]
def u2f(u): return struct.unpack('>d', struct.pack('>Q', u))[0]
def enc(samples):
    """samples: [(ts_ms, value)];返回 (BW, ts_bits, val_bits)"""
    w = BW(); tb = vb = 0
    t0, v0 = samples[0]; w.bits(t0, 64); w.bits(f2u(v0), 64)
    prev_t, prev_d, prev_u = t0, 0, f2u(v0); pl, pt = 99, 99     # 99 表示还没有可复用的窗口
    for t, v in samples[1:]:
        n0 = w.nbits; d = t - prev_t; dod = d - prev_d
        if dod == 0: w.bit(0)
        elif -64 <= dod <= 63: w.bits(0b10, 2); w.bits(dod & 0x7F, 7)
        elif -256 <= dod <= 255: w.bits(0b110, 3); w.bits(dod & 0x1FF, 9)
        elif -2048 <= dod <= 2047: w.bits(0b1110, 4); w.bits(dod & 0xFFF, 12)
        else: w.bits(0b1111, 4); w.bits(dod & 0xFFFFFFFF, 32)
        tb += w.nbits - n0; prev_t, prev_d = t, d
        n0 = w.nbits; u = f2u(v); x = u ^ prev_u
        if x == 0: w.bit(0)
        else:
            lz = min(64 - x.bit_length(), 31); tz = (x & -x).bit_length() - 1
            if pl != 99 and lz >= pl and tz >= pt:
                w.bit(1); w.bit(0); w.bits(x >> pt, 64 - pl - pt)
            else:
                w.bit(1); w.bit(1); w.bits(lz, 5); sig = 64 - lz - tz; w.bits(sig & 0x3F, 6); w.bits(x >> tz, sig); pl, pt = lz, tz
        vb += w.nbits - n0; prev_u = u
    return w, tb, vb
def dec(buf, nbits, n):
    r = BR(buf, nbits); t = r.bits(64); u = r.bits(64); out = [(t, u2f(u))]; prev_d = 0; pl = pt = 0
    for _ in range(n - 1):
        if r.bit() == 0: dod = 0
        else:
            if r.bit() == 0: dod = r.bits(7); dod = dod - 128 if dod >= 64 else dod
            elif r.bit() == 0: dod = r.bits(9); dod = dod - 512 if dod >= 256 else dod
            elif r.bit() == 0: dod = r.bits(12); dod = dod - 4096 if dod >= 2048 else dod
            else: dod = r.bits(32); dod = dod - (1 << 32) if dod >= (1 << 31) else dod
        d = prev_d + dod; t += d; prev_d = d
        if r.bit() == 0: x = 0
        else:
            if r.bit() == 0: x = r.bits(64 - pl - pt) << pt
            else:
                pl = r.bits(5); sig = r.bits(6) or 64; pt = 64 - pl - sig; x = r.bits(sig) << pt
        u ^= x; out.append((t, u2f(u)))
    return out

# ============ 一 ============
print('== 一:不同形状的数据每个样本占多少位。每种 3600 个样本(1 秒一个点,共 1 小时)。先验证编码后能无损还原;再看时间戳部分、数值部分各占多少位/样本,总共占多少字节,和“每个样本 16 字节”(8 字节时间戳 + 8 字节浮点)、“把这 16 字节的原始数据整体交给 zstd(级别 3)”比较')
rnd = random.Random(4); N = 3600; T0 = 1_790_000_000_000
def mk(kind):
    ts_exact = [T0 + i * 1000 for i in range(N)]
    ts_jit = [T0 + i * 1000 + rnd.randrange(-5, 6) for i in range(N)]
    if kind == 'const': return [(t, 42.0) for t in ts_exact]
    if kind == 'counter_fixed': return [(t, float(10 * i)) for i, t in enumerate(ts_exact)]
    if kind == 'counter_rand':
        c = 0.0; out = []
        for t in ts_exact: c += rnd.randrange(0, 40); out.append((t, c))
        return out
    if kind == 'gauge_step': return [(t, float(rnd.choice([20, 20, 20, 21, 20, 19]))) for t in ts_exact]
    if kind == 'gauge_float':
        v = 0.5; out = []
        for t in ts_exact: v = min(1, max(0, v + rnd.gauss(0, 0.02))); out.append((t, v))
        return out
    if kind == 'gauge_rand_float': return [(t, rnd.random()) for t in ts_exact]
    if kind == 'counter_jitter': return [(t, float(10 * i)) for i, t in enumerate(ts_jit)]
    if kind == 'counter_irregular':
        t = T0; out = []; c = 0.0
        for i in range(N): t += rnd.randrange(500, 1500); c += 10; out.append((t, c))
        return out
KINDS = [('const', '恒定值'), ('counter_fixed', '计数器,每秒固定 +10,时间间隔恰好 1 s'), ('counter_rand', '计数器,每秒随机 +0~39'), ('gauge_step', '整数 gauge,在 19~21 之间跳'), ('gauge_float', '浮点 gauge,随机游走(σ = 0.02)'), ('gauge_rand_float', '浮点 gauge,每次完全随机'), ('counter_jitter', '计数器 +10,时间戳有 ±5 ms 抖动'), ('counter_irregular', '计数器 +10,时间间隔在 0.5~1.5 s 之间随机')]
rows = []; allok = True
for kind, label in KINDS:
    s = mk(kind); w, tb, vb = enc(s); back = dec(bytes(w.buf), w.nbits, len(s)); ok = back == s; allok &= ok
    raw = b''.join(struct.pack('>qd', t, v) for t, v in s); z = len(zstd.compress(raw, 3)) if hasattr(zstd, 'compress') else -1
    rows.append((label, '是' if ok else '否', f'{tb / (N - 1):.2f}', f'{vb / (N - 1):.2f}', len(w.buf), f'{len(w.buf) / N:.2f}', z))
table(rows, ['数据形状', '解码后与原样本完全一致', '时间戳 位/样本', '数值 位/样本', 'Gorilla 编码后字节数', '字节/样本', '16 字节原始数据交给 zstd -3 后的字节数'])
print(f'  所有形状都无损还原:{allok}。时间间隔恰好固定时,时间戳只要 1 位;计数器每秒固定 +10 时数值的 XOR 变化很小;随机浮点数几乎没得压缩(每个样本接近 64 位的数值部分);时间戳有抖动或间隔不规则时,delta-of-delta 不再为 0,时间戳部分增大到几位到十几位')

# ============ 二 ============
print('== 二:Prometheus 里真实的 chunk。一个 target 暴露 150 条序列:50 个计数器(每秒随机增加 0~19)、50 个浮点 gauge(随机游走)、50 个恒定值。Prometheus 每秒抓取,运行 300 s(每条序列 300 个左右的样本),然后打开 admin API 对 head 做快照(生成块),统计快照里 chunks 目录的字节数、index 文件的字节数、样本总数。再从 Prometheus 把同一批原始样本读出来,用我的编码器编码,比较')
state = {'c': [0.0] * 50, 'g': [0.5] * 50}; rg = random.Random(11)
def body():
    out = []
    for i in range(50): out.append(f'counter_{i} {state["c"][i]}'); out.append(f'gauge_{i} {state["g"][i]!r}'); out.append(f'const_{i} 7')
    return ('\n'.join(out) + '\n').encode()
svc = Svc(lambda h: h.reply(200, body(), {'Content-Type': 'text/plain; version=0.0.4'}), 'm'); stop = threading.Event()
def drv():
    k = 0
    while not stop.is_set():
        for i in range(50): state['c'][i] += rg.randrange(0, 20); state['g'][i] = min(1.0, max(0.0, state['g'][i] + rg.gauss(0, 0.02)))
        k += 1; time.sleep(max(0, T_START + k - time.time()))
T_START = time.time(); th = threading.Thread(target=drv, daemon=True); th.start()
prom = Prom('v82', f"""global:
  scrape_interval: 1s
scrape_configs:
  - job_name: lab
    static_configs:
      - targets: ['127.0.0.1:{svc.port}']
""", flags=['--web.enable-admin-api']).start()
time.sleep(300); stop.set(); th.join(2)
import http.client as hc
cn = hc.HTTPConnection('127.0.0.1', prom.port, timeout=60); cn.request('POST', '/api/v1/admin/tsdb/snapshot?skip_head=false'); r = cn.getresponse(); snap = json.loads(r.read()); cn.close()
sname = snap['data']['name']; sdir = prom.d / 'data' / 'snapshots' / sname
chunk_bytes = sum(p.stat().st_size for p in sdir.rglob('chunks/*')); index_bytes = sum(p.stat().st_size for p in sdir.rglob('index')); metas = [json.loads(p.read_text()) for p in sdir.rglob('meta.json')]
nsamp = sum(m['stats']['numSamples'] for m in metas); nser = sum(m['stats']['numSeries'] for m in metas); nchunks = sum(m['stats']['numChunks'] for m in metas)
res = prom.query('{job="lab",__name__=~"counter_.*|gauge_.*|const_.*"}[10m]'); mine = 0; mine_n = 0; kinds = collections.defaultdict(lambda: [0, 0, 0, 0]); tbits = vbits = 0
for sr in res:
    pts = [(int(round(float(t) * 1000)), float(v)) for t, v in sr['values']]
    if len(pts) < 2: continue
    w, tb, vb = enc(pts); assert dec(bytes(w.buf), w.nbits, len(pts)) == pts; mine += len(w.buf); mine_n += len(pts); tbits += tb; vbits += vb; k = sr['metric']['__name__'].split('_')[0]; kinds[k][0] += len(w.buf); kinds[k][1] += len(pts); kinds[k][2] += tb; kinds[k][3] += vb
table([('块里的序列数 / chunk 数 / 样本数', f'{nser} / {nchunks} / {nsamp:,}'), ('chunks 目录的字节数', f'{chunk_bytes:,}'), ('每个样本的 chunk 字节数(Prometheus)', f'{chunk_bytes / nsamp:.2f}'), ('index 文件的字节数', f'{index_bytes:,}'), ('每条序列的 index 字节数', f'{index_bytes / nser:.0f}'), ('我的编码器编码同一批样本(含各序列的 16 字节起始值,不含 chunk 头)', f'{mine:,} 字节,{mine / mine_n:.2f} 字节/样本'), ('未压缩(每个样本 16 字节)', f'{16 * nsamp:,} 字节')], ['项目', '结果'])
print('  分序列类型的结果(我的编码器;时间戳位/样本、数值位/样本、字节/样本):' + ';'.join(f'{k}:{v[2] / v[1]:.2f}、{v[3] / v[1]:.2f}、{v[0] / v[1]:.2f}' for k, v in sorted(kinds.items())) + f';全部序列平均:时间戳 {tbits / mine_n:.2f} 位/样本、数值 {vbits / mine_n:.2f} 位/样本。这批样本都解码回来与原样本逐个相同(断言通过)')
print(f'  Prometheus 里每个样本平均占 {chunk_bytes / nsamp:.2f} 字节(chunks 目录,含 chunk 头),我的编码器是 {mine / mine_n:.2f} 字节;三种类型差别很大:计数器和恒定值很省,随机游走的浮点 gauge 几乎压不动,是主要的开销。恒定值序列也不是几乎免费——真实的抓取时间戳有毫秒级抖动(见上一组的“时间戳 位/样本”),时间戳部分比理想的 1 位大。我的编码器是论文版本,和 Prometheus 的 chunk 格式在时间戳位宽、chunk 头(每个 chunk 有样本数、校验和)等细节上不同,两个字节数在同一个量级,不要求相等')
prom.stop(); svc.stop()

# ============ 三 ============
print('== 三:压缩之外还有什么。上面 150 条序列、300 秒的块,拆开看磁盘上各部分的大小(chunks、index、meta、tombstones),并估算这 150 条序列每天(86400 个 1 秒间隔样本)需要的 chunk 空间(按上面测到的每样本字节数线性外推,算出来的)')
parts = {}
for p in sdir.rglob('*'):
    if p.is_file(): parts[p.name if p.parent.name != 'chunks' else 'chunks/*'] = parts.get(p.name if p.parent.name != 'chunks' else 'chunks/*', 0) + p.stat().st_size
table([(k, f'{v:,}') for k, v in sorted(parts.items())], ['快照里的文件', '字节数'])
per_day = chunk_bytes / nsamp * 86400 * nser
print(f'  按每样本 {chunk_bytes / nsamp:.2f} 字节外推:{nser} 条序列 × 86400 个样本 = {nser * 86400:,} 个样本,约 {per_day / 1e6:.1f} MB/天(算出来的);序列数多、标签多时 index 的占比会变大(上面每条序列的 index 约 {index_bytes / nser:.0f} 字节,和样本数无关)')
print('ERRORS', dict(ERRORS))
