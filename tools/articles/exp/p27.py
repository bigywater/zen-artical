import sys, os, asyncio, random, aiohttp; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p27')
DELAYS = {'A': 0.01, 'C': 0.1, 'B': 1.0}      # A 很快,C 中等,B 很慢
COUNTS = {'A': 100, 'C': 100, 'B': 30}
def mk(delay): return lambda h: (time.sleep(delay), h.reply(200, b'ok'))[1]
servers = {k: Srv(mk(v)) for k, v in DELAYS.items()}
for s in servers.values(): s.th.start()

def urls_grouped(order): return [(k, servers[k].url(f'/{i}')) for k in order for i in range(COUNTS[k])]
def urls_shuffled(seed=1):
    u = urls_grouped('ACB'); random.Random(seed).shuffle(u); return u

async def global_fifo(urls, workers):
    for x in servers.values(): x.reset()
    q = asyncio.Queue()
    for u in urls: q.put_nowait(u)
    done = {k: [] for k in DELAYS}; t0 = time.perf_counter()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
        async def worker():
            while True:
                try: k, u = q.get_nowait()
                except asyncio.QueueEmpty: return
                async with s.get(u) as r: await r.read()
                done[k].append(time.perf_counter() - t0)
        await asyncio.gather(*[worker() for _ in range(workers)])
    return done

async def per_domain(urls, per_dom):
    for x in servers.values(): x.reset()
    qs = {k: asyncio.Queue() for k in DELAYS}
    for k, u in urls: qs[k].put_nowait((k, u))
    done = {k: [] for k in DELAYS}; t0 = time.perf_counter()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
        async def worker(k):
            while True:
                try: _, u = qs[k].get_nowait()
                except asyncio.QueueEmpty: return
                async with s.get(u) as r: await r.read()
                done[k].append(time.perf_counter() - t0)
        await asyncio.gather(*[worker(k) for k in DELAYS for _ in range(per_dom)])
    return done

def line(done):
    allt = max(max(v) for v in done.values())
    return f'全部完成 {allt:.1f} 秒;A(快站点,100 个)全部完成于 {max(done["A"]):.1f} 秒,中位完成时刻 {median(done["A"]):.1f} 秒;C(中等,100 个)完成于 {max(done["C"]):.1f} 秒;B(慢站点,30 个)完成于 {max(done["B"]):.1f} 秒;各站点收到的并发峰值 A={servers["A"].peak} C={servers["C"].peak} B={servers["B"].peak}'

print('(三个站点:A 每个请求 0.01 秒、C 0.1 秒、B 1.0 秒;URL 数量 A 100 个、C 100 个、B 30 个)')
print('== 一:一个全局先进先出队列,10 个 worker,URL 随机打乱')
print('  ' + line(asyncio.run(global_fifo(urls_shuffled(), 10))))
print('== 二:同样的全局队列和 10 个 worker,但 URL 按站点分组(爬虫常见:先从一个站点发现的一批链接),慢站点排在最前面')
print('  慢站点 B 排最前:' + line(asyncio.run(global_fifo(urls_grouped('BAC'), 10))))
print('  快站点 A 排最前:' + line(asyncio.run(global_fifo(urls_grouped('ACB'), 10))))
print('== 三:每个站点自己的队列和 3 个 worker(共 9 个并发),URL 顺序同上')
print('  慢站点 B 排最前:' + line(asyncio.run(per_domain(urls_grouped('BAC'), 3))))
print('  快站点 A 排最前:' + line(asyncio.run(per_domain(urls_grouped('ACB'), 3))))
print('== 四:每个站点的并发数不同时的取舍(慢站点排最前,其余同上)')
for pd in (1, 3, 6):
    print(f'  每个站点 {pd} 个 worker(共 {pd * 3} 个并发):' + line(asyncio.run(per_domain(urls_grouped('BAC'), pd))))
for s in servers.values(): s.stop()
purge()
