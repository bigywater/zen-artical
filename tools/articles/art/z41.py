from lib import *
R = J('z41')
def S(k): return [l for l in out('z41').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("用官方 TxnLogToolkit 读三个节点各自的事务日志:每个节点都是 27 条事务(含创建会话、create、set、delete、multi、关闭会话),最后一条都是同一个 closeSession(zxid 0x10000001b)。逐行比较,三个节点的内容完全相同——包括时间戳、会话 id、cxid、zxid。每个节点把同一个 proposal 原样写进自己的日志。", t=tl(S(1)), done=[0, 1, 2, 3], kv=KV([['三个节点的日志', '逐行相同']], ['三个节点的日志'])),
    step("一条事务里同时有 cxid 和 zxid:cxid 是客户端自己的请求序号(同一会话内递增:0x2、0x17、0x18、0x19),zxid 是集群给事务的全局序号(0x100000003、0x100000018…)。客户端的「请求」(cxid)被 leader 变成集群的「事务」(zxid)。日志里还能看到事务内容:create /t/a,hello;setData /t/a,world,1(新版本号 1);delete '/t/n0。", t=tl(S(2)), kv=KV([['cxid', '客户端请求序号'], ['zxid', '集群事务序号']], ['zxid'])),
    step("multi 在日志里是一条事务:「multi create: /t/m1 1 …;create: /t/m2 2 …」两个子操作放在同一条记录里,只占一个 zxid(0x10000001a)——这就是 multi 原子性的来源(第 21 篇)。", t=tl(S(3)), done=[0], kv=KV([['multi', '一条事务,一个 zxid']], ['multi'])),
]
A = dict(
    n=41, series='zookeeper', tags='ZooKeeper,Proposal,事务日志,zxid,真实验证,动画演示',
    desc='Proposal、Transaction、Commit 的关系实测:用 TxnLogToolkit 读 3 个节点的事务日志,27 条事务逐行完全相同(时间戳、会话 id、cxid、zxid);cxid 是客户端请求序号、zxid 是集群事务序号;multi 是日志里的一条事务。',
    lead='Proposal、Transaction、Commit 在 ZooKeeper 里分别指什么、怎么对应?我没有去读源码,而是从结果看:三个节点事务日志里的内容,是不是同一份。',
    facts=[('27 条完全相同', '3 个节点事务日志逐行比较的结果'), ('cxid vs zxid', '客户端请求序号 vs 集群事务序号'), ('multi = 1 条事务', '一条记录里有多个子操作,占一个 zxid')],
    body=[
        sec('三个节点的日志逐行相同', '', term('', blk('z41', 1)), '<p>这说明 leader 发出的 proposal 就是要写进每个节点事务日志的那条记录,「提交」只是把它应用到内存里的数据树。至于类名与方法之间的源码对应关系,本文没有读源码,留给第 99 篇的源码阅读。</p>'),
        sec('一条事务的结构', '', term('', blk('z41', 2))),
        sec('multi 事务', '', term('', blk('z41', 3))),
        sec('分步演示', '', demo('事务日志', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。3 节点伪集群;TxnLogToolkit 是 3.9.6 jar 里的官方类;比较的是 version-2 下所有 log.* 文件里带 zxid 的行', '没有验证:proposal 与 commit 消息在网络上的格式、源码里 Request / Proposal / TxnHeader 之间的对象关系、事务日志里 digest 校验字段'],
)
