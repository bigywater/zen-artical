import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f6'); R = {}
import threading, asyncio, contextvars, concurrent.futures, random
from flask import Flask, request, g, copy_current_request_context
from werkzeug.local import Local, release_local
cv = contextvars.ContextVar('cv', default='默认值')
tl_ = threading.local()
print('== 一:ContextVar 与线程:主线程里 set 之后,新线程看到的是默认值还是主线程的值')
cv.set('主线程设的值'); out = {}
t = threading.Thread(target=lambda: out.update(thread=cv.get())); t.start(); t.join()
ctx = contextvars.copy_context(); t = threading.Thread(target=lambda: out.update(copied=ctx.run(cv.get))); t.start(); t.join()
print('  新线程里 cv.get():', out['thread'], '| 把 copy_context() 带进线程用 ctx.run:', out['copied']); R['thread'] = dict(out)
print('  Python 版本', sys.version.split()[0], '| sys.flags.thread_inherit_context =', getattr(sys.flags, 'thread_inherit_context', '(没有这个 flag)')); R['flag'] = str(getattr(sys.flags, 'thread_inherit_context', None))
print()
print('== 二:ContextVar 与 asyncio:每个 Task 创建时复制一份上下文,各自修改互不影响')
async def worker(name, delay):
    cv.set(f'{name} 设的值'); await asyncio.sleep(delay); return f'{name} 睡醒后读到 {cv.get()}'
async def main2():
    cv.set('main 设的值'); res = await asyncio.gather(worker('任务A', 0.05), worker('任务B', 0.01), worker('任务C', 0.03)); return res, cv.get()
res, after = asyncio.run(main2()); [print('  ' + r) for r in res]; print('  gather 结束后 main 里 cv.get() =', after); R['async'] = [res, after]
print()
print('== 三:threading.local 在 asyncio 里会串:同一个线程里的多个协程共享同一个 threading.local;ContextVar 不会')
async def w_tl(name, delay):
    tl_.v = name; await asyncio.sleep(delay); return f'{name} 睡醒后读到 {tl_.v}'
async def w_cv(name, delay):
    cv.set(name); await asyncio.sleep(delay); return f'{name} 睡醒后读到 {cv.get()}'
async def main3(w): return await asyncio.gather(w('X', 0.05), w('Y', 0.01), w('Z', 0.03))
r1 = asyncio.run(main3(w_tl)); r2 = asyncio.run(main3(w_cv)); print('  threading.local:', r1); print('  ContextVar     :', r2); R['tl_vs_cv'] = [r1, r2]
print()
print('== 四:werkzeug.local.Local:接口像 threading.local,底层是 ContextVar;线程与协程里都隔离')
L = Local(); L.name = '主线程'; seen = {}
def w4(n): L.name = f'线程{n}'; time.sleep(0.02); seen[n] = L.name
ths = [threading.Thread(target=w4, args=(i,)) for i in range(3)]; [t.start() for t in ths]; [t.join() for t in ths]
async def a4(n): L.name = f'任务{n}'; await asyncio.sleep(0.01 * (3 - n)); return L.name
async def m4(): return await asyncio.gather(*[a4(i) for i in range(3)])
ares = asyncio.run(m4()); print('  3 个线程各自读到:', [seen[i] for i in range(3)], '| 3 个协程各自读到:', ares, '| 主线程读到:', L.name)
print('  Local 的内部存储:', type(object.__getattribute__(L, '_Local__storage')).__name__, '(ContextVar)'); R['local'] = [[seen[i] for i in range(3)], ares, L.name, type(object.__getattribute__(L, '_Local__storage')).__name__]
release_local(L); print('  release_local(L) 之后访问 L.name:', end=' ')
try: L.name
except AttributeError as e: print('AttributeError:', e); R['release'] = str(e)
print()
print('== 五:真实的 gunicorn --threads 8:16 个并发请求,每个把自己的参数存进 g,随机睡一会儿再读回来')
d = app('f6', {'app.py': '''
import random, time, os
from flask import Flask, g, request
app = Flask(__name__)
@app.get("/who")
def who():
    g.me = request.args["n"]
    time.sleep(random.uniform(0.05, 0.25))
    return f"{g.me}|{request.args['n']}|thread-ok"
'''})
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--threads', '8', '--workers', '1', 'app:app']) as s:
    res = {}
    def req(i): res[i] = s.get(f'/who?n={i}')[2].decode()
    ths = [threading.Thread(target=req, args=(i,)) for i in range(16)]; t0 = time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; dt = ms(t0)
bad = [i for i in res if res[i].split('|')[0] != str(i) or res[i].split('|')[1] != str(i)]
print(f'  16 个并发请求(单 worker、8 线程)总耗时 {dt:.0f} ms;g 里读回来的值与自己的参数不一致的请求数:{len(bad)};示例:{[res[i] for i in range(3)]}'); R['gunicorn'] = [round(dt), len(bad), [res[i] for i in range(3)]]
print()
print('== 六:把请求交给线程池:不带上下文拿不到 request;用 ctx = copy_context() + ctx.run 或 copy_current_request_context 可以')
app = Flask('demo6'); out = {}
@app.get('/')
def idx():
    ex = concurrent.futures.ThreadPoolExecutor(2)
    def plain(): return request.path
    def safe(): return request.path
    try: out['直接 submit'] = ex.submit(plain).result()
    except Exception as e: out['直接 submit'] = f'{type(e).__name__}'
    out['copy_current_request_context'] = ex.submit(copy_current_request_context(safe)).result()
    ctx = contextvars.copy_context(); out['copy_context().run'] = ex.submit(ctx.run, safe).result(); ex.shutdown(); return 'ok'
app.test_client().get('/'); [print(f'  {k}: {v}') for k, v in out.items()]; R['pool'] = dict(out)
save('f6', R)
