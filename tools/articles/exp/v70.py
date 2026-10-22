import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import subprocess as sp
tee('v70'); reset()
print('基数爆炸:标签维度对时间序列数量的影响。Prometheus 3.15.0(自己起的,默认存储设置,抓取我写的暴露 /metrics 的 Python 服务),看序列数增加时 Prometheus 的内存(RSS)、抓取耗时、查询耗时怎么变化;标签维度怎么相乘;标签值不断变化(churn)时 head 里的序列数;sample_limit 与 metric_relabel_configs 的保护作用')
def prom_cfg(targets, interval=5, extra='', self_port=None):
    me = f'''
  - job_name: self
    static_configs:
      - targets: ['127.0.0.1:{self_port}']
''' if self_port else ''
    return f'''global:
  scrape_interval: {interval}s
  evaluation_interval: {interval}s
scrape_configs:
  - job_name: lab
    scrape_timeout: {min(interval, 10)}s
    {extra}
    static_configs:
      - targets: [{", ".join(repr(t) for t in targets)}]{me}'''
class Exposer:
    """暴露固定内容的 /metrics:payload 可以是 bytes,也可以是每次请求现算的函数"""
    def __init__(self, payload): self.payload = payload; self.n = 0; self.svc = Svc(self.app, 'm'); self.port = self.svc.port
    def app(self, h):
        self.n += 1; p = self.payload() if callable(self.payload) else self.payload; h.reply(200, p, {'Content-Type': 'text/plain; version=0.0.4'})
    def stop(self): self.svc.stop()
def rss_mb(prom): return int(sp.run(['ps', '-o', 'rss=', '-p', str(prom.p.pid)], capture_output=True, text=True).stdout.strip()) / 1024
def scalar(prom, q):
    r = prom.query(q); return float(r[0]['value'][1]) if r else float('nan')
