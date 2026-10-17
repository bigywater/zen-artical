from lib import *
S = SS('c50')
steps = [
    step("--network-alias web --network-alias www 的容器,docker inspect 里该网络下的 Aliases = [\"web\",\"www\"];不带 --network-alias 的容器 Aliases = null,默认 bridge 上的容器也是 null(容器名、容器 ID 不出现在 Aliases 里,但仍然能被解析,见 c48)。", t=tl(S(1)), done=lidx(S(1), '--network-alias web'), mark=lidx(S(1), '不带 --network-alias', '默认 bridge 上的容器'), kv=KV([['--network-alias web --network-alias www', 'Aliases = [web, www]'], ['没设别名', 'Aliases = null'], ['默认 bridge', 'null,也没有名字解析']], ['--network-alias web --network-alias www'])),
    step("别名是按网络生效的:docker network connect --alias api bwlab-c50n2 把容器接入第二个网络,n1 里 Aliases 仍是 [web, www],n2 里是 [api]。在 n1 的另一个容器解析 web → 172.19.0.2,解析 api → 失败;在 n2 的容器解析 api → 172.20.0.2;解析 web → 得到 127.0.53.53,那是上游 DNS 对不认识的短名字返回的保留地址,不是任何容器。", t=tl(S(2)), done=lidx(S(2), 'plain(在 n1)解析 web', 'b(在 n2)解析 api'), mark=lidx(S(2), 'plain(在 n1)解析 api', 'b(在 n2)解析 web'), kv=KV([['n1', 'Aliases = [web, www]'], ['n2', 'Aliases = [api]'], ['跨网络解析', 'api 在 n1 解析失败;web 在 n2 得到 127.0.53.53(不是容器)']], ['跨网络解析'])),
    step("3 个容器共用别名 db(IP 172.19.0.4、.5、.6):解析 db 一次返回全部 3 个地址;连续 6 次解析,返回的第一个地址是 172.19.0.6、.6、.5、.6、.5、.4,顺序在变。别名可以指向多个容器,DNS 返回全部,顺序不固定。", t=tl(S(3)), done=lidx(S(3), '3 个容器的 IP'), mark=lidx(S(3), '连续 6 次'), b=bars([['db 返回的地址数', 3, '3']], 3, done=[0]), kv=KV([['共用别名 db', '一次返回 3 个地址'], ['连续 6 次的第一个地址', '顺序不固定']], ['共用别名 db'])),
    step("docker network disconnect bwlab-c50n2 之后,n2 里解析 api → 失败,别名随之消失。删掉共用别名的 s2 之后,解析 db 只剩 172.19.0.4 和 172.19.0.6。", t=tl(S(4)), done=lidx(S(4), '删掉 s2 之后'), mark=lidx(S(4), 'docker network disconnect'), kv=KV([['network disconnect', '该网络里的别名消失'], ['删掉一个容器', '它的地址从 db 里消失']], ['network disconnect'])),
]
A = mkartc('c50', 50, 'Docker,网络别名,network-alias,DNS,自定义网络,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测网络别名:--network-alias 写进该网络下的 Aliases,默认 bridge 没有;别名按网络生效,docker network connect --alias 可以给第二个网络设不同的别名;3 个容器共用别名 db 时一次解析返回全部 3 个地址,顺序变化;断开网络或删除容器后别名随之消失。',
    '网络别名是什么、在哪个范围生效?多个容器共用一个别名会怎样?这篇用 docker inspect 的 Aliases 和 nslookup 逐项验证,包括别名跨网络时的表现。',
    [('3 个地址', '3 个容器共用别名 db 时,一次解析返回的地址数'), ('Aliases = null', '没有设置 --network-alias 的容器和默认 bridge 上的容器'), ('127.0.53.53', '在不认识别名的网络里解析 web 得到的保留地址,不是任何容器')],
    [('Aliases', '<p>每个网络下,容器有自己的 <code>Aliases</code> 列表,只包含显式设置的别名,默认 bridge 上没有。</p>'),
     ('按网络生效', '<p><code>docker network connect --alias</code> 给容器在第二个网络里设置不同的别名。在 n1 里只能解析 n1 的别名,n2 里的 api 在 n1 解析失败。n2 里解析 n1 的别名 web 得到的是 127.0.53.53,那是上游 DNS 对未知短名字的回答(我没有查它的来源,只确认了它不是容器 IP),所以按名字访问之前应当检查地址是否合理。</p>'),
     ('共用别名', '<p>多个容器用同一个别名,解析一次得到全部地址,返回顺序会变化(6 次采样里第一个地址出现了 3 种不同的值),取第一个地址的客户端会因此分散到不同的容器(详见后面的 DNS 轮询一篇)。</p>'),
     ('清理', '<p>断开网络或删除容器后,别名和对应的地址立即消失。</p>')],
    steps,
    [ENV_C + '。解析用 busybox 的 nslookup(取返回的地址);别名取自 docker inspect 的 NetworkSettings.Networks.*.Aliases;两个自定义网络 172.19.0.0/16 和 172.20.0.0/16;实验后已删除容器和网络',
     '没有验证:--link 旧参数、Compose 服务名别名、IPv6、别名与容器名冲突、127.0.53.53 的来源、DNS 缓存对别名变化的延迟'],
    '网络别名')
