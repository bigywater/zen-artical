from lib import *
R = J('z52'); rows = R['rows']
def S(k): return [l for l in out('z52').split('== ')[k].splitlines()[1:] if l.strip()]
r = {(a, b): c for a, b, c in rows}
k3, k10 = [c for a, b, c in rows if a.startswith('kill') and b == 3][0], [c for a, b, c in rows if a.startswith('kill') and b == 10][0]
f3, f10 = [c for a, b, c in rows if a.startswith('进程冻结') and b == 3][0], [c for a, b, c in rows if a.startswith('进程冻结') and b == 10][0]
cl = [c for a, b, c in rows if a.startswith('正常')][0]
steps = [
    step(f"服务实例把自己注册成 /services/web 下的临时节点,另一个客户端 watch 这个父节点。实例消失的方式不同,被发现的时间差别巨大:正常退出(close 会话){cl:.0f} ms(几乎立刻);kill -9 在会话超时 3 s 下 {k3:.0f} ms、10 s 下 {k10:.0f} ms;进程冻结(SIGSTOP,类似长 GC)3 s 下 {f3:.0f} ms、10 s 下 {f10:.0f} ms。", t=tl(S(1)), b=bars([['close()', cl, f'{cl:.0f} ms'], ['kill -9 / 3 s', k3, f'{k3:.0f} ms'], ['冻结 / 3 s', f3, f'{f3:.0f} ms'], ['kill -9 / 10 s', k10, f'{k10:.0f} ms'], ['冻结 / 10 s', f10, f'{f10:.0f} ms']], f10 * 1.1, mark=[1, 2, 3, 4], done=[0]), kv=KV([['正常退出', f'{cl:.0f} ms'], ['崩溃 / 冻结', '≈ 会话超时']], ['崩溃 / 冻结'])),
    step(f"服务端按会话超时判定实例失联:kill -9 的会话超时从 3 s 改到 10 s,被发现的时间从 {k3:.0f} ms 变成 {k10:.0f} ms,差 {R['diff']:.0f} ms,约等于超时差 7000 ms。所以「服务摘除要多快」可以用会话超时直接调节——代价是更短的超时在 GC 停顿、网络抖动时更容易误摘(第 13、14 篇)。", t=tl(S(2)), done=[0], kv=KV([['摘除延迟', '≈ 会话超时'], ['取舍', '超时越短,越快但越容易误判']], ['摘除延迟'])),
]
A = dict(
    n=52, series='zookeeper', tags='ZooKeeper,故障检测,会话超时,服务注册,真实验证,动画演示',
    desc=f'服务故障感知实测:临时节点 + 父节点 watch。正常退出 {cl:.0f} ms 被发现;kill -9 / 进程冻结要等会话超时(3 s → {k3:.0f} / {f3:.0f} ms,10 s → {k10:.0f} / {f10:.0f} ms)。',
    lead='用 ZooKeeper 做服务注册,实例挂了多久能被发现?这篇让真实的实例进程用不同方式「消失」(正常退出、kill -9、被冻结),另一个客户端监听,量发现的时间,再把会话超时从 3 秒改到 10 秒看差别。',
    facts=[(f'{cl:.0f} ms', '实例正常关闭会话时被发现的时间'), (f'{k3:.0f} / {k10:.0f} ms', 'kill -9 在会话超时 3 s / 10 s 下被发现的时间'), ('≈ 会话超时', '崩溃与冻结被发现的时间由会话超时决定')],
    body=[
        sec('三种消失方式', '', term('', blk('z52', 1))),
        sec('会话超时就是摘除延迟', '', term('', blk('z52', 2)), '<p>这是服务发现里「实例挂了多久会被摘除」的答案,也是第 8 篇里临时节点消失时间的应用。如果应用要求更快的摘除,还可以叠加应用层的健康检查,本文没有测。</p>'),
        sec('分步演示', '', demo('故障感知', [('t', 'term', '输出'), ('b', 'bars', '被发现的时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,tickTime=1000;实例是单独的 Python 进程(kazoo),被观察者用 children watch;每种组合只测一次', '没有验证:集群里服务端切换对发现时间的影响、大量实例同时消失时的通知风暴(第 17 篇)、应用层健康检查的叠加、实例重新注册的竞态'],
)
