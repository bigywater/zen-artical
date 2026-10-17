import re
from lib import *
R = J('z98'); T = R['stdout']
def S(k): return [x for x in out('z98').split('== ')[k].splitlines()[1:] if x.strip()]
ev = re.search(r'收到 (\d+) 次事件', T).group(1)
m = re.search(r'顺序 (\d+) 个/s.*?64 goroutine (\d+) 个/s.*?;([\d.]+) 倍', T); sq, pl, mult = m.group(1), m.group(2), m.group(3)
lk = re.search(r'最终 (\d+) / 200,用时 ([\d.]+) s', T).groups()
fail = re.findall(r'调用 Get → zk: could not connect to a server\(耗时 (\d+) ms', T)
steps = [
    step("go-zookeeper/zk v1.0.4:错误是包级变量 —— 已存在 zk.ErrNodeExists、版本冲突 zk: version conflict、临时节点下建子节点 zk: ephemeral nodes may not have children;可以直接用 == 比较。FlagSequence 创建返回带序号的路径 /g/seq-0000000000。", t=tl(S(1)), done=[0], kv=KV([['错误', '包级变量,可直接比较']], ['错误'])),
    step(f"watch 是一次性的 channel:GetW 返回 (data, stat, <-chan Event);第一次变化收到 EventNodeDataChanged;不重新 GetW 就收不到第二次(channel 已关闭,读到零值事件)。在循环里重新 GetW:连续 Set 200 次,只收到 {ev} 次事件,最终值正确。和 kazoo、Curator 一样会合并。", t=tl(S(2)), done=[0], mark=[2], kv=KV([['watch', '一次性 channel'], ['200 次连续更新', f'{ev} 次事件']], ['watch'])),
    step(f"并发:2000 次 Create,单个 goroutine 顺序 {sq} 个/s,64 个 goroutine 同时 {pl} 个/s,约 {mult} 倍 —— 一个 Conn 可以被多个 goroutine 共享,请求在同一连接上流水线化。", t=tl(S(3)), done=[0], b=bars([['顺序', int(sq), f'{sq}/s'], ['64 goroutine', int(pl), f'{pl}/s']], int(pl), mark=[0], done=[1]), kv=KV([['顺序 / 并发', f'{sq} / {pl} 个/s']], ['顺序 / 并发'])),
    step("Multi:第一个操作成功、第二个(建已存在的节点)失败时整体失败,/m1 没有被建;两个都合法时都成功。", t=tl(S(4)), done=[0], kv=KV([['Multi', '原子,失败则全部不生效']], ['Multi'])),
    step(f"自带的锁 zk.NewLock:10 个 goroutine 各用独立连接累加 200 次:最终 {lk[0]} / 200,用时 {lk[1]} s;释放后 /glock 下没有子节点;锁节点名 _c_<32 位十六进制>-lock-<序号>,与 Curator 的命名风格相同(但我没有验证两者能否互相排斥)。", t=tl(S(5)), done=[0, 1], kv=KV([['zk.NewLock', f'{lk[0]} / 200']], ['zk.NewLock'])),
    step(f"服务端停止后,Go 客户端的调用不等待:连续 3 次 Get 都在 {fail[0]}、{fail[1]}、{fail[2]} ms 内返回 zk: could not connect to a server(fail fast)。事件 channel 依次是 StateDisconnected → StateConnecting(反复)→ StateConnected → StateHasSession。和 kazoo、Curator「调用一直等到恢复」不同:Go 要自己写重试。", t=tl(S(6)), mark=[5], kv=KV([['服务端不可用时', '调用立即失败(约 0.3–0.7 s)'], ['重试', '自己实现']], ['服务端不可用时'])),
]
A = dict(
    n=98, series='zookeeper', tags='ZooKeeper,Go,go-zookeeper,客户端,真实验证,动画演示',
    desc=f'go-zookeeper/zk v1.0.4 在真实 ZooKeeper 3.9.6 上的实测:错误为包级变量、watch 是一次性 channel(200 次更新收到 {ev} 次事件)、64 goroutine 并发 {mult} 倍、Multi 原子、自带锁 200/200、服务端不可用时调用立即失败而不是等待。',
    lead='Go 的 ZooKeeper 客户端风格和 kazoo、Curator 很不一样:没有重试策略、没有缓存、watch 是 channel。这篇用 go-zookeeper/zk 实测它的错误值、watch、并发、Multi、自带锁,以及服务端不可用时的行为。',
    facts=[('一次性 channel', 'GetW 的 watch;循环里重新 GetW,200 次更新收到 %s 次事件' % ev), (f'{mult} 倍', '64 个 goroutine 并发相对顺序调用的吞吐'), ('立即失败', '服务端不可用时 Get 在 0.3–0.7 s 内返回 ErrNoServer')],
    body=[
        sec('错误与基本调用', '', term('', blk('z98', 1))),
        sec('watch', '', term('', blk('z98', 2)), '<p>watch 的一次性语义见<a href="zookeeper-watcher-once.html">这一篇</a>。Go 里每个 watch 是一个 channel,触发一次后关闭。</p>'),
        sec('并发', '', term('', blk('z98', 3)), '<p>和 <a href="zookeeper-python-kazoo-client.html">kazoo</a>、<a href="zookeeper-curator.html">Curator</a> 一样,流水线化是提高吞吐的关键。</p>'),
        sec('Multi', '', term('', blk('z98', 4))),
        sec('自带的锁', '', term('', blk('z98', 5)), '<p>机制与<a href="zookeeper-distributed-lock.html">分布式锁</a>那篇相同。</p>'),
        sec('服务端不可用', '', term('', blk('z98', 6)), '<p>Go 客户端在服务端不可用时不阻塞等待而是立刻返回错误,调用方必须自己决定重试(带退避)。不要在没有消费事件 channel 的情况下使用:事件 channel 要有人读(我的程序里单独启了一个 goroutine 读)。我没有测不读事件 channel 会不会阻塞客户端。</p>'),
        sec('分步演示', '', demo('Go 客户端', [('t', 'term', '输出'), ('b', 'bars', '吞吐'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Go 1.27.1(darwin/arm64)+ github.com/go-zookeeper/zk v1.0.4(经代理下载);服务端重启为 SIGTERM 后重新启动', '没有验证:不消费事件 channel 时是否阻塞、其它 Go 客户端(如 samuel/go-zookeeper 的各分支)、TLS / SASL、会话过期后的行为细节、zk.Lock 与 Curator 锁的互斥'],
)
