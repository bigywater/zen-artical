from lib import *
R = J('z77')
def S(k): return [l for l in out('z77').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("SASL 要在服务端配 JAAS 与认证提供者:zoo.cfg 里 authProvider.1=…SASLAuthenticationProvider,JVM 参数 -Djava.security.auth.login.config 指向 Server 段(DIGEST-MD5:user_bob=\"bobsecret\")。一个坑:ZooKeeper 3.9 默认 zookeeper.fips-mode=true,客户端日志「Client will not use DIGEST-MD5 as SASL mechanism, because FIPS mode is enabled.」,SASL 会失败(「saslClient failed to initialize properly: it's null」),要在客户端和服务端都加 -Dzookeeper.fips-mode=false 才能用 DIGEST-MD5。", t=tl(S(1)), kv=KV([['fips-mode', '3.9 默认拒绝 DIGEST-MD5']], ['fips-mode'])),
    step("关掉 FIPS 之后:没有 JAAS 的客户端 whoami 只有 ip;JAAS 里是 bob 的客户端 state:SaslAuthenticated、whoami 显示「sasl: bob」;口令错误的客户端 state:AuthFailed、「SASL authentication failed using login context 'Client'.」。", t=tl(S(1)[1:4]), done=[1], mark=[2], kv=KV([['正确口令', 'SaslAuthenticated → sasl: bob'], ['错误口令', 'AuthFailed']], ['正确口令'])),
    step("sasl ACL:bob 创建 /bobs,ACL = sasl:bob:cdrwa;bob 读成功,alice(同样是合法 SASL 用户)读 → Insufficient permission,匿名读 → Insufficient permission。", t=tl(S(2)), done=[0, 1], mark=[2, 3], kv=KV([['sasl ACL', '按认证后的用户名授权']], ['sasl ACL'])),
    step("默认情况下匿名连接仍然允许(没有 SASL 也能 ls /)。要强制 SASL,用 -Dzookeeper.enforce.auth.enabled=true 与 -Dzookeeper.enforce.auth.schemes=sasl:匿名客户端 ls / → 「Session closed because client failed to authenticate」,bob 正常。(我先试过 requireClientAuthScheme,没有效果。)", t=tl(S(3)), done=[1], mark=[0], kv=KV([['强制 SASL', 'enforce.auth.enabled + schemes=sasl']], ['强制 SASL'])),
    step("Kerberos(GSSAPI):用 brew 的 krb5 在本机起一个 KDC(realm ZK.TEST、端口 7650),创建服务主体 zookeeper/localhost 和客户端主体 zkclient、otheruser,全部用 keytab 登录(不碰你的票据缓存)。zkclient 登录后 whoami 显示「sasl: zkclient@ZK.TEST」;ACL = sasl:zkclient@ZK.TEST:cdrwa 的节点,zkclient 能创建,otheruser(另一个合法 Kerberos 用户)读 → Insufficient permission,没有凭据的读 → Insufficient permission。", t=tl(S(4)), done=[0, 1], mark=[2, 3], kv=KV([['Kerberos', 'KDC + keytab + JAAS(Krb5LoginModule)'], ['身份', 'sasl:主体名@REALM']], ['Kerberos'])),
]
A = dict(
    n=77, series='zookeeper', tags='ZooKeeper,SASL,Kerberos,认证,真实验证,动画演示',
    desc='SASL/Kerberos 认证实测:DIGEST-MD5(需关闭 3.9 默认的 fips-mode)与 Kerberos(本机 KDC,zookeeper/localhost 与 zkclient 主体、keytab)都跑通;sasl ACL 按认证身份授权;enforce.auth 可强制必须 SASL 认证。',
    lead='ZooKeeper 的 SASL 认证有两种常用机制:DIGEST-MD5 和 Kerberos。这篇都真的跑一遍:先用不需要 KDC 的 DIGEST-MD5,再用 brew 的 krb5 在本机搭一个 KDC,用 keytab 做 Kerberos 登录,最后验证 sasl ACL。',
    facts=[('fips-mode', '3.9 默认拒绝 DIGEST-MD5,必须在两端加 -Dzookeeper.fips-mode=false'), ('sasl:bob / sasl:zkclient@ZK.TEST', 'SASL 与 Kerberos 的 ACL id'), ('enforce.auth', '用 -Dzookeeper.enforce.auth.enabled / schemes 强制必须认证')],
    body=[
        sec('DIGEST-MD5', '', term('', blk('z77', 1)), '<p>DIGEST-MD5 的用户名口令写在服务端 JAAS 文件里(<code>user_bob="bobsecret"</code>),这只适合实验。</p>'),
        sec('sasl ACL', '', term('', blk('z77', 2))),
        sec('强制认证', '', term('', blk('z77', 3))),
        sec('Kerberos', '', term('', blk('z77', 4)), '<p>KDC 只绑定本机端口 7650,realm 与密钥都是临时生成的;客户端登录用 keytab(<code>useTicketCache=false</code>),所以不会读写你系统的 Kerberos 票据缓存。</p>'),
        sec('分步演示', '', demo('SASL 与 Kerberos', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;DIGEST-MD5 与 Kerberos 各一个节点;Kerberos 用 brew 的 krb5(KDC 本机 7650),客户端是官方 CLI + JAAS', '没有验证:跨主机的 Kerberos(DNS / 反向解析 / 时钟偏差)、票据续期、kerberos.removeHostFromPrincipal 等简化选项、集群节点间的 Kerberos(quorum.auth)、sasl.superUser'],
)
