import sys, os, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s3'); reset_s()
SP = '''
import scrapy, time
class A(scrapy.Spider):
    name = 'a'
    async def start(self):
        for i in range(@N@): yield scrapy.Request('@U@/a%d' % i, dont_filter=True)
    def parse(self, r): pass
SET = {'LOG_LEVEL': 'ERROR', 'TELNETCONSOLE_ENABLED': False, 'REMOTE_CONTROL_ENABLED': False, 'CONCURRENT_REQUESTS': 10}
'''
def slow(h): time.sleep(0.3); h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
def sp(s, n=10): return SP.replace('@U@', s.url('').rstrip('/')).replace('@N@', str(n))
def last(out, n=1): return ' | '.join(l.strip() for l in out.split('\n') if l.strip())[-300:] if out else '(无输出)'

print('== 一:CrawlerProcess / AsyncCrawlerProcess 的 start() 只能调一次:第二次 start 会怎样(每次爬 10 个各延迟 0.3 s 的页面,并发 10)')
d = sdir('s3a')
with Srv(slow) as s:
    for cls in ('CrawlerProcess', 'AsyncCrawlerProcess'):
        rc, out, t = py(d, sp(s) + f'''
from scrapy.crawler import {cls}
p = {cls}(SET)
p.crawl(A); t0 = time.perf_counter(); p.start(); print('第一次 start() 返回,耗时 %.2f s' % (time.perf_counter() - t0))
try:
    p.crawl(A); p.start(); print('第二次 start() 也返回了')
except BaseException as e: print('第二次:', type(e).__module__ + '.' + type(e).__name__, e)
''')
        print(f'  $ {cls}(SET); p.crawl(A); p.start(); p.crawl(A); p.start()')
        for l in out.split('\n'): print('    ' + l)

print('== 二:同一个进程里跑两个 spider:CrawlerProcess 并发,CrawlerRunner 链式顺序(各 10 个页面,并发 10,延迟 0.3 s)')
d = sdir('s3b')
with Srv(slow) as s:
    rc, out, t = py(d, sp(s) + '''
from scrapy.crawler import CrawlerProcess
class B(A): name = 'b'
p = CrawlerProcess(SET)
p.crawl(A); p.crawl(B); t0 = time.perf_counter(); p.start()
print('CrawlerProcess:crawl(A); crawl(B); start()  总耗时 %.2f s' % (time.perf_counter() - t0))
''')
    print('  ' + out); n1 = len(s.log)
with Srv(slow) as s:
    rc, out, t = py(d, sp(s) + '''
from scrapy.utils.reactor import install_reactor
install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')
from scrapy.crawler import CrawlerRunner
from twisted.internet import reactor, defer
class B(A): name = 'b'
r = CrawlerRunner(SET)
@defer.inlineCallbacks
def run():
    yield r.crawl(A); yield r.crawl(B); reactor.stop()
t0 = time.perf_counter(); run(); reactor.run()
print('CrawlerRunner:yield crawl(A); yield crawl(B)  总耗时 %.2f s' % (time.perf_counter() - t0))
''')
    print('  ' + out); n2 = len(s.log)
print(f'  两种方式服务器收到的请求数:{n1}、{n2}(都是 2 × 10)')

print('== 三:CrawlerRunner 要自己管 reactor:没装、装了不停、正确写法')
d = sdir('s3c')
with Srv(slow) as s:
    rc, out, t = py(d, sp(s) + '''
from scrapy.crawler import CrawlerRunner
r = CrawlerRunner(SET); d = r.crawl(A)
''')
    print(f'  (a) 没有先 install_reactor 就 CrawlerRunner(SET).crawl(A):退出码 {rc}')
    print('      ' + [l for l in out.split('\n') if 'RuntimeError' in l][-1].strip())
    rc, out, t = py(d, sp(s) + '''
from scrapy.utils.reactor import install_reactor
install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')
from scrapy.crawler import CrawlerRunner
from twisted.internet import reactor
r = CrawlerRunner(SET); d = r.crawl(A)
d.addBoth(lambda _: print('crawl 的 Deferred 触发了'))
reactor.run(); print('reactor.run() 返回了')
''', timeout=5)
    print(f'  (b) 装了 reactor,crawl 结束后没有 reactor.stop():5 秒内输出 {out!r},退出码 {rc}(-9 = 超时被杀:Deferred 触发了,但 reactor.run() 一直不返回,进程不会自己退出)')
    rc, out, t = py(d, sp(s) + '''
from scrapy.utils.reactor import install_reactor
install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')
from scrapy.crawler import CrawlerRunner
from twisted.internet import reactor
r = CrawlerRunner(SET); d = r.crawl(A)
d.addBoth(lambda _: reactor.stop())
reactor.run(); print('reactor.run() 返回了')
''', timeout=10)
    print(f'  (c) d.addBoth(lambda _: reactor.stop()):{out!r},退出码 {rc},耗时 {t:.2f} s')

