from lib import *
R = J('d136')
def S(k): return [l for l in out('d136').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("探针(kubelet / 负载均衡)用 Pod IP 当 Host、走 http 访问一个普通视图 /healthz/(ALLOWED_HOSTS=['example.com'],SECURE_SSL_REDIRECT=True):Host 是 10.0.0.5 → 400;Host 是 example.com 但走 http → 301 重定向到 https;只有 Host 对、走 https 才是 200。这三种都会让探针失败。", t=tl(S(1)), mark=[0, 1], done=[2], kv=KV([['Pod IP 作 Host', '400(ALLOWED_HOSTS)'], ['http 探针', '301(SSL 重定向)']], ['Pod IP 作 Host'])),
    step("解法一:把存活探针做成放在 MIDDLEWARE 最前面的中间件(/live/):Host 是 10.0.0.5 或 example.com、走 http 都是 200,数据库查询 0 次,不设置会话 cookie——它在 Host 校验、SSL 重定向、会话中间件之前就返回了。", t=tl(S(2)), done=[0, 1], kv=KV([['最前面的中间件', '绕过 Host 校验、重定向、会话、数据库']], ['最前面的中间件'])),
    step("存活与就绪要分开:/ready/ 检查数据库(select 1)。数据库运行时 /ready/ → 200;数据库停掉后 /ready/ → 503(OperationalError),而 /live/ 仍然是 200。如果存活探针也检查数据库,数据库一抖,所有实例都会被判定为「该重启」。", t=tl(S(3)), mark=[4], done=[1, 2], kv=KV([['/ready/', '依赖数据库 → 503'], ['/live/', '不依赖 → 200']], ['/ready/'])),
    step("数据库地址不可达(连接挂起而不是拒绝)时,是 connect_timeout 在起作用:连接 10.255.255.1、connect_timeout=2,/ready/ 在约 2053 ms 返回 503。没有设置 connect_timeout 会挂多久,我没有测(没有等到默认超时)。", t=tl(S(4)), mark=[0], kv=KV([['connect_timeout=2', '约 2 s 后 503']], ['connect_timeout=2'])),
]
A = dict(
    n=136, series='django', tags='Django,健康检查,部署,ALLOWED_HOSTS,PostgreSQL,真实验证,动画演示',
    desc='健康检查:探针用 Pod IP 当 Host 走 http 会被 ALLOWED_HOSTS 拒(400)或被 SSL 重定向(301);放在 MIDDLEWARE 最前面的存活中间件绕开这些、0 次数据库查询;就绪探针查数据库,数据库停掉后 503 而存活仍是 200;connect_timeout=2 使不可达的数据库约 2 s 后返回 503。',
    lead='健康检查看起来是最简单的接口,在 Django 里却会踩到前面几篇讲过的坑:ALLOWED_HOSTS、SSL 重定向、会话中间件。这篇用探针的真实视角请求一遍,再把存活与就绪分开,看数据库挂了会怎样。',
    facts=[('400 / 301 / 200', '普通视图作探针:Pod IP 作 Host / http / https + 正确 Host'), ('0 次查询', '放在 MIDDLEWARE 最前面的存活中间件'), ('503 vs 200', '数据库停掉后,就绪探针 503,存活探针仍 200')],
    body=[
        sec('普通视图作探针会失败', '', term('', blk('d136', 1)), '<p>探针从集群内部访问,Host 通常是 Pod IP,协议是 http。前者违反 ALLOWED_HOSTS(第 122 篇),后者触发 SSL 重定向(第 121 篇)。也可以用 <code>SECURE_REDIRECT_EXEMPT</code> 豁免路径、把 Pod IP 加进 ALLOWED_HOSTS,这两种做法本文没有测。</p>'),
        sec('存活探针:最前面的中间件', '', term('', blk('d136', 2)), '<p>它必须放在 <code>MIDDLEWARE</code> 的第一位,并且不要调用 <code>request.get_host()</code>。代价是它不走任何后续中间件,也就没有任何认证与日志。</p>'),
        sec('就绪探针:检查依赖', '', term('', blk('d136', 3)), '<p>存活探针回答「进程还活着吗」,不应当依赖数据库;就绪探针回答「能处理请求吗」,可以检查数据库。第一次请求 /ready/ 要新建数据库连接,所以耗时远高于 /live/。</p>'),
        sec('数据库不可达时', '', term('', blk('d136', 4)), '<p>给探针里的数据库连接设置 <code>connect_timeout</code>,让它在探针自己的超时之内失败。</p>'),
        sec('分步演示', '', demo('健康检查', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。自己起的临时 PostgreSQL 16;用 Client 模拟探针(HTTP_HOST、secure);数据库停止用 pg_ctl;不可达地址用 10.255.255.1', '没有验证:Kubernetes 的真实探针配置(超时、失败阈值)、负载均衡器的健康检查行为、没有 connect_timeout 时的挂起时长、探针对缓存 / 消息队列等其它依赖的检查'],
)
