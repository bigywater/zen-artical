import sys, os, struct, socket, collections, concurrent.futures as cf; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
tee('p31')
# URL 类别(每个 URL 的行为固定):名字 → (数量, 描述)
MIX = [('ok', 400, '正常 200'), ('t503', 100, '第 1 次 503,之后 200'), ('treset', 100, '第 1 次连接被重置,之后 200'), ('ttimeout', 50, '第 1 次响应超时,之后 200'),
       ('t429', 50, '前 2 次 429,之后 200'), ('t502', 50, '前 2 次 502,之后 200'), ('p404', 100, '永远 404'), ('p403', 50, '永远 403'), ('p500', 100, '永远 500(页面有 bug)')]
TOTAL = sum(n for _, n, _ in MIX)

def make_server():
    seen = collections.Counter(); lock = threading.Lock()
    def fn(h):
        kind = h.path.split('/')[1]
        with lock: seen[h.path] += 1; k = seen[h.path]
        if kind == 'ok': return h.reply(200, b'ok')
        if kind == 't503': return h.reply(503, b'') if k == 1 else h.reply(200, b'ok')
        if kind == 'treset':
            if k == 1:
                h.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); h.close_connection = True; h.connection.close(); return
            return h.reply(200, b'ok')
        if kind == 'ttimeout':
            if k == 1: time.sleep(0.5)
            return h.reply(200, b'ok')
        if kind == 't429': return h.reply(429, b'') if k <= 2 else h.reply(200, b'ok')
        if kind == 't502': return h.reply(502, b'') if k <= 2 else h.reply(200, b'ok')
        if kind == 'p404': return h.reply(404, b'')
        if kind == 'p403': return h.reply(403, b'')
        if kind == 'p500': return h.reply(500, b'')
    return fn
import threading

def classify(res):
    """res: int 状态码 或 异常名字符串"""
    return res

POLICIES = [
    ('不重试', lambda r: False),
    ('任何失败都重试', lambda r: not (isinstance(r, int) and 200 <= r < 300)),
    ('只重试网络错误(异常)', lambda r: isinstance(r, str)),
    ('网络错误 + 所有 5xx', lambda r: isinstance(r, str) or (isinstance(r, int) and r >= 500)),
    ('网络错误 + 408/425/429 + 502/503/504', lambda r: isinstance(r, str) or r in (408, 425, 429, 502, 503, 504)),
]
def attempt(s, url):
    try: return s.get(url, timeout=0.2).status_code
    except requests.exceptions.ReadTimeout: return 'ReadTimeout'
    except requests.exceptions.ConnectionError: return 'ConnectionError'

def run_policy(retry_if, max_tries=3):
    with Srv(make_server()) as sv:
        urls = [(kind, f'{sv.url("/")}{kind}/{i}'.replace(sv.url('/') + kind, sv.url('/') + kind)) for kind, n, _ in MIX for i in range(n)]
        s = requests.Session(); s.mount('http://', requests.adapters.HTTPAdapter(pool_maxsize=64))
        res = {}
        def work(item):
            kind, url = item; r = None
            for t in range(max_tries):
                r = attempt(s, url)
                if not retry_if(r) or t == max_tries - 1: break
                time.sleep(0.01)
            return kind, r
        t0 = time.perf_counter()
        with cf.ThreadPoolExecutor(32) as ex: out = list(ex.map(work, urls))
        el = time.perf_counter() - t0
        n_req = len(sv.log)
        okc = collections.Counter(k for k, r in out if r == 200); failc = collections.Counter(k for k, r in out if r != 200)
        perm = {'p404', 'p403', 'p500'}
        wasted = sum(max(0, sum(1 for l in sv.log if l['path'].split('/')[1] == kd) - dict((k_, n_) for k_, n_, _ in MIX)[kd]) for kd in perm)
        return dict(ok=sum(okc.values()), n_req=n_req, wasted=wasted, el=el, okc=okc, failc=failc)

print('== 一:1000 个 URL 的混合场景(行为按 URL 固定):' + ';'.join(f'{k} {n} 个({d})' for k, n, d in MIX))
print('  每个 URL 最多尝试 3 次,重试间隔 0.01 秒,请求超时 0.2 秒,32 个线程')
print(f'  {"策略":<34}{"最终成功":>8}{"服务器收到":>10}{"其中浪费在永久错误上":>20}{"耗时":>8}')
results = {}
for name, f in POLICIES:
    r = run_policy(f); results[name] = r
    print(f'  {name:<30}{r["ok"]:>8}{r["n_req"]:>10}{r["wasted"]:>16}{r["el"]:>7.1f} 秒')

print('== 二:每种策略下,哪一类 URL 最终没成功(按类别的失败个数)')
for name, r in results.items():
    print(f'  {name}:' + (', '.join(f'{k} {v}' for k, v in sorted(r['failc'].items())) or '无'))

print('== 三:"永远 500" 的页面(程序 bug)和 "第 1 次 503" 的区别在客户端看不出来:同样是 5xx')
for kind in ('t503', 'p500'):
    with Srv(make_server()) as sv:
        s = requests.Session(); rs = [attempt(s, f'{sv.url("/")}{kind}/1') for _ in range(3)]
        print(f'  连续请求 3 次 /{kind}/1:{rs}')
purge()
