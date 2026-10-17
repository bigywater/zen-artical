from lib import *
R = J('z83'); b = R['barrier']; dbl = R['double']; cl = R['crash_leave']
def S(k): return [l for l in out('z83').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"Barrier:「关上」就是 /bar 这个 znode 存在;10 个等待者 wait() 被挡住(1 秒后仍全部在等)。控制者删掉 /bar,10 个在 {b['first']:.0f}–{b['last']:.0f} ms 内全被唤醒;之后新来的 wait() 立即返回(0.8 ms)。", t=tl(S(1)), done=[0], b=bars([['最早唤醒', b['first'], f"{b['first']:.1f} ms"], ['最晚唤醒', b['last'], f"{b['last']:.1f} ms"]], 20, done=[0, 1]), kv=KV([['放行', '删除 /bar'], ['10 个唤醒跨度', f"{b['last']-b['first']:.1f} ms"]], ['放行'])),
    step("DoubleBarrier:5 个参与者,第 5 个迟到 2 秒。p0–p3 在 0 秒调用 enter() 都等到了 2.0 秒才一起进入;干活时间各不同(0.2–1.0 s),最慢的 p4 在 3.05 s 调用 leave(),所有人在 3.07 s 一起离开(最大差 2 ms)。入口一起进、出口一起出。", t=tl(S(2)), mark=[0], done=[0], kv=KV([['一起进入', '2.04 s(最大差 0 ms)'], ['一起离开', '3.07 s(最大差 2 ms)']], ['一起进入'])),
    step(f"同一路径再来一轮:5 个参与者第二轮全部完成({R['reuse']} / 5),/dbar 下没有残留子节点,所以可以重复使用。", t=tl(S(3)), done=[0], kv=KV([['重复使用', f"{R['reuse']} / 5 完成"], ['残留节点', '无']], ['重复使用'])),
    step(f"只来了 4 个(要求 5 个):4 个都在 enter() 里一直等,没有超时参数;/dbar3 下有 {R['short']} 个节点。人数永远凑不齐就会永远卡住,所以需要自己在外面加超时或监控。", t=tl(S(4)), mark=[0], kv=KV([['人数不齐', '永远等'], ['enter 超时参数', '没有']], ['人数不齐'])),
    step(f"3 个参与者都进入后 kill -9 其中一个:另外两个的 leave() 在 {cl[0]:.1f} s 后(会话超时 3 s)才返回 —— 死掉的参与者的临时节点要等会话过期才消失,其他人才能离开。崩溃会把「一起离开」拖慢到会话超时。", t=tl(S(5)), mark=[0], b=bars([['会话超时', 3.0, '3 s'], ['其余两个 leave 返回', cl[0], f"{cl[0]:.1f} s"]], 4, done=[0], mark=[1]), kv=KV([['崩溃后 leave', f"{cl[0]:.1f} s"]], ['崩溃后 leave'])),
]
A = dict(
    n=83, series='zookeeper', tags='ZooKeeper,分布式栅栏,Barrier,kazoo,真实验证,动画演示',
    desc=f'kazoo 的 Barrier 与 DoubleBarrier 实测:删除 /bar 后 10 个等待者在 {b["last"]:.0f} ms 内全部放行;DoubleBarrier 入口一起进(0 ms 差)、出口一起出(2 ms 差),可重复使用;人数不齐永远等;参与者 kill -9 后其余的 leave 等到会话过期({cl[0]:.1f} s)。',
    lead='让一批进程「等齐了再一起开始」「都做完了再一起结束」,这就是栅栏。ZooKeeper 上有两种配方:单次放行的 Barrier,和进出都同步的 DoubleBarrier。这篇量放行的同步程度、重复使用、人数不齐会怎样,以及参与者崩溃时会怎样。',
    facts=[(f'{b["last"]:.0f} ms', '删除 /bar 后 10 个等待者全部放行的跨度'), ('2 ms', 'DoubleBarrier 5 个参与者离开时刻的最大差'), (f'{cl[0]:.1f} s', '参与者 kill -9 后其余参与者 leave 返回的时间')],
    body=[
        sec('Barrier:一个 znode 的开关', '', term('', blk('z83', 1)), '<p>等待者 watch 这个 znode 的删除事件;控制者删掉它就是放行。10 个 watcher 同时被触发(单个路径,惊群规模取决于等待者数量,见<a href="zookeeper-watcher-storm.html">watch 风暴</a>)。</p>'),
        sec('DoubleBarrier:进出都同步', '', term('', blk('z83', 2)), '<p>每个参与者在 /dbar 下建一个临时节点;子节点数达到要求人数时进入放行,离开时节点逐个删除、删光时放行。典型用法:一批 worker 等所有人就绪再开始计算、全做完再汇总。</p>'),
        sec('可重复使用', '', term('', blk('z83', 3))),
        sec('人数不齐', '', term('', blk('z83', 4)), '<p>这是用 DoubleBarrier 最容易踩的坑:启动一个参与者失败了,其余的就卡在 <code>enter()</code> 上,没有任何报错。</p>'),
        sec('参与者崩溃', '', term('', blk('z83', 5)), '<p>节点是临时节点,所以崩溃的参与者最终会被清除,leave 不会永远卡住,但要等一个<a href="zookeeper-session-expire.html">会话超时</a>。对称地,如果参与者在 enter 之前崩溃,其余人则永远等(上一节)。</p>'),
        sec('分步演示', '', demo('分布式栅栏', [('t', 'term', '输出'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。kazoo 2.11.0 的 Barrier 与 DoubleBarrier;前三项用线程内的独立客户端,崩溃测试用独立子进程,会话超时 3 s', '没有验证:DoubleBarrier 的 leave 超时、参与者在 enter 之前崩溃后的补位、数百个参与者时的放行跨度、Curator 的 DistributedBarrier / DistributedDoubleBarrier(见第 92 篇)'],
)
