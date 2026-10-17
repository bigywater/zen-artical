from lib import *
S = SS('c69')
steps = [
    step("一轮操作:创建卷和网络、给镜像打 tag、run --rm 一个挂卷并接网络的容器、删 tag、删卷和网络。docker events --since/--until 按时间顺序给出 15 条:volume create → network create → image tag → container create → container attach → volume mount → network connect → container start → network disconnect → volume unmount → container die → container destroy → image untag → volume destroy → network destroy。事件的 Type 有 container、image、volume、network。", t=tl(S(1)), done=lidx(S(1), 'container  start', 'container  die'), mark=lidx(S(1), 'volume     mount', 'network    connect', 'volume     unmount'), kv=KV([['容器', 'create → attach → start → die → destroy'], ['卷', 'create → mount → unmount → destroy'], ['网络', 'create → connect → disconnect → destroy'], ['镜像', 'tag / untag']], ['容器'])),
    step("一条事件(--format '{{json .}}')的字段:Action、Actor、Type、scope、time、timeNano;Actor.Attributes 里有 name、image、自己加的标签 bwlab,以及 Docker Desktop 加的 desktop.docker.io/ports.scheme;time 是秒(1791639558),timeNano 是纳秒。", t=tl(S(2)), done=lidx(S(2), '顶层字段', 'Actor.Attributes'), kv=KV([['顶层字段', 'Action、Actor、Type、scope、time、timeNano'], ['Actor.Attributes', 'name、image、容器的标签']], ['顶层字段'])),
    step("过滤:--filter type=network 只剩 network/create、connect、disconnect、destroy;type=container 加 event=die 只剩 container/die;container=bwlab-c69c2 加 event=start 和 event=die 只剩 container/start 与 container/die。同类的 filter 取或,不同类的取与。", t=tl(S(3)), done=lidx(S(3), '--filter type=network', 'event=die'), kv=KV([['type=', '事件类型'], ['event=', '具体动作,可重复'], ['container=', '按容器过滤']], ['event='])),
    step("能看多久以前的事件:--since 1h 和 --since 24h 都只取到 256 条,最早的是 3~4 分钟前——不管时间窗口多大,只能回看到最近的 256 条(看起来是一个固定大小的缓冲,我没有查文档或源码)。", t=tl(S(4)), done=lidx(S(4), '--since 1h', '--since 24h'), b=bars([['--since 1h 取到', 256, '256'], ['--since 24h 取到', 256, '256']], 256, done=[0, 1]), kv=KV([['--since 1h / 24h', '都是 256 条'], ['最早', '几分钟前']], ['--since 1h / 24h'])),
]
A = mkartc('c69', 69, 'Docker,docker events,事件,filter,监控,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 docker events:一轮对卷、网络、镜像、容器的操作产生 15 条事件(容器 create → attach → start → die → destroy,卷 create → mount → unmount → destroy,网络 create → connect → disconnect → destroy);事件有 Action、Actor、Type、scope、time、timeNano 字段;--filter type= / event= / container= 过滤;--since 24h 也只能回看到最近的 256 条。',
    'docker events 到底有哪些事件、字段长什么样、怎么过滤、能回看多久?这篇用一轮完整的操作把事件按顺序列出来,并测出历史回看的上限。',
    [('15 条事件', '创建卷和网络、打 tag、run 一个容器、清理资源,docker events 记录的事件数'), ('256 条', '--since 1h 和 --since 24h 都只能取到的事件数'), ('create → mount → unmount → destroy', '卷的完整事件序列')],
    [('事件序列', '<p>容器 create、attach、start、die、destroy;卷 create、mount、unmount、destroy;网络 create、connect、disconnect、destroy;镜像 tag、untag。<code>--rm</code> 的容器 die 之后紧跟着 destroy。</p>'),
     ('字段', '<p>JSON 格式下每条事件有 Type、Action、Actor(含 ID 和 Attributes)、scope、time、timeNano。容器的 Actor.Attributes 带 name、image 和镜像/容器上的标签,可以用来按标签过滤。</p>'),
     ('过滤', '<p><code>--filter type=…</code>、<code>event=…</code>、<code>container=…</code> 可以组合。过滤的是 docker events 命令的输出,不影响 docker 记录事件。</p>'),
     ('回看', '<p>--since 无论写 1h 还是 24h,都只拿到 256 条。想长期保留事件,要用 <code>docker events</code> 持续订阅并自己存储。</p>')],
    steps,
    [ENV_C + '。事件由 docker events --since/--until 取出(JSON 格式),用 Python 解析;卷、网络、容器、镜像名都以 bwlab-c69 开头;回看上限用 --since 1h 与 24h 两次查询得到;实验后已删除资源',
     '没有验证:256 条上限的原因和配置、daemon 类事件、插件事件、health_status 与 oom 事件(见 c65、c37)、高事件量下的丢失、docker events 的 --until 与实时流的差别'],
    'docker events')
