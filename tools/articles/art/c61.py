from lib import *
S = SS('c61')
steps = [
    step("设置:compose.yaml 的 environment 有 T_Y: environment-${T_I}、T_Z: environment、T_PASS(不写值);env_file service.env 有 T_X=from-envfile、T_Y=from-envfile、T_I=envfile-I;.env 有 T_I=dotenv 和 T_ONLY_DOTENV=yes。docker compose run 进容器看 T_ 开头的变量:T_I=envfile-I、T_X=from-envfile、T_Y=environment-dotenv、T_Z=environment。T_PASS 因为 shell 里没设,没有出现。", t=tl(S(1)), done=lidx(S(1), '默认:'), mark=lidx(S(1), 'compose.yaml 里的 environment 有'), kv=KV([['T_X', 'from-envfile(只在 env_file)'], ['T_Y', 'environment-dotenv(environment 胜过 env_file,且 ${T_I} 用的是 .env 的 dotenv)'], ['T_I', 'envfile-I(env_file 的)'], ['T_PASS', '不写值且 shell 没设 → 不出现']], ['T_Y'])),
    step("优先级:同时出现在 env_file 和 environment 的 T_Y,容器里取 environment 的;.env 里独有的 T_ONLY_DOTENV 不在容器里——.env 默认只用于 compose.yaml 里的 ${…} 插值,不进容器。shell 里设 T_I=shell,插值变成 T_Y=environment-shell(shell 高于 .env),但容器里的 T_I 仍是 env_file 的 envfile-I;T_PASS 不写值,shell 里设 T_PASS=from-shell 后容器里就有了;docker compose run -e T_Z=cli -e T_X=cli,T_Z 和 T_X 都被命令行覆盖。", t=tl(S(2)), done=lidx(S(2), 'T_PASS 不写值', 'docker compose run -e'), mark=lidx(S(2), 'T_ONLY_DOTENV', 'shell 里设 T_I=shell'), kv=KV([['environment 对 env_file', 'environment 优先'], ['shell 对 .env(插值)', 'shell 优先'], ['run -e', '覆盖前面所有']], ['run -e'])),
    step("--env-file other.env(T_I=other-env-file)替换了默认的 .env:插值得到 T_Y=environment-other-env-file,容器里的 T_I 仍是 envfile-I。docker compose config 展开后的 environment 是 {T_I: envfile-I, T_PASS: null, T_X: from-envfile, T_Y: environment-dotenv, T_Z: environment};用 --env-file other.env 后 T_Y 变成 environment-other-env-file。", t=tl(S(3)), done=lidx(S(3), '--env-file other.env 之后'), mark=lidx(S(3), 'docker compose config 展开后'), kv=KV([['--env-file', '替换默认的 .env 用于插值'], ['config 的 T_PASS', 'null(需要从 shell 带入)']], ['--env-file'])),
    step("插值语法:${T_MISSING:-default-value}-${T_EMPTY-unset},两个变量都没设时展开成 echo default-value-unset;T_EMPTY 设成空串后,${T_EMPTY-unset}(不带冒号)不再用默认值,变成 echo default-value-;${T_REQUIRED:?必须设置 T_REQUIRED} 未设置时 docker compose config 退出码 1,报 required variable T_REQUIRED is missing a value。", t=tl(S(4)), done=lidx(S(4), '未设、T_EMPTY 未设', 'T_EMPTY 设成空串'), mark=lidx(S(4), 'T_REQUIRED'), kv=KV([[':-default', '未设置或为空时用默认值'], ['-default(无冒号)', '只在未设置时用默认值'], [':?msg', '缺失时报错退出 1']], [':?msg'])),
]
A = mkartc('c61', 61, 'Docker,Docker Compose,环境变量,env_file,.env,插值,真实验证,动画演示',
    '在 Docker Compose v5.5.1 里实测环境变量的来源与优先级:environment 胜过 env_file;.env 只用于 compose.yaml 里的 ${…} 插值,不进容器;shell 高于 .env;不写值的 environment 项从 shell 透传;docker compose run -e 覆盖一切;--env-file 替换 .env;${VAR:-x}、${VAR-x}、${VAR:?msg} 的区别。',
    'Compose 里的环境变量有 .env、env_file、environment、shell、命令行好几个来源,谁覆盖谁?.env 里的变量会进容器吗?这篇设计了一组故意重名的变量,逐项量出结果。',
    [('environment 胜过 env_file', '同名变量 T_Y 在两处都有时,容器里取 environment 的'), ('.env 不进容器', '.env 里独有的变量不在容器里,只用于插值'), ('退出码 1', '${VAR:?msg} 对未设置的变量,docker compose config 的退出码')],
    [('三层关系', '<p>容器里的变量:<code>environment</code> 覆盖 <code>env_file</code>;<code>docker compose run -e</code> 又覆盖前两者。</p>'),
     ('.env 的角色', '<p>.env 提供的是 compose.yaml 里 <code>${…}</code> 插值用的变量,不会自动放进容器;而 env_file 的内容不参与插值(T_I 在 env_file 里是 envfile-I,插值仍用 .env 的 dotenv)。插值时 shell 的变量高于 .env,<code>--env-file</code> 可以换掉 .env。</p>'),
     ('透传', '<p>environment 里只写变量名不写值,从运行 compose 的 shell 里取;shell 没设就不出现。</p>'),
     ('默认值语法', '<p><code>:-</code> 对未设置或空串都用默认值;不带冒号的 <code>-</code> 只对未设置用默认值;<code>:?</code> 缺失时报错。env_file 与 image 的 ENV 的优先级关系我没有测。</p>')],
    steps,
    [ENV_C + '。Docker Compose v5.5.1;变量都以 T_ 开头,运行时清除了 shell 里已有的 T_* 变量避免干扰;容器内的值用 docker compose run --rm -T web env 读取,展开结果用 docker compose config --format json;实验后已删除临时文件和容器',
     '没有验证:image 的 ENV 与 env_file 的优先级、env_file 的 required: false 和 format 选项、多个 --env-file、COMPOSE_ENV_FILES、docker compose up(而不是 run)的环境差异、secrets 与 configs'],
    '环境变量的优先级')
