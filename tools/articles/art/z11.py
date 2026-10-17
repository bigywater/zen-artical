from lib import *
R = J('z11'); sp = R['spread']
def S(k): return [l for l in out('z11').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"连接串里写 3 个地址时,客户端会打乱顺序、随机挑一个连(这是 kazoo 的行为)。连续 12 个客户端各连到哪个节点:{', '.join(f'{p} 端口 {c} 次' for p, c in sorted(sp.items()))}——大致均匀,没有固定偏向某个节点(包括 leader)。", t=tl(S(1)), kv=KV([['选哪个节点', '随机,不是按顺序']], ['选哪个节点'])),
    step("握手完成后,服务端的 cons 命令里能看到这个连接:会话 id(sid=0x3000b…,最高字节 3 是创建它的服务端的 myid)、协商后的超时 to=8000(客户端请求 8000 ms)、lop=SESS(最后一个操作是建立会话)、est 是建立时间戳。会话 id 与超时是客户端和服务端握手确认的两个关键值。", t=tl(S(2)), kv=KV([['sid', '会话 id,最高字节 = 服务端 myid'], ['to', '协商后的会话超时(ms)']], ['sid'])),
    step(f"连接的服务端被 kill -9:客户端先进入 SUSPENDED(连接断了,会话还没丢),随后连上另一个节点 → CONNECTED,会话 id 不变、临时节点还在。本次从 SUSPENDED 到 CONNECTED 约 {R['failover']['states'][1][0] - R['failover']['states'][0][0]} ms(被杀的恰好是 leader,期间需要重新选举,不同次运行的数字会不同)。", t=tl(S(3)), done=[0, 1], kv=KV([['SUSPENDED', '连接断了,会话还在'], ['重连', '换节点,同一个会话']], ['SUSPENDED'])),
    step("连接串里只有一个地址、而这个节点被停掉:客户端停在 SUSPENDED(3 秒后仍是 connected=False),不会放弃;节点重新启动后自动回到 CONNECTED。把全部节点地址都写进连接串,故障转移才能发生。", t=tl(S(4)), mark=[0], done=[1], kv=KV([['单地址', '节点挂了就只能等']], ['单地址'])),
]
A = dict(
    n=11, series='zookeeper', tags='ZooKeeper,客户端,连接,故障转移,真实验证,动画演示',
    desc='ZooKeeper 客户端连接流程实测(3 节点集群 + kazoo):连接串里的地址被随机挑选;握手确认会话 id(最高字节是服务端 myid)和协商后的超时;服务端被 kill 后客户端 SUSPENDED → 换节点 CONNECTED,会话不变;只写一个地址则无法转移。',
    lead='客户端怎么连上 ZooKeeper 集群?连接串里的多个地址怎么用?服务端挂了会发生什么?这篇用真实的 3 节点集群和 kazoo 把连接建立、握手确认和故障转移逐步量出来。',
    facts=[('随机选择', '连接串里的地址被打乱后依次尝试(kazoo 行为)'), ('SUSPENDED → CONNECTED', '服务端被 kill 后,客户端在同一个会话里换节点重连'), ('sid 最高字节', '会话 id 的最高字节是创建它的服务端的 myid')],
    body=[
        sec('连接串与选择', '', term('', blk('z11', 1)), '<p>连接串里的写法是 <code>host1:port,host2:port,host3:port</code>(可以带 chroot 路径后缀)。不同语言的客户端选择策略可能不同,这里测的是 kazoo。</p>'),
        sec('握手确认了什么', '', term('', blk('z11', 2))),
        sec('服务端挂了', '', term('', blk('z11', 3)), '<p>SUSPENDED 表示「连接断了、会话还可能有效」,此时客户端不应当假设自己持有的锁、临时节点已经失效,也不应当继续假设它们有效——要等到重新 CONNECTED 或者 LOST 才能决定(下一篇看 LOST)。</p>'),
        sec('只写一个地址', '', term('', blk('z11', 4))),
        sec('分步演示', '', demo('客户端连接', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;客户端 kazoo 2.11.0;被 kill 的节点是客户端当时连着的那个', '没有验证:Java 客户端(Curator)的选择策略与 DNS 解析(第 92 篇)、chroot、TLS 连接(第 75 篇)、连接超时 / 读超时的具体值、客户端在 SUSPENDED 期间的请求排队行为'],
)
