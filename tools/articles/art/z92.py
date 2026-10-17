import re
from lib import *
R = J('z92'); T = R['stdout']
def S(k): return [x for x in out('z92').split('== ')[k].splitlines()[1:] if x.strip()]
m = re.search(r'同步 (\d+) 个/s.*inBackground (\d+) 个/s.*;([\d.]+) 倍', T); sy, bg, mult = int(m.group(1)), int(m.group(2)), float(m.group(3))
gone = re.search(r'消失于 \+([\d.]+) s', T).group(1)
steps = [
    step("Curator 的流式 API:create().creatingParentsIfNeeded().withMode(...).forPath(...);带 namespace=app1 的客户端建 /cfg/db,另一个不带 namespace 的客户端看到的真实路径是 /app1/cfg/db —— namespace 就是替你加路径前缀,方便多应用共用集群。服务端错误是 KeeperException 的子类(BadVersionException、NodeExistsException)。", t=tl(S(1)), done=[0], kv=KV([['namespace', '自动加前缀 /app1'], ['异常', 'KeeperException 子类']], ['namespace'])),
    step(f"同步 vs 后台:建 2000 个节点,同步 {sy} 个/s,inBackground {bg:,} 个/s,约 {mult:.0f} 倍。和 kazoo 的 *_async 一样,流水线能大幅提高吞吐。", t=tl(S(2)), done=[0], b=bars([['同步', sy, f"{sy}/s"], ['inBackground', bg, f"{bg:,}/s"]], bg, mark=[0], done=[1]), kv=KV([['同步 / 后台', f"{sy} / {bg:,} 个/s"]], ['同步 / 后台'])),
    step("短中断(服务端被冻结 5 s,会话超时 6 s):状态序列 SUSPENDED(4.1 s,即 2/3 会话超时)→ RECONNECTED(5.9 s);会话 id 不变,临时节点一直在;中断期间发起的 setData 被重试策略托住,恢复后成功。Curator 的状态比 ZooKeeper 原生多一个 RECONNECTED,用来区分「重新连上、会话还在」和「第一次连上」。", t=tl(S(3)), done=[0], kv=KV([['状态序列', 'SUSPENDED → RECONNECTED'], ['会话', '没变']], ['状态序列'])),
    step(f"长中断(冻结 12 s,超过会话超时):SUSPENDED(4.1 s)→ LOST(10.1 s,SUSPENDED 之后又过了 6 s 的会话超时)→ RECONNECTED(12 s),Curator 自动换了新会话(id 变了);中断期间的 setData 在恢复后成功。PersistentNode 的临时节点自动在新会话下重新出现,不需要像<a href='zookeeper-service-discovery.html'>服务发现那篇</a>的 kazoo 例子那样手写重新注册。旧会话的普通临时节点在服务端上消失的时间两次测量不同(+0.0 s 与 +{gone} s,我没有查出原因)。", t=tl(S(4)), mark=[2], kv=KV([['状态序列', 'SUSPENDED → LOST → RECONNECTED'], ['PersistentNode', '自动重建']], ['PersistentNode'])),
]
A = dict(
    n=92, series='zookeeper', tags='ZooKeeper,Curator,Java,客户端,真实验证,动画演示',
    desc=f'Curator 5.7.1 在真实 ZooKeeper 3.9.6 上的实测:namespace 的真实路径前缀;同步 {sy} vs 后台 {bg:,} 个/s;服务端冻结 5 s 与 12 s 时 ConnectionStateListener 的 SUSPENDED / LOST / RECONNECTED 序列、重试策略托住中断期间的调用、PersistentNode 自动重建。',
    lead='Curator 是 Java 里事实标准的 ZooKeeper 客户端,它做的事主要是:重试、状态管理、流式 API,再加一堆现成的配方。这篇从 Maven 拉 Curator 5.7.1,量 namespace、后台调用的吞吐,以及服务端冻结(模拟长 GC)时状态机怎么走、调用与临时节点怎么恢复。',
    facts=[(f'{mult:.0f} 倍', '后台(inBackground)相对同步创建的吞吐'), ('LOST', '冻结超过会话超时后的状态序列:SUSPENDED → LOST → RECONNECTED'), ('自动重建', 'PersistentNode 在新会话下自动重建临时节点')],
    body=[
        sec('流式 API 与 namespace', '', term('', blk('z92', 1))),
        sec('同步与后台', '', term('', blk('z92', 2)), '<p>对照<a href="zookeeper-python-kazoo-client.html">kazoo</a>的结果:Java 的 inBackground 和 Python 的 create_async 都是把请求在一个连接上流水线化,服务端按批处理。</p>'),
        sec('短中断', '', term('', blk('z92', 3)), '<p>用 <code>kill -STOP</code> 冻结 ZooKeeper 进程来模拟「服务端不响应」(TCP 连接保持,没有重置)。客户端在 2/3 会话超时后没读到响应才判定 SUSPENDED。</p>'),
        sec('长中断', '', term('', blk('z92', 4)), '<p>LOST 是客户端自己根据会话超时算出来的:服务端冻结时它既不能通知也不能确认。因此冻结期间可能出现「客户端认为会话丢了、服务端上旧会话的临时节点还在」的一小段窗口(这里实测 0 到 7 s)—— 不要假设旧会话的临时节点在新会话建立时已经消失。</p>'),
        sec('分步演示', '', demo('Curator 行为', [('t', 'term', '输出'), ('b', 'bars', '吞吐'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Curator 5.7.1(Maven Central,经代理下载)+ zookeeper 3.9.6 jar,OpenJDK 17;服务端中断用 kill -STOP / -CONT 模拟,会话超时 6 s;重试策略为 ExponentialBackoffRetry(200 ms, 最多 12 次, 最大睡眠 2 s)', '没有验证:真正的网络分区(SIGSTOP 与断网并不完全等价)、旧会话临时节点滞留的根因、Curator 的 SessionFailRetryLoop / ConnectionStateErrorPolicy 等进阶选项、与 Spring Cloud 的整合(见第 106 篇)'],
)
