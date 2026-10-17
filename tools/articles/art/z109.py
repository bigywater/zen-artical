from lib import *
R = J('z109'); sr = R['src']; cp = R['copy']; vf = R['verify']; sy = R['sync']; na = R['noauth']; ep = R['eph']; pf = R['prefix']; st = R['subtree']
def S(k): return [x for x in out('z109').split('== ')[k].splitlines()[1:] if x.strip()]
steps = [
    step(f"造一份有代表性的数据:{sr['total']} 个 znode(分层配置 /app/svc*/环境/key*、/queue 下 {sr['sequential']} 个顺序节点、{sr['ephemeral']} 个临时节点、{sr['acl']} 个带 digest ACL 的节点)。第一道坎:没有凭据的迁移工具遍历只读到 {na['without']} 个,{na['blocked']} 个因 ACL 拒绝而读不了(NoAuthError);给迁移工具加上 digest 凭据才读全 {na['with_auth']} 个。迁移账号必须能读所有节点。", t=tl(S(1)), mark=[0], kv=KV([['znode', sr['total']], ['无凭据遍历', f"漏 {na['blocked']} 个(NoAuthError)"]], ['无凭据遍历'])),
    step(f"整体搬迁:遍历 ZooKeeper,key 取 znode 路径、value 取数据,每 100 个 key 一个 etcd 事务:{cp['n']} 个 key 用时 {cp['s']:.2f} s。把 etcd 里全部 key 读回逐个比较:路径集合相同({vf['same']})、数据不同 {vf['diff']} 个、整体 SHA-256 一致({vf['sha_eq']})。数据本身搬运很容易,难的是语义。", t=tl(S(2)), done=[0], kv=KV([['搬迁用时', f"{cp['s']:.2f} s"], ['核对', '路径与数据完全一致']], ['核对'])),
    step(f"搬不过去的语义(都是实测):① 版本号:ZooKeeper 里 version=0,搬后 etcd 里 version=1、mod_revision 是新的,依赖 version 的 CAS 要重新读;② 临时节点:{sr['ephemeral']} 个临时节点搬过去是普通 key,关闭 ZooKeeper 里那些会话后,ZooKeeper 剩 {ep['zk_left']} 个、etcd 里仍有 {ep['etcd_left']} 个 —— 要用租约自己重建;③ ACL:读回的字段只有 key、value、版本、revision,没有 ACL,我没有配置 etcd 的授权,所以没迁移任何访问控制;④ 顺序节点只是名字里带序号的普通 key,自动加序号要自己用事务实现(我没有实现)。", t=tl(S(3) if len(out('z109').split('== ')) > 4 else S(3)), mark=[0], kv=KV([['version', '重置'], ['临时节点', f"etcd 里残留 {ep['etcd_left']} 个"]], ['临时节点'])),
    step(f"目录语义:ZooKeeper 的 /app/svc1 不存在,etcd 用前缀 /app/svc1 查询却返回 {pf['no_slash']} 个 key(把 svc10–svc19 全匹配了),带斜杠的 /app/svc1/ 则返回 {pf['slash']} 个;列出 /app/svc00 的子节点,ZooKeeper 返回 {st['zk']} 个直接子节点,etcd 的前缀查询返回整棵子树 {st['etcd']} 个 key。迁移后所有「列子节点」的代码都要改成「前缀 + 按层级过滤」。", t=tl(S(4)), mark=[0], b=bars([['ZooKeeper get_children', st['zk'], str(st['zk'])], ['etcd 前缀 /app/svc00/', st['etcd'], str(st['etcd'])]], st['etcd'], mark=[1], done=[0]), kv=KV([['列子节点', f"ZK {st['zk']} 个 / etcd 前缀 {st['etcd']} 个"]], ['列子节点'])),
    step(f"切换期间的增量同步:用 DataWatch 与 ChildrenWatch 追踪 /app 子树(为 4906 个 znode 挂 watch 用了 23 s,服务端 watch 数 {R['sync_watches']}),同时对 ZooKeeper 做 300 次随机变更({sy['ops']}):同步后 ZooKeeper {sy['zk']} 个 / etcd {sy['etcd']} 个,缺少 {sy['miss']}、多出 {sy['extra']}、数据不同 {sy['bad']};写入到 etcd 的延迟中位 {sy['lag_med']:.0f} ms、最大 {sy['lag_max']:.0f} ms。这个同步器只覆盖新建、修改、删除;没有处理 ACL、临时节点和顺序节点。", t=tl(S(5)), done=[0, 1], kv=KV([['增量同步', f"缺少 {sy['miss']} / 多出 {sy['extra']} / 不同 {sy['bad']}"], ['同步延迟(中位)', f"{sy['lag_med']:.0f} ms"]], ['增量同步'])),
]
A = dict(
    n=109, series='zookeeper', tags='ZooKeeper,etcd,迁移,真实验证,动画演示',
    desc=f'把一份 {sr["total"]} 个 znode 的 ZooKeeper 数据真实迁移到 etcd:{cp["s"]:.2f} s 搬完且逐个核对一致;搬不过去的语义(版本号、临时节点残留 {ep["etcd_left"]} 个、ACL、顺序节点、目录前缀查询);用 watch 做增量同步 300 次随机变更后零差异、延迟中位 {sy["lag_med"]:.0f} ms。',
    lead='把数据从 ZooKeeper 搬到 etcd 并不难,难的是「搬完之后行为一样」。这篇用一份有代表性的数据(分层配置、顺序节点、临时节点、ACL)做一次真实迁移:整体拷贝并核对、列出所有搬不过去的语义,再用 watch 做切换期间的增量同步。',
    facts=[(f'{cp["s"]:.2f} s', f'{cp["n"]} 个 key 整体拷贝到 etcd 并核对一致'), (f'{ep["etcd_left"]} 个', '会话关闭后 ZooKeeper 里消失、但在 etcd 里残留的临时节点数'), (f'{sy["lag_med"]:.0f} ms', 'watch 增量同步写入 etcd 的延迟(中位),300 次变更零差异')],
    body=[
        sec('数据与权限', '', term('', blk('z109', 1)), '<p>ACL 的机制见<a href="zookeeper-acl.html">ACL 那篇</a>:迁移账号需要对所有节点有读权限,否则漏数据时没有任何报错(我的工具专门捕获了 NoAuthError 才发现)。</p>'),
        sec('整体拷贝与核对', '', term('', blk('z109', 2))),
        sec('搬不过去的语义', '', term('', blk('z109', 3)), '<p>临时节点的语义见<a href="zookeeper-ephemeral-persistent.html">那一篇</a>:它依赖会话。etcd 里与之对应的是租约(lease),但租约要由客户端定期续约,不是搬过去就有。</p>'),
        sec('目录与前缀', '', term('', blk('z109', 4))),
        sec('增量同步', '', term('', blk('z109', 5)), '<p>用 watch 追踪变化要小心第 85 篇讲过的合并:快速的连续更新可能只看到最后一次,所以这里是「读最新值再写入」,最终一致,但不保证每次变更都转发。</p>'),
        sec('分步演示', '', demo('ZooKeeper → etcd 迁移', [('t', 'term', '输出'), ('b', 'bars', '数量'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。ZooKeeper 3.9.6 单节点、etcd 3.7.2 单节点(HTTP/JSON 网关,事务每批 100 个 put);数据是脚本生成的合成数据,随机种子固定;增量同步器用 kazoo 的 DataWatch / ChildrenWatch', '没有验证:双写与灰度切流(读写切换顺序)、租约方式重建临时节点语义、etcd 的 RBAC 迁移 ACL、顺序节点的 etcd 实现、百万级 znode 的迁移耗时与 etcd 事务上限(单事务最多多少操作我只用了 100)、从旧 ZooKeeper 版本迁移'],
)
