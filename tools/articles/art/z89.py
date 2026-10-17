from lib import *
R = J('z89'); lb = R['list_bytes']; cb = R['callbacks']; w = R['watch']
def S(k): return [x for x in out('z89').split('== ')[k].splitlines()[1:] if x.strip()]
steps = [
    step(f"1000 个服务 × 5 个实例。分层 /h/<服务>/<实例>:消费者读一个服务的实例列表只拉 {lb['h']} 字节;平铺(5000 个节点同一个目录):要拉整个目录 {lb['f']:,} 字节。", t=tl(S(1)), done=[0], b=bars([['分层 get_children', lb['h'], f"{lb['h']} B"], ['平铺 get_children', lb['f'], f"{lb['f']:,} B"]], lb['f'], mark=[1], done=[0]), kv=KV([['读一个服务', f"分层 {lb['h']} B / 平铺 {lb['f']:,} B"]], ['读一个服务'])),
    step(f"随机改 {cb['changes']} 次不同服务的实例列表(每次一建一删,共 {cb['changes']*2} 次变更):只订阅 svc0042 目录的分层消费者回调 {cb['h']} 次;订阅整个平铺目录的消费者回调 {cb['f']} 次,每次都要重新拉 {lb['f']:,} 字节。目录要按「谁关心谁」切分。", t=tl(S(1)), mark=[len(S(1)) - 1], kv=KV([['无关变更的回调', f"分层 {cb['h']} / 平铺 {cb['f']}"]], ['无关变更的回调'])),
    step("实例信息常是 URL(dubbo://10.0.0.1:20880/com.foo.Bar?weight=100)。直接当节点名 create 会 NoNodeError:/ 被当作层级分隔符。URL 编码后可以建,读回来再解码。节点名里不能放 /,也要避开 ZooKeeper 不允许的字符。", t=tl(S(2)), done=[0], kv=KV([['含 / 的名字', 'NoNodeError'], ['URL 编码', '可以,读回解码']], ['含 / 的名字'])),
    step(f"权重等元信息放哪?编码进节点名:消费者只需要目录上 {w['name']} 个 watch,但改权重要删旧建新,消费者收到 2 次 children 回调;放节点数据:每个实例一个 DataWatch 加目录一个 ChildrenWatch = {w['data']} 个 watch,改权重只触发 1 次精确回调。watch 总数是服务端内存与重新注册成本。", t=tl(S(3)), mark=[0], b=bars([['名字编码', w['name'], f"{w['name']} 个 watch"], ['节点数据', w['data'], f"{w['data']} 个 watch"]], 210, mark=[1], done=[0]), kv=KV([['元信息在名字里', f"{w['name']} 个 watch"], ['元信息在数据里', f"{w['data']} 个 watch"]], ['元信息在数据里'])),
]
A = dict(
    n=89, series='zookeeper', tags='ZooKeeper,注册中心,数据模型,真实验证,动画演示',
    desc=f'注册中心的 znode 布局实测:1000 服务 × 5 实例,分层读一个服务 {lb["h"]} 字节 vs 平铺 {lb["f"]:,} 字节;100 次无关变更分层消费者回调 {cb["h"]} 次 vs 平铺 {cb["f"]} 次;URL 不能直接当节点名;元信息放名字 {w["name"]} 个 watch、放数据 {w["data"]} 个。',
    lead='用 ZooKeeper 做注册中心,先要定节点怎么摆:按服务分层还是平铺?实例信息放节点名还是节点数据?这篇用 1000 个服务、5000 个实例做对比,量读取字节、无关变更引起的回调数、URL 作节点名的陷阱和 watch 数量。',
    facts=[(f'{lb["h"]} vs {lb["f"]:,} B', '读一个服务的实例列表:分层 vs 平铺'), (f'{cb["h"]} vs {cb["f"]}', '100 次无关服务的变更引起的回调:分层 vs 平铺'), (f'{w["name"]} vs {w["data"]}', '一个服务 200 个实例:元信息放名字 vs 放数据的 watch 数')],
    body=[
        sec('分层 vs 平铺', '', term('', blk('z89', 1)), '<p>分层让目录等于「订阅边界」:消费者只关心自己依赖的服务,所以只 watch 那几个目录。平铺的目录越大,每次变更触发的 <code>get_children</code> 响应越大(响应里是全部子节点名,见<a href="zookeeper-many-znodes.html">大目录</a>)。</p>'),
        sec('节点名里放什么', '', term('', blk('z89', 2)), '<p>Dubbo 的注册中心就是这样:提供者的完整 URL 经 URL 编码后作为 <code>/dubbo/&lt;服务&gt;/providers/</code> 下的节点名。具体源码见<a href="zookeeper-dubbo-registry-source.html">第 101 篇</a>。</p>'),
        sec('元信息:名字还是数据', '', term('', blk('z89', 3)), '<p>常用折中:不变的信息(地址、协议)放节点名,会变的(权重、状态)放数据并只对确实要变的实例订阅;或者把动态信息放到另一个目录里。</p>'),
        sec('分步演示', '', demo('注册中心数据模型', [('t', 'term', '输出'), ('b', 'bars', '字节 / watch 数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。kazoo 2.11.0;watch 数取自 mntr 的 zk_watch_count(我观察到 wchs 没有统计 children watch);随机服务的变更次数只有 100 次、一次实验,回调数是该次的实际值', '没有验证:Dubbo 与 Spring Cloud 真实的目录结构(见第 101、106 篇)、数万实例规模、大目录的 get_children 在 ACL 打开时的耗时'],
)
