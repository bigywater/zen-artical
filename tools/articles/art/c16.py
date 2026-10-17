from lib import *
S = SS('c16')
steps = [
    step("默认配置的 registry:2 不允许删除镜像:对 manifest 发 DELETE 返回 405,正文 {\"errors\":[{\"code\":\"UNSUPPORTED\",\"message\":\"The operation is unsupported.\"}]}。要删除,得在启动时设置 REGISTRY_STORAGE_DELETE_ENABLED=true。", t=tl(S(1)), done=lidx(S(1), 'DELETE'), kv=KV([['默认', 'DELETE manifest → 405 UNSUPPORTED'], ['开启删除', 'REGISTRY_STORAGE_DELETE_ENABLED=true']], ['默认'])),
    step("开启删除后推两个镜像,共用 alpine 基础层,各有一个 2 MiB 随机文件。推 app:1 后,registry 磁盘上有 4 个 blob 文件、共 6216 KB;再推 app:2,新增 3 个文件、2136 KB(输出里有 1 行 Layer already exists——共用的基础层没有重传),总共 7 个文件、8352 KB。", t=tl(S(2)), done=lidx(S(2), '再推 app:2 后'), mark=lidx(S(2), '推 app:1 后'), b=bars([['推 app:1 后 (KB)', 6216, '6216'], ['再推 app:2 后 (KB)', 8352, '8352']], 8352, done=[0], mark=[1]), kv=KV([['app:1', '4 个文件,6216 KB'], ['再加 app:2', '+3 个文件,+2136 KB'], ['共用层', '没有重传']], ['共用层'])),
    step("删除 app:1 的 manifest:DELETE 返回 202;tags/list 里只剩 [\"2\"];GET manifests/1 → 404。但磁盘上仍是 7 个 blob 文件,8320 KB(删除前 8352 KB,只少了 32 KB)——DELETE 只删了引用,层的内容还在磁盘上。", t=tl(S(3)), done=lidx(S(3), 'DELETE manifests', 'GET manifests/1'), mark=lidx(S(3), '删除后磁盘上'), b=bars([['删除前磁盘 (KB)', 8352, '8352'], ['删除 manifest 后 (KB)', 8320, '8320']], 8352, done=[0], mark=[1]), kv=KV([['DELETE manifest', '202,tag 消失'], ['磁盘', '7 个文件,几乎没变(-32 KB)']], ['磁盘'])),
    step("garbage-collect 才真正回收:--dry-run 报告 4 行 eligible for deletion,磁盘不变(7 个文件、8320 KB);真正执行后也是 4 行,磁盘剩 4 个 blob 文件、6248 KB,回收了 3 个文件、2072 KB。“4 行”和“3 个文件”为什么差一个,我没有查(推测其中有不是 blob 数据文件的条目)。", t=tl(S(4)), done=lidx(S(4), 'GC 之后磁盘'), mark=lidx(S(4), '--dry-run', 'dry-run 之后'), b=bars([['GC 前 (KB)', 8320, '8320'], ['GC 后 (KB)', 6248, '6248']], 8320, done=[1], mark=[0]), kv=KV([['dry-run', '只报告,磁盘不变'], ['执行', '7 → 4 个文件,8320 → 6248 KB']], ['执行'])),
    step("GC 之后留下的镜像不受影响:删掉本地的 app:2 后再 docker pull,退出码 0,拉取成功;拉已经删除的 app:1,退出码 1,报 not found。", t=tl(S(5)), done=lidx(S(5), 'docker pull app:2'), mark=lidx(S(5), '已删除'), kv=KV([['app:2', 'pull 成功'], ['app:1(已删)', 'not found']], ['app:2'])),
    step("把同一个镜像 docker tag 成另一个仓库名 c16/other 再推:输出里有 2 行 Mounted from c16/app(f0deb84d7ced、3f26bc2dec0b),0 行 Layer already exists;磁盘上 blob 文件数仍是 4 个,总大小 6248 → 6336 KB(多了 88 KB,没查是什么)。同一个 registry 里,不同仓库之间的层是共享的,推送时直接 mount,不重新上传。", t=tl(S(6)), done=lidx(S(6), '"Mounted from"'), mark=lidx(S(6), '之后磁盘'), kv=KV([['推到新仓库名', '2 层 Mounted from c16/app'], ['磁盘上 blob 文件', '4 → 4 个'], ['总大小', '6248 → 6336 KB']], ['推到新仓库名'])),
]
A = mkartc('c16', 16, 'Docker,registry,本地仓库,垃圾回收,garbage-collect,真实验证,动画演示',
    '在本机 registry:2 上实测自建仓库的推送与回收:默认 DELETE manifest 返回 405,开启 REGISTRY_STORAGE_DELETE_ENABLED 后返回 202 但磁盘几乎没变(8352 → 8320 KB),要 garbage-collect 才回收(8320 → 6248 KB,7 → 4 个 blob 文件);不同仓库之间推送共享层时直接 Mounted from。',
    '在自己的机器上起一个镜像仓库很容易,但删镜像为什么不释放磁盘?这篇用 registry:2 实测:共享层只存一份、DELETE 之后磁盘不变、garbage-collect 才真正回收,以及跨仓库推送时层是怎么被复用的。',
    [('405 → 202', '默认配置下 DELETE manifest 返回 405;开启删除后返回 202'), ('8320 → 6248 KB', 'garbage-collect 前后 registry 磁盘上的 blob 数据大小(7 → 4 个文件)'), ('2 行 Mounted from', '同一个镜像推到另一个仓库名时,层直接从原仓库挂载')],
    [('默认不能删', '<p>registry:2 默认拒绝删除:DELETE manifest 返回 405 UNSUPPORTED。需要在启动时设置环境变量 <code>REGISTRY_STORAGE_DELETE_ENABLED=true</code>。</p>'),
     ('共享层只存一份', '<p>两个镜像共用 alpine 基础层,各自有一个 2 MiB 的随机文件。推完两个镜像,磁盘上只有 7 个 blob 文件(8352 KB),第二次推送输出里有一行 <code>Layer already exists</code>。</p>'),
     ('DELETE 不等于释放磁盘', '<p>删除 app:1 的 manifest 后,tag 消失、GET 返回 404,但磁盘占用从 8352 KB 只降到 8320 KB。层的数据文件都还在。</p>'),
     ('garbage-collect', '<p>在 registry 容器里执行 <code>registry garbage-collect /etc/docker/registry/config.yml</code> 才会回收没人引用的 blob:磁盘从 8320 KB 降到 6248 KB,7 个文件变 4 个。先用 <code>--dry-run</code> 看一遍不会改动。回收时有新的写入会怎样,我没有测。</p>'),
     ('不影响其它镜像', '<p>回收之后,没被删除的 app:2 可以重新拉取;已删除的 app:1 报 not found。</p>'),
     ('跨仓库挂载', '<p>同一个 registry 里,把 c16/app:2 推成 c16/other:2,docker 输出 <code>Mounted from c16/app</code>,没有重新上传层内容。磁盘上的 blob 文件数不变,总大小多了 88 KB(我没有查那是什么,推测是新仓库的元数据)。</p>')],
    steps,
    [ENV_C + '。registry:2 经 dpull.py 加载,运行在本机 127.0.0.1 的 9700、9701 端口上(一个默认配置、一个开启删除);磁盘用量用容器内 du -sk /var/lib/registry 和 find 统计 blob 数据文件;2 MiB 文件是 os.urandom 随机数据(层几乎不可压缩);实验后已删除容器和镜像',
     '没有验证:Docker Hub 或 Harbor 等其它实现的删除与回收、使用外部存储(S3、本地卷)时的行为、回收与并发推送的冲突、认证与 HTTPS、镜像带 provenance 证明时 DELETE 的影响、registry 的缓存(pull-through)模式'],
    '本地 registry')
