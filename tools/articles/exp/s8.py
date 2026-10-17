import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s8'); reset_s()
def ok(h): h.reply(200, '<html>x</html>', {'Content-Type': 'text/html'})
def go(code, settings=None, tag='s8', srv=ok, host=None):
    d = sdir(tag)
    with Srv(srv) as s:
        rc, out, t = runspider(d, code.replace('@U@', s.url('').rstrip('/')), dict({'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1}, **(settings or {})))
    return s, ev(d), out, stats(out), d

print('== 一:默认的队列类,以及有无 JOBDIR 时请求进了哪个队列(stats)')
r = subprocess.run([SPY, '-c', 'from scrapy.settings import default_settings as d; print(d.SCHEDULER); print(d.SCHEDULER_PRIORITY_QUEUE); print(d.SCHEDULER_MEMORY_QUEUE); print(d.SCHEDULER_DISK_QUEUE); print(d.SCHEDULER_START_MEMORY_QUEUE); print(d.SCHEDULER_START_DISK_QUEUE); print(d.DUPEFILTER_CLASS)'], capture_output=True, text=True)
for k, v in zip(('SCHEDULER', 'SCHEDULER_PRIORITY_QUEUE', 'SCHEDULER_MEMORY_QUEUE', 'SCHEDULER_DISK_QUEUE', 'SCHEDULER_START_MEMORY_QUEUE', 'SCHEDULER_START_DISK_QUEUE', 'DUPEFILTER_CLASS'), r.stdout.split()): print(f'  {k:<30} = {v}')
CODE1 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/seed')
    def parse(self, response):
        if response.url.endswith('seed'):
            for i in range(20): yield scrapy.Request('@U@/p%d' % i)
"""
for tag, stt in (('不设 JOBDIR', {}), ('JOBDIR=<目录>', {'JOBDIR': str(sdir('s8job1'))})):
    s, E, out, st, d = go(CODE1, stt)
    print(f'  {tag}:' + ', '.join(f'{k.split("scheduler/")[1]}={v}' for k, v in sorted(st.items()) if k.startswith('scheduler/')))

print('== 二:Request.priority:数值大的先出队(并发 1;一个种子页的回调里一次性产生 12 个不同优先级的请求)')
CODE2 = """
import scrapy
PR = [0, 5, -3, 10, 0, 5, -3, 10, 1, 1, 0, 0]
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/seed')
    def parse(self, response):
        if response.url.endswith('seed'):
            for i, p in enumerate(PR): yield scrapy.Request('@U@/r%d-p%d' % (i, p), priority=p)
"""
s, E, out, st, d = go(CODE2)
order = [l['path'][1:] for l in s.log][1:]
print('  产生顺序(序号-优先级):' + ' '.join(f'{i}:{p}' for i, p in enumerate([0, 5, -3, 10, 0, 5, -3, 10, 1, 1, 0, 0])))
print('  服务器收到的顺序:     ' + ' '.join(o.replace('r', '').replace('-p', ':') for o in order))
print('  → 优先级 10 的两个(3、7)最先且后产生的 7 在前;同优先级内后产生的先出(LIFO)')

print('== 三:同优先级内的顺序由 SCHEDULER_MEMORY_QUEUE 决定:改成 FifoMemoryQueue 就是先产生先出')
s, E, out, st, d = go(CODE2, {'SCHEDULER_MEMORY_QUEUE': 'scrapy.squeues.FifoMemoryQueue'})
order = [l['path'][1:] for l in s.log][1:]
print('  服务器收到的顺序:     ' + ' '.join(o.replace('r', '').replace('-p', ':') for o in order))

print('== 四:有 JOBDIR 时,不可序列化的请求(callback 是 lambda)退回内存队列:警告、stats,以及“内存队列先于磁盘队列”造成的优先级错乱')
CODE4 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('@U@/seed')
    def parse(self, response):
        if response.url.endswith('seed'):
            yield scrapy.Request('@U@/disk-p5', priority=5)                                    # 可序列化 → 磁盘队列
            yield scrapy.Request('@U@/disk-p9', priority=9)                                    # 可序列化 → 磁盘队列
            yield scrapy.Request('@U@/mem-p-1', priority=-1, callback=lambda r: None)           # lambda → 不能序列化 → 内存队列
"""
s, E, out, st, d = go(CODE4, {'JOBDIR': str(sdir('s8job4'))})
print('  服务器收到的顺序:' + ' '.join(l['path'][1:] for l in s.log[1:]))
s2, E2, out2, st2, d2 = go(CODE4, {'JOBDIR': str(sdir('s8job4b')), 'SCHEDULER_DEBUG': 1})
w = [l.strip() for l in out2.split('\n') if 'Unable to serialize request' in l]
print('  默认(SCHEDULER_DEBUG=False)时日志里没有任何警告;SCHEDULER_DEBUG=1 时:' + (w[0].split(' - reason: ')[0].replace('[scrapy.core.scheduler] ', '') + ' - reason: ' + w[0].split(' - reason: ')[1].split(' - no more')[0] if w else '(也没有)'))
print('  stats:' + ', '.join(f'{k.split("scheduler/")[1]}={v}' for k, v in sorted(st.items()) if k.startswith('scheduler/') and 'enqueued/' in k or k == 'scheduler/unserializable') )


print('== 五:DownloaderAwarePriorityQueue 的优先级是“每个域名各排各的”,不是全局的:并发 1,域名 A 的 3 个请求优先级 0,域名 B 的 3 个请求优先级 100')
CODE6 = """
import scrapy
class S(scrapy.Spider):
    name = 's'
    async def start(self): yield scrapy.Request('http://127.0.0.1:@P@/seed')
    def parse(self, response):
        if response.url.endswith('seed'):
            for i in range(3): yield scrapy.Request('http://127.0.0.1:@P@/a%d' % i, priority=0)
            for i in range(3): yield scrapy.Request('http://localhost:@P@/b%d' % i, priority=100)
"""
for tag, pq in (('DownloaderAwarePriorityQueue(默认)', None), ('ScrapyPriorityQueue', 'scrapy.pqueues.ScrapyPriorityQueue')):
    d = sdir('s8f')
    with Srv(ok) as s:
        stt = {'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS': 1}
        if pq: stt['SCHEDULER_PRIORITY_QUEUE'] = pq
        rc, out, t = runspider(d, CODE6.replace('@P@', str(s.port)), stt)
    print(f'  {tag}:服务器收到的顺序 {" ".join(dict(l["hdrs"])["Host"].split(":")[0][0].replace("1", "A").replace("l", "B") + l["path"][2:] for l in s.log[1:])}  (A=127.0.0.1 优先级 0,B=localhost 优先级 100)')

print('== 六:默认的 DownloaderAwarePriorityQueue 不支持 CONCURRENT_REQUESTS_PER_IP')
d = sdir('s8g')
with Srv(ok) as s:
    rc, out, t = runspider(d, CODE1.replace('@U@', s.url('').rstrip('/')), {'LOG_LEVEL': 'INFO', 'CONCURRENT_REQUESTS_PER_IP': 2})
print(f'  -s CONCURRENT_REQUESTS_PER_IP=2:退出码 {rc};服务器收到 {len(s.log)} 个请求')
print('  ' + [l for l in out.split('\n') if l.startswith('ValueError')][-1][:150])
