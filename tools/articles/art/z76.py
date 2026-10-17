from lib import *
R = J('z76')
def S(k): return [l for l in out('z76').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("ssl.clientAuth=need(双向 TLS):TLS 客户端不带证书 → 握手失败(certificate_required);带 client1 证书(我的 CA 签发)→ 正常;带一张自签名、同样叫 CN=client1 的证书 → 同样失败(服务端只信任它的信任库里的 CA,只有名字相同没用)。", t=tl(S(1)), done=[1], mark=[0, 2], kv=KV([['need', '没有受信任的客户端证书就拒绝'], ['自签名冒名证书', '被拒绝']], ['need'])),
    step("证书的主题(DN)就是 ZooKeeper 里的身份(x509 认证):client1 的 whoami 显示「x509: CN=client1」,client2 是「x509: CN=client2」。不需要额外配置用户名口令——身份来自证书。", t=tl(S(2)), done=[0, 1], kv=KV([['x509 身份', '证书 DN,如 CN=client1']], ['x509 身份'])),
    step("用 x509 ACL 按证书授权:client1 创建 /only-client1,ACL = x509:CN=client1:cdrwa;client1 读 → secret;client2(也是合法证书,CN=client2)读 → Insufficient permission。getAcl 显示 'x509,'CN=client1 : cdrwa。能连上集群不等于有权限,授权仍由 ACL 决定。", t=tl(S(3)), done=[1, 2], mark=[3], kv=KV([['能连上', '≠ 有权限'], ['x509 ACL', '按证书 DN 授权']], ['能连上'])),
    step("ssl.clientAuth=want:证书可有可无——不带证书的客户端仍能连上(匿名),带 client1 证书的被识别为 x509: CN=client1。要强制每个客户端都有证书,必须用 need。", t=tl(S(4)), done=[0, 1], kv=KV([['want', '有证书就认证,没有也放行']], ['want'])),
]
A = dict(
    n=76, series='zookeeper', tags='ZooKeeper,mTLS,双向认证,x509,真实验证,动画演示',
    desc='mTLS 双向认证实测:ssl.clientAuth=need 时无证书、自签名冒名证书都握手失败;证书 DN 成为 x509 身份(whoami: x509: CN=client1);x509 ACL 按证书授权(client2 被拒);clientAuth=want 时无证书的客户端仍可匿名连接。',
    lead='TLS 只让客户端确认服务端是谁;双向 TLS 还要服务端确认客户端是谁。这篇配置 ssl.clientAuth,验证没有证书、冒名证书、合法证书三种连接的结果,再用证书 DN 做 ACL。',
    facts=[('need vs want', 'need 强制客户端证书;want 有没有都放行'), ('x509: CN=client1', '证书 DN 就是 ZooKeeper 里的身份'), ('能连 ≠ 能访问', '合法证书仍要被 ACL 授权')],
    body=[
        sec('clientAuth=need', '', term('', blk('z76', 1))),
        sec('证书就是身份', '', term('', blk('z76', 2))),
        sec('按证书授权', '', term('', blk('z76', 3))),
        sec('clientAuth=want', '', term('', blk('z76', 4))),
        sec('分步演示', '', demo('双向 TLS', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;本机 openssl 生成的 CA、client1、client2 以及一张自签名冒名证书;客户端是官方 CLI(PKCS12 密钥库)', '没有验证:证书吊销、DN 里含逗号等特殊字符的 ACL 写法、ssl.authProvider 自定义、集群里节点间的双向认证(第 78 篇只验证了加密)'],
)
