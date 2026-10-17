from lib import *
S = SS('c63')
steps = [
    step("docker compose up -d --scale worker=3:得到 worker-1、worker-2、worker-3 三个容器。再 --scale worker=1:只剩 worker-1,而且是原来那个容器(容器 ID 没变),编号大的被删掉。再 --scale worker=3:worker-1 仍是原来的,worker-2 是新建的(容器 ID 变了)。", t=tl(S(1)), done=lidx(S(1), '--scale worker=3:', 'worker=1:剩下'), mark=lidx(S(1), '再 --scale worker=3'), b=bars([['--scale worker=3', 3, '3'], ['--scale worker=1', 1, '1'], ['再 --scale worker=3', 3, '3']], 3, done=[0, 1, 2]), kv=KV([['缩容', '保留编号小的,删编号大的'], ['再扩容', '补出来的是新容器']], ['缩容'])),
    step("client 容器 nslookup worker(服务名),得到 172.19.0.3、172.19.0.4、172.19.0.5 三个地址,恰好是 3 个副本各自的真实 IP——服务名解析到所有副本。", t=tl(S(2)), done=lidx(S(2), 'client 解析 worker'), kv=KV([['服务名 worker', '解析出 3 个 IP'], ['与真实 IP', '完全一致']], ['服务名 worker'])),
    step("deploy.replicas: 2 写在 compose 文件里,docker compose up -d 起了 worker-1、worker-2;命令行再加 --scale worker=4 覆盖它,变成 4 个副本。", t=tl(S(3)), done=lidx(S(3), 'deploy.replicas: 2', '--scale worker=4'), kv=KV([['deploy.replicas: 2', '2 个副本'], ['--scale worker=4', '命令行覆盖,4 个副本']], ['--scale worker=4'])),
    step("带端口映射时扩容:固定宿主机端口 \"9941:80\" --scale worker=2 → 退出码 1,报 failed to set up container networking … 端口冲突,运行中的副本只有 worker-2;端口范围 \"9942-9944:80\" → 退出码 0,两个副本都在运行;只写容器端口 \"80\" → 退出码 0,两个副本都在运行(宿主机端口由 docker 随机分配)。", t=tl(S(4)), done=lidx(S(4), '端口范围', '只写容器端口'), mark=lidx(S(4), '固定宿主机端口'), kv=KV([['"9941:80"', '2 个副本抢同一个宿主机端口,失败'], ['"9942-9944:80"', '从范围里分配,成功'], ['"80"', '随机宿主机端口,成功']], ['"9941:80"'])),
    step("container_name 与扩容:worker 设了 container_name: bwlab-c63-fixed,--scale worker=2 → 退出码 1,警告 WARNING: The \"worker\" service is using the custom container name \"bwlab-c63-fixed\". Docker requires each container to have a unique name——名字固定了就不能有第二个副本。", t=tl(S(5)), done=lidx(S(5), 'container_name'), kv=KV([['container_name', '固定名字只能有 1 个容器'], ['--scale 2', '退出码 1']], ['container_name'])),
]
A = mkartc('c63', 63, 'Docker,Docker Compose,scale,replicas,扩容,端口冲突,真实验证,动画演示',
    '在 Docker Compose v5.5.1 里实测扩缩容:--scale worker=3 得到 worker-1..3,缩到 1 保留编号小的原容器,再扩容补出新容器;服务名解析出所有副本的 IP;deploy.replicas 被 --scale 覆盖;固定宿主机端口映射在扩容时冲突(退出码 1),端口范围或只写容器端口则成功;设了 container_name 就不能扩容。',
    'docker compose --scale 到底做了什么?缩容删哪个、服务名怎么解析、带端口映射的服务能不能扩、container_name 会不会挡路?这篇逐项实测。',
    [('编号小的保留', '--scale 缩容时保留 worker-1,删掉编号大的'), ('3 个 IP', 'client 解析服务名 worker 得到的地址数,与 3 个副本一一对应'), ('退出码 1', '固定宿主机端口 "9941:80" 扩成 2 个副本时 docker compose up 的退出码')],
    [('缩容与扩容', '<p>缩容保留编号小的容器(原容器,ID 不变),删除编号大的;再扩容出来的是新容器。</p>'),
     ('名字解析', '<p>服务名解析出所有副本的 IP(顺序可能变,见后面的 DNS 轮询一篇),这是 compose 里最简单的服务发现。</p>'),
     ('replicas', '<p><code>deploy.replicas</code> 在 <code>docker compose up</code> 里生效;命令行的 <code>--scale</code> 优先。</p>'),
     ('端口映射', '<p>多个副本不能抢同一个宿主机端口,要用端口范围或让 docker 随机分配。固定端口那次实验里最终只有 worker-2 在运行,具体是 worker-1 没起来还是被清理,我没有细查。</p>'),
     ('container_name', '<p>设了 <code>container_name</code> 的服务只能有一个容器,<code>--scale</code> 到 2 会被拒绝。</p>')],
    steps,
    [ENV_C + '。Docker Compose v5.5.1;服务是 alpine:3.20 sleep 300;容器 ID 前 6 位用来判断是否是同一个容器;DNS 用 busybox nslookup(排除了 127.0.0.11:53 这行服务器地址);端口 9941–9944 是我选的空闲端口;项目 bwlab-c63,实验后已 down -v',
     '没有验证:缩容时被删容器的选择规则的完整描述(只看到保留编号小的)、滚动更新、副本的负载均衡(DNS 轮询见后面一篇)、资源限制 deploy.resources、docker compose up --scale 与 depends_on 的组合'],
    'compose 扩缩容')
