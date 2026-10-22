from lib import *
S = SS('v48')
steps = [
    step("Consul 失去多数。3 个 server 杀掉 2 个,只剩 1 个,3 秒后在这个节点上做请求。默认读 KV:HTTP 500(rpc error getting client: failed to get conn,没有 leader),1 ms。读 KV 加 ?stale:HTTP 200,读到数据,0 ms。读 KV 加 ?consistent:HTTP 500。写 KV:HTTP 500。服务目录默认读:HTTP 500;加 ?stale:HTTP 200,读到服务。没有多数时,默认的读和所有写入都失败;加 ?stale 之后任何 server 都能回答(可能是旧数据),由调用方显式选择用“可能旧”换“可用”。etcd 的 serializable 读(第 47 篇)是同一个思路。", t=tl(S(1)), mark=lidx(S(1), '默认', '?consistent', '写 KV'), done=lidx(S(1), '?stale'), b=bars([['默认读 KV', 500, 'HTTP 500'], ['?stale 读 KV', 200, 'HTTP 200'], ['写 KV', 500, 'HTTP 500'], ['服务目录 ?stale', 200, 'HTTP 200']], 500, mark=[0, 2], done=[1, 3]), kv=KV([['默认读 / ?consistent / 写', '全部 HTTP 500(没有 leader)'], ['?stale 读', 'HTTP 200,可能是旧数据'], ['服务目录 ?stale', '仍能查到服务']], ['?stale 读'])),
    step("leader 挂掉之后多久恢复写入。3 节点集群,每秒写一次,杀掉 leader,统计到第一次写入成功的时间,每个系统 4 次。etcd(默认选举超时 1 s):2.08、2.07、2.08、2.07 s,中位数 2.08 s。Consul(默认 Raft 参数):9.52、11.94、12.24、10.28 s,中位数 11.11 s。两个 CP 系统在 leader 挂掉之后都要先重新选主才能继续写,期间写入不可用;这里 Consul 的故障转移时间约是 etcd 的 5 倍,取决于各自的默认参数,不是 CP 本身的差别。", t=tl(S(2)), mark=lidx(S(2), 'consul'), done=lidx(S(2), 'etcd'), b=bars([['etcd:写入恢复 中位数 s', 2.08, '2.08'], ['Consul:写入恢复 中位数 s', 11.11, '11.11(9.52~12.24)']], 12, done=[0], mark=[1]), kv=KV([['etcd', '2.07~2.08 s'], ['Consul(默认参数)', '9.52~12.24 s'], ['原因', '选主期间不可写;时长取决于各自的默认参数']], ['Consul(默认参数)'])),
    step("AP 模型:多主复制加最后写入者胜,3 个副本都接受读写,每 0.3 s 反熵。把 R0 和 {R1, R2} 分区 3 秒。分区期间 4 次写入全部成功(4 / 4),可用性 100%;R0 一侧 /svc/web = from-R0、/svc/a = only-R0、读不到 /svc/b;R1、R2 一侧 /svc/web = from-R12、/svc/b = only-R12、读不到 /svc/a——两边读到的不一样。愈合后 0.28 s 三个副本收敛,/svc/web 留下的是 from-R12,被覆盖(丢掉)的写入是 from-R0;/svc/a 和 /svc/b 都保留。对照:CP 系统在少数派一侧拒绝写入(第 1 节),没有分叉也没有丢更新;AP 用冲突解决换来分区期间的可用。", t=tl(S(3)), mark=lidx(S(3), '分区期间 R0', '分区期间 R1'), done=lidx(S(3), '愈合后'), b=bars([['分区期间写入成功', 4, '4 / 4'], ['愈合后收敛用时 s', 0.28, '0.28'], ['被覆盖的写入', 1, '1(from-R0)'], ['分区期间两边读到的 /svc/web', 2, '2 种不同的值']], 4, done=[0, 1], mark=[2, 3]), kv=KV([['分区期间', '4 / 4 写入成功,两边读到不同的值'], ['愈合后', '0.28 s 收敛,保留 from-R12,丢掉 from-R0'], ['CP 系统', '少数派一侧拒绝写入,无分叉']], ['愈合后'])),
]
A = mkartv('v48', 48, '微服务,注册中心,CP,AP,Consul,etcd,一致性,真实验证,动画演示',
    '实测服务发现的一致性取舍:Consul 失去多数后默认读和写都是 HTTP 500,加 ?stale 才能读;leader 挂掉后写入恢复 etcd 约 2.08 s、Consul(默认参数)约 11.11 s;AP 的多主复制模型在分区期间 4 / 4 次写入成功,但两边读到不同的值、愈合后一个写入被覆盖。',
    '服务发现该选 CP 还是 AP?分区时 CP 系统怎么表现、AP 系统又丢了什么?etcd 和 Consul 的故障转移要多久?这篇用 etcd 3.7.2、Consul 2.0.4 的真实集群和一个很小的 AP 复制模型对照。',
    [('HTTP 500 对 200', 'Consul 只剩 1 个 server 时,默认读与加 ?stale 的读的状态码(写入也是 500)'), ('2.08 对 11.11 s', 'leader 被杀后,etcd 与 Consul(默认参数)恢复写入的中位数时间'), ('4 / 4 对 丢 1 个', 'AP 模型分区期间的写入成功率,以及愈合后被最后写入者胜覆盖掉的写入数')],
    [('CP 在少数派', '<p>默认读和写都失败;显式选 stale 读才能读到可能旧的数据。</p>'),
     ('故障转移', '<p>选主期间不可写,时长取决于默认参数。</p>'),
     ('AP', '<p>分区期间两边都可用、读到不同的值;愈合后用冲突解决合并,会丢更新。</p>')],
    steps,
    [ENV_V + '。etcd 3.7.2 和 Consul 2.0.4(Homebrew cask,3 个 server 都在 127.0.0.1 的不同端口,Raft)都是自己起的真实集群;“分区”用杀掉其余节点只剩一个来模拟,没有做对称的网络分区;AP 一侧是我写的 Python 复制模型(多主、最后写入者胜、反熵),不是 Nacos 的 Distro 协议,更不是 Eureka;故障转移时间用的是两个系统各自的默认参数,Consul 的 11 秒左右没有调参也没有分析原因',
     '没有验证:Nacos 的 AP 模式(Distro)与 CP 模式(Raft)的真实行为(见后面 Nacos 的篇目);ZooKeeper 的对照(见 ZooKeeper 系列第 108、110 篇);Consul 的 autopilot 与 raft 参数调优;网络分区时两侧都有节点(对称分区)的行为;etcd 的 learner / 非投票成员'],
    '服务发现的一致性取舍')
