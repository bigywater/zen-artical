from lib import *
R = J('d117'); tt = R['ttfb']; w = R['warns']
def L(k): return [l for l in out('d117').split('== ')[k + 1].splitlines()[1:] if l.strip()]
L1, L2, L3 = L(0), L(1), L(2)
f = lambda k: f"{tt[k]['first']:.0f}"
steps = [
    step("用 StreamingHttpResponse 发 5 个事件(text/event-stream),每个间隔 0.3 s,客户端记录每批数据到达的时间。生成器有两种写法:async 生成器(await asyncio.sleep)和普通生成器(time.sleep);服务器有 ASGI(uvicorn)与 WSGI(gunicorn)。", n=fl([['async 生成器', 'await asyncio.sleep'], ['sync 生成器', 'time.sleep']], cur=[0, 1]), kv=KV([['事件', '5 个,间隔 0.3 s']], ['事件'])),
    step(f"uvicorn + async 生成器:首批 {f('uvicorn_as')} ms 到达,最后一批 {tt['uvicorn_as']['total']:.0f} ms,5 批分开到达——真正的流式。", t=tl(L1[:1]), done=[0], b=bars([['首批到达', tt['uvicorn_as']['first'], f"{f('uvicorn_as')} ms"], ['最后一批', tt['uvicorn_as']['total'], f"{tt['uvicorn_as']['total']:.0f} ms"]], 1600, done=[0, 1]), kv=KV([['ASGI + async 生成器', '流式']], ['ASGI + async 生成器'])),
    step(f"uvicorn + sync 生成器:首批 {f('uvicorn_ss')} ms,最后一批 {tt['uvicorn_ss']['total']:.0f} ms,5 批同时到——被缓冲了。服务端警告:「{w['uvicorn'][0]}」。", t=tl(L1[1:3]), mark=[0], b=bars([['首批到达', tt['uvicorn_ss']['first'], f"{f('uvicorn_ss')} ms"], ['最后一批', tt['uvicorn_ss']['total'], f"{tt['uvicorn_ss']['total']:.0f} ms"]], 1600, mark=[0]), kv=KV([['ASGI + sync 生成器', '被缓冲,不是流式']], ['ASGI + sync 生成器'])),
    step(f"gunicorn(WSGI)反过来:sync 生成器首批 {f('gunicorn_ss')} ms、流式;async 生成器首批 {f('gunicorn_as')} ms、最后一批 {tt['gunicorn_as']['total']:.0f} ms,同样被缓冲,并有警告:「{w['gunicorn'][0]}」。", t=tl(L1[3:]), b=bars([['WSGI + sync:首批', tt['gunicorn_ss']['first'], f"{f('gunicorn_ss')} ms"], ['WSGI + async:首批', tt['gunicorn_as']['first'], f"{f('gunicorn_as')} ms"]], 1600, mark=[1], done=[0]), kv=KV([['规则', '生成器类型要与服务器匹配']], ['规则'])),
    step("客户端读到第一批就断开:服务端 async 生成器的 finally 执行了(events.log 里有记录),说明生成器被中止并做了清理。", t=tl(L2), done=[0], kv=KV([['客户端断开', 'async 生成器被取消,finally 执行']], ['客户端断开'])),
    step(f"并发长连接:uvicorn 单个进程同时 30 个 async 流(每个 1.5 s)总耗时 {R['c_uv']:.0f} ms;gunicorn 一个同步 worker 同时 6 个流(每个 1.5 s)总耗时 {R['c_gu']:.0f} ms(6 × 1.5 s,一个接一个)。", t=tl(L3), b=bars([['uvicorn:30 个流', R['c_uv'], f"{R['c_uv']:.0f} ms"], ['gunicorn:6 个流', R['c_gu'], f"{R['c_gu']:.0f} ms"]], 9200, mark=[1], done=[0]), kv=KV([['同步 worker', '一个长连接占满一个 worker']], ['同步 worker'])),
]
A = dict(
    n=117, series='django', tags='Django,StreamingHttpResponse,SSE,ASGI,真实验证,动画演示',
    desc=f'流式响应要让生成器类型与服务器匹配:uvicorn + async 生成器首批 {f("uvicorn_as")} ms、5 批分开到达;uvicorn + sync 生成器和 gunicorn + async 生成器都被缓冲到 {tt["uvicorn_ss"]["total"]:.0f} ms 才一起到,并有警告;客户端断开时 async 生成器的 finally 会执行;uvicorn 单进程 30 个长流 {R["c_uv"]:.0f} ms,gunicorn 同步 worker 6 个长流 {R["c_gu"]:.0f} ms。',
    lead='想用 StreamingHttpResponse 做 SSE 或长连接,要先弄清两件事:生成器该写成 sync 还是 async?一个长连接会占用什么?这篇在 uvicorn 与 gunicorn 上把四种组合、客户端断开、以及并发长连接都量出来。',
    facts=[('生成器要与服务器匹配', 'ASGI 用 async 生成器,WSGI 用 sync 生成器;不匹配会被缓冲并警告'), (f'{R["c_uv"]:.0f} ms', 'uvicorn 单进程同时 30 个 1.5 s 的长流的总耗时'), (f'{R["c_gu"]:.0f} ms', 'gunicorn 一个同步 worker 同时 6 个 1.5 s 的长流(排队)')],
    body=[
        sec('四种组合的首批到达时间', '', term('', blk('d117', 1)), '<p>缓冲的意思是:服务端把整个生成器读完才开始发,首批到达时间等于总时间。Django 在这两种不匹配的情况下都会打出警告,可以从日志里发现。</p>'),
        sec('客户端断开', '', term('', blk('d117', 2)), '<p>生成器里的 <code>try/finally</code> 在客户端断开后执行了,适合放释放资源的代码。这是在 uvicorn + async 生成器下测的,别的服务器没有测。</p>'),
        sec('并发长连接', '', term('', blk('d117', 3)), '<p>ASGI 下一个进程能同时挂很多长连接(这里 30 个);WSGI 同步 worker 一次只处理一个请求,一个长流会占满一个 worker。这就是长连接场景要用 ASGI(或者多线程 worker)的原因。</p>'),
        sec('分步演示', '', demo('流式响应与长连接', [('n', 'flow', '两种生成器'), ('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。uvicorn 与 gunicorn 同步 worker 各 1 个进程;事件 5 个、间隔 0.3 s;30 / 6 个并发流由本机线程发出', '没有验证:数千以上的并发连接、代理(nginx)对 SSE 的缓冲、gunicorn gthread / gevent worker、心跳与超时设置、浏览器 EventSource 的重连行为'],
)
