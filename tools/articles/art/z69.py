from lib import *
R = J('z69'); st = R['steps']; w = R['writes']
def S(k): return [l for l in out('z69').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("起点:3 个节点全部是官方发行包的 ZooKeeper 3.8.4(一个 leader、两个 follower),我另外下载了 apache-zookeeper-3.8.4-bin 的 jar;升级目标是 brew 里的 3.9.6。", t=tl(S(1)), done=[0], kv=KV([['起点', '3.8.4 × 3'], ['目标', '3.9.6']], ['起点'])),
    step("滚动升级:先升级两个 follower,最后升级 leader;每个节点:停止 → 换成 3.9.6 的 jar → 用原数据目录启动 → 等它同步完成。过程中 3.8.4 与 3.9.6 的节点混合组成集群,仍然选出 leader 并正常服务。" + ';'.join(f"升级 {x['node']}({x['was']})用时 {x['s']:.1f} s,写入最长间隔 {x['gap']:.0f} ms" for x in st) + "。升级 follower 时写入的最长间隔很小(只有连在它上面的客户端需要重连),升级 leader 时因为要重新选举间隔最长。", t=tl(S(2)), b=bars([[f"升级 {x['node'].split('-')[1]} 号({x['was']})", x['gap'], f"{x['gap']:.0f} ms"] for x in st], max(x['gap'] for x in st) * 1.1, done=[0, 1, 2]), kv=KV([['follower', '间隔小'], ['leader', f"{st[-1]['gap']:.0f} ms(重新选举)"]], ['leader'])),
    step(f"升级完成:3 个节点都是 3.9.6;写线程在整个过程中确认的写入 {w['acked']} 个,有 {w['fails']} 次调用抛出异常(升级过程中的连接断开),确认之后丢失 {w['lost']} 个;三个节点 zxid 一致({R['same_zxid']})。", t=tl(S(3)), done=[0, 1, 2], kv=KV([['确认的写', f"{w['acked']} 个,丢失 {w['lost']} 个"], ['最终版本', '全部 3.9.6']], ['确认的写'])),
]
A = dict(
    n=69, series='zookeeper', tags='ZooKeeper,滚动升级,版本,真实验证,动画演示',
    desc=f'ZooKeeper 3.8.4 → 3.9.6 滚动升级实测:先 follower 后 leader,混合版本集群正常服务;写入最长中断分别为 {st[0]["gap"]:.0f} / {st[1]["gap"]:.0f} / {st[2]["gap"]:.0f} ms(最后一次是 leader 重新选举);{w["acked"]} 个确认的写入全部保留。',
    lead='升级 ZooKeeper 不应该停服务。这篇用官方发行包的 3.8.4 起一个 3 节点集群,持续写入的同时逐个节点升级到 3.9.6,看混合版本能不能工作、每一步对客户端的影响多大。',
    facts=[('3.8.4 → 3.9.6', '混合版本的集群正常服务,最终 3 个节点都是 3.9.6'), (f'{st[-1]["gap"]:.0f} ms', '升级 leader 时写入的最长间隔(重新选举)'), (f'{w["lost"]} 个丢失', f'{w["acked"]} 个已确认的写入全部保留')],
    body=[
        sec('起点', '', term('', blk('z69', 1))),
        sec('逐个节点升级', '', term('', blk('z69', 2)), '<p>顺序是先 follower、最后 leader,这样 leader 只需要变换一次。每次都等升级的节点 zxid 追上 leader 再继续下一个。</p>'),
        sec('结果', '', term('', blk('z69', 3))),
        sec('只验证了这一对版本', '', '<p>本文只测了 3.8.4 → 3.9.6。其它版本之间(尤其跨大版本如 3.4 → 3.5 以上)有各自的升级注意事项(例如配置格式、动态配置),没有测。升级前仍应阅读目标版本的发行说明,并先备份(第 59 篇)。</p>'),
        sec('分步演示', '', demo('滚动升级', [('t', 'term', '输出'), ('b', 'bars', '最长间隔'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3.8.4 来自 archive.apache.org 的 apache-zookeeper-3.8.4-bin.tar.gz;写线程是 kazoo,每 10 ms 一次;3 节点伪集群', '没有验证:跨更多版本的升级、降级、客户端库对服务端版本的兼容、升级过程中配置参数的差异、客户端(Java / Go)在升级中的行为'],
)
