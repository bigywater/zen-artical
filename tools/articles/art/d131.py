from lib import *
R = J('d131'); c = R['conc']; w = R['workers']; t = R['term']
def S(k): return [l for l in out('d131').split('== ')[k].splitlines()[1:] if l.strip()]
u, dp, gu = c['uvicorn'], c['daphne'], c['gunicorn-uvicorn']
steps = [
    step(f"20 个并发请求、每个视图等 0.5 s,各起 1 个进程:uvicorn async {u['a']:.0f} ms / sync {u['s']:.0f} ms;daphne {dp['a']:.0f} / {dp['s']:.0f} ms;gunicorn + UvicornWorker {gu['a']:.0f} / {gu['s']:.0f} ms。三种部署方式的并发表现没有区别,async 与 sync 视图都不排队(与第 111 篇一致)。", t=tl(S(1)), b=bars([['uvicorn', u['a'], f"{u['a']:.0f} ms"], ['daphne', dp['a'], f"{dp['a']:.0f} ms"], ['gunicorn+Uvicorn', gu['a'], f"{gu['a']:.0f} ms"]], 600, done=[0, 1, 2]), kv=KV([['三种 ASGI 部署', '同样的并发表现']], ['三种 ASGI 部署'])),
    step(f"从启动进程到第一次能响应:uvicorn {u['boot']:.0f} ms、gunicorn + UvicornWorker {gu['boot']:.0f} ms、daphne {dp['boot']:.0f} ms(这个数字含我轮询时固定的 0.3 s 等待,只看相对大小;daphne 明显更慢,原因我没有查)。", t=tl(S(1)), b=bars([['uvicorn', u['boot'], f"{u['boot']:.0f} ms"], ['gunicorn+Uvicorn', gu['boot'], f"{gu['boot']:.0f} ms"], ['daphne', dp['boot'], f"{dp['boot']:.0f} ms"]], 2400, mark=[2], done=[0, 1]), kv=KV([['启动', 'daphne 最慢(本测法)']], ['启动'])),
    step("ASGI 的 lifespan 协议:uvicorn 在 info 日志里写「ASGI 'lifespan' protocol appears unsupported.」后继续启动——Django 的 ASGIHandler 不实现 lifespan,这条是正常提示,不是错误。", t=tl(S(2)), mark=[1], done=[2], kv=KV([['lifespan', 'Django 不支持,uvicorn 自动跳过']], ['lifespan'])),
    step(f"uvicorn --workers 2:40 个并发请求(各等 0.3 s)总耗时 {w['total']:.0f} ms,两个 worker 进程各处理了 {w['dist'][0]} 和 {w['dist'][1]} 个——均匀分摊。", t=tl(S(3)), done=[0], kv=KV([['--workers 2', f"{w['dist']}"]], ['--workers 2'])),
    step(f"SIGTERM 时还有一个 2 秒的在途请求:uvicorn 让它完成(结果 {t['uvicorn']['result']}),进程在 {t['uvicorn']['ms']:.0f} ms 后退出;daphne 立刻退出({t['daphne']['ms']:.0f} ms),在途请求的客户端得到 {t['daphne']['result']}(连接被断开)。滚动发布时这个差别会变成用户看到的错误。", t=tl(S(4)), mark=[1], done=[0], kv=KV([['uvicorn', 'SIGTERM 等在途请求完成'], ['daphne', '默认配置下直接断开']], ['daphne'])),
]
A = dict(
    n=131, series='django', tags='Django,ASGI,uvicorn,daphne,部署,真实验证,动画演示',
    desc=f'uvicorn、daphne、gunicorn + UvicornWorker 跑同一个 Django ASGI 应用:20 个并发请求都约 {u["a"]:.0f} ms;Django 不支持 lifespan(uvicorn 日志提示后继续);uvicorn --workers 2 均匀分摊;SIGTERM 时 uvicorn 等在途请求完成,daphne 直接断开。',
    lead='Django 的 ASGI 应用可以交给 uvicorn、daphne,或者 gunicorn 配 UvicornWorker。它们在并发、启动、多进程和优雅停止上有什么差别?这篇把三者各起一个真实进程,用同一个应用逐项对比。',
    facts=[(f'{u["a"]:.0f} ms', '三种 ASGI 部署方式处理 20 个并发请求,几乎一样'), ('lifespan', 'Django 不支持,uvicorn 日志提示后正常启动'), ('SIGTERM', 'uvicorn 等在途请求完成;daphne 直接断开(本测法)')],
    body=[
        sec('并发与启动', '', term('', blk('d131', 1)), '<p>并发能力来自 ASGI 与 Django 的线程分配(第 112、113 篇),与用哪个服务器关系不大。</p>'),
        sec('lifespan 提示', '', term('', blk('d131', 2))),
        sec('多个 worker', '', term('', blk('d131', 3)), '<p>uvicorn 自带的多进程模式由它自己管理 worker;需要更完整的进程管理(重启、信号)时,常见做法是 gunicorn 加 UvicornWorker,这里只验证了它能跑通并行,没有比较两者的进程管理能力。</p>'),
        sec('优雅停止', '', term('', blk('d131', 4)), '<p>daphne 的结果是它的默认启动参数下的现象,是否有选项可以让它等在途请求,我没有查。</p>'),
        sec('分步演示', '', demo('ASGI 服务器', [('t', 'term', '输出'), ('b', 'bars', '数字'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。uvicorn 0.54.0、daphne 4.2.3、uvicorn-worker 0.4.0、gunicorn 26.2.0;视图里 sleep 模拟等待;各配置只测一次', '没有验证:WebSocket / Channels、HTTP/2、长时间运行的内存、TLS 终止在 uvicorn / daphne 上、hypercorn 与 granian、更多 worker 时的启动时间'],
)
