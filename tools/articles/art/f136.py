from lib import *
S = SS('f136')
R = J('f136'); io = R['io']; cp = R['cpu']; bl = R['block']; one = R['cpu_one']
k = list(io)
s1, s4, gt, fr, fn = [io[x][0] / 1000 for x in k]
c1, c4, cg, cf = [cp[x] / 1000 for x in list(cp)]
b1, b2 = list(bl.values())
steps = [
    step(f"8 个并发请求,每个在视图里等 1 秒(模拟等数据库或外部接口):gunicorn sync 1 个 worker 总共 {s1:.2f} 秒(一个接一个,串行);sync 4 个 worker {s4:.2f} 秒(4 个进程各处理 2 个);gthread 1 个 worker × 8 线程 {gt:.2f} 秒(8 个线程同时在等);flask run 开发服务器默认多线程 {fr:.2f} 秒;flask run --without-threads {fn:.2f} 秒(退回串行)。同步的 Flask 一个请求占一个线程或进程,等待的时间里它什么也做不了,并发度就等于线程数或进程数。", b=bars([['sync ×1', s1, f'{s1:.1f} s'], ['sync ×4', s4, f'{s4:.1f} s'], ['gthread 8 线程', gt, f'{gt:.1f} s'], ['flask run', fr, f'{fr:.1f} s'], ['--without-threads', fn, f'{fn:.1f} s']], s1, mark=[0, 4], done=[1, 2, 3]), t=tl(S(1)), mark=lidx(S(1), 'sync,1 个 worker', 'without-threads'), done=lidx(S(1), '4 个 worker', 'gthread', '开发服务器'), kv=KV([['sync 1 个 worker', f'{s1:.1f} 秒,串行'], ['4 个 worker / 8 线程', f'{s4:.1f} / {gt:.1f} 秒'], ['开发服务器', '默认多线程']], ['sync 1 个 worker'])),
    step(f"8 个并发请求,每个在视图里做固定量的纯计算(单个请求约 {one:.2f} 秒 CPU,本机 10 核):sync 1 个 worker {c1:.2f} 秒;sync 4 个 worker {c4:.2f} 秒;gthread 8 线程 {cg:.2f} 秒;开发服务器 {cf:.2f} 秒。线程在纯计算上没有帮助(Python 的 GIL 让同一进程里的线程轮流执行,{cg:.2f} 秒约等于串行的 {c1:.2f} 秒),多进程才有。(我第一次用「忙等到截止时间」模拟计算,得到的 gthread 总耗时只有 0.69 秒,那是因为各线程都在等同一个墙钟时间,并不消耗 CPU,结果不能说明问题,改成固定计算量后才对。)", b=bars([['sync ×1', c1, f'{c1:.2f} s'], ['sync ×4', c4, f'{c4:.2f} s'], ['gthread 8 线程', cg, f'{cg:.2f} s']], c1, mark=[0, 2], done=[1]), t=tl(S(2)), mark=lidx(S(2), 'sync,1 个 worker', 'gthread'), done=lidx(S(2), '4 个 worker'), kv=KV([['线程', '纯计算上不加速(GIL)'], ['进程', '多核并行']], ['线程'])),
    step(f"同一个 worker 里,一个慢请求会不会挡住快请求:sync 1 个 worker 在处理一个 2 秒的慢请求时,另一个只要 0 秒的请求等了 {b1:.0f} ms(排在后面);gthread 的同一个 worker 里,同样的快请求只用了 {b2:.0f} ms(另一个线程直接处理)。一个 sync worker 就是一个「队头阻塞」。", t=tl(S(3)), mark=lidx(S(3), 'sync,1 个 worker'), done=lidx(S(3), 'gthread'), kv=KV([['sync 1 个 worker', f'快请求被挡 {b1:.0f} ms'], ['gthread', f'快请求 {b2:.0f} ms']], ['sync 1 个 worker'])),
    step(f"线程并发不会让请求数据串掉:同一个进程的 8 个线程里并发处理 8 个请求,每个请求把自己的参数写进 g、睡 0.3 秒再读回来,读错的有 {R['ctx_wrong']} 个。request、g、session 这些上下文对象背后是按线程(或协程)隔离的存储,第 143 篇会展开。", t=tl(S(4)), done=lidx(S(4), '8 个并发请求'), kv=KV([['request / g', '按线程隔离,不会串']], ['request / g'])),
]
A = mkartf('f136', 136, 'Flask,同步模型,gunicorn,线程,GIL,真实验证,动画演示',
    f'实测 Flask 的同步请求模型:8 个各等 1 秒的请求在 sync 单 worker 下 {s1:.1f} 秒、4 个 worker 下 {s4:.1f} 秒、8 线程下 {gt:.1f} 秒;纯计算请求线程不加速而多进程加速;一个慢请求挡住 sync worker 里的快请求 {b1:.0f} ms;线程里的 request 与 g 不会串。',
    'Flask 是同步框架,到底意味着什么?一个 worker 能同时处理几个请求?线程和进程哪个对等待有帮助、哪个对计算有帮助?这篇用真实的 gunicorn 与开发服务器,把等待型和计算型两种负载各跑一遍。',
    [(f'{s1:.0f} → {gt:.0f} 秒', '8 个各等 1 秒的请求:gunicorn sync 单 worker 与 8 线程的总耗时'), (f'{cg:.1f} vs {c4:.1f} 秒', '8 个纯计算请求:8 线程与 4 个进程的总耗时'), ('0 个', '8 个线程并发写读 g 时读错的个数')],
    [('等待型负载', '<p>上一篇:<a href="flask-trusted-proxy-headers.html">信任代理头配置</a>;下一篇:<a href="flask-async-view.html">Flask Async View</a>。</p>'), ('计算型负载', None), ('队头阻塞', None), ('上下文互相独立', None)],
    steps, [ENV_F + '。gunicorn sync 与 gthread worker、flask run(Werkzeug 开发服务器),本机 10 核', '没有验证:gevent 与 eventlet 的协作式并发(见第 142 篇)、真实数据库等待下的数字、内存占用随 worker 与线程数的变化、Python 3.13 之后的自由线程(无 GIL)构建'], 'Flask 同步请求模型', panels=[('t', 'term', '实验输出'), ('b', 'bars', '总耗时'), ('kv', 'kv', '要点')])
