from lib import *
S = SS('c59')
steps = [
    step("三个服务:app(无 profile)、debug(profiles: [debug])、tools(profiles: [tools, debug])。docker compose config --services 只列出 app;加 --profile debug 才列出 app、debug、tools。docker compose up -d 只启动了 app;--profile tools up -d 启动 app 和 tools;--profile debug up -d 启动全部三个(tools 同时属于 debug);环境变量 COMPOSE_PROFILES=tools 的效果与 --profile tools 一样(app、tools)。", t=tl(S(1)), done=lidx(S(1), 'docker compose up -d 之后', '--profile tools up -d'), mark=lidx(S(1), '--profile debug up -d', 'COMPOSE_PROFILES=tools'), b=bars([['up -d', 1, '1'], ['--profile tools', 2, '2'], ['--profile debug', 3, '3']], 3, done=[0], mark=[1, 2]), kv=KV([['没有 profile 的服务', '总是启动'], ['有 profile 的服务', '默认不启动,--profile 或 COMPOSE_PROFILES 才启动'], ['多个 profile', '任意一个被激活就启动']], ['有 profile 的服务'])),
    step("直接点名一个带 profile 的服务不需要 --profile:docker compose up -d debug,退出码 0,只启动了 debug(不连带 app,因为 debug 不依赖它);docker compose run --rm tools echo hello-from-tools 也直接成功,输出 hello-from-tools,run 之后没有留下容器。", t=tl(S(2)), done=lidx(S(2), 'up -d debug', 'hello-from-tools'), kv=KV([['up -d debug', '点名即激活,只启动 debug'], ['run --rm tools', '直接运行,不需要 --profile']], ['up -d debug'])),
    step("没有 profile 的 app 依赖带 profile 的 debug:docker compose up -d 退出码 1,报 service \"app\" depends on undefined service \"debug\": invalid compose project,什么都没启动;加 --profile debug 才成功,启动 app、debug、tools。", t=tl(S(3)), done=lidx(S(3), '加 --profile debug'), mark=lidx(S(3), 'app depends_on debug'), kv=KV([['依赖了带 profile 的服务', '不激活就报 invalid compose project'], ['加 --profile debug', '成功启动']], ['依赖了带 profile 的服务'])),
    step("--profile \"*\" up -d 启动全部三个服务。不带 profile 的 docker compose down 之后,debug 和 tools 还在运行,只有 app 被停掉;要用 --profile \"*\" down 才全部清理。", t=tl(S(4)), done=lidx(S(4), '--profile "*" down 之后'), mark=lidx(S(4), '不带 profile 的 docker compose down'), kv=KV([['--profile "*"', '启用所有 profile'], ['不带 profile 的 down', '带 profile 的服务不会被停掉'], ['清理', '用 --profile "*" down']], ['不带 profile 的 down'])),
]
A = mkartc('c59', 59, 'Docker,Docker Compose,profiles,COMPOSE_PROFILES,服务分组,真实验证,动画演示',
    '在 Docker Compose v5.5.1 里实测 profiles:没有 profile 的服务总是启动,带 profile 的默认不启动,--profile 或 COMPOSE_PROFILES 才启动;点名一个服务(up debug、run tools)会直接激活它;没有 profile 的服务依赖带 profile 的服务时会报 invalid compose project;不带 profile 的 down 不会停掉带 profile 的服务。',
    '想把调试工具、迁移任务这类服务放进同一个 compose 文件,却不想默认启动?profiles 就是干这个的。这篇逐项实测哪些命令会激活它、依赖带 profile 的服务会怎样,以及一个容易留下残留容器的 down 陷阱。',
    [('3 个服务', '--profile debug 才会一起启动的服务数(默认只有 app 1 个)'), ('invalid compose project', '没有 profile 的服务依赖带 profile 的服务、又没激活它时的报错'), ('down 之后还剩 2 个', '不带 profile 的 docker compose down 停不掉带 profile 的 debug 和 tools')],
    [('激活方式', '<p><code>--profile</code> 参数或环境变量 <code>COMPOSE_PROFILES</code>;一个服务可以属于多个 profile,任意一个被激活就会启动。</p>'),
     ('点名', '<p>直接 <code>up</code> 或 <code>run</code> 某个带 profile 的服务不需要 --profile,点名本身就激活了它。</p>'),
     ('依赖', '<p>没有 profile 的服务不能依赖带 profile 的服务,除非同时激活那个 profile,否则 compose 直接报「依赖了未定义的服务」。</p>'),
     ('清理', '<p>不带 profile 的 <code>docker compose down</code> 只处理当前激活的服务,带 profile 的容器会留下来。清理要加 <code>--profile "*"</code>。</p>')],
    steps,
    [ENV_C + '。Docker Compose v5.5.1;服务都是 alpine:3.20 sleep 120;运行状态取自 docker ps 的容器名;compose 项目名 bwlab-c59,实验后已用 --profile "*" down -v 清理',
     '没有验证:depends_on 的 required: false 对 profile 服务的效果、profiles 与 extends / include 的交互、COMPOSE_PROFILES 写多个值的分隔方式(逗号)、docker compose ps 默认是否列出未激活的容器'],
    'compose profiles')
