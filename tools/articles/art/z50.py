from lib import *
R = J('z50')
def S(k): return [l for l in out('z50').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("默认(静态配置、没有开 reconfigEnabled)的集群上执行 reconfig -remove 3,得到「KeeperErrorCode = Reconfig is disabled」。动态重配置需要显式开启:standaloneEnabled=false、reconfigEnabled=true,成员写在 dynamicConfigFile 里(每行 server.N=host:quorum:election:role;host:clientPort)。", t=tl(S(1)), mark=[0], kv=KV([['默认', 'reconfig 被禁用'], ['开启', 'reconfigEnabled=true + dynamicConfigFile']], ['默认'])),
    step("动态配置的 3 节点集群:config 命令返回当前成员(每行含客户端端口)和配置版本 version=100000000(十六进制,= 第 1 个 epoch 的 counter 0,版本号本身也是一个 zxid)。", t=tl(S(2)), done=[0, 1, 2, 3], kv=KV([['config', '成员 + 版本(version 是 zxid)']], ['config'])),
    step(f"加入节点:reconfig -add server.4=…:participant;…,返回「Committed new configuration」并列出 4 个成员,version 变成 100000036;新节点启动后 {R['n4']['ms']:.0f} ms 成为 {R['n4']['mode']},znode 数与其它节点一致(55)。reconfig 本身是一个事务,版本号就是它的 zxid。", t=tl(S(3)), done=[1, 2, 3, 4, 5], kv=KV([['reconfig -add', '提交新配置,版本 = 它的 zxid'], ['新节点', f"{R['n4']['ms']:.0f} ms 后追上"]], ['reconfig -add'])),
    step(f"移除节点:reconfig -remove 1 返回新配置(只剩 server.2/3/4,version=10000003a)。有意思的是被移除的 1 号节点进程还在、Mode 仍显示 {R['victim']['mode']},它自己看到的 config 已经不包含它;leader 的 zk_synced_followers 仍是 3。移除成员不会自动停掉那个进程,需要自己停——这一点我只观察了几秒。", t=tl(S(4)), mark=[0], kv=KV([['被移除的节点', '进程还在,config 不含它'], ['要做的', '自己停掉它']], ['被移除的节点'])),
]
A = dict(
    n=50, series='zookeeper', tags='ZooKeeper,reconfig,动态配置,真实验证,动画演示',
    desc=f'动态重配置实测:默认 reconfig 被禁用(Reconfig is disabled);开启 reconfigEnabled + dynamicConfigFile 后 config 命令返回成员与版本;reconfig -add 4 号节点后 {R["n4"]["ms"]:.0f} ms 追上并成为 follower;reconfig -remove 后被移除的进程仍在运行。',
    lead='ZooKeeper 3.5 之后可以在不重启全集群的情况下增删成员(reconfig)。这篇开启动态配置,实际执行 config、reconfig -add、reconfig -remove,看版本号、新节点同步和被移除节点的状态。',
    facts=[('Reconfig is disabled', '默认配置下执行 reconfig 的错误'), ('version = zxid', 'config 的版本号就是提交这次配置的事务 zxid'), (f'{R["n4"]["ms"]:.0f} ms', 'reconfig -add 后新节点启动到成为 follower 的时间')],
    body=[
        sec('默认是禁用的', '', term('', blk('z50', 1))),
        sec('动态配置与 config 命令', '', term('', blk('z50', 2)), '<p>动态配置要求把 <code>clientPort</code> 从静态配置里移到成员行里(<code>;127.0.0.1:7300</code>),并且静态配置里不能再有 <code>clientPortAddress</code>(我一开始漏了这个,节点直接报「Invalid config」退出)。我还用 <code>-Dzookeeper.skipACL=yes</code> 跳过了 reconfig 的权限检查,生产环境应当用超级用户或 ACL(第 71 篇)。</p>'),
        sec('加入节点', '', term('', blk('z50', 3))),
        sec('移除节点', '', term('', blk('z50', 4))),
        sec('分步演示', '', demo('动态重配置', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。动态配置伪集群(3 + 1);reconfig 用官方 ZooKeeperMain;skipACL=yes', '没有验证:权限配置下的 reconfig、同时增加多个节点(第 51 篇)、观察者与 participant 互相转换、reconfig 失败(比如破坏多数派)时的错误、被移除节点长期运行的后果'],
)
