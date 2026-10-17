from lib import *
R = J('z3'); d = R['defaults']; ng = R['negot']
def S(k): return [l for l in out('z3').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"最小配置(只有 dataDir 和 clientPort):用四字命令 conf 看生效值——tickTime={d['tickTime']}(默认 2000 ms)、minSessionTimeout={d['minSessionTimeout']}(= 2 × tickTime)、maxSessionTimeout={d['maxSessionTimeout']}(= 20 × tickTime)、maxClientCnxns={d['maxClientCnxns']}。", t=tl(S(1)[:5]), done=[0, 1, 2, 3], kv=KV([['tickTime', '2000 ms'], ['会话超时范围', '[2×tick, 20×tick]']], ['会话超时范围'])),
    step(f"会话超时的协商(tickTime=1000,范围 2000–20000):客户端请求 500 ms → 实际 {ng['500']} ms;2000 → {ng['2000']};8000 → {ng['8000']};60000 → {ng['60000']} ms。服务端把客户端的请求夹进 [min, max]。协商后的值用四字命令 cons 里的 to= 读出。", t=tl(S(2)), b=bars([['请求 500', ng['500'], f"→ {ng['500']}"], ['请求 2000', ng['2000'], f"→ {ng['2000']}"], ['请求 8000', ng['8000'], f"→ {ng['8000']}"], ['请求 60000', ng['60000'], f"→ {ng['60000']}"]], 21000, mark=[0, 3], done=[1, 2]), kv=KV([['客户端设的超时', '只是请求值'], ['实际', '被夹进 [min, max]']], ['实际'])),
    step("自己设值:tickTime=500、minSessionTimeout=1000、maxSessionTimeout=3000、maxClientCnxns=2,conf 全部如实反映;客户端请求 20000 ms 只得到 3000 ms。maxClientCnxns=2 时同一个 IP 已有 2 个连接,第 3 个客户端得到 KazooTimeoutError,连四字命令 cons(也是一个连接)也被拒绝,返回空。集群节点的 conf 里能看到 initLimit=3、syncLimit=2。", t=tl(S(3)), mark=[2, 3], done=[0, 1], kv=KV([['maxClientCnxns', '按 IP 限制,四字命令也算一个连接']], ['maxClientCnxns'])),
    step("写错参数名:把 tickTime 写成 tickTim=1000,ZooKeeper 照常启动,conf 里的 tickTime 仍是 2000,日志里一行关于 tickTim 的提示都没有。拼错参数名不会报错,只会悄悄用默认值。", t=tl(S(4)), mark=[0, 1], kv=KV([['拼错参数名', '静默忽略,用默认值']], ['拼错参数名'])),
]
A = dict(
    n=3, series='zookeeper', tags='ZooKeeper,zoo.cfg,配置,真实验证,动画演示',
    desc=f'用 conf 命令看 zoo.cfg 的生效值:tickTime 默认 2000 ms,会话超时范围 [2×tick, 20×tick];客户端请求 60000 ms 被夹到 {ng["60000"]} ms;maxClientCnxns 连四字命令也算;拼错参数名(tickTim)静默忽略。',
    lead='zoo.cfg 里几个参数最常被问:tickTime、会话超时、maxClientCnxns、initLimit / syncLimit。这篇不抄文档,每个都起一个实例,用四字命令 conf 和 cons 看它实际生效的值,并试一试写错参数名会怎样。',
    facts=[('2 × tick ~ 20 × tick', '服务端允许的会话超时范围(默认);客户端请求的值被夹在里面'), (f'{ng["60000"]} ms', 'tickTime=1000 时,客户端请求 60000 ms 实际得到的会话超时'), ('静默忽略', '拼错的参数名不会报错、日志里也没有提示')],
    body=[
        sec('默认值', '', term('', blk('z3', 1))),
        sec('会话超时怎么协商', '', term('', blk('z3', 2)), '<p>在客户端库里设置的「会话超时」只是一个请求值。想知道真正生效的值,要看服务端:四字命令 <code>cons</code> 里每个连接的 <code>to=</code>。</p>'),
        sec('自己设置的值与连接限制', '', term('', blk('z3', 3)), '<p><code>maxClientCnxns</code> 是按客户端 IP 统计的并发连接数上限。注意:监控脚本用四字命令也会占用名额,上限设得很小时,监控自己会被拒绝。</p>'),
        sec('写错参数名', '', term('', blk('z3', 4)), '<p>改完配置后,务必用 <code>conf</code> 命令确认值真的变了,不要只看进程启动成功。</p>'),
        sec('分步演示', '', demo('zoo.cfg 的生效值', [('t', 'term', '输出'), ('b', 'bars', '会话超时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。四字命令白名单设为 *(默认只有 srvr 等少数命令可用,见第 66、67 篇);客户端 kazoo', '没有验证:全部 zoo.cfg 参数(如 autopurge、snapCount 见第 53、54 篇;forceSync 见第 55 篇)、initLimit / syncLimit 对集群行为的影响(只验证了 conf 里能看到)、动态配置文件(第 50 篇)'],
)
