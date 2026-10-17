from lib import *
S = SS('c75')
steps = [
    step("整个 Docker 里开始时有容器 8、镜像 7、卷 19、网络 4(别的项目的),所以下面每条 prune 都带 --filter label=bwlab=1,只清理本实验创建的、带这个标签的对象。docker container prune 只删已停止的:exited 和 created 的容器各被删掉一个(输出 Deleted Containers 列出两个 ID,Total reclaimed space 8.192kB);运行中的 bwlab-c75-running 还在。", t=tl(S(1)), done=lidx(S(1), '剩下的 bwlab 容器'), mark=lidx(S(1), 'docker container prune -f'), kv=KV([['已停止(exited)和只创建(created)', '被 prune 删除'], ['运行中', '保留']], ['已停止(exited)和只创建(created)'])),
    step("镜像:连续构建同一个 tag 两次再 docker tag 出 :old——悬空镜像数是 0(这个镜像存储下重新构建同名 tag 不留悬空镜像,见 c13)。docker image prune -f(不带 -a)Total reclaimed space 0B,bwlab-c75-img 还在;docker image prune -a -f 才把没有容器使用的 bwlab-c75-img:latest 和 :old 都 untagged 并删除(reclaimed 9.723kB),之后镜像没了。", t=tl(S(2)), done=lidx(S(2), 'image prune -a -f'), mark=lidx(S(2), 'docker image prune -f', '悬空镜像'), kv=KV([['image prune(不带 -a)', '只删悬空镜像,这里没有,0B'], ['image prune -a', '删除所有没有容器使用的镜像']], ['image prune -a'])),
    step("卷:docker volume prune -f(带 label 过滤)reclaimed 0B,命名卷 bwlab-c75-named 还在——默认只清理匿名卷;加 -a 才把没有容器引用的命名卷也删掉(输出 Deleted Volumes: bwlab-c75-named),之后命名卷没了。", t=tl(S(3)), done=lidx(S(3), 'prune -a -f'), mark=lidx(S(3), 'docker volume prune -f'), kv=KV([['volume prune', '只清理匿名卷,命名卷保留'], ['volume prune -a', '连没人引用的命名卷也删']], ['volume prune -a'])),
    step("网络:docker network prune -f 删除了没有容器连接的 bwlab-c75-net(输出 Deleted Networks)。", t=tl(S(4)), done=lidx(S(4), 'Deleted Networks') if False else lidx(S(4), 'docker network prune'), kv=KV([['network prune', '删除没有容器连接的自定义网络']], ['network prune'])),
    step("别人的东西没被动到:整个 Docker 里的容器 8 → 8、镜像 7 → 7、卷 19 → 19、网络 4 → 4,本实验对象全部清理(剩 0 个)。过滤条件 label=bwlab=1 起到了作用——不带它的 prune 会清理 Docker Desktop 里所有未使用的东西(我没有执行)。", t=tl(S(5)), done=lidx(S(5), '整个 Docker 里'), mark=lidx(S(5), '本实验的对象还剩'), b=bars([['容器 前', 8, '8'], ['容器 后', 8, '8'], ['卷 前', 19, '19'], ['卷 后', 19, '19']], 19, done=[0, 1, 2, 3]), kv=KV([['--filter label=bwlab=1', '只动本实验的对象'], ['别的对象', '数量不变']], ['--filter label=bwlab=1'])),
]
A = mkartc('c75', 75, 'Docker,prune,docker system prune,清理磁盘,label过滤,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测各种 prune,全部带 --filter label=bwlab=1 只清理自己创建的对象:container prune 只删 exited 和 created 的容器;image prune 不带 -a 只删悬空镜像(这里是 0B),-a 才删没有容器使用的镜像;volume prune 只清匿名卷,-a 才删命名卷;network prune 删没有容器的自定义网络;别的对象前后数量不变。',
    'docker system prune 到底会删什么?container / image / volume / network 各自的 prune 有什么规则,哪些要加 -a?怎么确保不误删别人的东西?这篇在一个有很多其它数据的 Docker 里,全程用标签过滤,逐个验证。',
    [('带 label 过滤', '全部 prune 都加 --filter label=bwlab=1,别的对象数量前后不变'), ('卷默认只清匿名卷', 'docker volume prune 不删没人引用的命名卷,加 -a 才删'), ('悬空镜像 0 个', '这个镜像存储下重新构建同名 tag 不会留下悬空镜像,image prune 不带 -a 没东西可删')],
    [('先限定范围', '<p>这台 Docker 里有别的项目的容器、卷、镜像,所以我给自己创建的每个对象打了标签 <code>bwlab=1</code>,每次 prune 都带 <code>--filter label=bwlab=1</code>。<strong>不带过滤的 prune 会清理所有符合条件的对象,在共用的机器上先想清楚再运行</strong>。</p>'),
     ('容器与镜像', '<p>container prune 删所有已停止的容器(exited、created),不管运行中的;image prune 默认只删悬空镜像,加 <code>-a</code> 才删所有没有容器使用的镜像。</p>'),
     ('卷', '<p>volume prune 默认只清匿名卷,命名卷即使没有容器引用也保留;加 <code>-a</code> 才删。数据在卷里,所以这是个安全的默认。</p>'),
     ('网络', '<p>network prune 删除没有任何容器连接的自定义网络。</p>'),
     ('验证', '<p>前后对比整个 Docker 的对象数量(容器 8、镜像 7、卷 19、网络 4)没有变化,说明过滤起了作用。</p>')],
    steps,
    [ENV_C + '。所有 prune 都带 --filter label=bwlab=1,只作用于本实验创建的对象;没有运行 docker system prune 和 docker builder prune(它们会影响共用的数据和构建缓存);前后对象数量用 docker ps / images / volume ls / network ls 统计;实验后已全部清理',
     '没有验证:docker system prune 的行为(不运行)、docker builder prune 的规则(until、keep-storage)、prune 与正在使用的镜像层的关系、--filter until=的效果、prune 之后磁盘空间的实际释放(Docker Desktop 虚拟机磁盘不会自动缩小)'],
    'docker prune')
