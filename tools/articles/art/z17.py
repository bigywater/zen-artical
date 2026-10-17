from lib import *
R = J('z17'); nt, hd = R['notify'], R['herd']
def S(k): return [l for l in out('z17').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("300 个客户端都对同一个节点 /hot 注册了 data watch:服务端 wchs 显示「300 connections watching 1 paths Total watches:300」,mntr 的 zk_watch_count = 300。一个节点上可以挂很多 watch,服务端为每个连接记一个。", t=tl(S(1)), kv=KV([['wchs', '300 个连接 × 1 个路径']], ['wchs'])),
    step(f"一次 set 触发全部 300 个 watcher:set 调用自己用时 {nt['set_ms']:.0f} ms;{nt['n']}/300 个收到通知,第一个 {nt['first']:.0f} ms、中位 {nt['med']:.0f} ms、最后一个 {nt['last']:.0f} ms。对照只有 1 个 watcher 时通知在 {R['one']:.1f} ms 到达。通知是服务端逐个连接发送的,watcher 越多,同一次修改让 set 本身和最后一个通知都更慢。", t=tl(S(2) + S(4)), b=bars([['1 个 watcher', R['one'], f"{R['one']:.1f} ms"], ['300 个:第一个', nt['first'], f"{nt['first']:.0f} ms"], ['300 个:中位', nt['med'], f"{nt['med']:.0f} ms"], ['300 个:最后一个', nt['last'], f"{nt['last']:.0f} ms"]], nt['last'] * 1.1, mark=[3], done=[0, 1, 2]), kv=KV([['通知扇出', '每个 watcher 一次发送']], ['通知扇出'])),
    step(f"惊群:通知到达后 300 个客户端立刻重新 get 并重新注册 watch(典型写法),全部完成共 {hd['total']:.0f} ms,客户端侧单次 get 延迟中位 {hd['med']:.1f} ms、最大 {hd['mx']:.1f} ms,服务端自己统计的 zk_max_latency 只有 {hd['srv_max']} ms——这个规模下服务端并不吃力,延迟主要在客户端线程调度上。", t=tl(S(3)), kv=KV([['300 个同时重读', f"{hd['total']:.0f} ms 完成"], ['服务端 max 延迟', f"{hd['srv_max']} ms"]], ['服务端 max 延迟'])),
]
A = dict(
    n=17, series='zookeeper', tags='ZooKeeper,Watcher,惊群,真实验证,动画演示',
    desc=f'Watcher 风暴实测:300 个客户端 watch 同一个节点,一次 set 后 {nt["n"]} 个通知在 {nt["last"]:.0f} ms 内到齐(中位 {nt["med"]:.0f} ms,对照单个 watcher {R["one"]:.1f} ms);通知后 300 个客户端同时重读重注册共 {hd["total"]:.0f} ms,服务端 zk_max_latency 仅 {hd["srv_max"]} ms。',
    lead='一个节点上挂了几百上千个 watcher,它一变化,所有人同时收到通知又同时去读——这就是 Watcher 风暴(惊群)。这篇在 300 个客户端的规模上量通知扇出的时间和惊群时服务端的负载。',
    facts=[(f'{nt["last"]:.0f} ms', '300 个 watcher 的通知全部到达的时间'), (f'{hd["total"]:.0f} ms', '收到通知后 300 个客户端同时重读并重注册 watch 的总时间'), (f'{hd["srv_max"]} ms', '惊群时服务端自己统计的最大延迟')],
    body=[
        sec('一个节点上的很多 watch', '', term('', blk('z17', 1))),
        sec('一次修改,全部通知', '', term('', blk('z17', 2) + '\n' + blk('z17', 4))),
        sec('通知之后的惊群', '', term('', blk('z17', 3)), '<p>规模放大后(几千到几万个 watcher)才会成为问题。常见的缓解办法:让 watcher 只监听必要的节点、用「一个监听者 + 本地广播」代替每个客户端各自 watch、在重读前加随机延迟。这些办法本文没有实验验证。</p>'),
        sec('分步演示', '', demo('Watcher 风暴', [('t', 'term', '输出'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,JVM 堆 256 MiB;300 个 kazoo 客户端是同一进程里的线程(客户端侧的延迟含 Python 线程调度);只测一次', '没有验证:上千上万个 watcher、集群里分散在多个节点上的 watcher、通知发送的内部实现、缓解办法的效果'],
)
