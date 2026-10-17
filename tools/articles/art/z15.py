from lib import *
R = J('z15')
def S(k): return [l for l in out('z15').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("三种 watch 对应三种读操作:get(path, watch)(数据 watch)、exists(path, watch)(存在 watch,节点不存在也能注册)、get_children(path, watch)(子节点 watch)。数据 watch:set → NodeDataChanged,delete → NodeDeleted。存在 watch:create 不存在的节点 → NodeCreated,对已存在节点 set → NodeDataChanged。", t=tl(S(1)[:4]), done=[0, 1, 2, 3], kv=KV([['数据 watch', 'CHANGED / DELETED'], ['存在 watch', 'CREATED(也能监听不存在的节点)']], ['存在 watch'])),
    step("子节点 watch:在父节点下 create 子节点 → NodeChildrenChanged;delete 子节点 → NodeChildrenChanged;但修改子节点自己的数据 → 没有事件;删除父节点本身 → NodeDeleted。对父节点注册的「数据 watch」,在它下面创建子节点 → 没有事件。", t=tl(S(1)[4:]), done=[0, 2, 3], mark=[1, 4], kv=KV([['子节点 watch', '只管子节点的增删'], ['改子节点的数据', '不触发']], ['改子节点的数据'])),
    step("事件里没有数据:事件对象只有 type(CHANGED)、state(CONNECTED)、path(/n)三个字段,没有新数据字段;收到 NodeDataChanged 后必须再 get 一次才能拿到新值(这里是 v2)。", t=tl(S(2)), kv=KV([['事件内容', 'type / state / path']], ['事件内容'])),
    step("一次性:注册一次 watch 之后连续 set 3 次,只收到 1 个事件;要继续接收就必须重新注册(第 16 篇展开)。", t=tl(S(3)), mark=[0], kv=KV([['watch', '触发一次就失效']], ['watch'])),
]
A = dict(
    n=15, series='zookeeper', tags='ZooKeeper,Watcher,监听机制,真实验证,动画演示',
    desc='Watcher 实测:数据 watch / 存在 watch / 子节点 watch 各自被哪些操作触发(子节点 watch 不管子节点的数据修改,存在 watch 能监听不存在的节点);事件只带 type、state、path,不带数据;一次性,触发后要重新注册。',
    lead='Watcher 是 ZooKeeper 最有特色的功能,也是最容易理解错的:谁能触发它?事件里有什么?触发后还有效吗?这篇做一个触发矩阵,每一种「注册 + 操作」组合都真实执行一遍。',
    facts=[('3 种 watch', '数据(get)、存在(exists)、子节点(get_children)'), ('事件不带数据', '只有 type / state / path,要再读一次'), ('一次性', '触发后失效,连续写 3 次只收到 1 个事件')],
    body=[
        sec('触发矩阵', '', term('', blk('z15', 1)), '<p>kazoo 里 watch 的事件类型叫 CHANGED / DELETED / CREATED / CHILD,对应 Java 客户端的 NodeDataChanged / NodeDeleted / NodeCreated / NodeChildrenChanged。</p>'),
        sec('事件里有什么', '', term('', blk('z15', 2))),
        sec('一次性触发', '', term('', blk('z15', 3))),
        sec('分步演示', '', demo('Watcher', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;两个 kazoo 客户端:一个注册 watch,一个做修改;每种组合使用独立路径', '没有验证:持久 watch(第 16 篇)、重连之后 watch 是否保留(客户端库行为)、同一路径多次注册的去重(第 18 篇)、顺序保证(事件与读取之间的先后)'],
)
