from lib import *
R = J('z91'); a = R['async']; sh = R['short']; lg = R['long']
def S(k): return [x for x in out('z91').split('== ')[k].splitlines()[1:] if x.strip()]
steps = [
    step("异常对照:kazoo 把服务端错误码映射成 Python 异常 —— 已存在 NodeExistsError、不存在 NoNodeError、有子节点 NotEmptyError、版本不符 BadVersionError、临时节点下建子节点 NoChildrenForEphemeralsError、父节点不存在 NoNodeError。", t=tl(S(1)), done=[0], kv=KV([['异常基类', 'kazoo.exceptions']], ['异常基类'])),
    step(f"同步 vs 异步:建 2000 个节点,同步 {a['sync']:.0f} 个/s,create_async 流水线 {a['asyn']:,.0f} 个/s,约 {a['asyn']/a['sync']:.0f} 倍(同步每次都等一个往返和一次 fsync,异步让请求在同一连接上排队、服务端成批提交)。批量写用 *_async 或 transaction。", t=tl(S(2)), done=[0], b=bars([['同步', a['sync'], f"{a['sync']:.0f}/s"], ['异步', a['asyn'], f"{a['asyn']:,.0f}/s"]], a['asyn'], mark=[0], done=[1]), kv=KV([['同步 / 异步', f"{a['sync']:.0f} / {a['asyn']:,.0f} 个/s"]], ['同步 / 异步'])),
    step(f"所有 watch 回调在同一个线程里执行:/w1 的回调睡 2 秒,/w2 本该立即触发的回调被拖到 {R['block']:.0f} ms 才执行。回调里不要做阻塞操作 —— 丢给别的线程。", t=tl(S(3)), mark=[0], kv=KV([['回调线程', '共享一个'], ['被拖延', f"{R['block']:.0f} ms"]], ['被拖延'])),
    step("服务端不可用时 start(timeout=3):3.1 s 后抛 KazooTimeoutError,state 是 LOST。生产启动流程要处理这个异常,并决定是退出还是重试。", t=tl(S(4)), done=[0], kv=KV([['连不上', 'KazooTimeoutError']], ['连不上'])),
    step(f"服务端重启(短中断,约 1.7 s):状态 SUSPENDED → CONNECTED,会话 id 不变({sh['same']}),临时节点还在({sh['eph']});中断期间发起的 get 没有立刻失败,而是等到重连后才返回(成功)。长中断(约 6.7 s,超过会话超时):SUSPENDED → LOST → CONNECTED,会话 id 变了,临时节点没了;中断期间发起的 get 在 {lg['call_dur']:.0f} s 后抛 SessionExpiredError;而且服务端重启后客户端又过了约 {lg['call_rel']:.1f} s 才重连成功(重连退避)。", t=tl(S(5)), mark=[0], kv=KV([['短中断', 'SUSPENDED → CONNECTED,会话保留'], ['长中断', 'SUSPENDED → LOST → CONNECTED,新会话']], ['长中断'])),
]
A = dict(
    n=91, series='zookeeper', tags='ZooKeeper,Python,kazoo,客户端,真实验证,动画演示',
    desc=f'kazoo 2.11.0 实测:异常对照;同步 {a["sync"]:.0f} vs 异步流水线 {a["asyn"]:,.0f} 个/s;回调线程共享,一个睡 2 秒拖延另一个 {R["block"]:.0f} ms;连不上抛 KazooTimeoutError;服务端短重启会话保留、长中断会话丢失并经历 SUSPENDED → LOST → CONNECTED。',
    lead='kazoo 是 Python 里最常用的 ZooKeeper 客户端。这篇不抄文档,只量你写代码时一定会撞上的行为:异常长什么样、同步和异步差多少、回调线程被阻塞会怎样、连不上怎么办、服务端重启时状态怎么变。',
    facts=[(f'{a["asyn"]/a["sync"]:.0f} 倍', '异步流水线相对同步调用的吞吐'), (f'{R["block"]:.0f} ms', '一个回调睡 2 秒时另一个回调被拖延的时间'), ('LOST', '中断超过会话超时后经历 SUSPENDED → LOST → CONNECTED,临时节点丢失')],
    body=[
        sec('异常', '', term('', blk('z91', 1))),
        sec('同步与异步', '', term('', blk('z91', 2)), '<p>异步的好处在<a href="zookeeper-request-pipeline.html">请求流水线</a>那篇讲过:一个连接上请求可以连续发出,不用等上一个返回。</p>'),
        sec('回调线程', '', term('', blk('z91', 3)), '<p>kazoo 默认的 handler 是线程版,所有 watch 与状态监听回调共用一个线程。这也是为什么<a href="zookeeper-service-discovery.html">服务发现那篇</a>里监听器里同步 <code>create</code> 没有成功:我观察到它没重建节点,没有查根因,但这与「回调线程不能阻塞」是一致的。</p>'),
        sec('连不上', '', term('', blk('z91', 4))),
        sec('服务端重启与会话', '', term('', blk('z91', 5)), '<p>状态含义见<a href="zookeeper-session.html">会话</a>。SUSPENDED 期间发起的调用会一直等,不会立刻抛 ConnectionLoss,需要有上限时请自己设超时。</p>'),
        sec('分步演示', '', demo('kazoo 行为', [('t', 'term', '输出'), ('b', 'bars', '吞吐'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。kazoo 2.11.0、Python 3.14;服务端为单节点,重启用 SIGTERM 停止 / 重新启动,不擦数据;会话超时 3 s', '没有验证:gevent / asyncio 的 handler、kazoo 的 SASL / TLS 配置(见第 75、77 篇的 Java 侧)、DataWatch 的 allow_missing_node 等参数的全部组合、client.retry 的各种策略'],
)
