from lib import *
S = SS('f166')
R = J('f166'); k = [x for x in R if x not in ('t0',)]
a2, a2p, b1, b1p, b1f = [R[x] for x in k[:5]]
t0 = R['t0']
steps = [
    step(f"2 个 sync worker、--timeout 2,一个 6 秒的慢请求把其中一个 worker 拖到被杀(慢请求自己得到 {a2['slow'][0]},约 {a2['slow'][1]:.0f} ms 时被杀);期间两个客户端每 50 ms 请求一次 /fast,共 {a2['n']} 个,失败 {a2['bad']} 个,p99 {a2['p99']:.0f} ms,最大 {a2['mx']:.0f} ms——另一个 worker 一直在服务,被杀的那一个没有被注意到。日志里 WORKER TIMEOUT {a2['to']} 次、worker 启动 {a2['boots']} 次(2 个初始加 1 个重启)。--preload 下结果相同({a2p['n']} 个、失败 {a2p['bad']}、p99 {a2p['p99']:.0f} ms)。worker 数多时,一个坏请求只丢一个 worker,服务看起来正常。", t=tl(S(1)), done=lidx(S(1), '2 个 worker'), kv=KV([['2 个 worker', f"/fast 失败 {a2['bad']},p99 {a2['p99']:.0f} ms"], ['被杀的 worker', '另一个 worker 接着服务']], ['2 个 worker'])),
    step(f"只有 1 个 worker 时,同样的场景:不加 --preload(应用导入要 1.5 秒):/fast 的 p99 是 {b1['p99']:.0f} ms、最大 {b1['mx']:.0f} ms——慢请求占着唯一的 worker 直到 2 秒被杀,新 worker 再花 1.5 秒导入应用,排队的请求等了约 4 秒(失败 {b1['bad']} 个,只是慢);--preload(master 导入一次,新 worker 直接从 master fork)最大 {b1p['mx']:.0f} ms——只等到被杀为止,没有再等导入;导入很快时最大 {b1f['mx']:.0f} ms(等的是慢请求自己的约 3 秒:--timeout 2 实际在约 {b1f['slow'][1] / 1000:.1f} 秒时才杀掉,gunicorn 每隔一段时间才检查一次)。杀掉 worker 之后的恢复时间,取决于应用导入有多重——--preload 能把这部分省掉。", b=bars([['不加 --preload', b1['mx'], f"{b1['mx']:.0f} ms"], ['--preload', b1p['mx'], f"{b1p['mx']:.0f} ms"], ['导入很快', b1f['mx'], f"{b1f['mx']:.0f} ms"]], b1['mx'], mark=[0], done=[1, 2]), t=tl(S(2)), mark=lidx(S(2), '不加 --preload'), done=lidx(S(2), '--preload', '导入很快'), kv=KV([['1 个 worker,不加 --preload', f"请求最多等 {b1['mx']:.0f} ms"], ['--preload', f"最多等 {b1p['mx']:.0f} ms"]], ['--preload'])),
    step(f"--timeout 0 关闭超时:4 秒的慢请求得到 {t0[0]},用时 {t0[1]:.0f} ms,日志里没有 WORKER TIMEOUT——没有人会杀掉卡住的 worker,一个死循环的请求就能永久占住一个 worker。0 只适合明确知道有长请求、并且别处有保护(反向代理超时、gthread 或 gevent)的场景。", t=tl(S(3)), done=lidx(S(3), '--timeout 0'), kv=KV([['--timeout 0', '永远不杀,卡住的 worker 不会被回收']], ['--timeout 0'])),
]
A = mkartf('f166', 166, 'Flask,gunicorn,worker timeout,preload,重启,真实验证,动画演示',
    f'实测 gunicorn 的 worker timeout:2 个 worker 时一个被杀的 worker 不影响服务(/fast 失败 {a2["bad"]}、p99 {a2["p99"]:.0f} ms);只有 1 个 worker 时,不加 --preload 的排队请求最多等 {b1["mx"]:.0f} ms,--preload 降到 {b1p["mx"]:.0f} ms;--timeout 0 时慢请求永不被杀。',
    'worker 被 --timeout 杀掉之后会发生什么?对其他请求有多大影响?--preload 有什么用?--timeout 0 安全吗?这篇用真实的 gunicorn 与持续的请求流把答案量出来。',
    [(f'{b1["mx"]:.0f} → {b1p["mx"]:.0f} ms', '单 worker 被杀后 /fast 的最大延迟:不加 --preload 与加 --preload(导入要 1.5 秒)'), (f'失败 {a2["bad"]}', '2 个 worker 时一个被杀,/fast 失败的请求数'), ('WORKER TIMEOUT', '被杀的 worker 在 gunicorn 日志里的标志')],
    [('2 个 worker', '<p>上一篇:<a href="flask-gunicorn-worker-count.html">Gunicorn Worker 数量</a>;下一篇:<a href="flask-pool-size.html">连接池大小</a>。</p><p>第 147 篇看过 --timeout 在各种 worker 类型下的行为,这一篇看 worker 被杀之后对其他请求的影响。</p>'), ('只有 1 个 worker', '<p>应用导入用 time.sleep 模拟重型依赖的加载时间。</p>'), ('--timeout 0', None)],
    steps, [ENV_F + '。gunicorn sync worker', '没有验证:gthread 与 gevent 下的行为(第 147 篇看过 --timeout 对它们不生效)、--max-requests 的自动重启与抖动参数、容器编排对健康检查失败的重启叠加、preload 与数据库连接在 fork 后的问题(第 145 篇提到)'], 'Worker Timeout')
