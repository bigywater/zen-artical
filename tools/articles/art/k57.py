from lib import *
S = SS('k57')
F1 = [['整体挂载 /whole', '..data 切换'], ['subPath /etc/app.conf', '绑定到旧文件'], ['改 ConfigMap', 'v1 → v2'], ['62 秒后', '/whole=v2,/etc/app.conf=v1']]
F2 = [['/whole', '符号链接 → ..data'], ['/etc/app.conf', '普通文件'], ['mountinfo', '来源 …/..2026_…43/app.conf//deleted'], ['节点上 ..data', '已指向新目录']]
F3 = [['subPath 文件还是 v1', ''], ['crictl stop 容器', '重启容器'], ['restartCount=1', 'Pod 没重建'], ['/etc/app.conf', 'v2']]
F4 = [['整个卷挂到 /var', '原内容被遮住'], ['subPath 挂单个文件', '原内容都在']]
F5 = [['POD_NAME=w1 / w2', 'downward API 注入'], ['subPathExpr=$(POD_NAME)', '展开成子目录'], ['共用 hostPath', 'w1/out.log、w2/out.log']]
PANELS = [('f', 'flow', 'subPath 挂载'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("同一个 ConfigMap 挂两次:整体挂到 /whole,subPath: app.conf 单文件挂到 /etc/app.conf。把 app.conf 从 v1 改成 v2:/whole/app.conf 62 秒后变成 v2,再等到总共 122 秒,/etc/app.conf 仍是 v1。", f=fl(F1, cur=[2], mark=[1], done=[0, 3]), t=tl(S(1), mark=lidx(S(1), '62 秒后'), done=lidx(S(1), '一直是 v1')), b=bars([['整体挂载更新', 62, '62 s'], ['subPath 一直没更新', 122, '122 s 仍是 v1']], 122, done=[0], mark=[1]), kv=KV([['整体挂载', '跟着 kubelet 同步更新'], ['subPath', '更新不了'], ['等多久都一样', '122 秒之后还是 v1']], ['subPath'])),
    step("ls 看:/whole 里的 app.conf 是指向 ..data/app.conf 的符号链接,/etc/app.conf 是一个普通文件。mountinfo 里 /whole 的来源是 …/volumes/kubernetes.io~configmap/cfg,而 /etc/app.conf 的来源是 cfg/..2026_10_10_14_56_43.…/app.conf//deleted——一个已经被删除的旧时间戳目录里的旧文件。节点上 ..data 此刻指向 ..2026_10_10_14_57_45.…,里面的 app.conf 是 v2。", f=fl(F2, cur=[2], done=[0, 1, 3]), t=tl(S(2), mark=lidx(S(2), 'app.conf//deleted'), done=lidx(S(2), '现在指向')), kv=KV([['subPath 是 bind mount', '绑定的是当时那个文件,不是路径'], ['旧目录被删', '//deleted 表示它已经脱离目录树'], ['..data 切换', '只影响按路径查找的整体挂载']], ['bind mount'])),
    step("用 crictl 停掉容器、让 kubelet 重启它(restartCount=1,Pod 没有重建)之后,/etc/app.conf 变成 v2:新容器启动时,kubelet 重新从卷里取了当前版本去做 subPath 的绑定。", f=fl(F3, cur=[1, 2], done=[3]), t=tl(S(3), mark=lidx(S(3), 'restartCount=1'), done=lidx(S(3), "app.conf='v2'")), kv=KV([['重启容器', '重新做 subPath 绑定,拿到新文件'], ['不用重建 Pod', '改完 ConfigMap 重启容器即可'], ['想自动更新', '别用 subPath,或加外部 reloader']], ['重启容器'])),
    step("subPath 的真正用途。busybox 的 /var 原来有 run、spool、www;把整个卷挂到 /var 之后只剩 app.conf、other.conf、run,spool 和 www 被遮住了;用 subPath 把 app.conf 单独挂到 /var/app.conf,/var 里是 app.conf、run、spool、www,原来的文件都在。", f=fl(F4, cur=[0, 1]), t=tl(S(4), mark=lidx(S(4), '原来的内容被遮住'), done=lidx(S(4), '原来的文件都在')), kv=KV([['整个卷挂到目录', '原目录里的内容被遮住'], ['subPath', '只往目录里“加”一个文件'], ['代价', '不会随 ConfigMap 更新']], ['subPath'])),
    step("subPathExpr: $(POD_NAME):两个 Pod 共用节点上的 hostPath /tmp/k57-shared,各自用 subPathExpr 展开环境变量 POD_NAME,节点上得到 w1/out.log(内容 w1)和 w2/out.log(内容 w2),互不干扰。", f=fl(F5, cur=[1], done=[2]), t=tl(S(5), done=lidx(S(5), 'w1/out.log')), kv=KV([['subPathExpr', '用环境变量(含 downward API)展开子路径'], ['共用的卷', '每个 Pod 写自己的子目录'], ['hostPath', '本实验里的共享卷,实验后已删']], ['subPathExpr'])),
]
A = mkartk('k57', 57, 'Kubernetes,subPath,ConfigMap,volumeMounts,bind mount,subPathExpr,真实验证,动画演示',
    '在 kind 集群里实测 subPath 挂载为什么不更新:同一个 ConfigMap 改成 v2,整体挂载 62 秒后更新,subPath 挂的文件 122 秒后仍是 v1;mountinfo 显示它绑定的是已被删除的旧时间戳目录里的旧文件(//deleted);重启容器后才取到 v2;subPath 的价值是只往目录里加一个文件而不遮住原有内容,subPathExpr 可以给每个 Pod 独立的子目录。',
    '用 subPath 挂的 ConfigMap 文件,为什么怎么改都不更新?这篇把同一个 ConfigMap 分别整体挂载和 subPath 挂载,对比文件类型、mountinfo 的来源路径和重启后的行为,直接看到原因。',
    [('62 秒 vs 永远', '整体挂载更新用了 62 秒;subPath 挂载等到 122 秒仍是旧值'), ('//deleted', 'subPath 挂载在 mountinfo 里绑定的是已被删除的旧目录里的文件'), ('1 次容器重启', '重启容器(不重建 Pod)后 subPath 文件才变成新内容')],
    [('同一个 ConfigMap,两种结果', '<p>把同一个 ConfigMap 整体挂到 <code>/whole</code>,又用 <code>subPath: app.conf</code> 把单个文件挂到 <code>/etc/app.conf</code>。把 <code>app.conf</code> 从 v1 改成 v2:整体挂载的 <code>/whole/app.conf</code> 在 62 秒后变成 v2(同步延迟在不同次运行里有 1~86 秒的差别,见上一篇);<code>/etc/app.conf</code> 即使等到 122 秒仍是 v1。</p>'),
     ('为什么:绑定的是旧文件', '<p><code>/whole/app.conf</code> 是指向 <code>..data/app.conf</code> 的符号链接,更新靠切换 <code>..data</code>;而 <code>/etc/app.conf</code> 是一个普通文件,它是 bind mount。<code>mountinfo</code> 里这个挂载的来源是 <code>…/cfg/..2026_10_10_14_56_43.…/app.conf//deleted</code>——启动时那个时间戳目录里的文件,更新后这个目录被 kubelet 删掉了,所以带 <code>//deleted</code>。bind mount 绑定的是当时的文件本身,不是路径,新内容写在新的目录里,它永远看不到。节点上的 <code>..data</code> 此时已指向新目录,里面的 <code>app.conf</code> 是 v2。</p>'),
     ('怎么让它变', '<p>重启容器(Pod 不用重建)就够了:用 crictl 停掉容器,kubelet 重启后 <code>restartCount=1</code>,<code>/etc/app.conf</code> 变成 v2——新容器启动时重新做了 subPath 的绑定。实际操作里常用 <code>kubectl rollout restart</code>,或者干脆不用 subPath(把配置挂到独立目录再用 <code>--config</code> 指过去),或者借助 reloader 之类的外部控制器。</p>'),
     ('subPath 的价值', '<p>把整个卷挂到 <code>/var</code>,原来 <code>/var</code> 下的 <code>spool</code>、<code>www</code> 就被遮住了(只剩 <code>app.conf</code>、<code>other.conf</code> 和 <code>run</code>;<code>run</code> 应该是为 <code>/var/run/secrets</code> 的令牌挂载留下的);用 subPath 把单个文件挂到 <code>/var/app.conf</code>,原有的 <code>run</code>、<code>spool</code>、<code>www</code> 都还在——这是 subPath 存在的理由,代价就是不会更新。</p>'),
     ('subPathExpr', '<p><code>subPathExpr</code> 可以用环境变量展开路径:两个 Pod 共用节点上的 hostPath <code>/tmp/k57-shared</code>,各自 <code>subPathExpr: $(POD_NAME)</code>(<code>POD_NAME</code> 由 downward API 注入),节点上得到 <code>w1/out.log</code> 和 <code>w2/out.log</code>,互不覆盖。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);每 0.5 秒 kubectl exec 读文件得到更新延迟;mountinfo 取自容器内的 /proc/self/mountinfo;subPath 重启实验用 crictl stop 触发 kubelet 重启容器;每种情形各一次(同步延迟本身在多次运行中为 1~86 秒)',
     '没有验证:subPath 用在 Secret / projected / emptyDir 上的差别(机制相同,本文只测了 ConfigMap);subPath 指向目录而不是文件时的更新行为;subPath 与符号链接的安全限制(CVE 相关的 subPath 逃逸检查);hostPath 上 subPathExpr 的权限;应用用 inotify 监听配置文件的行为'],
    'subPath', PANELS)
