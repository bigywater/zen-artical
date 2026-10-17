from lib import *
S = SS('c58')
steps = [
    step("db 要 3 秒后才就绪(先 sleep 3 再创建 /tmp/ready),web 只写 depends_on: [db]。docker compose up -d 退出码 0、只用了 0.4 秒;db 与 web 的启动时间差只有 0.10 秒——depends_on 只保证 db 的容器先启动,不等它真正就绪。", t=tl(S(1)), done=lidx(S(1), 'docker compose up -d', 'db 与 web'), b=bars([['db 就绪需要 (秒)', 3, '3'], ['web 比 db 晚启动 (秒)', 0.1, '0.10']], 3, done=[1], mark=[0]), kv=KV([['depends_on: [db]', '只保证 db 容器先启动'], ['web 比 db 晚', '0.10 秒'], ['db 就绪', '3 秒后']], ['depends_on: [db]'])),
    step("给 db 加健康检查(test -f /tmp/ready,interval 1s),web 写 depends_on: db: condition: service_healthy:docker compose up -d 用了 3.9 秒才返回(退出码 0),db 与 web 的启动时间差是 3.61 秒,db 的健康状态是 healthy——web 是在 db 通过健康检查之后才启动的。", t=tl(S(2)), done=lidx(S(2), '3.61 秒'), b=bars([['web 比 db 晚启动 (秒)', 3.61, '3.61'], ['不等就绪时 (秒)', 0.1, '0.10']], 3.61, done=[0], mark=[1]), kv=KV([['service_healthy', 'web 等 db 健康后才启动'], ['时间差', '3.61 秒'], ['up -d 用时', '3.9 秒']], ['service_healthy'])),
    step("condition: service_completed_successfully 等一次性任务退出:job 睡 2 秒后 exit 0 → docker compose up -d 退出码 0(2.4 秒),web 容器 Up;job exit 1 → docker compose up -d 退出码 1(2.4 秒),报 service \"job\" didn't complete successfully: exit 1,web 容器的状态是 Created——创建了但没有启动。", t=tl(S(3)), done=lidx(S(3), 'job 退出码 0'), mark=lidx(S(3), 'job 退出码 1'), kv=KV([['job exit 0', 'web 启动,up 退出码 0'], ['job exit 1', 'up 退出码 1,web 停在 Created']], ['job exit 1'])),
    step("依赖会被一起拉起:a ← b ← c,只指定 docker compose up -d c,启动了 a、b、c 三个容器;加 --no-deps 只启动了 c 一个。", t=tl(S(4)), done=lidx(S(4), '只指定启动 c'), mark=lidx(S(4), '--no-deps'), b=bars([['up c:启动的容器数', 3, '3'], ['up --no-deps c:启动的容器数', 1, '1']], 3, done=[0], mark=[1]), kv=KV([['up c', '连带启动 a、b'], ['--no-deps', '只启动 c']], ['--no-deps'])),
]
A = mkartc('c58', 58, 'Docker,Docker Compose,depends_on,healthcheck,service_healthy,启动顺序,真实验证,动画演示',
    '在 Docker Compose v5.5.1 里实测 depends_on:只写服务名时 web 比需要 3 秒才就绪的 db 只晚 0.10 秒启动;condition: service_healthy 让 web 等到健康检查通过(晚 3.61 秒);service_completed_successfully 在任务 exit 1 时让 up 以 1 退出、web 停在 Created;启动 c 会连带启动依赖,--no-deps 则只启动自己。',
    'depends_on 写了就能保证 db 准备好了吗?service_healthy 和 service_completed_successfully 又是怎么回事?这篇用一个故意延迟就绪的 db 和一个会失败的一次性任务,量出三种写法下的真实启动顺序和时间差。',
    [('0.10 秒', '只写 depends_on 时,web 比 3 秒后才就绪的 db 晚启动的时间'), ('3.61 秒', 'service_healthy 下,web 比 db 晚启动的时间'), ('退出码 1', '依赖的一次性任务 exit 1 时,docker compose up -d 的退出码(web 停在 Created)')],
    [('只写 depends_on', '<p>短写法的 <code>depends_on: [db]</code> 只控制启动顺序:db 容器启动后,web 立刻跟着启动(晚 0.10 秒),不管 db 里的程序有没有就绪。应用要自己重试连接,或者用 condition。</p>'),
     ('service_healthy', '<p>需要 db 定义 <code>healthcheck</code>。web 会等到 db 变成 healthy,<code>docker compose up -d</code> 也一直等到那时才返回(3.9 秒)。健康检查的 interval 影响等待的颗粒度。</p>'),
     ('service_completed_successfully', '<p>适合数据库迁移、初始化这类一次性任务。任务成功退出,web 才启动;任务失败,compose 报错并以 1 退出,web 容器被创建但不启动。</p>'),
     ('连带启动', '<p>启动 c 会把它依赖的 a、b 一起启动;<code>--no-deps</code> 跳过依赖。</p>')],
    steps,
    [ENV_C + '。Docker Compose v5.5.1;用 alpine:3.20 与 sh 脚本模拟 db 的延迟就绪;启动时间取自 docker inspect 的 State.StartedAt,时间差取两个容器之差;每种情形运行一次;compose 项目名都以 bwlab 开头,实验后已用 compose down -v 和清理脚本删除',
     '没有验证:restart: true 的依赖更新行为、required: false、跨 profile 的依赖、依赖服务重启时 web 的行为、真实数据库的就绪判断、service_started 的显式写法(与短写法等价,我没有逐项对比)'],
    'depends_on 条件')
