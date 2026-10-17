from lib import *
R = J('z16'); co = R['coalesce']
def S(k): return [l for l in out('z16').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"带重新注册的 watcher(通知回调里重新 get 并重新注册):另一个客户端连续写 {co['writes']} 次,watcher 只收到 {co['notif']} 次通知,「通知后重新读取」看到 {co['seen']} 个不同的值。有一部分写入发生在「通知已触发、还没重新注册」的间隙里,没有产生通知——通知次数小于写入次数。", t=tl(S(1)), b=bars([['写入次数', co['writes'], str(co['writes'])], ['通知次数', co['notif'], str(co['notif'])]], co['writes'] * 1.05, mark=[1], done=[0]), kv=KV([['通知', '会合并 / 丢失中间状态'], ['最终值', '重新读取总能拿到最新']], ['通知'])),
    step("所以 watch 只适合当「有变化了」的信号,不能当变化日志用;要得到最新状态,收到通知后读取,并且读取时重新注册(get 带 watch),读到的就是注册那一刻之后的最新值。需要每一次变化的场景,要靠版本号或顺序节点自己记录。", t=tl(S(1)[1:]), kv=KV([['正确用法', '通知 → 重新读 + 重新注册']], ['正确用法'])),
    step("持久 watch(3.6+,addWatch,mode=PERSISTENT):注册一次,3 次 set 全部收到 NodeDataChanged(zxid 依次递增),再在下面创建子节点又收到 NodeChildrenChanged——不再需要重新注册。(用官方 CLI 的交互会话注册,事件打印在它的输出里;kazoo 没有这个 API。)", t=tl(S(2)), done=[1, 2, 3, 4], kv=KV([['PERSISTENT', '不会失效,收到每一次事件']], ['PERSISTENT'])),
    step("PERSISTENT_RECURSIVE:对 /pr 注册后,子树里任何位置的变化都收到:/pr/a 的数据修改(NodeDataChanged)、/pr/a/b 创建(NodeCreated)、/pr/c 创建与删除(NodeCreated / NodeDeleted)——孙子节点也算,而且是完整的路径。", t=tl(S(3)), done=[1, 2, 3, 4], kv=KV([['PERSISTENT_RECURSIVE', '整棵子树,含孙子节点']], ['PERSISTENT_RECURSIVE'])),
]
A = dict(
    n=16, series='zookeeper', tags='ZooKeeper,Watcher,一次性触发,持久watch,真实验证,动画演示',
    desc=f'Watcher 一次性触发的后果:写 {co["writes"]} 次、带重新注册的 watcher 只收到 {co["notif"]} 次通知(间隙里的变化没有通知),但重新读取总能拿到最新值;持久 watch(addWatch PERSISTENT / PERSISTENT_RECURSIVE)注册一次持续收到事件,递归模式覆盖整棵子树。',
    lead='Watch 触发一次就失效,这个设计带来一个微妙的问题:从触发到重新注册之间的变化怎么办?这篇用 200 次快速写入量出来,再看 3.6 之后的持久 watch 怎么解决它。',
    facts=[(f'{co["notif"]} / {co["writes"]}', '通知次数 / 写入次数(重新注册之间的变化没有通知)'), ('最新值不会丢', '通知后重新读取,读到的总是注册时刻之后的最新版本'), ('持久 watch', 'addWatch 注册一次,PERSISTENT_RECURSIVE 覆盖整棵子树')],
    body=[
        sec('一次性触发与合并', '', term('', blk('z16', 1)), '<p>注意:通知次数每次运行都会不同,它取决于写入速度和回调里重新注册的快慢。结论是「少于写入次数」,不是 147 这个数。</p>'),
        sec('持久 watch', '', term('', blk('z16', 2)), '<p>持久 watch 是 ZooKeeper 3.6 加入的功能。它不会失效,但也意味着服务端会长期持有这些 watch 的内存,用得过多的后果见第 17、18 篇。</p>'),
        sec('递归持久 watch', '', term('', blk('z16', 3))),
        sec('分步演示', '', demo('一次性与持久', [('t', 'term', '输出'), ('b', 'bars', '次数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;一次性 watcher 用 kazoo,持久 watch 用官方 ZooKeeperMain 的交互会话(addWatch);写入 200 次', '没有验证:持久 watch 在断线重连后的行为、PERSISTENT_RECURSIVE 对大子树的开销、Curator 的 CuratorCache 如何基于它实现(第 95 篇)、watch 事件的顺序保证'],
)
