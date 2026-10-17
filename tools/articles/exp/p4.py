import sys, os, inspect; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, threading
tee('p4')

def timed(fn):
    t0 = time.perf_counter()
    try: r = fn(); return f'成功 {r.status_code}', ms(t0)
    except Exception as e: return f'{type(e).__name__}', ms(t0)

print('== 一:连接超时:连一个收不到回应的地址(192.0.2.1 是 RFC 5737 保留给文档的 TEST-NET-1 地址,SYN 发出去没有人回)')
print('  (本机回环做不出连接超时:macOS 上监听队列满了之后,新连接是立刻被重置,而不是卡住)')
for to in ((0.5, 5), (1.5, 5), 1.0):
    res, t = timed(lambda: requests.get('http://192.0.2.1:9/', timeout=to))
    print(f'  timeout={to!s:<8} → {res},耗时 {t:.0f} ms')
print('  异常类的继承关系:' + ' → '.join(c.__name__ for c in requests.exceptions.ConnectTimeout.__mro__[:5]))
print('  ReadTimeout 的继承关系:' + ' → '.join(c.__name__ for c in requests.exceptions.ReadTimeout.__mro__[:3]))

print('== 二:读超时:连上了,服务器过了 2 秒才开始回应')
def late(h): time.sleep(2.0); h.reply(200, b'ok')
with Srv(late) as sv:
    for to in ((5, 1.0), 1.0, (0.2, 3.0)):
        res, t = timed(lambda: requests.get(sv.url('/'), timeout=to))
        print(f'  timeout={to!s:<10} → {res},耗时 {t:.0f} ms')

print('== 三:读超时是"两次数据到达的间隔",不是总时长:服务器每 0.5 秒发 1 个字节,共 6 个字节(整个响应要 3 秒)')
def dribble(h):
    h.send_response(200); h.send_header('Content-Length', '6'); h.end_headers(); h.wfile.flush()
    for _ in range(6):
        time.sleep(0.5); h.wfile.write(b'x'); h.wfile.flush()
with Srv(dribble) as sv:
    for to in (1.0, 0.3):
        t0 = time.perf_counter()
        try:
            r = requests.get(sv.url('/'), timeout=to); res = f'成功 {r.status_code},收到 {len(r.content)} 个字节'
        except Exception as e: res = f'{type(e).__name__}:{str(e)[:110]}'
        print(f'  timeout={to}(每个间隔 0.5 秒)→ {res},耗时 {ms(t0):.0f} ms')
import requests.models as _m
L, st = inspect.getsourcelines(_m.Response.iter_content.__wrapped__ if hasattr(_m.Response.iter_content, '__wrapped__') else _m.Response.iter_content)
src = inspect.getsource(_m)
rl_ = src.split('\n')
for i, l in enumerate(rl_):
    if 'except ReadTimeoutError' in l: print(f'  requests/models.py 第 {i + 1}-{i + 2} 行:{rl_[i].strip()} → {rl_[i + 1].strip()}')

print('== 四:想要"总时长上限",requests 没有这个参数,只能自己在读取循环里检查截止时间')
def forever(h):
    h.send_response(200); h.send_header('Content-Length', '100000'); h.end_headers(); h.wfile.flush()
    try:
        for _ in range(100000): time.sleep(0.2); h.wfile.write(b'x'); h.wfile.flush()
    except Exception: pass
with Srv(forever) as sv:
    t0 = time.perf_counter(); got = 0; deadline = t0 + 2.0; why = '读完'
    with requests.get(sv.url('/'), timeout=1.0, stream=True) as r:
        for chunk in r.iter_content(1):
            got += len(chunk)
            if time.perf_counter() > deadline: why = '超过自己设的 2 秒截止时间,主动停止'; break
    print(f'  服务器每 0.2 秒发 1 个字节永不结束,timeout=1.0 + 自己的 2 秒截止时间:{why};耗时 {ms(t0):.0f} ms,收到 {got} 个字节')

print('== 五:不传 timeout 会怎样(默认是 None,永远等)')
doc = inspect.getdoc(requests.api.request).splitlines()
k = [n for n, l in enumerate(doc) if l.startswith(':param timeout')][0]
print('  requests.request 文档里对 timeout 的说明:' + ' '.join(l.strip() for l in doc[k:k + 3]))
ev = threading.Event()
def hang(h): ev.wait(10); h.reply(200, b'late')
with Srv(hang) as sv:
    box = {}
    def call():
        t0 = time.perf_counter()
        try: box['r'] = requests.get(sv.url('/')).status_code
        except Exception as e: box['r'] = type(e).__name__
        box['t'] = ms(t0)
    th = threading.Thread(target=call, daemon=True); th.start()
    time.sleep(3.0)
    print(f'  服务器收到请求后一直不回应,3.0 秒后这个没有 timeout 的请求还在阻塞吗?{th.is_alive()}(服务器已收到 {len(sv.log)} 个请求)')
    ev.set(); th.join(5)
    print(f'  放行之后它的结果:{box.get("r")},总耗时 {box.get("t", 0):.0f} ms')
purge()
