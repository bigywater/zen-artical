from lib import *
S = SS('f148')
R = J('f148'); dl = R['delay']; cp = R['cap']; g3 = R['gevent300']
k = list(cp); a, b = cp[k[0]], cp[k[1]]
steps = [
    step(f"消息送达延迟(各 10 条消息、随机时刻发布):长轮询(服务端用 threading.Condition 挂起请求,有新消息立刻唤醒)的送达延迟中位数 {dl['long'][0]:.1f} ms、最大 {dl['long'][1]:.1f} ms;每秒一次的短轮询中位数 {dl['short'][0]:.0f} ms、最大 {dl['short'][1]:.0f} ms(平均要等半个轮询间隔)。长轮询的延迟接近一次本机往返,短轮询的延迟取决于间隔。", b=bars([['长轮询 中位数', max(dl['long'][0], 1), f"{dl['long'][0]:.1f} ms"], ['每秒短轮询 中位数', dl['short'][0], f"{dl['short'][0]:.0f} ms"]], dl['short'][0], mark=[1], done=[0]), t=tl(S(1)), done=lidx(S(1), '长轮询'), mark=lidx(S(1), '短轮询'), kv=KV([['长轮询', f"{dl['long'][0]:.1f} ms"], ['每秒短轮询', f"{dl['short'][0]:.0f} ms"]], ['长轮询'])),
    step(f"每个等待中的轮询占一个线程:gunicorn gthread 1 个 worker × 8 线程,8 个客户端在等待,第 9 个普通请求 /ping 用了 {a:.0f} ms(要等某个轮询超时释放线程,这里轮询的超时是 3 秒);gevent 同样的场景 /ping 只要 {b:.0f} ms;gevent 同时挂着 300 个等待中的轮询,/ping 仍然只用 {g3[0]:.0f} ms,整个 gunicorn(含 master)内存约 {g3[1]:.0f} MB。长轮询在同步线程模型下很快耗尽并发,协程模型(或专门的实时服务)才合适。", b=bars([['gthread 8 线程', a, f'{a:.0f} ms'], ['gevent', max(b, 1), f'{b:.0f} ms']], a, mark=[0], done=[1]), t=tl(S(2)), mark=lidx(S(2), 'gthread'), done=lidx(S(2), 'gevent'), kv=KV([['gthread', f'8 个轮询占满线程,普通请求等 {a:.0f} ms'], ['gevent', f'300 个轮询,/ping {g3[0]:.0f} ms,约 {g3[1]:.0f} MB']], ['gevent'])),
    step(f"不丢消息要靠游标:客户端上次收到 id=1,断开期间服务端又发布了 id=2、3;重新连接时带 since=1,拿到的就是 {R['cursor']};之后没有新消息,since=3 的轮询等 {R['empty'][1]:.0f} ms 超时返回 {R['empty'][0]}(空)。客户端要记住最后收到的 id,每次重连都带上;超时返回空并立刻重连。", t=tl(S(3)), done=lidx(S(3), 'since=1', 'since=3'), kv=KV([['since 游标', '重连后从上次的位置继续,不丢消息'], ['超时', '返回 204,客户端立刻重连']], ['since 游标'])),
]
A = mkartf('f148', 148, 'Flask,长轮询,Condition,gevent,真实验证,动画演示',
    f'实测 Flask 长轮询:服务端用 threading.Condition 挂起请求,送达延迟中位数 {dl["long"][0]:.1f} ms(每秒短轮询是 {dl["short"][0]:.0f} ms);gthread 8 线程被 8 个等待的轮询占满后普通请求要等 {a:.0f} ms,gevent 挂着 300 个轮询仍然 {g3[0]:.0f} ms;用 since 游标重连不丢消息。',
    '长轮询在 Flask 里怎么写?延迟比短轮询好多少?为什么它特别吃线程?断线重连会不会丢消息?这篇用真实的 gunicorn gthread 与 gevent worker,把这些量出来。',
    [(f'{dl["long"][0]:.1f} → {dl["short"][0]:.0f} ms', '送达延迟中位数:长轮询与每秒短轮询'), (f'{a:.0f} vs {b:.0f} ms', '8 个轮询在等待时,普通请求的耗时:gthread 8 线程与 gevent'), ('since', '用来在重连时不丢消息的游标参数')],
    [('长轮询的延迟', '<p>上一篇:<a href="flask-request-timeout.html">请求超时</a>;下一篇:<a href="flask-server-sent-events.html">Server-Sent Events</a>。</p>'), ('占用线程', None), ('游标与重连', None)],
    steps, [ENV_F + '。gunicorn gthread 与 gevent worker', '没有验证:多进程下事件的共享(需要 redis 发布订阅等,见第 145 篇)、经过 nginx 时 proxy_read_timeout 与缓冲的影响、浏览器端的实现、大量轮询客户端同时超时重连造成的惊群'], '长轮询')