def wait_data(prom, metric, timeout=60.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if prom.query(metric): return True
        time.sleep(0.5)
    return False

# ============ 一 ============
print('== 一:序列数与资源。服务暴露 N 条序列(一个指标名 http_requests_total,带 route 和 user 两个标签,值固定不变),Prometheus 每 5 s 抓取一次。等抓取稳定(至少 4 次)后,看 Prometheus 进程的 RSS、head 里的序列数、该 target 的抓取耗时 scrape_duration_seconds、对这个指标做 sum() 和 topk(5, ...) 的查询耗时(各查 5 次取中位数),以及 /metrics 的响应体大小。N = 1000、10000、100000、300000')
rows = []
for N in (1000, 10000, 100000, 300000):
    body = ('# TYPE http_requests_total counter\n' + ''.join(f'http_requests_total{{route="/r{i % 50}",user="u{i}"}} {i % 7}\n' for i in range(N))).encode()
    ex = Exposer(body); prom = Prom(f'v70a{N}', prom_cfg([f'127.0.0.1:{ex.port}'], 5)).start(); base = rss_mb(prom); assert wait_data(prom, 'http_requests_total')
    time.sleep(22); series = scalar(prom, 'prometheus_tsdb_head_series') if prom.query('prometheus_tsdb_head_series') else float('nan')
    cnt = scalar(prom, 'count(http_requests_total)'); dur = scalar(prom, 'scrape_duration_seconds{job="lab"}')
    def qt(q):
        ts = []
        for _ in range(5): t = time.perf_counter(); prom.query(q); ts.append(time.perf_counter() - t)
        return statistics.median(ts) * 1000
    t_sum = qt('sum(http_requests_total)'); t_top = qt('topk(5, http_requests_total)')
    rows.append((f'{N:,}', f'{cnt:,.0f}', f'{base:.0f}', f'{rss_mb(prom):.0f}', f'{dur * 1000:.0f}', f'{len(body) / 1e6:.2f}', f'{t_sum:.0f}', f'{t_top:.0f}')); prom.stop(); ex.stop()
table(rows, ['暴露的序列数 N', 'Prometheus 里 count() 的结果', 'Prometheus 刚启动时 RSS(MB)', '抓取稳定后 RSS(MB)', '抓取耗时(ms)', '/metrics 体积(MB)', 'sum() 查询(ms)', 'topk(5) 查询(ms)'])
print('  序列数从一千涨到三十万,内存、抓取耗时、/metrics 体积和查询耗时都随之增长;每个序列在内存里要存标签集合、倒排索引、最近的样本,抓取一次要解析所有序列。这里的值是固定的,真实的序列还要存时间戳和不同的值,内存会更多')

# ============ 二 ============
print('== 二:标签维度相乘。用 prometheus_client 记录 http_requests_total,标签 method(5 个取值)、route(20 个)、status(5 个)、再加 user_id。不加 user_id 时序列数是前三个标签取值数的乘积(如果每个组合都出现);加上 user_id(1000 个用户,每个用户随机访问 30 次)之后,序列数是多少')
from prometheus_client import CollectorRegistry, Counter, generate_latest
rnd = random.Random(4); rows = []
for name, labels, with_user in (('method × route × status', ['method', 'route', 'status'], False), ('再加 user_id', ['method', 'route', 'status', 'user_id'], True)):
    reg = CollectorRegistry(); c = Counter('reqs', 'x', labels, registry=reg)
    if not with_user:
        for m in range(5):
            for r in range(20):
                for s in range(5): c.labels(f'M{m}', f'/r{r}', str(200 + s)).inc()
    else:
        for u in range(1000):
            for _ in range(30): c.labels(f'M{rnd.randrange(5)}', f'/r{rnd.randrange(20)}', str(200 + rnd.randrange(5)), f'u{u}').inc()
    txt = generate_latest(reg).decode(); n = sum(1 for l in txt.splitlines() if l.startswith('reqs_total{')); rows.append((name, n, f'{len(txt) / 1000:.0f}'))
table(rows, ['标签', '序列数', '/metrics 文本大小(KB)'])
print(f'  5 × 20 × 5 = {5 * 20 * 5} 条;加上取值很多的标签(用户 ID、请求 ID、完整 URL、IP)之后,序列数由标签值的组合决定,而不是由请求量决定——3 万次请求产生了上表里这么多条序列')

# ============ 三 ============
print('== 三:标签值不断变化(churn)。服务每次被抓取时暴露 1000 条序列,但其中的 request_id 标签值每次都是新的(同一时刻只有 1000 条“活”的序列)。Prometheus 每 2 s 抓取一次,运行 60 s。看 head 里的序列数和累计创建的序列数怎么随时间变化')
counter = {'n': 0}
def churn_payload():
    base = counter['n']; counter['n'] += 1000
    return ('# TYPE rq gauge\n' + ''.join(f'rq{{request_id="id{base + i}"}} 1\n' for i in range(1000))).encode()
sp_ = free_port(); ex = Exposer(churn_payload); prom = Prom('v70c', prom_cfg([f'127.0.0.1:{ex.port}'], 2, self_port=sp_), port=sp_).start(); assert wait_data(prom, 'rq'); rows = []
for k in range(6):
    time.sleep(10); rows.append((f'{(k + 1) * 10} s', f'{scalar(prom, "prometheus_tsdb_head_series"):,.0f}', f'{scalar(prom, "prometheus_tsdb_head_series_created_total"):,.0f}', f'{scalar(prom, "count(rq)"):,.0f}', f'{rss_mb(prom):.0f}'))
table(rows, ['运行时间', 'head 里的序列数', '累计创建的序列数', '当前能查到的“活”序列(count(rq))', 'Prometheus RSS(MB)'])
print('  每次抓取都产生 1000 条新序列,旧的序列停止更新、被标记为过期(stale),但仍然留在 head 里直到被压缩进磁盘块并回收;所以 head 里的序列数和内存会持续增长,即使同一时刻“活”的序列数不变')
prom.stop(); ex.stop()

# ============ 四 ============
print('== 四:限制与保护。目标暴露 10000 条序列(6 个 route × 约 1667 个 user)。(a)抓取配置 sample_limit: 5000;(b)metric_relabel_configs 把 user 标签 labeldrop 掉(多条序列合并成同一个标签集合);(c)metric_relabel_configs 用 labeldrop 去掉 user 之前先对 user 取哈希放进一个 6 个取值的桶标签(hashmod)。看 up、本次抓取的样本数,和实际存进去的序列数')
body = ('# TYPE http_requests_total counter\n' + ''.join(f'http_requests_total{{route="/r{i % 6}",user="u{i}"}} {i % 7}\n' for i in range(10000))).encode()      # 值各不相同,labeldrop 之后合并成同一个标签集合的样本才会被认作“同一时间戳、不同值”
rows = []
for name, extra in (('(a)sample_limit: 5000', 'sample_limit: 5000'), ('(b)labeldrop user', '''metric_relabel_configs:
      - {action: labeldrop, regex: user}'''), ('(c)hashmod 成 6 个桶后 labeldrop', '''metric_relabel_configs:
      - {action: hashmod, source_labels: [user], target_label: ubucket, modulus: 6}
      - {action: labeldrop, regex: user}''')):
    sp_ = free_port(); ex = Exposer(body); prom = Prom('v70d', prom_cfg([f'127.0.0.1:{ex.port}'], 3, extra, self_port=sp_), port=sp_).start(); time.sleep(14)
    up = scalar(prom, 'up{job="lab"}'); scraped = scalar(prom, 'scrape_samples_scraped{job="lab"}'); post = scalar(prom, 'scrape_samples_post_metric_relabeling{job="lab"}'); cnt = scalar(prom, 'count(http_requests_total)')
    dupm = scalar(prom, 'prometheus_target_scrapes_sample_duplicate_timestamp_total'); logtxt = (prom.d / 'out.log').read_text(errors='replace'); dlog = sum(1 for l in logtxt.splitlines() if 'uplicate' in l)
    rows.append((name, f'{up:.0f}', f'{scraped:,.0f}', f'{post:,.0f}', f'{cnt:,.0f}' if cnt == cnt else '0(没有存进去)', f'{dupm:.0f}' if dupm == dupm else '-', dlog)); prom.stop(); ex.stop()
table(rows, ['配置', 'up', '抓到的样本数 scrape_samples_scraped', '重新打标签之后的样本数', '实际存进去的序列数 count()', 'Prometheus 自己的 sample_duplicate_timestamp 计数', '日志里含 duplicate 的行数'])
print('  sample_limit 是整个抓取的熔断:超过限制,这一次抓取整体失败(up = 0),一条都不存;labeldrop 去掉区分序列的标签会让多条序列变成同一个标签集合,只能存下一个样本(这里一万条序列并成了 count() 那一列的条数);想保留一点分布信息,可以先 hashmod 再 labeldrop')
print('ERRORS', dict(ERRORS))
