import sys, os, json, time, hashlib, subprocess, textwrap, threading, random, statistics, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import redis
tee('p67')
d = pdir('p67'); P = free_port(9700)
srvp = subprocess.Popen(['redis-server', '--port', str(P), '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--dir', str(d), '--daemonize', 'no'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
r = redis.Redis(port=P)
for _ in range(100):
    try: r.ping(); break
    except Exception: time.sleep(0.05)
def url(i): return f'https://shop.example.com/category/{i % 97}/item/{i}?ref=list&page={i % 13}'
def used(): return r.info('memory')['used_memory']
def med(f, n=3): v = sorted(f() for _ in range(n)); return v[n // 2], v[0], v[-1]
CHILD = textwrap.dedent('''
    import sys, json, time, redis, random
    cfg = json.loads(sys.argv[1]); r = redis.Redis(port=cfg['port'], decode_responses=True); N = cfg['n']; mode = cfg['mode']
    def url(i): return f'https://shop.example.com/category/{i % 97}/item/{i}?ref=list&page={i % 13}'
    K, M = 7, cfg.get('m', 1 << 22)
    import hashlib
    def pos(u):
        h = hashlib.blake2b(u.encode(), digest_size=32).digest(); return [int.from_bytes(h[4 * j:4 * j + 4], 'big') % M for j in range(K)]
    while not r.exists('go'): time.sleep(0.001)
    mine = 0
    for i in range(N):
        u = url(i)
        if mode == 'check_then_add':
            if not r.sismember('seen', u): r.sadd('seen', u); mine += 1
        elif mode == 'sadd':
            if r.sadd('seen', u): mine += 1
        elif mode == 'bloom_check_then_set':
            ps = pos(u)
            if not all(r.getbit('bf', p) for p in ps):
                for p in ps: r.setbit('bf', p, 1)
                mine += 1
        elif mode == 'bloom_atomic':
            pipe = r.pipeline(transaction=True)
            for p in pos(u): pipe.setbit('bf', p, 1)
            if not all(pipe.execute()): mine += 1
    r.incrby('crawled', mine)
''')
open(d / 'child.py', 'w').write(CHILD)
def race(mode, workers=8, n=3000, m=1 << 22):
    r.flushall(); ps = [subprocess.Popen([sys.executable, str(d / 'child.py'), json.dumps(dict(port=P, n=n, mode=mode, m=m))]) for _ in range(workers)]
    time.sleep(0.8); r.set('go', 1)
    for p in ps: p.wait()
    return int(r.get('crawled') or 0)
try:
    print('== 一:8 个 worker 进程各自处理同一批 3000 个 URL(顺序相同,模拟多个 worker 同时拿到重复的链接),每个"新"URL 算抓一次。先查再加(SISMEMBER 然后 SADD)与直接用 SADD 的返回值(重复各跑 3 次)')
    for mode, lab in (('check_then_add', '先 SISMEMBER 再 SADD'), ('sadd', '只用 SADD 的返回值(1 = 新加入)')):
        res = [race(mode) for _ in range(3)]
        print(f'  {lab}:3 次实验抓取次数 {res}(不同 URL 一共 3000 个,多出来的是重复抓取)')
    print('== 二:内存:同一批 URL 用不同的数据结构保存(各存 30 万个 URL,每个约 70 字节;redis-server 8.10.2,INFO memory 的 used_memory 差值)')
    N = 300000; urls = [url(i) for i in range(N)]; avg = sum(len(u) for u in urls) / N
    print(f'  URL 平均 {avg:.0f} 字节')
    def mem(label, fn):
        r.flushall(); r.execute_command('MEMORY', 'PURGE'); b = used(); fn(); a = used(); print(f'  {label:44s} {(a - b) / 1048576:7.1f} MiB,平均每个 URL {(a - b) / N:6.1f} 字节')
    def add_set(items):
        p = r.pipeline(False)
        for k, it in enumerate(items):
            p.sadd('s', it)
            if k % 5000 == 4999: p.execute()
        p.execute()
    mem('SET:完整 URL 字符串', lambda: add_set(urls))
    print(f'    编码 {r.object("encoding", "s").decode()}')
    mem('SET:blake2b 8 字节摘要', lambda: add_set([hashlib.blake2b(u.encode(), digest_size=8).digest() for u in urls]))
    mem('SET:md5 16 字节摘要', lambda: add_set([hashlib.md5(u.encode()).digest() for u in urls]))
    def bloom():
        M = int(N * 9.6); K = 7; p = r.pipeline(False)
        for k, u in enumerate(urls):
            h = hashlib.blake2b(u.encode(), digest_size=32).digest()
            for j in range(K): p.setbit('bf', int.from_bytes(h[4 * j:4 * j + 4], 'big') % M, 1)
            if k % 2000 == 1999: p.execute()
        p.execute()
    mem('位图 Bloom(每个元素 9.6 位,7 个哈希)', bloom)
    M = int(N * 9.6); K = 7; fp = 0; probes = 100000
    for i in range(N, N + probes):
        h = hashlib.blake2b(url(i).encode(), digest_size=32).digest(); ps = [int.from_bytes(h[4 * j:4 * j + 4], 'big') % M for j in range(K)]
        pp = r.pipeline(False)
        for q in ps: pp.getbit('bf', q)
        if all(pp.execute()): fp += 1
    print(f'    对 {probes} 个没加入过的 URL 查询,Bloom 误判 {fp} 个 = {fp * 100 / probes:.2f}%(理论值约 1%)')
    def hll():
        p = r.pipeline(False)
        for k, u in enumerate(urls):
            p.pfadd('h', u)
            if k % 5000 == 4999: p.execute()
        p.execute()
    mem('HyperLogLog(只能数个数,不能判断是否见过)', hll)
    print(f'    PFCOUNT = {r.pfcount("h")}(真实 {N},误差 {abs(r.pfcount("h") - N) * 100 / N:.2f}%)')
    print(f'    8 字节摘要在 {N} 个 URL 里出现碰撞的概率 ≈ n²/2^65 = {N * N / 2 ** 65:.1e}(这是算出来的,没有实测)')
    print('== 三:吞吐:往 SET 里加 20 万个 URL(每个方式 3 次取中位数,括号为最小–最大)')
    urls2 = [url(i) for i in range(200000)]
    def t_single():
        r.flushall(); t0 = time.perf_counter()
        for u in urls2[:20000]: r.sadd('s', u)
        return 20000 / (time.perf_counter() - t0)
    def t_pipe(batch):
        def f():
            r.flushall(); t0 = time.perf_counter()
            for s in range(0, 200000, batch):
                p = r.pipeline(False)
                for u in urls2[s:s + batch]: p.sadd('s', u)
                p.execute()
            return 200000 / (time.perf_counter() - t0)
        return f
    def t_multi():
        r.flushall(); t0 = time.perf_counter()
        for s in range(0, 200000, 1000): r.sadd('s', *urls2[s:s + 1000])
        return 200000 / (time.perf_counter() - t0)
    for lab, f in (('逐个 SADD(一次往返一个,只跑 2 万个)', t_single), ('pipeline,每批 100 个(每个 SADD 都返回新/旧)', t_pipe(100)), ('pipeline,每批 1000 个', t_pipe(1000)), ('一条 SADD 带 1000 个成员(只返回新加入的个数)', t_multi)):
        m, lo, hi = med(f); print(f'  {lab:46s} 中位 {m:9.0f} 个/秒({lo:.0f}–{hi:.0f})')
    print('== 四:Bloom 过滤器的"查了再置位"与"置位并看旧值"(8 个 worker 处理同一批 3000 个 URL;位图 2^24 位(2 MiB),元素远少于容量)')
    for mode, lab in (('bloom_check_then_set', '先 GETBIT 全部检查,没见过再 SETBIT'), ('bloom_atomic', '在 MULTI/EXEC 里对 7 个位置 SETBIT,用返回的旧值判断')):
        res = [race(mode, m=1 << 24) for _ in range(3)]; print(f'  {lab}:3 次实验抓取次数 {res}(3000 个不同 URL;位图很大,Bloom 自身的误判可以忽略)')
    print('== 五:带过期时间的去重:SET key NX EX 2(2 秒内不重复抓,之后可以再抓)')
    r.flushall(); seq = []
    for k in range(3): seq.append(r.set('seen:a', 1, nx=True, ex=2) or None)
    time.sleep(2.2); seq.append(r.set('seen:a', 1, nx=True, ex=2) or None)
    print(f'  连续 3 次 SET NX EX 2 的返回:{seq[:3]};等 2.2 秒后再 SET NX:{seq[3]}(返回 True 表示拿到了,None 表示已存在)')
    def per_key(n=100000):
        r.flushall(); r.execute_command('MEMORY', 'PURGE'); b = used(); p = r.pipeline(False)
        for k in range(n):
            p.set(b'seen:' + hashlib.blake2b(url(k).encode(), digest_size=8).digest(), 1, nx=True, ex=86400)
            if k % 5000 == 4999: p.execute()
        p.execute(); return (used() - b) / n
    pk = per_key(); r.flushall(); r.execute_command('MEMORY', 'PURGE'); b = used(); add_set([hashlib.blake2b(url(k).encode(), digest_size=8).digest() for k in range(100000)]); ps = (used() - b) / 100000
    print(f'  10 万个 URL:每个 URL 一个带过期时间的 key(SET NX EX):平均每个 {pk:.0f} 字节;全部放进一个 SET(8 字节摘要):平均每个 {ps:.0f} 字节')
    print('== 六:一个超大的 SET 删除时会卡住别的请求吗(200 万个成员,另一个连接每 1 ms 发一次 PING 看延迟)')
    for how in ('DEL', 'UNLINK'):
        r.flushall(); add_set([hashlib.md5(url(k).encode()).digest() for k in range(2000000)])
        lat = []; stop = threading.Event()
        def ping():
            rr = redis.Redis(port=P)
            while not stop.is_set():
                t0 = time.perf_counter(); rr.ping(); lat.append((time.perf_counter() - t0) * 1000); time.sleep(0.001)
        th = threading.Thread(target=ping); th.start(); time.sleep(0.2); t0 = time.perf_counter(); r.execute_command(how, 's'); dt = (time.perf_counter() - t0) * 1000; time.sleep(0.3); stop.set(); th.join()
        print(f'  {how}:命令本身返回用了 {dt:.0f} ms;期间 PING 最大延迟 {max(lat):.0f} ms(共 {len(lat)} 次,中位 {statistics.median(lat):.2f} ms)')
finally:
    try: r.shutdown(nosave=True)
    except Exception: pass
    try: srvp.wait(5)
    except Exception: srvp.kill()
purge()
