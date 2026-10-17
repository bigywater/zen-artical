from lib import *
R = J('z104'); e = R['end']; g = R['gap']
def S(k): return [x for x in out('z104').split('== ')[k].splitlines()[1:] if x.strip()]
steps = [
    step("起点:ZooKeeper 模式的 3 broker 集群(Kafka 3.9.2),4 个主题(含 __consumer_offsets)和一个消费组 g1;一个后台生产者每 20 ms 同步写一条(acks=all)。迁移前 ZooKeeper 里没有 /migration 节点,/controller 是 broker 1。", t=tl(S(1)), done=[0], kv=KV([['模式', 'ZooKeeper'], ['/migration', '不存在']], ['模式'])),
    step("启动 KRaft controller(node.id=3000,单节点投票,迁移开关 zookeeper.metadata.migration.enable=true,并连着 ZooKeeper);它的 cluster id 必须是 ZooKeeper 里 /cluster/id 的那个,所以用 kafka-storage.sh format -t <那个 id> 格式化。启动后 ZooKeeper 里多了 /migration 节点,controller 日志里 KRaftMigrationDriver 从 UNINITIALIZED → INACTIVE,然后「Became active migration driver」。此时 /controller 仍是旧的 ZooKeeper controller(broker 1)。", t=tl(S(2)), done=[0], kv=KV([['新增', '/migration 节点'], ['/controller', '仍是 broker 1']], ['新增'])),
    step("滚动重启 3 个 broker(仍是 ZooKeeper 模式,加上 controller.quorum.voters 与迁移开关,每个约 5–6 s):controller 日志出现「Completed migration of metadata from ZooKeeper to KRaft. 66 records were generated」,状态依次 ZK_MIGRATION → SYNC_KRAFT_TO_ZK → KRAFT_CONTROLLER_TO_BROKER_COMM → DUAL_WRITE。ZooKeeper 里 /controller 变成 brokerid=3000、kraftControllerEpoch=1:KRaft controller 接管了 controller 的角色,同时继续把元数据写回 ZooKeeper(DUAL_WRITE),所以此刻还可以回滚。", t=tl(S(3)), mark=[3], kv=KV([['状态', 'DUAL_WRITE'], ['/controller', 'brokerid=3000']], ['状态'])),
    step("把 broker 逐个切成纯 KRaft(process.roles=broker,去掉 zookeeper.*)后重启:ZooKeeper 里 /brokers/ids 变成空 —— broker 不再向 ZooKeeper 注册。/controller 与 /migration 还留着,因为 controller 仍开着迁移开关。", t=tl(S(4)), done=[0], kv=KV([['/brokers/ids', '空'], ['broker 模式', '纯 KRaft']], ['/brokers/ids'])),
    step(f"收尾:controller 去掉 zookeeper.* 与迁移开关重启,然后停掉 ZooKeeper —— 后台生产者仍在写(4 秒 143 条)。整个过程生产者共写入并确认 {e['sent']} 条,发送错误 {len(e['errs'])} 种,最长相邻确认间隔 {g['max']:.1f} s;事后 mig 主题读回 {e['read']} 条,丢失 {e['miss']}、重复 {e['dup']};所有主题的分区数与副本数不变,消费组 g1 的 offset 与迁移前完全一致。", t=tl(S(5)), done=[0, 1, 2], b=bars([['写入并确认', e['sent'], str(e['sent'])], ['读回', e['read'], str(e['read'])], ['丢失', e['miss'], str(e['miss'])], ['重复', e['dup'], str(e['dup'])]], e['sent'], done=[0, 1, 2, 3]), kv=KV([['写入 / 读回', f"{e['sent']} / {e['read']}"], ['丢失 / 重复', f"{e['miss']} / {e['dup']}"], ['最长写入停顿', f"{g['max']:.1f} s"]], ['丢失 / 重复'])),
]
A = dict(
    n=104, series='zookeeper', tags='ZooKeeper,Kafka,KRaft,迁移,真实验证,动画演示',
    desc=f'真实把一个 Kafka 3.9.2 的 3 broker 集群从 ZooKeeper 迁移到 KRaft(控制器 → 滚动重启 → 切纯 KRaft → 停 ZooKeeper):过程中后台生产者确认写入 {e["sent"]} 条,读回 {e["read"]} 条、丢失 {e["miss"]}、重复 {e["dup"]},最长写入停顿 {g["max"]:.1f} s,主题与消费组 offset 不变。',
    lead='ZooKeeper 迁移到 KRaft 是 Kafka 3.x → 4.0 的必经之路。这篇不转述文档,而是真的把一个在线集群迁一遍:先起 KRaft controller,滚动重启 broker 触发元数据迁移,再把 broker 切成纯 KRaft,最后停掉 ZooKeeper,全程有生产者持续写入,事后核对数据与元数据。',
    facts=[(f'{e["miss"]} / {e["dup"]}', f'迁移全程 {e["sent"]} 条消息的丢失 / 重复数'), (f'{g["max"]:.1f} s', '迁移全程生产者相邻两次确认的最长间隔'), ('DUAL_WRITE', '迁移期间 KRaft controller 同时写 ZooKeeper,可以回滚')],
    body=[
        sec('起点', '', term('', blk('z104', 1)), '<p>起点的 ZooKeeper 节点见上一篇(<a href="zookeeper-kafka-zookeeper-history.html">Kafka 在 ZooKeeper 里存什么</a>)。</p>'),
        sec('第一步:KRaft controller', '', term('', blk('z104', 2))),
        sec('第二步:broker 带迁移开关滚动重启', '', term('', blk('z104', 3)), '<p>每个 broker 重启期间,生产者会遇到 leader 切换(和<a href="zookeeper-kafka-zookeeper-history.html">controller 被杀</a>类似),重试机制把它们吸收了。</p>'),
        sec('第三步:切成纯 KRaft', '', term('', blk('z104', 4))),
        sec('第四步:收尾', '', term('', blk('z104', 5)), '<p>这一步之后 ZooKeeper 完全没有参与。我没有测回滚路径,也没有核对文档里这一步之后是否还能回滚。</p>'),
        sec('分步演示', '', demo('ZooKeeper → KRaft', [('t', 'term', '输出'), ('b', 'bars', '消息数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Kafka 3.9.2(自带 ZooKeeper 3.8.4 客户端);3 个 broker 端口 7901–7903,KRaft controller 单节点 7910(生产环境应为 3 节点以上的投票);zookeeper.session.timeout.ms=6000;生产者 kafka-python-ng,acks=all、同步发送', '没有验证:迁移前后的回滚、3 节点 controller 投票、有 ACL / 配额 / SCRAM 的集群、大量分区的迁移耗时、事务与幂等生产者在迁移中的行为、Kafka 3.9 之前版本的迁移(要求 3.4+)'],
)
