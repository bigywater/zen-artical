import sys, os, subprocess, pickle; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ec import *
from pl import free_port
import redis, brotli
tee('e22')
d = pdir('e22'); sys.path.insert(0, str(d))
(d / 't.proto').write_text('syntax = "proto3"; package t; message Meta { string referrer = 1; int32 priority = 2; repeated string tags = 3; } message Task { string url = 1; int32 depth = 2; string parent = 3; int32 retry = 4; string ua = 5; string accept_language = 6; Meta meta = 7; int64 enqueued = 8; }')
subprocess.run(['protoc', f'--python_out={d}', f'--proto_path={d}', str(d / 't.proto')], check=True)
import t_pb2
P_ = free_port(9700)
srv = subprocess.Popen(['redis-server', '--port', str(P_), '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--dir', str(d), '--daemonize', 'no'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
r = redis.Redis(port=P_)
for _ in range(100):
    try: r.ping(); break
    except Exception: time.sleep(0.05)
UA = 'MyCrawler/1.0 (+https://example.org/bot.html; ops@example.org)'
def tasks(n, seed=22):
    rr = random.Random(seed)
    return [{'url': f'https://shop.example.com/category/{rr.randrange(97)}/item/{rr.randrange(5000000)}?ref=list&page={rr.randrange(40)}', 'depth': rr.randrange(6), 'parent': f'https://shop.example.com/category/{rr.randrange(97)}/', 'retry': rr.choice([0, 0, 0, 1, 2]),
             'ua': UA, 'accept_language': 'zh-CN,zh;q=0.9,en;q=0.8', 'meta': {'referrer': 'https://shop.example.com/', 'priority': rr.randrange(10), 'tags': rr.sample(TAGS, 2)}, 'enqueued': 1760000000 + rr.randrange(86400)} for _ in range(n)]
def pbt(x):
    m = t_pb2.Task(url=x['url'], depth=x['depth'], parent=x['parent'], retry=x['retry'], ua=x['ua'], accept_language=x['accept_language'], enqueued=x['enqueued']); m.meta.referrer = x['meta']['referrer']; m.meta.priority = x['meta']['priority']; m.meta.tags.extend(x['meta']['tags']); return m.SerializeToString()
def used(): return r.info('memory')['used_memory']
def netin(): return r.info('stats')['total_net_input_bytes']
NT = 100000; T = tasks(NT); Ttrain = tasks(5000, seed=5)
SHORT = lambda x: {'u': x['url'], 'd': x['depth'], 'p': x['parent'], 'r': x['retry'], 'm': [x['meta']['priority'], x['meta']['tags'], x['enqueued']]}   # 常量(UA、语言、referrer)不进任务体
zc = zstandard.ZstdCompressor(level=3)
def build_dict(enc): return zstandard.train_dictionary(8192, [enc(x) for x in Ttrain])
dj = build_dict(j); dm = build_dict(msgpack.packb); dp = build_dict(pbt)
ENC = [('JSON', j), ('JSON(常量字段不进任务体)', lambda x: j(SHORT(x))), ('MessagePack', msgpack.packb), ('Protobuf', pbt), ('pickle(只在可信环境用)', pickle.dumps),
       ('JSON + zstd-3', lambda x: zc.compress(j(x))), ('JSON + zstd-3 + 字典', lambda x, z=zstandard.ZstdCompressor(level=3, dict_data=dj): z.compress(j(x))), ('Protobuf + zstd-3 + 字典', lambda x, z=zstandard.ZstdCompressor(level=3, dict_data=dp): z.compress(pbt(x))), ('JSON + lz4', lambda x: lz4.frame.compress(j(x)))]
print(f'== 一:一个爬虫任务体(url、深度、父页面、重试次数、UA、语言、meta……)的长度;任务样例:{j(T[0]).decode()[:240]}…')
print(f'  任务数 {NT};紧凑 JSON 平均 {sum(len(j(x)) for x in T[:2000]) / 2000:.0f} 字节')
print('== 二:10 万个任务放进 Redis 列表(RPUSH,pipeline 每批 500)后,Redis 实际多用的内存和网络入流量;服务器 redis-server(8.10.2),不持久化')
print(f'  {"编码":30s} {"平均载荷":>8s} {"Redis 内存增量":>12s} {"每任务内存":>9s} {"其中 Redis 自身开销":>14s} {"网络入流量":>10s}')
mem = {}
for lab, f in ENC:
    r.flushall(); r.execute_command('MEMORY', 'PURGE'); m0 = used(); n0 = netin(); payloads = [f(x) for x in T]
    for s in range(0, NT, 500):
        p = r.pipeline(False)
        for b in payloads[s:s + 500]: p.rpush('q', b)
        p.execute()
    m1 = used(); n1 = netin(); pl = sum(map(len, payloads)) / NT; mem[lab] = (m1 - m0) / NT
    print(f'  {lab:30s} {pl:8.1f} {(m1 - m0) / 1048576:10.1f}MiB {(m1 - m0) / NT:8.1f}B {(m1 - m0) / NT - pl:12.1f}B {(n1 - n0) / 1048576:8.1f}MiB')
print('== 三:放进去再取出来的吞吐:10 万个任务 RPUSH 之后 LPOP(单线程,pipeline 每批 500),含编码/压缩和解码的 CPU')
for lab, f in ENC:
    if lab.startswith('JSON(常量'): continue
    dec = {'JSON': json.loads, 'MessagePack': msgpack.unpackb, 'Protobuf': t_pb2.Task.FromString, 'pickle(只在可信环境用)': pickle.loads, 'JSON + zstd-3': lambda b: json.loads(zstandard.ZstdDecompressor().decompress(b)), 'JSON + zstd-3 + 字典': None, 'Protobuf + zstd-3 + 字典': None, 'JSON + lz4': lambda b: json.loads(lz4.frame.decompress(b))}[lab]
    if lab == 'JSON + zstd-3 + 字典': zdd = zstandard.ZstdDecompressor(dict_data=dj); dec = lambda b: json.loads(zdd.decompress(b))
    if lab == 'Protobuf + zstd-3 + 字典': zdd2 = zstandard.ZstdDecompressor(dict_data=dp); dec = lambda b: t_pb2.Task.FromString(zdd2.decompress(b))
    ts = []
    for _ in range(3):
        r.flushall(); t0 = time.perf_counter()
        for s in range(0, NT, 500):
            p = r.pipeline(False)
            for x in T[s:s + 500]: p.rpush('q', f(x))
            p.execute()
        t1 = time.perf_counter(); got = 0
        for s in range(0, NT, 500):
            p = r.pipeline(False)
            for _ in range(500): p.lpop('q')
            for b in p.execute(): dec(b); got += 1
        ts.append((t1 - t0, time.perf_counter() - t1))
    ts.sort(key=lambda t: sum(t)); a, b = ts[1]
    print(f'  {lab:30s} 入队 {NT / a:8.0f} 个/秒;出队 + 解码 {NT / b:8.0f} 个/秒')
print('== 四:把多个任务打包成一个 Redis 元素(每个元素 N 个任务,整体 zstd-3):内存和租约的粒度(第 66 篇的租约以"元素"为单位)')
print(f'  {"每元素任务数":>10s} {"元素数":>7s} {"Redis 内存增量":>12s} {"每任务内存":>9s}')
for k in (1, 10, 50, 200):
    r.flushall(); r.execute_command('MEMORY', 'PURGE'); m0 = used()
    for s in range(0, NT, 500 * k):
        p = r.pipeline(False)
        for e in range(s, min(NT, s + 500 * k), k): p.rpush('q', zc.compress(b'\n'.join(j(x) for x in T[e:e + k])))
        p.execute()
    m1 = used(); print(f'  {k:10d} {NT // k:7d} {(m1 - m0) / 1048576:10.1f}MiB {(m1 - m0) / NT:8.1f}B')
print('  (元素里装的任务越多,每个任务的内存越小,但一个 worker 取走一个元素就是取走 N 个任务,崩溃时要重新入队 N 个;租约、重试、去重都以元素为粒度)')
print('== 五:把页面缓存在 Redis 里(每页 13 KiB 的 HTML,5000 页):原样 / lz4 / zstd-3 / zstd-3 + 字典;内存与读取吞吐')
PGS = pages(5500); train_pg, pg = PGS[:500], PGS[500:]; dpg = zstandard.train_dictionary(65536, train_pg)
FM = [('原样', lambda b: b, lambda b: b), ('lz4', lz4.frame.compress, lz4.frame.decompress), ('zstd-3', zc.compress, zstandard.ZstdDecompressor().decompress), ('zstd-3 + 字典', zstandard.ZstdCompressor(level=3, dict_data=dpg).compress, zstandard.ZstdDecompressor(dict_data=dpg).decompress), ('brotli q5', lambda b: brotli.compress(b, quality=5), brotli.decompress)]
print(f'  {"存储方式":14s} {"平均值大小":>9s} {"Redis 内存增量":>13s} {"写入":>10s} {"读取 + 解压":>14s}')
for lab, enc, dec in FM:
    r.flushall(); r.execute_command('MEMORY', 'PURGE'); m0 = used(); vals = [enc(b) for b in pg]
    t0 = time.perf_counter()
    for s in range(0, len(pg), 50):
        p = r.pipeline(False)
        for i in range(s, min(len(pg), s + 50)): p.set(f'p:{i}', vals[i])
        p.execute()
    tw = time.perf_counter() - t0; m1 = used(); t0 = time.perf_counter(); ok = True
    for s in range(0, len(pg), 50):
        p = r.pipeline(False)
        for i in range(s, min(len(pg), s + 50)): p.get(f'p:{i}')
        for i, v in zip(range(s, s + 50), p.execute()): ok &= (dec(v) == pg[i])
    tr = time.perf_counter() - t0
    print(f'  {lab:14s} {sum(map(len, vals)) / len(vals):9.0f} {(m1 - m0) / 1048576:11.1f}MiB {len(pg) / tw:8.0f}/秒 {len(pg) / tr:11.0f}/秒 {"(解压校验通过)" if ok else "(校验失败)"}')
print('== 六:Redis 里每个元素自己的开销:同样 300 字节的载荷,放进列表元素 / 单独的 key / 哈希的 field,每个元素多占多少内存(10 万个)')
payload = lambda i: (b'%08d' % i) + b'x' * 292
for lab, fn in (('列表元素 RPUSH q', lambda p, i: p.rpush('q', payload(i))), ('单独的 key SET k:i', lambda p, i: p.set(b'k:%d' % i, payload(i))), ('哈希 field HSET h', lambda p, i: p.hset('h', b'%d' % i, payload(i))), ('集合成员 SADD s', lambda p, i: p.sadd('s', payload(i)))):
    r.flushall(); r.execute_command('MEMORY', 'PURGE'); m0 = used()
    for s in range(0, 100000, 500):
        p = r.pipeline(False)
        for i in range(s, s + 500): fn(p, i)
        p.execute()
    m1 = used(); print(f'  {lab:22s} 每个元素共占 {(m1 - m0) / 100000:6.1f} 字节(载荷 300 字节,额外 {(m1 - m0) / 100000 - 300:5.1f} 字节)')
try: r.shutdown(nosave=True)
except Exception: pass
try: srv.wait(5)
except Exception: srv.kill()
purge()
