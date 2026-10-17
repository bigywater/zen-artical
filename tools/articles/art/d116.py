from lib import *
R = J('d116'); lat = R['lat']; cc = R['conc']
def L(k): return [l for l in out('d116').split('== ')[k + 1].splitlines()[1:] if l.strip()]
d_ = lat['sync1'] - lat['none']
steps = [
    step("Django 的中间件有 sync_capable / async_capable 两个标志。普通类中间件默认只支持 sync。在 ASGI 下,只支持 sync 的中间件会被适配(在线程里运行);只支持 async 的中间件(自己声明 async_capable=True)不用适配。", n=fl([['只支持 sync 的中间件', '要适配'], ['async 中间件', '不需要适配']], cur=[0]), kv=KV([['标志', 'sync_capable / async_capable']], ['标志'])),
    step(f"串行请求一个 async 视图 400 次,uvicorn:没有中间件 {lat['none']:.3f} ms;5 个 async 中间件 {lat['async5']:.3f} ms;1 个只支持 sync 的中间件 {lat['sync1']:.3f} ms(约 +{d_:.2f} ms);5 个只支持 sync 的 {lat['sync5']:.3f} ms(几乎不比 1 个多)。", t=tl(L(0)), b=bars([['没有中间件', lat['none'], f"{lat['none']:.3f}"], ['5 个 async', lat['async5'], f"{lat['async5']:.3f}"], ['1 个 sync', lat['sync1'], f"{lat['sync1']:.3f}"], ['5 个 sync', lat['sync5'], f"{lat['sync5']:.3f}"]], 0.75, mark=[2, 3], done=[0, 1]), kv=KV([['第一个 sync 中间件', f'+{d_:.2f} ms(一次线程切换)'], ['后面的 sync 中间件', '几乎不再增加']], ['第一个 sync 中间件'])),
    step("django.request 的 DEBUG 日志会记录适配:Asynchronous handler adapted for middleware proj.mw.SyncMW.(5 个 sync 中间件去重后只有这一行);全是 async 中间件时日志里没有 adapted 的行。", t=tl(L(1)), mark=[0], kv=KV([['日志线索', 'adapted for middleware …']], ['日志线索'])),
    step(f"更重要的问题:sync 中间件里的阻塞会不会拖垮并发?20 个并发请求,中间件里等 0.2 s:async 中间件里 await asyncio.sleep(0.2) 总耗时 {cc['asyncsleep']:.0f} ms;sync 中间件里 time.sleep(0.2) 总耗时 {cc['syncsleep']:.0f} ms——几乎一样,因为每个请求的 sync 部分在自己的线程里(和 112、113 篇一致)。", t=tl(L(2)), b=bars([['async 中间件 await sleep', cc['asyncsleep'], f"{cc['asyncsleep']:.0f} ms"], ['sync 中间件 time.sleep', cc['syncsleep'], f"{cc['syncsleep']:.0f} ms"]], 500, done=[0, 1]), kv=KV([['结论', 'sync 中间件不会让请求互相排队(这个测法下)']], ['结论'])),
]
A = dict(
    n=116, series='django', tags='Django,中间件,ASGI,异步,真实验证,动画演示',
    desc=f'同步中间件在 ASGI 下会被适配到线程里:400 次串行请求,没有中间件 {lat["none"]:.3f} ms → 1 个 sync 中间件 {lat["sync1"]:.3f} ms(+{d_:.2f} ms),5 个 sync 也只有 {lat["sync5"]:.3f} ms;DEBUG 日志会记录 adapted;20 并发下 sync 中间件里 sleep 并不会让请求排队({cc["syncsleep"]:.0f} ms vs {cc["asyncsleep"]:.0f} ms)。',
    lead='ASGI 下只要有一个中间件不支持 async,Django 就得为它做适配。这篇量一下适配的代价、日志里怎么看出来,以及「sync 中间件会不会毁掉并发」这个常见担心有没有在实验里成立。',
    facts=[(f'+{d_:.2f} ms', '加 1 个只支持 sync 的中间件后,单个请求的耗时增量(uvicorn,DEBUG=True)'), (f'{lat["sync5"]:.3f} ms', '5 个 sync 中间件的耗时,几乎与 1 个相同'), (f'{cc["syncsleep"]:.0f} vs {cc["asyncsleep"]:.0f} ms', '20 并发下 sync / async 中间件里等 0.2 s 的总耗时')],
    body=[
        sec('适配的代价', '', term('', blk('d116', 1)), '<p>额外耗时约 0.15 ms,而且第一个 sync 中间件之后几乎不再增加——推测是连续的 sync 中间件共用了同一次线程切换(我没有查源码验证)。这里的请求耗时是 DEBUG=True 时串行测的,数字只用来比较,不是绝对性能。</p>'),
        sec('怎么在日志里发现', '', term('', blk('d116', 2))),
        sec('sync 中间件会毁掉并发吗?', '', term('', blk('d116', 3)), '<p>在这个测法下不会:20 个并发请求,sync 中间件里 <code>time.sleep(0.2)</code> 与 async 中间件里 <code>await asyncio.sleep(0.2)</code> 总耗时相同。原因是每个请求的同步部分在自己的线程里(第 112 篇)。但线程数不是无限的(第 113 篇量到过线程池上限),并发数远高于 20 时未必仍然成立,本文没有测。</p>'),
        sec('分步演示', '', demo('同步中间件与 ASGI', [('n', 'flow', '标志'), ('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。uvicorn 1 个进程;中间件是自己写的 4 种极简类(sync / sync sleep / async / async sleep);延迟是 400 次串行请求的中位数(先预热 30 次)', '没有验证:第三方中间件的真实开销、中间件里访问 ORM / session 的情形、并发数很高时的线程池耗尽、sync 与 async 中间件混排时的适配次数(本文只测了全 sync 与全 async)'],
)
