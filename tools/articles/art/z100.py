import re, pathlib
from lib import *
R = J('z100'); T = R['java']; cl = R['close']; sp = R['supress']
def S(k): return [x for x in out('z100').split('== ')[k].splitlines()[1:] if x.strip()]
BASE = pathlib.Path(__file__).resolve().parents[2] / 'zksrc' / 'org/apache/zookeeper/server'
def load(p): return (BASE / p).read_text().splitlines()
WM = load('watch/WatchManager.java'); DT = load('DataTree.java')
def find(L, pat, start=0):
    for i in range(start, len(L)):
        if pat in L[i]: return i
def rng(L, a, b): return '\n'.join(L[a:b + 1])
i = find(WM, 'Set<Watcher> list = watchTable.get(path);'); add = rng(WM, i - 0, i + 5) + '\n        ...\n' + rng(WM, find(WM, 'list.add(watcher);'), find(WM, 'list.add(watcher);') + 6)
j = find(WM, 'if (!pathParentIterator.atParentPath())'); trig = rng(WM, j, j + 9)
k = find(DT, 'WatcherOrBitSet processed = dataWatches.triggerWatch'); dele = rng(DT, k, k + 3)
m = find(DT, 'if (parentCVersion > parent.stat.getCversion())'); cre = rng(DT, m, m + 3)
n2 = find(DT, 'dataWatches.triggerWatch(path, Event.EventType.NodeCreated'); cre2 = rng(DT, n2, n2 + 2)
jp = re.search(r'收到 (\d+) 个事件,按类型:(\{.*?\})', T); ev, bt = jp.group(1), jp.group(2)
steps = [
    step("WatchManager 里有两张表:watchTable(路径 → Set<Watcher>)和 watch2Paths(Watcher → 路径集合)。Set 决定了去重:同一连接对同一路径注册 100 次 exists watch,服务端的 zk_watch_count 只是 0 → 1;另一条连接注册 1 次 → 2。DataTree 里 dataWatches 与 childWatches 是两个独立的管理器:同一连接再对 /w 注册 get_children,→ 3。", t=tl(S(1)), done=[0], kv=KV([['重复注册', '100 次 → 1 个'], ['data / child', '两个管理器各计 1']], ['重复注册'])),
    step("触发即移除:triggerWatch 里对被触发的 watcher 做 iterator.remove()。验证:一个 get watch 触发前 zk_watch_count=4,set 一次后 3,回调收到一次 CHANGED。标准 watch 一次性,与客户端重新注册的需要一致。", t=tl(S(2)), done=[0], kv=KV([['触发', '该 watch 被移除'], ['zk_watch_count', '4 → 3']], ['触发'])),
    step(f"连接关闭时 removeWatcher(watcher) 遍历 watch2Paths 把这条连接的所有 watch 清掉。验证:500 条连接各在 10 个节点上注册 watch(zk_watch_count {cl['base']} → {cl['peak']}),500 次 close() 全部返回后第一次读取就已回到 {cl['first']}(基线 {cl['base']})—— 连接关闭后 watch 不会残留。", t=tl(S(3)), done=[0], b=bars([['基线', cl['base'], str(cl['base'])], ['500 连接 × 10 watch', cl['peak'], str(cl['peak'])], ['全部 close 后', cl['first'], str(cl['first'])]], cl['peak'], mark=[1], done=[0, 2]), kv=KV([['close 之后', f"{cl['first']}(= 基线)"], ['峰值', cl['peak']]], ['close 之后'])),
    step(f"持久递归 watch(addWatch(path, PERSISTENT_RECURSIVE),Java 原生客户端):注册后 zk_watch_count 0 → 1,随后在它下面建 3 层节点、改 5 次、删 1 次,收到 {ev} 个事件({bt});全部触发之后 zk_watch_count 仍是 1 —— 不会被移除,而且子孙节点的变化触发了祖先路径上的 watch(源码里 PathParentIterator 的 atParentPath 分支)。", t=tl(S(6)), done=[0, 1], kv=KV([['持久递归 watch', '不被移除,覆盖子孙节点'], ['事件', f'{ev} 个']], ['持久递归 watch'])),
    step(f"deleteNode 里三行:先 dataWatches.triggerWatch(path, NodeDeleted),把已处理的 watcher 集合 processed 传给 childWatches.triggerWatch 的 supress 参数,再触发父节点的 NodeChildrenChanged。验证:同一连接同时有 data watch 与 child watch,delete 后服务端发给它 {sp['a']} 字节,只有 data watch 的连接是 {sp['b']} 字节 —— 相等,说明只发了一个 NodeDeleted 通知。", t=tl(S(5)), done=[0], b=bars([['A:data + child', sp['a'], f"{sp['a']} B"], ['B:只有 data', sp['b'], f"{sp['b']} B"]], 40, done=[0, 1]), kv=KV([['同一 watcher 的 NodeDeleted', '只发 1 个通知']], ['同一 watcher 的 NodeDeleted'])),
    step("createNode 更新父节点:cversion 变大时才写入 cversion 并把 pzxid 设为这次事务的 zxid。验证:创建前 cversion=0;创建 /par/c 后 cversion=1,pzxid 等于子节点的 czxid;删除后 cversion=2,pzxid 变成删除事务的 zxid。", t=tl(S(4)), done=[0], kv=KV([['创建子节点', 'cversion +1,pzxid = czxid'], ['删除子节点', 'cversion +1']], ['创建子节点'])),
]
A = dict(
    n=100, series='zookeeper', tags='ZooKeeper,源码,DataTree,WatchManager,真实验证,动画演示',
    desc=f'读 ZooKeeper 3.9.6 的 WatchManager 与 DataTree 源码并逐条验证:Set 去重(重复注册 100 次只计 1)、触发即移除、连接关闭时清理、持久递归 watch 不被移除并覆盖子孙节点、delete 时 supress 使同一 watcher 只收到一个通知、createNode 更新父节点 cversion 与 pzxid。',
    lead='上一篇读了选举的源码。这一篇读 watch 的存储(WatchManager)和内存数据树(DataTree)里创建、删除节点的几段代码,每个结论都用真实运行验证:数据结构决定的行为,比如重复注册会怎样、连接断了 watch 去哪了、delete 时 data watch 与 child watch 的通知如何合并。',
    facts=[('100 → 1', '同一连接对同一路径重复注册 100 次,服务端 watch 数增加 1'), (f'{cl["peak"]} → {cl["first"]}', '500 条连接 × 10 个 watch 关闭后,zk_watch_count 立即回到基线'), (f'{sp["a"]} = {sp["b"]} B', 'delete 时有无 child watch,服务端发给该连接的字节相同:只发一个通知')],
    body=[
        sec('watchTable 与 Set<Watcher>', '', src('org/apache/zookeeper/server/watch/WatchManager.java(3.9.6,addWatch 节选)', add), '<p>两张表互为反向索引:从路径找 watcher(触发时用),从 watcher 找路径(连接关闭时用)。路径对应的是 <code>HashSet</code>,所以重复添加同一个 watcher 不会增加条目。</p>', term('', blk('z100', 1)), '<p>DataTree 里有 <code>dataWatches</code> 和 <code>childWatches</code> 两个独立实例(创建于 <code>WatchManagerFactory.createWatchManager()</code>,默认类是 <code>WatchManager</code>)。<a href="zookeeper-watcher-storm.html">watch 数量对内存的影响</a>就是这两个表的大小。</p>'),
        sec('触发即移除', '', src('同一文件,triggerWatch 节选', trig), term('', blk('z100', 2)), '<p>所以「一次性」不是客户端约定,而是服务端触发时就从表里删掉。而持久 watch 保留(下面)。</p>'),
        sec('连接关闭', '', term('', blk('z100', 3)), '<p>清理由 <code>removeWatcher(Watcher)</code> 完成;验证显示关闭返回后没有残留。(默认的 <code>WatchManager</code> 之外还有 <code>WatchManagerOptimized</code>,它会延迟清理已死 watcher,我没有测。)</p>'),
        sec('持久递归 watch', '', term('', blk('z100', 6)), '<p>这个 API 是 ZooKeeper 3.6 加入的(<code>addWatch</code>),常见的 Python 客户端 kazoo 没有提供。</p>', term('', blk('z100', 7))),
        sec('delete 时的 supress', '', src('org/apache/zookeeper/server/DataTree.java(3.9.6,deleteNode 节选)', dele), term('', blk('z100', 5)), '<p>同一条连接如果既有 data watch 又有 child watch,只会收到一次 NodeDeleted。这个行为是在服务端合并的,不依赖客户端去重。</p>'),
        sec('createNode:父节点的 cversion 与 pzxid', '', src('同一文件,createNode 节选', cre + '\n        ...\n' + cre2), term('', blk('z100', 4)), '<p>这就是 <a href="zookeeper-znode-model.html">stat</a> 里 cversion 与 pzxid 的来源。「只有变大才更新」的注释写的是<em>快照回放</em>的场景。</p>'),
        sec('分步演示', '', demo('读源码 + 验证', [('t', 'term', '验证输出'), ('b', 'bars', '数量 / 字节'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。源码来自 Maven Central 的 zookeeper-3.9.6-sources.jar;watch 数取自 mntr 的 zk_watch_count;持久递归 watch 用 Curator 依赖里的 Java 原生客户端(kazoo 没有这个 API);「服务端发给连接的字节」用 TCP 代理统计', '没有验证:WatchManagerOptimized(BitHashSet 实现)与 WatcherCleaner 的延迟清理、PERSISTENT(非递归)watch 的行为、DataTree 中 ephemerals / ttls / containers 表的行为、快照回放时 cversion 的比较逻辑'],
)
