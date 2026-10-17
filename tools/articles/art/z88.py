from lib import *
R = J('z88'); k = R['kill']; t = R['term']; st = R['stop']
def S(x): return [l for l in out('z88').split('== ')[x].splitlines()[1:] if l.strip()]
steps = [
    step("每个提供者在 /svc/orders/<host:port> 下建一个临时节点(数据是 JSON 元信息),消费者 watch 这个目录得到实例列表。5 个提供者起来后,消费者看到全部 5 个。", t=tl(S(1)), done=[0], kv=KV([['注册', '临时节点'], ['发现', 'watch 子节点']], ['注册'])),
    step(f"上线:新提供者进程启动(含 Python 启动、连 ZooKeeper、建节点)到消费者看到它 {R['join_ms']:.0f} ms。", t=tl(S(2)), done=[0], kv=KV([['上线可见', f"{R['join_ms']:.0f} ms"]], ['上线可见'])),
    step(f"下线对比:kill -9 提供者,消费者在 {k['ms']/1000:.1f} s 后才摘掉它(会话超时 3 s),这期间请求失败 {k['fail']} 次(共 {k['ok'] + k['fail']} 次),失败后换一个实例重试全部成功({k['retried_ok']} 次)。SIGTERM 同样没有注销节点,{t['ms']/1000:.1f} s 后才摘掉,失败 {t['fail']} 次。进程被终止 ≠ 注销。", t=tl(S(3)), mark=[0], b=bars([['kill -9', k['ms'], f"{k['ms']/1000:.1f} s"], ['SIGTERM', t['ms'], f"{t['ms']/1000:.1f} s"], ['主动注销', R['graceful_ms'], f"{R['graceful_ms']:.0f} ms"]], 3500, mark=[0, 1], done=[2]), kv=KV([['kill -9', f"{k['ms']/1000:.1f} s,失败 {k['fail']}"], ['SIGTERM', f"{t['ms']/1000:.1f} s,失败 {t['fail']}"]], ['kill -9'])),
    step(f"提供者在退出前自己 delete 节点:消费者 {R['graceful_ms']:.0f} ms 内摘掉它,请求不会再发给它。所以正确的下线顺序是:先注销节点 → 等调用方摘掉 → 再关进程。", t=tl(S(4)), done=[0], kv=KV([['主动注销', f"{R['graceful_ms']:.0f} ms"]], ['主动注销'])),
    step(f"进程活着但被冻结超过会话超时(SIGSTOP 5 s):三种提供者的节点都被摘掉。解冻后:只注册一次的不再出现({st['naive']});在 kazoo 状态监听器里直接调用 create 的也没有重新出现({st['rereg_sync']});在监听器里新开线程再 create 的重新出现({st['rereg_thread']})。进程活着却从注册中心消失,对调用方来说就是服务下线了。", t=tl(S(5)), mark=[3], kv=KV([['只注册一次', '不再出现'], ['监听器里同步 create', '没有出现'], ['监听器里新线程 create', '重新出现']], ['只注册一次'])),
]
A = dict(
    n=88, series='zookeeper', tags='ZooKeeper,服务发现,服务注册,kazoo,真实验证,动画演示',
    desc=f'用 ZooKeeper 临时节点做服务发现:上线 {R["join_ms"]:.0f} ms 可见;kill -9 与 SIGTERM 都要 {k["ms"]/1000:.1f}–{t["ms"]/1000:.1f} s 才被摘除(期间请求失败 {k["fail"]}/{t["fail"]} 次,重试可挽回);主动注销 {R["graceful_ms"]:.0f} ms;会话过期后提供者必须重新注册(监听器里不能直接 create)。',
    lead='服务发现是 ZooKeeper 与 Dubbo、早期 Spring Cloud 的结合点:提供者建临时节点、消费者 watch 目录。这篇起几个真实的提供者进程,量上线与下线各要多久、下线期间消费者会发出多少失败请求、以及提供者「活着却被摘掉」之后会发生什么。',
    facts=[(f'{R["join_ms"]:.0f} ms', '新提供者上线到消费者看到'), (f'{k["ms"]/1000:.1f} s', 'kill -9 后被摘除(期间 %d 次请求失败,全部能靠重试挽回)' % k['fail']), (f'{R["graceful_ms"]:.0f} ms', '主动注销后消费者摘除')],
    body=[
        sec('注册与发现', '', term('', blk('z88', 1)), '<p>注册信息用<a href="zookeeper-ephemeral-persistent.html">临时节点</a>,所以提供者与 ZooKeeper 的会话断了节点会自己消失。数据模型细节见<a href="zookeeper-registry-data-model.html">下一篇</a>。</p>'),
        sec('上线', '', term('', blk('z88', 2))),
        sec('下线:被摘除前请求还会打过来', '', term('', blk('z88', 3)), '<p>摘除延迟等于<a href="zookeeper-session-expire.html">会话超时</a>(3 s 内加上一点调度)。这期间消费者仍可能向已死的实例发请求,所以消费者要做失败重试或熔断,不能只靠注册中心。</p>'),
        sec('主动注销', '', term('', blk('z88', 4))),
        sec('活着却被摘掉', '', term('', blk('z88', 5)), '<p>kazoo 状态监听器是在连接线程里回调的,如果在里面同步调用 <code>create</code>,我观察到节点没有被重新建立(我没有进一步查到根因,只确认了新开线程再调用就能成功)。无论用什么客户端,都要处理「会话过期后重新注册」。</p>'),
        sec('分步演示', '', demo('服务发现', [('t', 'term', '输出'), ('b', 'bars', '摘除耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。提供者是独立的 Python 子进程(本机 TCP 小服务),消费者每 20 ms 随机选一个当前列表里的实例发请求,失败后换一个重试;会话超时 3 s', '没有验证:Dubbo / Spring Cloud 的实际注册行为(见第 101、106 篇)、消费者本地缓存列表在 ZooKeeper 整体不可用时的表现、权重与路由、注册中心自我保护'],
)
