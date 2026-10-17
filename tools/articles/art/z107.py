import pathlib
from lib import *
R = J('z107'); k0 = R['k0']; rv = R['rv']; zt = R['zk_try']
def S(k): return [x for x in out('z107').split('== ')[k].splitlines()[1:] if x.strip()]
SRC = pathlib.Path(__file__).resolve().parents[2] / 'k8s' / 'src' / 'staging/src/k8s.io/apiserver/pkg/storage/storagebackend/factory/factory.go'
L = SRC.read_text().splitlines(); a = [i for i, l in enumerate(L) if l.startswith('func Create(')][0]; fac = '\n'.join(L[a:a + 9])
steps = [
    step(f"kube-apiserver(用 v1.37.1 的源码在本机编译)只配 --etcd-servers 指向本机 etcd 3.7.2,2 秒就绪。刚启动、什么都没建,etcd 的 /registry 下已有 {k0['n']} 个 key、{len(k0['tops'])} 个一级分类({'、'.join(k0['tops'][:6])} …):apiserver 自己把系统对象(服务、租约、flowschemas 等)写进了 etcd。", t=tl(S(1)), done=[0], kv=KV([['存储', 'etcd 的 /registry/…'], ['空集群的 key 数', k0['n']]], ['存储'])),
    step("通过 REST 创建 namespace demo 与 ConfigMap cm1,etcd 里出现 /registry/namespaces/demo 与 /registry/configmaps/demo/cm1:key 就是「/registry/<资源类型>/<命名空间>/<名字>」。ConfigMap 的值以 k8s\\x00 开头,是 Kubernetes 的 protobuf 存储格式,共 191 字节(里面能看到 ConfigMap、cm1、demo 等字符串)。", t=tl(S(2)), done=[0, 1], kv=KV([['key 规则', '/registry/<类型>/<ns>/<名字>'], ['值格式', 'k8s\\x00 + protobuf']], ['key 规则'])),
    step(f"API 返回的 metadata.resourceVersion 就是 etcd 该 key 的 mod_revision:创建后两者都是 {rv['rv']};PATCH 之后都变成 74。Kubernetes 的乐观并发、watch 的断点续传都建立在 etcd 的全局递增 revision 上 —— ZooKeeper 也有全局递增的 zxid,但它的 watch 是一次性的(第 16、85 篇)。", t=tl(S(3)), done=[0, 1, 2], b=bars([['创建后 resourceVersion', int(rv['rv']), rv['rv']], ['etcd mod_revision', rv['mod'], str(rv['mod'])]], 80, done=[0, 1]), kv=KV([['resourceVersion = mod_revision', '创建与 PATCH 后都相等']], ['resourceVersion = mod_revision'])),
    step("读源码:kube-apiserver 的存储工厂 Create() 里只有 etcd3(etcd2 已明确移除),其它类型一律返回 unknown storage type;v1.37.1 的 go.mod 里有 go.etcd.io/etcd/client/v3 v3.7.0,go.mod 与 vendor/modules.txt 里搜 zookeeper 都是 0 处。也就是说它没有可插拔的存储后端。", t=tl(['(源码阅读,没有程序输出)', 'factory.go: Create() 的 switch c.Type', '  etcd2 → 返回错误(已不再支持)', '  Unset / etcd3 → newETCD3Storage', '  其它 → unknown storage type', 'go.mod: go.etcd.io/etcd/client/v3 v3.7.0', 'go.mod、vendor/modules.txt 中 zookeeper:0 处']), done=[0], mark=[0], kv=KV([['存储类型', '只有 etcd3'], ['go.mod 中的 zookeeper', '0 处']], ['存储类型'])),
    step(f"把同一个 kube-apiserver 的 --etcd-servers 改成 ZooKeeper 的 7300 端口:日志里出现 grpc 连接错误 error reading server preface: EOF(ZooKeeper 不会说 gRPC),约 20 秒后「command failed … error creating storage factory: etcd grpc connection not ready: context deadline exceeded」,进程退出(退出码 1),从没有出现「Serving securely」,/readyz 连不上。Kubernetes 控制面没有办法用 ZooKeeper 代替 etcd。", t=tl(S(4)), mark=[0], kv=KV([['--etcd-servers=ZooKeeper', 'apiserver 启动失败,退出码 1'], ['原因', 'ZooKeeper 不说 etcd 的 gRPC']], ['--etcd-servers=ZooKeeper'])),
]
A = dict(
    n=107, series='zookeeper', tags='ZooKeeper,Kubernetes,etcd,apiserver,真实验证,动画演示',
    desc=f'从 v1.37.1 源码编译真实的 kube-apiserver 并连本机 etcd:空集群 /registry 已有 {k0["n"]} 个 key;创建 namespace 与 ConfigMap 后在 etcd 里找到它们(值是 k8s\\x00 开头的 protobuf);resourceVersion 等于 etcd 的 mod_revision;源码里只有 etcd3 存储;把 --etcd-servers 指向 ZooKeeper 则启动失败。',
    lead='ZooKeeper 与 Kubernetes 控制面是什么关系?答案是:没有关系。但「没有」这个结论值得验证。这篇从 Kubernetes 的源码编译出真正的 kube-apiserver,让它连本机 etcd,看它往 etcd 里写什么、resourceVersion 与 etcd 的 revision 是什么关系;读存储工厂的源码确认只有 etcd3;最后试一下把它指向 ZooKeeper,看它怎么失败。',
    facts=[(f'{k0["n"]} 个 key', '空集群启动后 etcd 的 /registry 下已有的 key 数'), ('= mod_revision', 'API 的 resourceVersion 与 etcd 该 key 的 mod_revision 相等'), ('退出码 1', 'kube-apiserver 的 --etcd-servers 指向 ZooKeeper 时的结果')],
    body=[
        sec('apiserver 在 etcd 里的数据', '', term('', blk('z107', 1)), term('', blk('z107', 2)), '<p>只启动了 kube-apiserver 与 etcd,没有 controller-manager、scheduler、kubelet,所以只验证了「控制面的存储」这一层,不是完整集群。</p>'),
        sec('resourceVersion 就是 etcd revision', '', term('', blk('z107', 3)), '<p>下一篇(<a href="zookeeper-etcd.html">ZooKeeper 与 etcd 对比</a>)会具体比较两者的 watch 与版本模型。</p>'),
        sec('源码:存储后端只有 etcd3', '', src('staging/src/k8s.io/apiserver/pkg/storage/storagebackend/factory/factory.go(kubernetes v1.37.1)', fac), '<p>另外在 v1.37.1 源码目录里统计:go.mod 里有 <code>go.etcd.io/etcd/client/v3 v3.7.0</code>,go.mod 与 vendor/modules.txt 中 <code>zookeeper</code> 出现 0 次(这两个数字是我用 grep 查的,没有写进实验输出文件)。</p>'),
        sec('指向 ZooKeeper', '', term('', blk('z107', 4))),
        sec('分步演示', '', demo('Kubernetes 与 ZooKeeper', [('t', 'term', '输出'), ('b', 'bars', '版本号'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。kube-apiserver 由 kubernetes-src.tar.gz(v1.37.1)在本机 go build 得到(darwin/arm64,所以 --version 显示 v0.0.0-master+…);etcd 3.7.2;apiserver 用 --token-auth-file 与 AlwaysAllow 授权,只做 REST 调用(没有用 kubectl,因为本机 kubectl 在空 kubeconfig 下会交互式询问用户名);本机 Docker 无法拉取镜像,所以没有用 kind', '没有验证:完整的 Kubernetes 集群(kubelet、controller-manager)、etcd 的压缩与 defrag 行为、大规模集群的 etcd 负载、Kubernetes 以外的 etcd 使用者、其它版本的 apiserver'],
)
