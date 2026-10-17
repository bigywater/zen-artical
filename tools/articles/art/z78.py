from lib import *
R = J('z78'); ar = R['at_rest']; qp, qt = R['quorum_plain'], R['quorum_tls']
def S(k): return [l for l in out('z78').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("静态数据(at rest)是明文:把「SUPER-SECRET-TOKEN-8842」写进 /token,再直接在数据目录的文件里搜:包含它的有事务日志 log.1 和快照 snapshot.35、snapshot.91(其它文件是它之前或之后的,不含这条数据)。digest ACL 只控制「通过 ZooKeeper 访问」,能读数据目录文件的人不需要任何口令。ZooKeeper 自己没有落盘加密。", t=tl(S(1)), mark=[0], kv=KV([['事务日志与快照', '明文'], ['ACL', '管不了文件系统访问']], ['事务日志与快照'])),
    step(f"传输中(客户端 ↔ 服务端):让客户端经过一个会记录字节流的代理。明文端口抓到 {367} 字节,含机密:{R['plain_wire']};TLS 端口抓到 6120 字节(握手 + 密文),含机密:{R['tls_wire']}。", t=tl(S(2)), mark=[0], done=[1], kv=KV([['明文端口', '抓包能看到机密'], ['TLS 端口', '抓不到']], ['明文端口'])),
    step(f"节点之间的复制流量(quorum 端口)默认也是明文:3 节点集群里经过代理抓到 {qp['size']} 字节,含机密:{qp['visible']};配置 sslQuorum=true(加 ssl.quorum.keyStore / trustStore)后,集群照常选出 leader,抓到 {qt['size']} 字节,含机密:{qt['visible']}。保护客户端流量的同时,别忘了节点之间的流量。", t=tl(S(3)), mark=[0], done=[1], kv=KV([['quorum 默认', '明文'], ['sslQuorum=true', '加密,集群正常']], ['quorum 默认'])),
    step("应用层加密(客户端先加密再写入,这里用 Fernet):读回后客户端解密得到原文;数据目录里所有文件都不再含明文机密。代价:服务端看不懂数据(不能按内容做任何事),密钥要自己管理与分发,密钥轮换时要重写所有数据。", t=tl(S(4)), done=[0, 1], kv=KV([['应用层加密', '磁盘上没有明文,但密钥自己管']], ['应用层加密'])),
]
A = dict(
    n=78, series='zookeeper', tags='ZooKeeper,加密,TLS,数据安全,真实验证,动画演示',
    desc='ZooKeeper 数据加密边界实测:落盘的事务日志与快照是明文;客户端明文端口抓包能看到机密、TLS 端口抓不到;节点间 quorum 流量默认明文、sslQuorum=true 后加密;应用层加密能让磁盘上没有明文。',
    lead='ZooKeeper 到底加密了什么?哪些地方是明文?这篇把一个「机密」写进去,然后在磁盘文件、客户端连接、节点间复制三个位置分别「抓一下」,看它是否出现在明文里,再试应用层加密。',
    facts=[('磁盘是明文', 'log.* 与 snapshot.* 里直接能搜到数据'), ('3 条通道', '客户端 ↔ 服务端、节点 ↔ 节点各自要单独配置 TLS'), ('应用层加密', '唯一能让磁盘上没有明文的办法(自己管密钥)')],
    body=[
        sec('落盘:明文', '', term('', blk('z78', 1))),
        sec('客户端与服务端之间', '', term('', blk('z78', 2))),
        sec('节点与节点之间', '', term('', blk('z78', 3)), '<p>字节是我写的 TCP 代理从每对节点的 quorum 连接上抓到的;election 端口的流量也经过代理,一并统计。</p>'),
        sec('应用层加密', '', term('', blk('z78', 4))),
        sec('分步演示', '', demo('加密边界', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。「抓包」用 zkl.Proxy 记录转发的字节;机密是自造的字符串;TLS 用本机 openssl 生成的证书;应用层加密用 Python cryptography 的 Fernet', '没有验证:磁盘加密(FileVault / LUKS / 云盘加密)、快照与日志备份的加密、AdminServer 的 HTTPS、密钥管理系统(KMS)的集成'],
)
