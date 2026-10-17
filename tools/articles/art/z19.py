from lib import *
R = J('z19'); l5, ul, gl = R['limit5'], R['unlimited'], R['global']
def S(k): return [l for l in out('z19').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"maxClientCnxns=5(按客户端 IP 限制):同一个 IP 依次开 8 个客户端,{l5['ok']} 个成功、{l5['bad']} 个失败(连接超时)。服务端日志里是「Error accepting new connection: Too many connections from /127.0.0.1 - max is 5」(客户端重试,所以出现很多行)。被拒的客户端只会看到连接超时,看不到「连接数太多」的错误——要去服务端日志里找原因。", t=tl(S(1)), mark=[0], kv=KV([['超限时', '客户端连接超时,服务端日志记录原因']], ['超限时'])),
    step("关掉一个已有连接,名额马上空出来:新的客户端立刻连上。限制只针对同时存在的连接数。", t=tl(S(2)), done=[0], kv=KV([['名额', '连接关闭即释放']], ['名额'])),
    step(f"maxClientCnxns=0 表示不限制:开 80 个客户端,{ul['ok']} 个成功、{ul['bad']} 个失败,服务端连接数 81(含我查询用的那一个)。", t=tl(S(3)), done=[0], kv=KV([['0', '不限制(按 IP)']], ['0'])),
    step(f"全局上限 zookeeper.maxCnxns(整个服务端,不区分 IP):设成 4、开 8 个客户端,{gl['ok']} 个成功、{gl['bad']} 个失败;日志里是「maxCnxns configured value is 4.」和「Too many connections 4 - max is 4」。本实验是用 JVM 系统属性设置的;能否写在 zoo.cfg 里我没有测。", t=tl(S(4)), mark=[0], kv=KV([['maxCnxns', '全局上限,系统属性'], ['maxClientCnxns', '每个 IP 的上限,zoo.cfg']], ['maxCnxns'])),
]
A = dict(
    n=19, series='zookeeper', tags='ZooKeeper,maxClientCnxns,连接限制,真实验证,动画演示',
    desc=f'maxClientCnxns 实测:=5 时同一 IP 开 8 个客户端 {l5["ok"]} 个成功、{l5["bad"]} 个连接超时,服务端日志记录「Too many connections from /127.0.0.1 - max is 5」;关闭连接后名额释放;=0 不限制({ul["ok"]} 个全部成功);全局上限 zookeeper.maxCnxns=4 时 {gl["ok"]} 个成功。',
    lead='maxClientCnxns 限制的是每个客户端 IP 的并发连接数。超过之后客户端看到的是什么?怎么释放?0 是什么意思?还有没有全局上限?这篇逐项验证。',
    facts=[(f'{l5["ok"]} 成功 / {l5["bad"]} 超时', 'maxClientCnxns=5 时,同一 IP 开 8 个客户端'), ('日志里找原因', '客户端只看到连接超时,拒绝原因只在服务端日志'), ('maxClientCnxns=0', '表示不限制;全局上限是另一个参数 zookeeper.maxCnxns')],
    body=[
        sec('每个 IP 的上限', '', term('', blk('z19', 1)), '<p>本机所有客户端都来自 127.0.0.1,所以同一个 IP 的限制很容易触发。生产环境里,如果客户端经过 NAT 或代理,大量客户端会共用一个源 IP,更容易撞上这个限制。(NAT 场景本文没有测。)</p>'),
        sec('释放与不限制', '', term('', blk('z19', 2) + '\n' + blk('z19', 3))),
        sec('全局上限', '', term('', blk('z19', 4))),
        sec('分步演示', '', demo('连接数限制', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,每个场景一个新实例;客户端是 kazoo(连接超时设 4 s);全局上限用 -Dzookeeper.maxCnxns=4', '没有验证:Netty 连接工厂下的行为、不同源 IP 之间互不影响(本机只有 127.0.0.1)、连接限流 connection throttling(BlueThrottle)、限制值与线程 / 文件描述符的关系'],
)