print('== 四:在 asyncio 程序里用 AsyncCrawlerRunner:装了 asyncio reactor 再 asyncio.run 会卡死;不用 reactor(TWISTED_REACTOR_ENABLED=False)或用 reactor 自己的循环才行')
d = sdir('s3d')
CASE4 = [('装了 asyncio reactor + asyncio.run(main())', '''
import asyncio
from scrapy.utils.reactor import install_reactor
install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')
from scrapy.crawler import AsyncCrawlerRunner
async def main():
    r = AsyncCrawlerRunner(SET)
    await r.crawl(A); print('crawl 1 完成'); await r.crawl(A); print('crawl 2 完成')
asyncio.run(main()); print('asyncio.run 返回')
'''), ('TWISTED_REACTOR_ENABLED=False + asyncio.run(main())', '''
import asyncio
from scrapy.crawler import AsyncCrawlerRunner
async def main():
    r = AsyncCrawlerRunner(dict(SET, TWISTED_REACTOR_ENABLED=False))
    await r.crawl(A); print('crawl 1 完成'); await r.crawl(A); print('crawl 2 完成')
asyncio.run(main()); print('asyncio.run 返回')
'''), ('装了 asyncio reactor + Deferred.fromFuture(main()) + reactor.run()', '''
import asyncio
from scrapy.utils.reactor import install_reactor
install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')
from scrapy.crawler import AsyncCrawlerRunner
from twisted.internet import reactor, defer
async def main():
    r = AsyncCrawlerRunner(SET)
    await r.crawl(A); print('crawl 1 完成'); await r.crawl(A); print('crawl 2 完成'); reactor.stop()
defer.Deferred.fromFuture(asyncio.ensure_future(main())); reactor.run(); print('reactor.run 返回')
''')]
with Srv(slow) as s:
    for tag, code in CASE4:
        rc, out, t = py(d, sp(s) + code, timeout=8)
        lines = [l for l in out.split('\n') if l.strip() and 'AiohttpDownloadHandler' not in l]
        print(f'  {tag}:退出码 {rc},耗时 {t:.1f} s;输出 {" / ".join(lines) if lines else "(无)"}' + ('(8 秒超时被杀,卡死)' if rc == -9 else ''))

print('== 五:Ctrl-C:CrawlerProcess 装了信号处理——第一次 SIGINT 优雅停止,第二次强制退出(爬 40 个各延迟 3 s 的页面,并发 4)')
def vslow(h): time.sleep(3); h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
d = sdir('s3e')
def run_sig(sigs, gap):
    with Srv(vslow) as s:
        write(d, 'sig.py', sp(s, 40).replace("'LOG_LEVEL': 'ERROR'", "'LOG_LEVEL': 'INFO', 'LOG_FORMAT': '[%(name)s] %(levelname)s: %(message)s'").replace("'CONCURRENT_REQUESTS': 10", "'CONCURRENT_REQUESTS': 4, 'CONCURRENT_REQUESTS_PER_DOMAIN': 4") + '''
from scrapy.crawler import CrawlerProcess
p = CrawlerProcess(SET); p.crawl(A); p.start(); print('start() 返回')
''')
        e = dict(os.environ); e.pop('PYTHONPATH', None)
        t0 = time.perf_counter(); pr_ = subprocess.Popen([SPY, 'sig.py'], cwd=d, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=e)
        time.sleep(1.5)
        for i in range(sigs):
            pr_.send_signal(signal.SIGINT); time.sleep(gap)
        try: o = pr_.communicate(timeout=20)[0]
        except subprocess.TimeoutExpired: pr_.kill(); o = pr_.communicate()[0] + '\n[超时被杀]'
        return stidy(o), time.perf_counter() - t0, pr_.returncode, s
for tag, sigs, gap in (('发一次 SIGINT', 1, 0.2), ('间隔 0.5 s 连发两次 SIGINT', 2, 0.5)):
    o, el, rc, s = run_sig(sigs, gap)
    L = o.split('\n'); sx = stats(o)
    print(f'  {tag}:进程退出码 {rc},从启动到退出共 {el:.1f} s(第 1.5 s 发的信号)')
    for l in L:
        if any(k in l for k in ('Received SIGINT', 'Closing spider', 'start() 返回', 'KeyboardInterrupt')): print('      ' + l.strip())
    print(f'      finish_reason={sx.get("finish_reason")};response_received_count={sx.get("response_received_count")};服务器收到 {len(s.log)} 个请求')
