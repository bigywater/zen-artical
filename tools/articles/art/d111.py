from lib import *
R = J('d111'); t = R['t']
def L(k): return [l for l in out('d111').split('== ')[1].splitlines()[1:] if l.strip()]
Ls = L(0)
tt = lambda k: t[k]['total']
steps = [
    step("测试方法:20 个并发请求,每个请求的视图里「等」0.5 秒(1 个 worker / 1 个进程);组合是 ASGI(uvicorn)与 WSGI(gunicorn 同步 worker)× async def 视图(await asyncio.sleep)与普通 def 视图(time.sleep)。如果请求真的并发,20 个请求总共约 0.5 秒;如果排队,约 10 秒。", n=fl([['uvicorn (ASGI)', '1 个进程'], ['gunicorn 同步 worker (WSGI)', '1 个 worker']], cur=[0, 1]), kv=KV([['并发请求', '20'], ['每个请求等待', '0.5 s']], ['并发请求'])),
    step(f"uvicorn + async def 视图:总耗时 {tt('asgi_async'):.0f} ms,20 个请求几乎同时完成(最快 {t['asgi_async']['fast']:.0f} / 最慢 {t['asgi_async']['slow']:.0f} ms)。", t=tl(Ls[:1]), b=bars([['uvicorn + async', tt('asgi_async'), f"{tt('asgi_async'):.0f} ms"]], 10500, done=[0]), kv=KV([['总耗时', f"{tt('asgi_async'):.0f} ms"]], ['总耗时'])),
    step(f"意外:uvicorn + 普通 def 视图(time.sleep)总耗时也只有 {tt('asgi_sync'):.0f} ms——sync 视图在 ASGI 下也没有排队。原因见下一篇:Django 在 ASGI 下把每个请求的 sync 视图放进它自己的线程里跑。", t=tl(Ls[1:2]), b=bars([['uvicorn + async', tt('asgi_async'), f"{tt('asgi_async'):.0f} ms"], ['uvicorn + sync', tt('asgi_sync'), f"{tt('asgi_sync'):.0f} ms"]], 10500, done=[0, 1]), kv=KV([['sync 视图在 ASGI 下', '也是并发的(每请求一个线程)']], ['sync 视图在 ASGI 下'])),
    step(f"gunicorn 同步 worker(WSGI)下:async def 视图总耗时 {tt('wsgi_async'):.0f} ms,普通 def 视图 {tt('wsgi_sync'):.0f} ms——都排队,20 × 0.5 s ≈ 10 s。单个请求最快 504 ms、最慢约 10 s。async def 视图放在 WSGI 上跑,没有任何并发好处。", t=tl(Ls[2:]), b=bars([['gunicorn + async', tt('wsgi_async'), f"{tt('wsgi_async'):.0f} ms"], ['gunicorn + sync', tt('wsgi_sync'), f"{tt('wsgi_sync'):.0f} ms"], ['uvicorn + async', tt('asgi_async'), f"{tt('asgi_async'):.0f} ms"], ['uvicorn + sync', tt('asgi_sync'), f"{tt('asgi_sync'):.0f} ms"]], 10500, mark=[0, 1], done=[2, 3]), kv=KV([['WSGI 同步 worker', '一次只处理一个请求'], ['async def 在 WSGI 上', '无并发收益']], ['async def 在 WSGI 上'])),
]
A = dict(
    n=111, series='django', tags='Django,异步,ASGI,uvicorn,gunicorn,真实验证,动画演示',
    desc=f'20 个并发请求、每个视图等 0.5 s:uvicorn(ASGI)下 async 与 sync 视图都是约 {tt("asgi_async"):.0f} ms;gunicorn 同步 worker(WSGI)下无论 async 还是 sync 都是约 {tt("wsgi_sync") / 1000:.1f} s。async def 视图要放在 ASGI 服务器上才有并发收益。',
    lead='把视图写成 async def,请求就并发了吗?不一定,取决于它跑在什么服务器上。这篇用真实的 uvicorn 和 gunicorn 各起一个进程,同样的视图打 20 个并发请求,看哪些组合真的并发。',
    facts=[(f'{tt("asgi_async"):.0f} ms', 'uvicorn 上 async 视图,20 个并发请求(每个等 0.5 s)'), (f'{tt("wsgi_async") / 1000:.1f} s', 'gunicorn 同步 worker 上同样的 async 视图:排队'), (f'{tt("asgi_sync"):.0f} ms', '意外:uvicorn 上的 sync 视图也没有排队')],
    body=[
        sec('同一个视图,两种服务器', '', term('', blk('d111', 1)), '<p>ASGI 下 async 与 sync 视图都是并发的,WSGI 同步 worker 下都是排队的——<b>所以 async def 本身不是并发的原因,ASGI 服务器才是</b>。两个视图要「等」的方式不同:<code>await asyncio.sleep</code> 不占线程,<code>time.sleep</code> 占着线程。在 ASGI 下 sync 视图能并发,是因为 Django 给每个请求分配了单独的线程(第 112、113 篇会用线程名验证)。</p>'),
        sec('这个实验没有说明的事', '', '<p>视图里的「等待」是 sleep,不是真的数据库或网络调用;并发数只有 20;worker 数是 1。sync 视图在 ASGI 下并发数很大时会受线程数量限制,本篇没有测。</p>'),
        sec('分步演示', '', demo('async 视图与服务器', [('n', 'flow', '部署'), ('t', 'term', '输出'), ('b', 'bars', '20 并发的总耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。uvicorn(1 个进程)与 gunicorn 同步 worker(1 个 worker),视图里用 sleep 模拟等待,20 个并发请求由本机线程发出;各组合只测了一次', '没有验证:真实的数据库 / 网络等待、gunicorn 多 worker 或 gthread worker、并发数远大于 20 时的线程数上限、runserver / daphne 上的表现'],
)
