from lib import *
R = J('d113'); ts = R['ts']; fifty = R['fifty']; conc = R['conc']
def L(k): return [l for l in out('d113').split('== ')[k + 1].splitlines()[1:] if l.strip()]
steps = [
    step("在一个 async 视图里连续 5 次 await sync_to_async(f)()(默认 thread_sensitive=True):5 次都在同一个线程 ThreadPoolExecutor-2_0——同一个请求里所有被 sync_to_async 包起来的同步代码共用一个线程。", t=tl(L(0)), done=[0], kv=KV([['thread_sensitive=True', '同一请求内同一个线程']], ['thread_sensitive=True'])),
    step(f"同一个请求里 gather 10 个各睡 0.2 s 的 sync_to_async:thread_sensitive=True 总耗时 {ts['1']['ms']:.0f} ms、只用 1 个线程(串行);thread_sensitive=False 总耗时 {ts['0']['ms']:.0f} ms、用了 10 个线程。", t=tl(L(1)), b=bars([['thread_sensitive=True', ts['1']['ms'], f"{ts['1']['ms']:.0f} ms"], ['thread_sensitive=False', ts['0']['ms'], f"{ts['0']['ms']:.0f} ms"]], 2100, mark=[0], done=[1]), kv=KV([['True', '同一线程,串行'], ['False', '线程池,并行']], ['True'])),
    step(f"不同请求之间不互相影响:20 个并发请求,每个各做一次 0.5 s 的 sync_to_async(默认 True),总耗时 {conc['total']:.0f} ms,用到 {conc['threads']} 个不同线程——「同一个线程」只在同一个请求之内成立。", t=tl(L(2)), done=[0], kv=KV([['20 个请求', f"{conc['threads']} 个线程"], ['总耗时', f"{conc['total']:.0f} ms"]], ['20 个请求'])),
    step(f"thread_sensitive=False 也有上限:一个请求里 gather 50 个 0.2 s 任务,总耗时 {fifty['ms']:.0f} ms,只用了 {fifty['n_threads']} 个线程(被线程池大小限制,大约分 4 批)。", t=tl(L(3)), b=bars([['理想(50 个并行)', 200, '200 ms'], ['实测', fifty['ms'], f"{fifty['ms']:.0f} ms"]], 900, mark=[1]), kv=KV([['线程数', f"{fifty['n_threads']}(本机)"]], ['线程数'])),
]
A = dict(
    n=113, series='django', tags='Django,asgiref,sync_to_async,线程,真实验证,动画演示',
    desc=f'sync_to_async 的线程行为:默认 thread_sensitive=True 时同一请求里全部同步代码共用一个线程(10 个 0.2 s 任务 {ts["1"]["ms"]:.0f} ms);thread_sensitive=False 用线程池({ts["0"]["ms"]:.0f} ms、10 个线程,50 个任务只用到 {fifty["n_threads"]} 个线程);不同请求互不影响。',
    lead='在 async 视图里调用同步代码要用 sync_to_async。它有一个 thread_sensitive 参数,决定「所有同步代码是不是共用一个线程」。这篇在真实的 uvicorn 里量出两种模式的线程与耗时差别。',
    facts=[('True vs False', f'10 个 0.2 s 任务:{ts["1"]["ms"]:.0f} ms(1 线程)vs {ts["0"]["ms"]:.0f} ms(10 线程)'), ('每请求独立', '20 个并发请求 → 20 个线程,互不排队'), (f'{fifty["n_threads"]} 个线程', '50 个任务在 thread_sensitive=False 下只用到的线程数(本机)')],
    body=[
        sec('thread_sensitive=True:同一个请求共用一个线程', '', term('', blk('d113', 1)), '<p>为什么要这样?因为 Django 的数据库连接是「每线程一个」,并且很多同步代码(ORM、部分中间件、事务)假定自己一直在同一个线程里。所以默认让同一个请求里的同步代码都回到同一个线程里执行。(这一段解释来自设计上的理解,本文实验验证的是「线程相同」这一现象。)</p>'),
        sec('代价:串行', '', term('', blk('d113', 2)), '<p>同一请求里 gather 多个 sync_to_async,默认模式下会排队执行。要并发就得 <code>thread_sensitive=False</code>,但这时每个任务在不同线程里,<b>ORM 会在每个线程里开自己的数据库连接</b>(下一篇 115 会在 PostgreSQL 上量到)。</p>'),
        sec('不同请求不会互相排队', '', term('', blk('d113', 3))),
        sec('线程池上限', '', term('', blk('d113', 4)), '<p>50 个任务只用了 14 个线程,总耗时约 4 个批次。这个上限我没有去拆它是由什么决定的(默认线程池大小、<code>ASGI_THREADS</code> 等),只报告本机现象。</p>'),
        sec('分步演示', '', demo('sync_to_async 的线程', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。uvicorn 1 个进程,视图里用 sync_to_async 包 time.sleep', '没有验证:线程池上限由什么决定、ASGI_THREADS 环境变量的作用、多 worker、嵌套 async_to_sync / sync_to_async 的线程归属'],
)
