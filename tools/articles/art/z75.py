from lib import *
R = J('z75'); lt = R['lat']
def S(k): return [l for l in out('z75').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("服务端同时开放明文端口 7300 和 TLS 端口 7301(secureClientPort + Netty 连接工厂 + PKCS12 密钥库)。明文客户端连 TLS 端口 → ConnectionLoss;TLS 客户端(信任我的 CA)连 7301 → 正常列出 [zookeeper];TLS 客户端不信任这个 CA → SSLHandshakeException(certificate_unknown,PKIX path building failed);而同一个服务端的明文端口 7300 仍然可用——开了 TLS 还留着明文端口,等于没加固。", t=tl(S(1)), done=[1, 3], mark=[0, 2], kv=KV([['明文连 TLS 端口', 'ConnectionLoss'], ['不信任 CA', 'SSLHandshakeException'], ['明文端口还开着', '风险']], ['明文端口还开着'])),
    step("主机名校验:连的是 127.0.0.1,服务端证书的 SAN 含 IP:127.0.0.1 与 localhost → 正常;换成 CN=wrong.example.com、没有 SAN 的证书 → 握手失败(certificate_unknown:No name matching localhost found);客户端关闭主机名校验(zookeeper.ssl.hostnameVerification=false)又能连上——但失去了防冒充的保护,不应当在生产里这么做。", t=tl(S(2)), done=[0, 2], mark=[1], kv=KV([['主机名校验', '证书必须匹配连接的主机名']], ['主机名校验'])),
    step("只开 TLS 端口(去掉明文 clientPort):明文客户端连 7305 → ConnectionLoss,TLS 客户端正常。要强制加密,必须关掉明文端口。", t=tl(S(3)), done=[1], mark=[0], kv=KV([['只开 TLS 端口', '明文客户端连不上']], ['只开 TLS 端口'])),
    step(f"kazoo(Python)用 PEM 证书走 TLS(use_ssl=True、ca=…、verify_certs=True)连 7307;同步写 300 次中位:明文 {lt['plain']:.2f} ms,TLS {lt['tls']:.2f} ms——差别可以忽略(写延迟被 fsync 主导,第 55 篇)。", t=tl(S(4)), b=bars([['明文', lt['plain'], f"{lt['plain']:.2f} ms"], ['TLS', lt['tls'], f"{lt['tls']:.2f} ms"]], max(lt.values()) * 1.2, done=[0, 1]), kv=KV([['TLS 开销', '同步写延迟几乎没有差别']], ['TLS 开销'])),
]
A = dict(
    n=75, series='zookeeper', tags='ZooKeeper,TLS,加密,客户端连接,真实验证,动画演示',
    desc=f'TLS 客户端连接实测:secureClientPort + Netty + PKCS12 密钥库;明文客户端连不上 TLS 端口;不信任 CA 或主机名不匹配握手失败;开了 TLS 若不关明文端口仍可明文访问;TLS 与明文同步写延迟 {lt["tls"]:.2f} vs {lt["plain"]:.2f} ms。',
    lead='给 ZooKeeper 加 TLS 要配哪些东西?哪些错误配置会让加固失效?这篇用本机生成的 CA 与证书,从配置、信任、主机名校验、明文端口四个方面验证,最后量一下 TLS 的延迟代价。',
    facts=[('明文端口要关', '开了 TLS 端口但不去掉 clientPort,明文照样能连'), ('主机名校验', '证书 SAN 不匹配时握手失败'), (f'{lt["tls"]:.2f} vs {lt["plain"]:.2f} ms', 'TLS 与明文的同步写 p50')],
    body=[
        sec('明文与 TLS 端口并存', '', term('', blk('z75', 1)), '<p>配置:<code>secureClientPort</code>、<code>serverCnxnFactory=…NettyServerCnxnFactory</code>、<code>ssl.keyStore.location / password / type</code>、<code>ssl.trustStore.*</code>;客户端用 <code>zookeeper.client.secure=true</code> 与 <code>ClientCnxnSocketNetty</code>。证书由本机 openssl 生成,有效期 30 天,仅用于实验。</p>'),
        sec('主机名校验', '', term('', blk('z75', 2))),
        sec('强制 TLS', '', term('', blk('z75', 3))),
        sec('Python 客户端与延迟', '', term('', blk('z75', 4))),
        sec('分步演示', '', demo('TLS 客户端', [('t', 'term', '输出'), ('b', 'bars', '延迟'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;本机 openssl 生成的 CA 与证书;官方 CLI 作 Java 客户端,kazoo 作 Python 客户端', '没有验证:证书过期 / 吊销(CRL / OCSP)、TLS 协议版本与密码套件选择、集群里的 TLS(节点间见第 78 篇)、证书热更新(ZooKeeper 的 ssl.*.reload 之类)'],
)
