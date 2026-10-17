import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s49'); reset_s()
def srv(h): time.sleep(0.5); h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
SP = """
import scrapy, resource, time
class S(scrapy.Spider):
    name = 's'
    async def start(self):
        r0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        t0 = time.perf_counter()
        for i in range(@N@):
            yield scrapy.Request('@U@/page/%d' % i, meta={'blob': str(i).zfill(8) * (@META@ // 8)} if @META@ else None, dont_filter=True)
        eng = self.crawler.engine
        EV(e='start 结束', secs=round(time.perf_counter() - t0, 2), queued=len(eng.scheduler), rss_delta_mb=round((resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - r0) / 1048576, 1))
    def parse(self, response): pass
"""
def run(n, meta=0, jobdir=False, tag='s49'):
    d = sdir(tag)
    with Srv(srv) as s:
        st = {'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1, 'CONCURRENT_REQUESTS_PER_DOMAIN': 1, 'CLOSESPIDER_TIMEOUT': 6, 'SCHEDULER_START_MEMORY_QUEUE': 'scrapy.squeues.LifoMemoryQueue', 'SCHEDULER_START_DISK_QUEUE': 'scrapy.squeues.PickleLifoDiskQueue'}
        if jobdir: st['JOBDIR'] = str(sdir('s49job'))
        rc, out, t = runspider(d, SP.replace('@N@', str(n)).replace('@META@', str(meta)).replace('@U@', s.url('').rstrip('/')), st, timeout=300)
    E = [x for x in ev(d) if x.get('e') == 'start 结束']
    return E[0] if E else {}, stats(out), d
print('== 一:start() 一口气 yield N 个请求(下载很慢,请求都积压在调度器里):内存队列 vs JOBDIR 磁盘队列——start() 耗时、调度器里的积压数、RSS 增量(ru_maxrss,MiB)')
print(f'  {"N":>8}{"队列":<20}{"start() 耗时 s":>14}{"积压":>9}{"RSS 增量 MiB":>14}{"每个请求约 KiB":>16}')
for n in (10000, 50000):
    for jd in (False, True):
        E, st, d = run(n, jobdir=jd)
        if not E: print(f'  {n:>8}{"磁盘 JOBDIR" if jd else "内存":<20}(没有结果)'); continue
        print(f'  {n:>8}{"磁盘 JOBDIR" if jd else "内存":<20}{E["secs"]:>14}{E["queued"]:>9}{E["rss_delta_mb"]:>14}{E["rss_delta_mb"] * 1024 / n:>16.2f}')
print('== 二:请求带 1 KB 的 meta 时的内存(50,000 个,内存队列)')
E, st, d = run(50000, meta=1024)
print(f'  无 meta:见上一节;带 1 KB meta:RSS 增量 {E["rss_delta_mb"]} MiB(每个请求约 {E["rss_delta_mb"] * 1024 / 50000:.2f} KiB),start() 耗时 {E["secs"]} s')
print('== 三:JOBDIR 目录大小(50,000 个请求落盘后)')
E, st, d = run(50000, jobdir=True)
jd = SD / 's49job'
tot = sum(p.stat().st_size for p in jd.rglob('*') if p.is_file())
print(f'  JOBDIR 总大小 {tot / 1048576:.1f} MiB,每个请求约 {tot / 50000:.0f} 字节;文件:' + ', '.join(f'{p.name}={p.stat().st_size // 1024} KiB' for p in sorted(jd.rglob('*')) if p.is_file() and p.stat().st_size > 1024))
