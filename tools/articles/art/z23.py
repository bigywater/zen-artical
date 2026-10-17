from lib import *
R = J('z23'); rows = R['rows']; sh = R['shard']
def S(k): return [l for l in out('z23').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("一个父节点下的子节点越多,get_children 越慢:" + ';'.join(f"{n} 个 → {m:.1f} ms" for n, tc, m, r in rows if m) + "(子节点名 40 个字符;kazoo 客户端)。延迟大致与子节点数成正比,因为整个子节点名列表要在一个响应里返回。", t=tl(S(1)), b=bars([[f'{n} 个', m, f'{m:.1f} ms'] for n, tc, m, r in rows if m], max(m for n, tc, m, r in rows if m) * 1.1, done=list(range(len([1 for n, tc, m, r in rows if m])))), kv=KV([['get_children', '随子节点数线性变慢']], ['get_children'])),
    step(f"分层可以绕开:同样 30000 个 znode 分到 100 个父节点下,每个父节点 300 个子节点,每个 get_children 的中位延迟 {sh['med']:.2f} ms、最大 {sh['mx']:.2f} ms,比单个大父节点的 {max(m for n, tc, m, r in rows if m):.1f} ms 小得多。把「扁平的大目录」改成按前缀分层(比如按 id 的前几位分桶),是 ZooKeeper 里常用的设计。", t=tl(S(2)), done=[0], kv=KV([['分层', '每层几百个子节点,延迟 < 0.3 ms']], ['分层'])),
    step("删除有大量子节点的父节点:delete /shard000 → NotEmptyError;必须先删子节点。kazoo 的 delete(recursive=True) 删除 300 个子节点加父节点用了几百毫秒(逐个删除)。大目录的清理很慢,要提前设计。", t=tl(S(3)), mark=[0], kv=KV([['delete', '非空节点失败,要递归删除']], ['delete'])),
    step("响应大小限制在客户端:30000 个子节点的 get_children 响应约 1.3 MiB,kazoo 毫无问题;但官方 Java 客户端(默认 jute.maxbuffer)执行 ls /big 直接收到 Disconnected,加 -Djute.maxbuffer=4194304 后才能完整返回(输出 126 万字符)。同一个数据,不同客户端的行为不同(第 24 篇)。", t=tl(S(4)), mark=[0], done=[1], kv=KV([['Java 客户端', '响应超过 jute.maxbuffer 就断开'], ['kazoo', '不检查']], ['Java 客户端'])),
]
A = dict(
    n=23, series='zookeeper', tags='ZooKeeper,大量znode,get_children,性能,真实验证,动画演示',
    desc=f'大量 ZNode 的性能问题:get_children 延迟随子节点数线性增长({rows[0][0]} 个 {rows[0][2]:.1f} ms → {rows[-1][0]} 个 {rows[-1][2]:.1f} ms);分到 100 个父节点下每个只要 {sh["med"]:.2f} ms;删除非空父节点要递归;官方 Java 客户端对超过 jute.maxbuffer 的 get_children 响应直接断开。',
    lead='一个父节点下放几万个子节点会怎样?这篇量 get_children 的延迟随子节点数的变化,再对比分层设计,最后看一个容易被忽略的事实:响应大小的限制其实在客户端。',
    facts=[(f'{rows[-1][0]} 个 → {rows[-1][2]:.1f} ms', '单个父节点下 get_children 的延迟(子节点名 40 字符)'), (f'{sh["med"]:.2f} ms', '同样数量分到 100 个父节点后,每个父节点 get_children 的中位延迟'), ('客户端检查响应大小', 'Java 客户端对 1.3 MiB 的响应断开,kazoo 不检查')],
    body=[
        sec('扁平大目录', '', term('', blk('z23', 1))),
        sec('分层', '', term('', blk('z23', 2))),
        sec('删除', '', term('', blk('z23', 3))),
        sec('Java 客户端的限制', '', term('', blk('z23', 4)), '<p>这一节说明,是否「超过上限」要看是哪个客户端:服务端发出去的响应并没有被限制,是 Java 客户端读到超长的包时主动断开。选客户端库和排查「莫名断开」问题时要想到这一点。</p>'),
        sec('分步演示', '', demo('大量 znode', [('t', 'term', '输出'), ('b', 'bars', 'get_children 延迟'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,JVM 堆 256 MiB;子节点名 40 个字符、数据为空;Java 客户端用官方 ZooKeeperMain', '没有验证:getChildren2 / 分页的 API(没有)、znode 总数达到百万级、大目录上的 watch 通知(会带来整个列表的重读)、快照与重启时间(第 10 篇已测 20 万)'],
)
