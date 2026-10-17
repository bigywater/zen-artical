import sys, os, signal, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s38'); reset_s()
class Site:
    def __init__(self): self.log = []
    def __call__(self, h):
        self.log.append(h.path)
        if h.path == '/': h.reply(200, '<html>' + ''.join(f'<a href="/p{i}">x</a>' for i in range(40)) + '</html>', {'Content-Type': 'text/html'}); return
        time.sleep(0.1); h.reply(200, f'<html>{h.path}</html>', {'Content-Type': 'text/html'})
SP = """
import scrapy
class S(scrapy.Spider):
    name = 'job'
    custom_settings = {'CONCURRENT_REQUESTS': 2, 'CONCURRENT_REQUESTS_PER_DOMAIN': 2, 'LOG_LEVEL': 'INFO', 'TELNETCONSOLE_ENABLED': False, 'REMOTE_CONTROL_ENABLED': False, 'SCHEDULER_MEMORY_QUEUE': 'scrapy.squeues.FifoMemoryQueue', 'SCHEDULER_DISK_QUEUE': 'scrapy.squeues.PickleFifoDiskQueue'}
    async def start(self): yield scrapy.Request('@U@/')
    def parse(self, response):
        if response.url.endswith('/'):
            for u in response.css('a::attr(href)').getall(): yield response.follow(u, callback=self.page, meta=META)
    def page(self, response):
        self.state['count'] = self.state.get('count', 0) + 1
        self.state.setdefault('urls', []).append(response.url.rsplit('/', 1)[-1])
"""
def start(d, sv_url, jobdir, meta='{}', extra_py='', sp=None):
    write(d, 'spider.py', (sp or SP).replace('@U@', sv_url).replace('META', meta) + extra_py)
    e = dict(os.environ); e.pop('PYTHONPATH', None); e['PYTHONUNBUFFERED'] = '1'
    return subprocess.Popen([SPY, '-m', 'scrapy', 'runspider', 'spider.py', '-s', f'JOBDIR={jobdir}'], cwd=d, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=e)
def run(d, sv, jobdir, kill_after=None, sig=signal.SIGINT, meta='{}', extra_py='', sp=None):
    n0 = len(sv.fn.log)
    p = start(d, sv.url('').rstrip('/'), jobdir, meta, extra_py, sp)
    if kill_after:
        time.sleep(kill_after); p.send_signal(sig)
    try: o = p.communicate(timeout=60)[0]
    except subprocess.TimeoutExpired: p.kill(); o = p.communicate()[0]
    return stidy(o), sv.fn.log[n0:]
def tree(jd):
    rows = []
    for p in sorted(jd.rglob('*')):
        if p.is_file(): rows.append((str(p.relative_to(jd)), p.stat().st_size))
    return rows
def pagesof(L): return [x for x in L if x.startswith('/p')]

