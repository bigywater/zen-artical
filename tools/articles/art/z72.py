from lib import *
R = J('z72')
def S(k): return [l for l in out('z72').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("world:唯一的 id 是 anyone,匿名也能读。auth:创建时写 ACL(auth, '')——不用写用户名口令,ZooKeeper 自动把「当前连接已认证的身份」换成具体的 digest id:alice 创建 /a 后实际保存的是 digest:alice:l+tY9T…=;bob 读 → 拒绝,alice 读 → 允许,匿名读 → 拒绝。", t=tl(S(1) + S(2)), done=[0, 2], mark=[1, 3], kv=KV([['world', '任何人'], ['auth', '创建者当前已认证的身份']], ['auth'])),
    step("digest 的 id 是 user:base64(sha1(user:password))。我自己算出 alice:apw 的值是 alice:l+tY9T55txG8G/8vAjsjlr4obeM=,与 ZooKeeper 保存的完全一致;再算一次还是同一个值——没有盐,所以口令弱的话,拿到 ACL(getAcl 谁都能读,只要有 ADMIN 之外的读 ACL 权限)就能离线猜口令。口令要足够长、随机。", t=tl(S(3)), done=[0, 1], kv=KV([['digest', 'sha1(user:password),无盐'], ['风险', '弱口令可被离线猜出']], ['风险'])),
    step("ip:按客户端源 IP 授权。本机客户端来自 127.0.0.1:ACL 是 ip:127.0.0.1 或 ip:127.0.0.0/8 的节点匿名可读;ACL 是 ip:10.0.0.0/8 的拒绝。注意 ip 方案信任连接的源地址,经过 NAT / 代理之后所有客户端看起来是同一个 IP,会被一起放行或一起拒绝。", t=tl(S(4)), done=[0, 1], mark=[2], kv=KV([['ip', '信任源地址,NAT 后失效']], ['ip'])),
    step("sasl / x509 方案需要服务端先启用对应的认证提供者(第 76、77 篇);没有启用时用它们设置 ACL,创建直接失败:InvalidACLError。", t=tl(S(5)), mark=[0, 1], kv=KV([['sasl / x509', '未启用对应提供者时 InvalidACL']], ['sasl / x509'])),
    step("一个容易踩的坑:创建节点时 ACL 里只有 bob 一个人有 READ、没有任何人有 ADMIN,那么连创建它的 admin 连接都读不了、也改不了它的 ACL(admin 读 → 拒绝,改 ACL → 拒绝)。ACL 里至少要给管理身份留 ADMIN 权限。(超级用户可以绕过,本文没有测。)", t=tl(S(6)), mark=[0], kv=KV([['没人有 ADMIN', '节点的 ACL 再也改不了']], ['没人有 ADMIN'])),
]
A = dict(
    n=72, series='zookeeper', tags='ZooKeeper,ACL,digest,ip,真实验证,动画演示',
    desc='Digest、IP、Auth、SASL ACL 对比实测:auth 方案自动变成创建者的 digest id;digest id = user:base64(sha1(user:password)) 无盐,与 ZooKeeper 保存的完全一致;ip 方案按源 IP / CIDR 授权;sasl / x509 未启用提供者时设置 ACL 会 InvalidACLError;没人有 ADMIN 权限的节点 ACL 改不了。',
    lead='ZooKeeper 的 ACL 有 world、auth、digest、ip、sasl、x509 几种方案。它们各自的 id 长什么样、信任什么、有什么坑?这篇每种都实际用一遍,并验证 digest 哈希到底是怎么算的。',
    facts=[('sha1(user:password)', 'digest id 的算法,无盐,我算的值与保存的一致'), ('auth 方案', '自动变成创建者当前身份的 digest id'), ('ip 方案', '信任源地址,经 NAT 后所有客户端是同一个 IP')],
    body=[
        sec('world 与 auth', '', term('', blk('z72', 1) + '\n' + blk('z72', 2))),
        sec('digest', '', term('', blk('z72', 3))),
        sec('ip', '', term('', blk('z72', 4))),
        sec('sasl 与 x509', '', term('', blk('z72', 5))),
        sec('忘了给自己留 ADMIN', '', term('', blk('z72', 6))),
        sec('分步演示', '', demo('ACL 方案', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;ip 方案只测了 127.0.0.1(本机只有这一个源地址);digest 口令是实验用的假口令', '没有验证:ip 方案经过真实 NAT / 反向代理的表现、x509 与 sasl 的完整使用(第 76、77 篇)、digest 之外的口令哈希加强、超级用户'],
)
