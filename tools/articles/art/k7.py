from lib import *
S = SS('k7')
F1 = [['watch rv=14898', 'b 创建之后'], ['MODIFIED a', 'rv=14899'], ['DELETED b', 'rv=14900'], ['ADDED c', 'rv=14901'], ['MODIFIED c', 'rv=14902']]
F2 = [['不带 rv / rv=0', '现有对象'], ['ADDED a、c…', '合成的初始事件'], ['实时事件', '之后的变化']]
F3 = [['客户端 rv=14929', ''], ['apiserver watch 缓存', '最老的是 15739'], ['ERROR 410', 'too old resource version'], ['重新 list', '拿新的 rv 再 watch']]
F4 = [['标签 app=x', 'ADDED'], ['改成 app=y', 'DELETED'], ['改回 app=x', 'ADDED'], ['改 data', 'MODIFIED'], ['删除', 'DELETED']]
PANELS = [('f', 'flow', 'watch 的事件'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("依次 创建 a、创建 b(rv=14898)、修改 a、删除 b、创建 c、修改 c。从 resourceVersion=14898 开始 watch,收到 4 个事件:MODIFIED a rv=14899、DELETED b rv=14900、ADDED c rv=14901、MODIFIED c rv=14902——只有 14898 之后发生的;从当前版本 14902 开始 watch 收到 0 个事件,watch 期间创建再删除 live 才收到 ADDED live、DELETED live。", f=fl(F1, cur=[1, 2, 3, 4], done=[0]), t=tl(S(1), mark=lidx(S(1), '收到 4 个事件'), done=lidx(S(1), '收到 0 个事件', 'ADDED live')), kv=KV([['从 rv 开始', '收到的是 rv 之后的事件,不含 rv 本身'], ['当前 rv', '什么都不会补发'], ['事件里的 rv', '就是那次修改的版本']], ['从 rv 开始'])),
    step("不带 resourceVersion 或 resourceVersion=0:先收到现有对象(a、c、kube-root-ca.crt)的 ADDED,已经删掉的 b 不会出现;sendInitialEvents=true(流式 list)在初始 ADDED 之后收到一个 BOOKMARK(rv=14923),注解是 k8s.io/initial-events-end: true,标志着“初始状态发完了”。", f=fl(F2, cur=[1], done=[0, 2]), t=tl(S(2), mark=lidx(S(2), 'BOOKMARK'), done=lidx(S(2), '不带 resourceVersion', 'resourceVersion=0')), kv=KV([['不带 rv / rv=0', '先发现有对象的 ADDED'], ['已删除的对象', '不会补发 DELETED'], ['sendInitialEvents', '用 BOOKMARK 标出初始事件结束']], ['sendInitialEvents'])),
    step("从旧版本 14929 开始 watch:再写 1200 次并手动压缩 etcd 到 16147 之后,仍能收到 1199 个事件(从 watch 缓存补发,压缩没有让它失效);继续写,累计 6200 次(80 秒)仍能收到 6199 个,累计 7200 次(92 秒)只收到 1 个 ERROR 事件:code 410、reason Expired、message “too old resource version: 14929 (15739)”;重新 list 得到 resourceVersion=22275,再从它 watch 正常。", f=fl(F3, cur=[2], mark=[1], done=[3]), t=tl(S(3), mark=lidx(S(3), '压缩没有让它失效', '出错时服务端发来的事件'), done=lidx(S(3), '恢复办法')), kv=KV([['etcd 压缩', '不影响还在 watch 缓存里的事件'], ['缓存装不下', '410 Expired,括号里是缓存里最老的版本'], ['恢复', '重新 list,再从新的 rv watch']], ['缓存装不下'])),
    step("带选择器的 watch(labelSelector=app=x):对象 sel 标签是 app=x 时 ADDED;改成 app=y 对这个 watch 来说“消失了”,收到 DELETED;改回 app=x 又收到 ADDED;改 data 是 MODIFIED;真正删除是 DELETED。", f=fl(F4, cur=[1], mark=[2], done=[0]), t=tl(S(4), mark=lidx(S(4), 'DELETED   sel rv=22285', 'ADDED     sel rv=22286'), done=lidx(S(4), 'MODIFIED')), kv=KV([['移出选择器', '对 watch 来说是 DELETED'], ['移入选择器', '对 watch 来说是 ADDED'], ['含义', '客户端的缓存要按事件而不是按“真的删除”处理']], ['移出选择器'])),
]
A = mkartk('k7', 7, 'Kubernetes,watch,resourceVersion,410 Gone,事件语义,真实验证,动画演示',
    '在 kind 集群里实测 watch 语义:从某个 resourceVersion 开始只会收到它之后的事件,当前版本 0 个;不带版本或 rv=0 先把现有对象当 ADDED 发一遍,被删除的对象不会补发;sendInitialEvents 用带 initial-events-end 注解的 BOOKMARK 标出初始事件结束;etcd 压缩并不会让旧版本失效,写到约 80 多秒、6000 多次之后 watch 缓存装不下才返回 410 too old resource version;带标签选择器时标签变化表现为 ADDED 与 DELETED。',
    'watch 是所有控制器的地基。从一个 resourceVersion 开始 watch 到底能收到什么?版本太旧时发生什么?这篇用真实的事件流把每种情形都跑出来,包括手动压缩 etcd 也没能让旧版本失效这个出乎意料的结果。',
    [('4 个 / 0 个', '从 b 创建时的版本 watch 与从当前版本 watch 各自收到的事件数'), ('410 Expired', 'too old resource version: 14929 (15739),写入累计 7200 次、过去 92 秒后出现'), ('DELETED', '对象标签改成 app=y 后,watch labelSelector=app=x 收到的事件')],
    [('从某个版本开始', '<p>依次创建 a、b,修改 a,删除 b,创建 c,修改 c。从 b 创建时的版本(14898)开始 watch,恰好收到它之后的 4 个事件:<code>MODIFIED a</code>、<code>DELETED b</code>、<code>ADDED c</code>、<code>MODIFIED c</code>,每个事件里的 <code>resourceVersion</code> 就是那次修改的版本。从当前版本开始 watch 一个事件也没有,直到有新的变化才会收到(创建再删除 <code>live</code> 得到 ADDED、DELETED)。</p>'),
     ('不指定版本', '<p>不带 <code>resourceVersion</code> 或写 <code>0</code>:服务端先把现有对象当作 <code>ADDED</code> 发一遍,再接实时事件。已经删掉的 b 不会补发 DELETED——所以“从头 watch”拿不到历史,只能拿到当前状态。较新的 <code>sendInitialEvents=true</code> 把 list 和 watch 合成一个流,初始对象发完后有一个注解为 <code>k8s.io/initial-events-end: true</code> 的 <code>BOOKMARK</code>,告诉客户端“初始状态完整了”。</p>'),
     ('版本太旧', '<p>这一节的结果和直觉不一样:写 1200 次后手动把 etcd 压缩到当前 revision,从旧版本 watch 仍然收到全部 1199 个事件——旧事件是从 apiserver 自己的 watch 缓存里补发的,压缩没有让它失效。继续写,累计 6200 次(过去 80 秒)还行,累计 7200 次(92 秒)才得到一个 <code>ERROR</code> 事件:<code>code: 410</code>、<code>reason: Expired</code>、<code>too old resource version: 14929 (15739)</code>,括号里是缓存里最老的版本。恢复办法是重新 list 拿到新的 <code>resourceVersion</code>,再从它 watch。</p>'),
     ('选择器下的事件', '<p>带 <code>labelSelector</code> 的 watch 看到的是“满足条件的对象集合”的变化:对象标签从 <code>app=x</code> 改成 <code>app=y</code>,对这个 watch 来说对象消失了,收到 <code>DELETED</code>;改回来又是 <code>ADDED</code>;条件内的修改才是 <code>MODIFIED</code>。客户端缓存收到 DELETED 并不代表对象真的被删除了。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);用 kubectl get --raw "<path>?watch=true&timeoutSeconds=N" 读事件流,watch 期间由脚本制造变化;1000~1200 次写入用 8 个线程并发的 kubectl patch 完成(约 85 次/秒);etcd 压缩用 etcd 静态 Pod 里的 etcdctl compact;版本号每次运行不同;每种情形各一次',
     '没有验证:410 出现的阈值由什么决定(缓存容量还是时间窗口,本机只观察到约 80~92 秒、6200~7200 次写入之间失效,没有区分两者);watch 缓存的大小调整参数;BOOKMARK 的周期;etcd 压缩后没有 watch 缓存的资源(缓存关闭时)的行为;HTTP/2 流的断开重连行为;很多 watcher 同时存在时的开销'],
    'watch 事件', PANELS)
