from lib import *
R = J('z73'); rc = R['recursive']
def S(k): return [l for l in out('z73').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("ACL 不继承:/p 用 digest 保护,在它下面创建 /p/c 时不指定 ACL,得到的是 world:anyone:31。结果:匿名按完整路径读 /p/c 成功(子节点的 ACL 是 world);匿名列出 /p 的子节点被拒绝(那是 /p 的 READ 权限)。保护了父节点不等于保护了子树。", t=tl(S(1)), mark=[1], done=[0], kv=KV([['子节点', '不继承父节点的 ACL'], ['按完整路径', '能绕过被保护的父节点']], ['子节点'])),
    step("创建 / 删除子节点看父节点的 ACL,读写子节点的数据看子节点自己的 ACL:匿名在 /p 下创建子节点 → 拒绝;匿名删除 /p/c(子节点是 world 但父节点只允许 admin)→ 拒绝;匿名修改 /p/c 的数据(子节点 world:cdrwa)→ 允许。", t=tl(S(2)), mark=[0, 1], done=[2], kv=KV([['创建 / 删除', '看父节点 ACL'], ['读 / 写数据', '看节点自己的 ACL']], ['创建 / 删除'])),
    step(f"要保护整棵子树必须逐个节点设置 ACL。一棵 5 层、每层 5 个子节点的树({rc['n']} 个节点),建树 {rc['build']:.1f} s,全是 world 时匿名能读深层节点;递归 set_acls 逐个同步请求用 {rc['secure']:.1f} s,之后匿名读深层节点被拒绝。大子树的加固是一次耗时的批处理,而且不是原子的(过程中有一段半保护状态)。", t=tl(S(3)), done=[0, 1], b=bars([['建树', rc['build'], f"{rc['build']:.1f} s"], ['递归 set_acls', rc['secure'], f"{rc['secure']:.1f} s"]], max(rc['build'], rc['secure']) * 1.1, done=[0, 1]), kv=KV([['递归授权', f"{rc['n']} 个节点 {rc['secure']:.1f} s"]], ['递归授权'])),
    step("新建的子节点仍然不继承:递归加固之后,再在 /tree/n0 下创建 new,它的 ACL 又是 world:anyone。所以创建时就带上 ACL(create 的 acl 参数),否则会有一小段「裸奔」时间窗。", t=tl(S(4)), mark=[0], kv=KV([['新子节点', '又是 world,创建时就要带 ACL']], ['新子节点'])),
]
A = dict(
    n=73, series='zookeeper', tags='ZooKeeper,ACL,继承,递归授权,真实验证,动画演示',
    desc=f'ACL 继承与递归授权实测:ACL 不继承(受保护的父节点下新建的子节点是 world:anyone,匿名按完整路径能读);创建 / 删除看父节点 ACL;{rc["n"]} 个节点的子树递归 set_acls 用 {rc["secure"]:.1f} s;加固之后新建的子节点又是 world。',
    lead='给一个目录设了 ACL,它下面的东西就安全了吗?不一定。这篇验证 ZooKeeper 的 ACL 完全不继承,以及要保护整棵子树的代价。',
    facts=[('不继承', '受保护的父节点下新建的子节点默认是 world:anyone'), ('完整路径能绕过', '匿名读不了父节点的子节点列表,但知道路径就能读子节点'), (f'{rc["n"]} 个节点 / {rc["secure"]:.1f} s', '递归给子树设置 ACL 的节点数与用时(逐个同步请求)')],
    body=[
        sec('ACL 不继承', '', term('', blk('z73', 1))),
        sec('谁的 ACL 管什么', '', term('', blk('z73', 2))),
        sec('递归授权的代价', '', term('', blk('z73', 3)), '<p>用异步请求或 multi 可以更快,本文只测了逐个同步的写法。</p>'),
        sec('新建节点', '', term('', blk('z73', 4))),
        sec('分步演示', '', demo('ACL 继承', [('t', 'term', '输出'), ('b', 'bars', '用时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;kazoo 同步请求;树是 5 层 × 5 个子节点', '没有验证:用 multi / 异步加速递归授权、客户端库的「创建节点时继承父 ACL」选项(有的库有)、Curator 的 ACLProvider'],
)
