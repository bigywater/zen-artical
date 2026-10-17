import sys, os, math, email.utils, datetime, inspect; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
tee('p30')

print('== 一:urllib3 的 Retry.parse_retry_after 怎么解析各种写法(单位:秒;源码里的 RETRY_AFTER_STATUS_CODES = %s)' % sorted(Retry.RETRY_AFTER_STATUS_CODES))
r = Retry()
now = datetime.datetime.now(datetime.timezone.utc)
cases = ['5', ' 5 ', '0', '-3', '1.5', '3600', '86400', email.utils.format_datetime(now + datetime.timedelta(seconds=10), usegmt=True), email.utils.format_datetime(now - datetime.timedelta(seconds=10), usegmt=True), 'soon', '']
for c in cases:
    try: v = r.parse_retry_after(c); out = f'{v:.1f} 秒'
    except Exception as e: out = f'{type(e).__name__}: {str(e)[:50]}'
    print(f'  Retry-After: {c!r:<34} → {out}')
src = inspect.getsource(Retry.sleep_for_retry); print('  Retry.sleep_for_retry 的实现:'); [print('    ' + l) for l in src.rstrip().splitlines()]

# 固定窗口限流服务器:每 1 秒窗口最多 LIMIT 个请求,超出回 429 并给出 Retry-After(窗口剩余秒数向上取整)
LIMIT = 5
def make_server(date_form=False):
    st = dict(win=None, n=0)
    def fn(h):
        now = time.time(); w = int(now)
        if st['win'] != w: st['win'] = w; st['n'] = 0
        st['n'] += 1
        if st['n'] > LIMIT:
            remain = math.ceil(w + 1 - now)
            ra = email.utils.format_datetime(datetime.datetime.fromtimestamp(w + 1, datetime.timezone.utc), usegmt=True) if date_form else str(max(1, remain))
            return h.reply(429, b'slow down', headers={'Retry-After': ra})
        h.reply(200, b'ok')
    return fn

def drive(sv, n, retry):
    s = requests.Session(); s.mount('http://', HTTPAdapter(max_retries=retry))
    t0 = time.perf_counter(); ok = bad = 0
    for _ in range(n):
        try:
            r = s.get(sv.url('/'));
            if r.status_code == 200: ok += 1
            else: bad += 1
        except Exception as e: bad += 1
    return ok, bad, time.perf_counter() - t0

print('== 二:限流服务器(每个自然秒最多 5 个请求,超出回 429 + Retry-After),客户端连续发 20 个请求,最多重试 6 次')
cfgs = [
    ('不重试(默认 max_retries=0)', Retry(total=0, status_forcelist=[429])),
    ('重试,忽略 Retry-After,固定 backoff 0(立刻重试)', Retry(total=6, status_forcelist=[429], backoff_factor=0, respect_retry_after_header=False)),
    ('重试,忽略 Retry-After,backoff_factor=0.2', Retry(total=6, status_forcelist=[429], backoff_factor=0.2, respect_retry_after_header=False)),
    ('重试,遵守 Retry-After(urllib3 默认)', Retry(total=6, status_forcelist=[429], backoff_factor=0)),
]
print(f'  {"客户端":<42}{"成功":>5}{"最终失败":>8}{"总耗时":>9}{"服务器收到":>10}{"其中 429":>9}')
for lab, rt in cfgs:
    st = []
    with Srv(make_server()) as sv:
        ok, bad, t = drive(sv, 20, rt)
        # 统计服务器收到的请求数:Srv 的日志不含状态码,这里用重放计数:总数 = len(sv.log)
        total = len(sv.log)
    print(f'  {lab:<40}{ok:>5}{bad:>8}{t:>7.1f} 秒{total:>9} 个{total - ok:>9}')

print('== 三:Retry-After 是 HTTP-date(绝对时间)写法时,urllib3 同样遵守')
with Srv(make_server(date_form=True)) as sv:
    ok, bad, t = drive(sv, 12, Retry(total=6, status_forcelist=[429], backoff_factor=0))
    print(f'  12 个请求:成功 {ok},最终失败 {bad},总耗时 {t:.1f} 秒,服务器收到 {len(sv.log)} 个请求')

print('== 四:Retry-After 的值很大会怎样:urllib3 有上限 Retry.DEFAULT_RETRY_AFTER_MAX = %d 秒(6 小时),可以用 retry_after_max 改' % Retry.DEFAULT_RETRY_AFTER_MAX)
print(f'  Retry().parse_retry_after("86400") = {Retry().parse_retry_after("86400"):.0f} 秒;Retry(retry_after_max=60).parse_retry_after("3600") = {Retry(retry_after_max=60).parse_retry_after("3600"):.0f} 秒')
def sleepy(h): h.reply(429, b'', headers={'Retry-After': '3'}) if len(sv4.log) == 1 else h.reply(200, b'ok')
for rmax in (None, 1):
    with Srv(sleepy) as sv4:
        s = requests.Session(); s.mount('http://', HTTPAdapter(max_retries=Retry(total=2, status_forcelist=[429], **({} if rmax is None else dict(retry_after_max=rmax)))))
        t0 = time.perf_counter(); r = s.get(sv4.url('/'))
        print(f'  服务器回 429 + Retry-After: 3,retry_after_max={"默认" if rmax is None else rmax}:重试后得到 {r.status_code},总耗时 {time.perf_counter() - t0:.1f} 秒')
print('== 五:哪些状态码会因为 Retry-After 被重试(源码 is_retry:在 status_forcelist 里,或者 总重试数>0 且 带了 Retry-After 且 状态码属于 RETRY_AFTER_STATUS_CODES)')
def make_once(code, with_header):
    sv = {}
    def fn(h):
        if len(sv['s'].log) == 1: h.reply(code, b'', headers={'Retry-After': '1'} if with_header else {})
        else: h.reply(200, b'ok')
    return sv, fn
for code, hdr, forcelist in ((503, True, [500]), (503, False, [500]), (429, True, []), (500, True, []), (503, True, [503]), (302, True, [])):
    sv, fn = make_once(code, hdr)
    with Srv(fn) as srv:
        sv['s'] = srv
        s = requests.Session(); s.mount('http://', HTTPAdapter(max_retries=Retry(total=2, status_forcelist=forcelist, redirect=0)))
        t0 = time.perf_counter()
        try: r = s.get(srv.url('/'), allow_redirects=False); res = str(r.status_code)
        except Exception as e: res = type(e).__name__
        print(f'  响应 {code}{" + Retry-After: 1" if hdr else "(无 Retry-After)"},status_forcelist={forcelist}:最终 {res},服务器收到 {len(srv.log)} 个请求,耗时 {time.perf_counter() - t0:.1f} 秒')
purge()
