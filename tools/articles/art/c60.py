from lib import *
S = SS('c60')
steps = [
    step("base 的 web:image alpine:3.20、command sleep 100、environment MODE=base / KEEP=from-base、ports 9901:80、volumes /srv/a:/data/a 和 /srv/b:/data/b、labels tier=base / owner=team-a。-f 只指定 compose.yaml 时(不自动加 override)就是这些;不带 -f,docker compose 自动读取 compose.yaml 和 compose.override.yaml 合并,合并后(docker compose config):image=alpine:3.19、command=sleep 200、environment 里 EXTRA=only-in-override / KEEP=from-base / MODE=override、ports 是 9901 和 9902、volumes 是 /srv/a:/data/a 和 /srv/c:/data/b、labels 里 tier=override / owner=team-a。", t=tl(S(1)), done=lidx(S(1), '不带 -f'), mark=lidx(S(1), '只有 compose.yaml'), kv=KV([['-f compose.yaml', '不会自动加 override'], ['不带 -f', '自动合并 compose.override.yaml']], ['不带 -f'])),
    step("合并规则:image、command 这类单值,override 覆盖 base;environment 和 labels 是映射,按键合并(MODE 被覆盖、KEEP 保留、EXTRA 新增;tier 被覆盖、owner 保留);ports 是列表,追加(9901 和 9902 都在);volumes 按挂载目标合并——/data/b 被换成 override 的源 /srv/c,/data/a 保留。", t=tl(S(2)), done=lidx(S(2), 'environment(映射)', 'labels(映射)'), mark=lidx(S(2), 'ports(列表)', 'volumes(列表)'), kv=KV([['单值', '后者覆盖'], ['environment、labels(映射)', '按键合并'], ['ports(列表)', '追加'], ['volumes', '按挂载目标合并']], ['volumes'])),
    step("-f 的顺序决定谁覆盖谁:-f compose.yaml -f compose.override.yaml -f extra.yaml 得到 image=alpine:3.18(extra 在最后);-f compose.yaml -f extra.yaml -f compose.override.yaml 得到 image=alpine:3.19(override 在最后)。后面的文件覆盖前面的。", t=tl(S(3)), done=lidx(S(3), 'extra.yaml → image', 'compose.override.yaml → image'), kv=KV([['最后一个 -f', '优先级最高'], ['顺序', 'extra 在最后 → 3.18;override 在最后 → 3.19']], ['最后一个 -f'])),
    step("!reset 清除、!override 整体替换:override 文件里写 ports: !reset []、volumes: !override [/srv/z:/data/z]、labels: !reset null、depends_on: !reset []。合并后 ports=[]、volumes 只有 /srv/z:/data/z(base 的两个都没了)、labels={}、depends_on=[];image 和 command 没写,保持 base 的 alpine:3.20 / sleep 100。", t=tl(S(4)), done=lidx(S(4), 'ports=[]'), kv=KV([['!reset', '清空(ports、labels、depends_on)'], ['!override', '整体替换(volumes 只剩新的)'], ['没写的字段', '保持 base']], ['!override'])),
]
A = mkartc('c60', 60, 'Docker,Docker Compose,override,多文件合并,!reset,!override,真实验证,动画演示',
    '用 docker compose config 实测 Compose 多文件合并:不带 -f 时 compose.override.yaml 自动合并;单值覆盖、environment 和 labels 按键合并、ports 追加、volumes 按挂载目标合并;-f 越靠后优先级越高;!reset 清空、!override 整体替换列表。',
    'compose.override.yaml 是怎么和 compose.yaml 合并的?哪些字段是覆盖,哪些是追加?想把 base 里的 ports 删掉怎么写?这篇不启动容器,直接看 docker compose config 展开后的结果。',
    [('9901 和 9902', 'ports 列表是追加:base 和 override 的端口都在'), ('alpine:3.18 vs 3.19', '-f 的顺序不同,最终 image 不同(最后一个文件优先)'), ('ports=[]', 'override 里写 ports: !reset [] 后合并结果的端口')],
    [('自动合并', '<p>不带 <code>-f</code> 时,<code>docker compose</code> 读取 <code>compose.yaml</code> 并自动叠加 <code>compose.override.yaml</code>;一旦用 <code>-f</code> 显式指定,就不会再自动加 override。</p>'),
     ('合并规则', '<p>单值(image、command)被覆盖;映射(environment、labels)按键合并;ports 列表追加,所以想「只在开发时多开一个端口」可以写在 override 里;volumes 以挂载目标为键,同一个目标会被替换。</p>'),
     ('多个 -f', '<p>后面的覆盖前面的:同样三个文件,顺序不同,最终 image 一个是 alpine:3.18,一个是 alpine:3.19。</p>'),
     ('!reset 与 !override', '<p>要删掉 base 里的列表,用 <code>!reset []</code>;要整体替换而不是合并,用 <code>!override</code>。我只在这个版本(v5.5.1)里验证,旧版 compose 是否支持这两个标签,没有测。</p>')],
    steps,
    [ENV_C + '。Docker Compose v5.5.1;只用 docker compose config --format json 展开配置,没有启动容器;ports 的发布端口只是配置值,没有实际占用;实验后已删除临时文件',
     '没有验证:extends 与 include 的合并规则、配置合并后实际启动的容器、env_file 的合并、docker compose config 对环境变量插值的结果、旧版本 compose 的行为'],
    'compose 多文件合并')
