import sys, os, asyncio, subprocess, concurrent.futures as cf; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import aiohttp, requests, lxml.html
ROW = '<tr class="r"><td><a href="/item/%d">商品 %d</a></td><td class="p">¥%d.00</td><td><span>库存 %d</span></td></tr>\n'
PAGE = ('<html><head><title>列表</title></head><body><table>' + ''.join(ROW % (i, i, i % 97, i % 13) for i in range(40000)) + '</table></body></html>').encode()
SMALL = b'<html><body>ok</body></html>'

def parse(body): return int(lxml.html.fromstring(body).xpath('count(//a)'))

def server(h):
    p = h.path.split('?')[0]
    if p == '/big': h.reply(200, PAGE)
    elif p == '/slow': time.sleep(0.1); h.reply(200, SMALL)
    else: h.reply(200, SMALL)

class Beat:
    """心跳:每 10 ms 醒一次,记录实际比预期晚了多久(事件循环被卡住的时间)。"""
    def __init__(self): self.lags = []; self.stop = False
    async def run(self):
        while not self.stop:
            t = time.perf_counter(); await asyncio.sleep(0.01); self.lags.append((time.perf_counter() - t - 0.01) * 1000)
    def summary(self): return f'心跳 {len(self.lags)} 次,最大延迟 {max(self.lags):.0f} ms,延迟超过 50 ms 的 {sum(1 for x in self.lags if x > 50)} 次'


def main():
    tee('p19')
    with Srv(server) as sv:
        print(f'== 一:先测基准:页面 {len(PAGE) / 1048576:.1f} MiB(4 万行表格),lxml 单次解析耗时')
        ts = []
        for _ in range(5):
            t0 = time.perf_counter(); n = parse(PAGE); ts.append(ms(t0))
        print(f'  lxml.html.fromstring + xpath 统计链接数:{n} 个链接,每次 {median(ts):.0f} ms(5 次中位数)')

        print('== 二:20 个并发抓取,抓完立刻解析。解析放在哪里,事件循环被卡多久')
        async def crawl(mode, n=20):
            beat = Beat(); bt = asyncio.create_task(beat.run()); loop = asyncio.get_running_loop()
            pool = cf.ProcessPoolExecutor(4) if mode == 'process' else None
            async with aiohttp.ClientSession() as s:
                async def one():
                    async with s.get(sv.url('/big')) as r: body = await r.read()
                    if mode == 'inline': return parse(body)
                    if mode == 'thread': return await loop.run_in_executor(None, parse, body)
                    return await loop.run_in_executor(pool, parse, body)
                if pool: await asyncio.gather(*[loop.run_in_executor(pool, int, 1) for _ in range(4)])   # 先把进程池预热,避免把进程启动算进去
                t0 = time.perf_counter(); res = await asyncio.gather(*[one() for _ in range(n)]); total = ms(t0)
            beat.stop = True; await bt
            if pool: pool.shutdown()
            return total, beat, res
        for mode, lab in (('inline', '直接在协程里解析(同步调用)'), ('thread', 'run_in_executor(None, …)(线程池)'), ('process', 'run_in_executor(ProcessPoolExecutor(4), …)(进程池)')):
            total, beat, res = asyncio.run(crawl(mode))
            print(f'  {lab}:20 个页面全部完成 {total:.0f} ms;{beat.summary()};解析结果一致 {set(res) == {80000 // 2}}')

    print('== 三:在协程里直接调用同步的 requests.get(服务器每个请求停 0.1 秒),10 个"并发"任务')
    with Srv(server) as sv:
        async def sync_in_coro():
            beat = Beat(); bt = asyncio.create_task(beat.run())
            async def one(): return requests.get(sv.url('/slow')).status_code
            t0 = time.perf_counter(); await asyncio.gather(*[one() for _ in range(10)]); total = ms(t0); beat.stop = True; await bt
            return total, beat
        async def async_ok():
            beat = Beat(); bt = asyncio.create_task(beat.run())
            async with aiohttp.ClientSession() as s:
                async def one():
                    async with s.get(sv.url('/slow')) as r: return r.status
                t0 = time.perf_counter(); await asyncio.gather(*[one() for _ in range(10)]); total = ms(t0)
            beat.stop = True; await bt; return total, beat
        async def to_thread():
            beat = Beat(); bt = asyncio.create_task(beat.run())
            async def one(): return (await asyncio.to_thread(requests.get, sv.url('/slow'))).status_code
            t0 = time.perf_counter(); await asyncio.gather(*[one() for _ in range(10)]); total = ms(t0); beat.stop = True; await bt
            return total, beat
        for fn, lab in ((sync_in_coro, '协程里直接 requests.get'), (async_ok, 'aiohttp'), (to_thread, 'asyncio.to_thread(requests.get, …)')):
            total, beat = asyncio.run(fn())
            print(f'  {lab}:10 个请求共 {total:.0f} ms;{beat.summary()};服务器同时处理的峰值 {sv.peak}')
            sv.reset()

    print('== 四:asyncio 调试模式怎么报告阻塞(PYTHONASYNCIODEBUG=1,slow_callback_duration 默认 0.1 秒)')
    CODE = r'''
    import asyncio, time
    async def main():
        time.sleep(0.35)      # 协程里的同步阻塞
    asyncio.run(main())
    '''
    d = pdir('p19'); import textwrap; (d / 'dbg.py').write_text(textwrap.dedent(CODE))
    o = subprocess.run([sys.executable, str(d / 'dbg.py')], capture_output=True, text=True, env={**os.environ, 'PYTHONASYNCIODEBUG': '1'})
    import re
    for l in o.stderr.splitlines():
        m = re.search(r'took ([\d.]+) seconds', l)
        if m: print(f"  Executing <Task finished name='Task-1' coro=<main() done, defined at …/dbg.py:3> … took {m.group(1)} seconds   (进程退出码 {o.returncode},这是 asyncio 记在 stderr 上的警告,不是异常)")
    purge()


if __name__ == '__main__':
    main()
