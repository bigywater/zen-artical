from lib import *
S = SS('f137')
R = J('f137'); g = R['gather']; ov = R['overhead']; lv = R['live']
k = list(lv); s_a, s_s = lv[k[0]]; t_a, t_s = lv[k[1]]
steps = [
    step(f"async def 视图可以直接用(这个环境里装了 asgiref 3.12.1,Flask 的 async 支持依赖它)。每个请求都新建一个事件循环——连续两个请求里 asyncio.get_running_loop() 的 id 不同,所在线程也不同;视图里仍然能用 request.path(请求上下文被带进了协程)。在一个请求内部,asyncio.gather 同时等三个各 0.5 秒的任务总共 {g[0]} 秒,而依次 await 三次要 {g[1]} 秒——async 视图的好处在「一个请求里要并发做几件 I/O」的时候。", t=tl(S(1)), done=lidx(S(1), 'GET /s', '一个请求里'), mark=lidx(S(1), '事件循环的 id'), kv=KV([['每个请求', '新建事件循环'], ['请求内并发', f'gather {g[0]} 秒 对 依次 {g[1]} 秒']], ['请求内并发'])),
    step(f"代价:每个请求的额外开销,sync 视图 {ov[0]:.0f} µs/请求,async 视图(只 await 一个 sleep(0)){ov[1]:.0f} µs/请求,多约 {ov[1] - ov[0]:.0f} µs(新建事件循环与线程切换,test client 里 3000 次取最小)。视图里本来就没有并发 I/O 时,async 只会更慢。", b=bars([['sync 视图', ov[0], f'{ov[0]:.0f} µs'], ['async 视图', ov[1], f'{ov[1]:.0f} µs']], ov[1], mark=[1], done=[0]), t=tl(S(2)), done=lidx(S(2), 'sync 视图'), kv=KV([['async 额外开销', f'约 {ov[1] - ov[0]:.0f} µs/请求']], ['async 额外开销'])),
    step(f"在 WSGI 服务器下 async 视图并不会突破 worker 的并发数:8 个并发请求各 await asyncio.sleep(1),gunicorn sync 1 个 worker 要 {s_a:.2f} 秒(和 time.sleep 的 sync 视图 {s_s:.2f} 秒一样,一个接一个);gthread 1 个 worker × 8 线程是 {t_a:.2f} 秒(和 sync 视图的 {t_s:.2f} 秒一样)。每个请求仍然占着一个 worker 线程,直到协程结束。要让一个进程里同时挂起成百上千个等待,需要 ASGI 服务器与原生异步框架(见第 140、141 篇)。", b=bars([['sync worker,async 视图', s_a, f'{s_a:.1f} s'], ['sync worker,sync 视图', s_s, f'{s_s:.1f} s'], ['8 线程,async 视图', t_a, f'{t_a:.1f} s']], s_a, mark=[0, 1], done=[2]), t=tl(S(3)), mark=lidx(S(3), 'gunicorn sync'), done=lidx(S(3), 'gthread'), kv=KV([['sync worker', f'async 视图 {s_a:.0f} 秒,仍是串行'], ['gthread 8 线程', f'{t_a:.0f} 秒']], ['sync worker'])),
]
A = mkartf('f137', 137, 'Flask,async,asyncio,asgiref,真实验证,动画演示',
    f'实测 Flask 的 async 视图:每个请求新建事件循环、请求内 asyncio.gather 把 3 个 0.5 秒的等待压到 {g[0]} 秒、每个请求多约 {ov[1] - ov[0]:.0f} µs 的开销、在 gunicorn 下 8 个并发的 async 视图在 sync worker 上仍需 {s_a:.1f} 秒而不会突破 worker 并发数。',
    'Flask 支持 async def 视图,它到底带来了什么?每个请求是不是都在同一个事件循环里?在 gunicorn 下能同时处理更多请求吗?这篇用真实的 asyncio 与 gunicorn 把边界量出来。',
    [(f'{g[1]} → {g[0]} 秒', '请求内三个各 0.5 秒的等待:依次 await 与 asyncio.gather'), (f'+{ov[1] - ov[0]:.0f} µs', 'async 视图相对 sync 视图每个请求多出的耗时'), (f'{s_a:.0f} 秒', 'gunicorn sync 单 worker 下 8 个并发 async 视图的总耗时(没有变快)')],
    [('事件循环与请求内并发', '<p>上一篇:<a href="flask-sync-request-model.html">Flask 同步请求模型</a>;下一篇:<a href="flask-async-view-boundary.html">Async View 的执行边界</a>。</p>'), ('额外开销', None), ('WSGI 下的并发', None)],
    steps, [ENV_F + '。asgiref 3.12.1、gunicorn sync 与 gthread worker', '没有验证:在 ASGI 服务器(uvicorn、hypercorn)下运行同样的视图(见第 140 篇)、异步数据库驱动、async 视图里调用阻塞代码的后果(见第 139 篇)、before_request 等钩子写成 async 的行为'], 'Flask Async View', panels=[('t', 'term', '实验输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')])
