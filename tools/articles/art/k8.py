from lib import *
S = SS('k8')
F1 = [['quiet', '从不变化 rv=41857'], ['noise', '7000 次写入'], ['watcher(无 bookmark)', '0 个事件'], ['watcher(有 bookmark)', '第 59.7 秒 BOOKMARK']]
F2 = [['41857', 'quiet 最后一次变化'], ['85 秒', 'watch 缓存最老 42466'], ['从 41857 重连', 'ERROR 410'], ['从 46796 重连', '成功']]
PANELS = [('f', 'flow', 'bookmark 与重连'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("watch 一个从不变化的对象 quiet,同时对另一个对象 noise 写 7000 次(87 秒)。不带 allowWatchBookmarks 的 watcher 收到 0 个事件,它所知道的最后版本一直是 41857;带 allowWatchBookmarks=true 的 watcher 在第 59.7 秒收到一个 BOOKMARK,resourceVersion=46796——事件里只有 kind 和 metadata.resourceVersion,没有别的字段。", f=fl(F1, cur=[3], mark=[2], done=[0, 1]), t=tl(S(1), mark=lidx(S(1), '收到 0 个事件', 'BOOKMARK resourceVersion=46796'), done=lidx(S(1), '一个 BOOKMARK 事件的原文')), kv=KV([['无 bookmark', '安静对象的 rv 永远停在 41857'], ['有 bookmark', '服务端定期告诉你“我现在到哪了”'], ['BOOKMARK 事件', '只有 resourceVersion,没有对象内容']], ['有 bookmark'])),
    step("写到 7000 次(85 秒)时,从 quiet 最后一次变化的版本 rv=41857 重连:ERROR 410,too old resource version: 41857 (42466),只能重新 list(得到 resourceVersion=48998);同一时刻,从最近收到的 BOOKMARK(rv=46796,27 秒前收到)重连:成功,没有 410。", f=fl(F2, cur=[2], mark=[3], done=[0, 1]), t=tl(S(2), mark=lidx(S(2), 'ERROR 410'), done=lidx(S(2), '成功,没有 410', '重新 list')), kv=KV([['从旧版本重连', '410,代价是整个 list 重来'], ['从 bookmark 重连', '版本够新,不需要 list'], ['意义', '省掉全量 list 对 apiserver 的冲击']], ['从 bookmark 重连'])),
]
A = mkartk('k8', 8, 'Kubernetes,watch,bookmark,allowWatchBookmarks,410 Gone,真实验证,动画演示',
    '在 kind 集群里实测 watch bookmark:对从不变化的对象 quiet 开两个 watcher,同时在别的对象上写 7000 次;不带 allowWatchBookmarks 的收到 0 个事件、记住的版本停在 41857,带的在第 59.7 秒收到一个只含 resourceVersion 的 BOOKMARK;85 秒时从 quiet 最后一次变化的版本重连得到 410 too old resource version,而从 27 秒前收到的 BOOKMARK 版本重连成功。',
    '一个关心的对象很少变化,集群却一直在写——客户端断线重连时拿着一个又旧又没用的 resourceVersion,就会收到 410,只能把整个集合重新 list 一遍。bookmark 就是服务端定期告诉客户端“我现在到哪了”,这篇做一个能稳定复现 410 的对比实验。',
    [('59.7 秒', '安静的对象上,带 allowWatchBookmarks 的 watcher 收到第一个 BOOKMARK 的时间'), ('0 个事件', '没有 bookmark 的 watcher 在 87 秒、7000 次别处写入期间收到的事件数'), ('410 vs 成功', '85 秒时从旧版本重连被拒绝,从 27 秒前的 BOOKMARK 版本重连成功')],
    [('安静的对象与 bookmark', '<p>实验里的 <code>quiet</code> 从不被修改,集群却在持续写别的对象。不带 <code>allowWatchBookmarks</code> 的 watcher 一个事件都收不到,它能记住的最后版本一直是创建时的 41857——集群的版本早就走远了。带 <code>allowWatchBookmarks=true</code> 的 watcher 在第 59.7 秒收到一个 <code>BOOKMARK</code> 事件:里面只有 <code>kind</code> 和 <code>metadata.resourceVersion</code>(46796),没有对象内容。它的含义是“到 46796 为止你没有漏掉任何事件”。</p>'),
     ('断线重连', '<p>写到第 7000 次(85 秒)时模拟断线重连。从 <code>quiet</code> 最后一次变化的版本 41857 重连得到 <code>ERROR 410: too old resource version: 41857 (42466)</code>(括号里是 apiserver 缓存里最老的版本),客户端只能重新 list 整个集合再 watch;从 27 秒前收到的 BOOKMARK 版本 46796 重连则直接成功。对只关心少数对象、又运行在写入频繁的集群里的客户端,bookmark 能避免反复全量 list。client-go 的 reflector 默认就会带上 <code>allowWatchBookmarks=true</code>。</p><p>要注意旧版本多久会失效不是固定值:同一个脚本的另一次运行里,写了 10000 次、105 秒之后从旧版本重连仍然成功(缓存窗口随写入速率变化),所以不要依赖“某个时间点一定 410”。这里的对比是用循环等到它第一次出现 410 为止。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0);两个 watcher 都是 kubectl get --raw "…configmaps?fieldSelector=metadata.name=quiet&resourceVersion=<创建时的版本>&watch=true",一个加 allowWatchBookmarks=true;noise 上的写入用 8 个线程并发的 kubectl patch(约 85 次/秒),每写 1000 次就用同样的 URL 试一次从 quiet 的旧版本重连,第一次出现 410 时再试从最近一个 BOOKMARK 的版本;版本号每次运行不同;每种情形各一次',
     '没有验证:BOOKMARK 的周期(只观察到约 60 秒一次,以及 watch 关闭前的那一个);同一个脚本另一次运行的结果(写 10000 次也没过期)说明窗口不固定;allowWatchBookmarks 对 list+watch 的 reflector 的完整流程;客户端对 BOOKMARK 事件的处理细节;watch 缓存关闭时的 bookmark 行为'],
    'bookmark 与重连', PANELS)