d = sdir('s38'); jd = d / 'crawl-1'
with Srv(Site()) as s:
    sv = s.fn
    print('== 一:第 1 次运行(JOBDIR=crawl-1,并发 2,40 个页面每个 0.1 s)在 1.5 秒时按一次 Ctrl-C(SIGINT):优雅停止后 JOBDIR 里留下什么')
    o1, L1 = run(d, s, jd, kill_after=1.5)
    st1 = stats(o1)
    print(f'  finish_reason={st1.get("finish_reason")};这次下载了 {len(pagesof(L1))} 个页面(+ 起始页);scheduler/enqueued={st1.get("scheduler/enqueued")}、dequeued={st1.get("scheduler/dequeued")}')
    for name, size in tree(jd): print(f'    {name:<34}{size:>7} 字节')

    print('== 二:第 2 次运行(同一个 JOBDIR)接着跑:剩下的页面、起始页是否重发、有没有重复')
    o2, L2 = run(d, s, jd)
    st2 = stats(o2)
    p1, p2 = pagesof(L1), pagesof(L2)
    print(f'  第 2 次:finish_reason={st2.get("finish_reason")};下载了 {len(p2)} 个页面,起始页重发了 {L2.count("/")} 次(自己写的 start() 没有 dont_filter,被 requests.seen 过滤);dupefilter/filtered={st2.get("dupefilter/filtered", 0)};scheduler/dequeued={st2.get("scheduler/dequeued")}')
    print(f'  两次合计:页面 {len(p1) + len(p2)} 次请求,不同页面 {len(set(p1) | set(p2))} 个(应为 40),两次重叠的页面 {len(set(p1) & set(p2))} 个')
    for name, size in tree(jd): print(f'    {name:<34}{size:>7} 字节')

    print('== 三:spider.state:self.state 是个字典,JOBDIR 里的 spider.state 把它存成 pickle,两次运行之间保留')
    import pickle
    stt = pickle.load(open(jd / 'spider.state', 'rb'))
    print(f'  spider.state 里的内容:count={stt.get("count")}、urls 的个数={len(stt.get("urls", []))};两次运行各自的 page 回调次数 {len(p1)} 和 {len(p2)}(合计 {len(p1) + len(p2)})')

    print('== 四:已经抓完的 JOBDIR 再跑一次:自己写的 start() 里的起始请求没有 dont_filter,也被 requests.seen 过滤,一个请求都不发;换成默认的 start_urls(自带 dont_filter=True)就会重发起始页')
    o3, L3 = run(d, s, jd)
    st3 = stats(o3)
    print(f'  第 3 次(自己写的 start()):服务器收到 {len(L3)} 个请求 {L3[:3]};dupefilter/filtered={st3.get("dupefilter/filtered")};finish_reason={st3.get("finish_reason")}')
    SP_URLS = SP.replace("    async def start(self): yield scrapy.Request('@U@/')", "    start_urls = ['@U@/']")
    o3b, L3b = run(d, s, jd, sp=SP_URLS)
    st3b = stats(o3b)
    print(f'  第 4 次(默认 start_urls):服务器收到 {len(L3b)} 个请求 {L3b[:3]};dupefilter/filtered={st3b.get("dupefilter/filtered")};finish_reason={st3b.get("finish_reason")}(起始页重发了,子链接全被过滤)')

    print('== 五:kill -9(SIGKILL)中途杀掉:队列状态没来得及写,恢复时会丢请求吗(新 JOBDIR)')
    jd2 = d / 'crawl-2'
    o4, L4 = run(d, s, jd2, kill_after=1.5, sig=signal.SIGKILL)
    for name, size in tree(jd2): print(f'    {name:<34}{size:>7} 字节')
    o5, L5 = run(d, s, jd2)
    st5 = stats(o5)
    q1, q2 = pagesof(L4), pagesof(L5)
    print(f'  kill -9 前下载了 {len(q1)} 个页面;恢复后又下载了 {len(q2)} 个;不同页面共 {len(set(q1) | set(q2))} 个(完整应为 40),缺 {40 - len(set(q1) | set(q2))} 个;重叠 {len(set(q1) & set(q2))} 个')
    print(f'  恢复那次:finish_reason={st5.get("finish_reason")};scheduler/dequeued={st5.get("scheduler/dequeued")}')

    print('== 六:请求无法序列化(callback 是 lambda,或 meta 里放了不能 pickle 的对象)时:退回内存队列,JOBDIR 恢复时丢失')
    jd3 = d / 'crawl-3'
    META_BAD = "{'lock': __import__('threading').Lock()}"
    o6, L6 = run(d, s, jd3, kill_after=1.2, meta=META_BAD)
    st6 = stats(o6)
    print(f'  meta 里放 threading.Lock():scheduler/unserializable={st6.get("scheduler/unserializable")};enqueued/memory={st6.get("scheduler/enqueued/memory")};enqueued/disk={st6.get("scheduler/enqueued/disk")}')
    o7, L7 = run(d, s, jd3, meta=META_BAD)
    r1, r2 = pagesof(L6), pagesof(L7)
    print(f'  第 1 次下载 {len(r1)} 个页面;恢复后又下载 {len(r2)} 个;不同页面共 {len(set(r1) | set(r2))} 个(完整应为 40)——内存队列里没落盘的请求在中断时丢了')
