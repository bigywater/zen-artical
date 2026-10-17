import json
from lib import *
R = J('r127'); cl = R['cli']; au = R['auth']; cn = R['conn']; rt = R['rtt']; mp = R['map']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tl(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
sh = lambda x: x.replace('Could not connect to Redis at 127.0.0.1:9152: ', '')
bp = R['bench']['plain']; bt = R['bench']['tls']
steps = [
    step("同一个实例同时开明文口和 TLS 口。明文 redis-cli 连 TLS 口:Connection reset by peer;用原始套接字发明文 PING:连接被重置。TLS 口不接受明文协议。", n=fl([['明文客户端', '→ TLS 口'], ['结果', 'Connection reset by peer']], mark=[1]), kv=KV([['明文 → TLS 口', '被重置']], ['明文 → TLS 口'])),
    step(f"服务端证书的校验:--tls --cacert ca.crt → {cl['ca']};不给 --cacert → {sh(cl['no_ca'])};给不相关的 CA → 同样 certificate verify failed;--insecure → {cl['insecure']}(什么都不校验,等于没有防中间人)。", t=tl(['--tls --cacert ca.crt        → ' + cl['ca'], '--tls(无 --cacert)        → ' + sh(cl['no_ca']), '--tls --cacert 不相关 CA   → ' + sh(cl['rogue_ca']), '--tls --insecure           → ' + cl['insecure']], cur=[0], mark=[1, 2, 3]), kv=KV([['--insecure', '能连,但不验证服务端']], ['--insecure'])),
    step(f"tls-auth-clients(是否要求客户端证书):yes 时,不带证书 → {au['yes_nocert'].split(': ')[-1]};带受信任 CA 签的证书 → {au['yes_cert']};带别的 CA 签的证书(CN 同名)→ 被拒。optional 时,不带证书 → {au['opt_nocert']},但带了不受信任的证书 → 仍被拒。", n=fl([['yes + 无证书', '被拒'], ['yes + 受信任证书', 'PONG'], ['yes + 不受信任证书', '被拒'], ['optional + 无证书', 'PONG'], ['optional + 不受信任证书', '被拒']], done=[1, 3], mark=[0, 2, 4]), kv=KV([['optional', '没证书可以,坏证书不行']], ['optional'])),
    step(f"协商结果:{R['ver'][0]},套件 {R['ver'][1]};客户端把主机名换成 wrong.example → 握手失败(Hostname mismatch);客户端只允许 TLS 1.2 或只允许 1.3 都能连上(服务端 tls-protocols 为空,即默认)。", kv=KV([['协议', R['ver'][0]], ['套件', R['ver'][1]], ['主机名不符', '握手失败']], ['主机名不符'])),
    step(f"代价一(建连):新建连接 + 1 次 PING,明文中位 {cn['plain_med']:.2f} ms,TLS 中位 {cn['tls_med']:.2f} ms(p99 {cn['plain_p99']:.2f} → {cn['tls_p99']:.2f} ms)。握手是主要代价,所以 TLS 下更要用连接池。", b=bars([['明文 建连+PING(中位 ms)', cn['plain_med'], f"{cn['plain_med']:.2f}"], ['TLS 建连+PING(中位 ms)', cn['tls_med'], f"{cn['tls_med']:.2f}"]], cn['tls_med'] * 1.1, mark=[1]), kv=KV([['建连', f"{cn['plain_med']:.2f} → {cn['tls_med']:.2f} ms"]], ['建连'])),
    step(f"代价二(已建立的连接):20000 次 PING 往返,明文中位 {rt['plain_med']:.0f} µs、TLS 中位 {rt['tls_med']:.0f} µs。redis-benchmark(-c 50,无流水线):明文 {bp[0]} / {bp[1]};TLS {bt[0]} / {bt[1]}。", b=bars([['明文 SET req/s', float(bp[0].split(': ')[1].split(' ')[0]), bp[0].split(': ')[1].split(' ')[0]], ['TLS SET req/s', float(bt[0].split(': ')[1].split(' ')[0]), bt[0].split(': ')[1].split(' ')[0]]], 130000, mark=[1]), kv=KV([['单次往返', f"{rt['plain_med']:.0f} → {rt['tls_med']:.0f} µs"]], ['单次往返'])),
    step(f"证书身份映射到 ACL 用户:tls-auth-clients-user 默认 off,此时带 CN=svc-app 证书的连接 ACL WHOAMI = default。设为 CN 后同一证书的连接变成用户 svc-app(用它的权限;SET app:1 → OK,SET other → NOPERM);CN=nobody 的证书因为没有这个用户,连接回落成 default(而且 INFO 里 acl_access_denied_tls_cert 加 1)。", n=fl([['映射 off:CN=svc-app', 'default'], ['映射 CN:CN=svc-app', '用户 svc-app'], ['映射 CN:CN=nobody', '回落 default']], done=[1], mark=[0, 2]), kv=KV([['CN 无对应用户', '回落到 default,不是拒绝']], ['CN 无对应用户'])),
]
A = dict(
    n=127, series='redis', tags='Redis,TLS,安全,真实验证,动画演示',
    desc=f'Redis TLS 实测(openssl 生成本地测试证书):明文口与 TLS 口共存、证书校验与 --insecure、tls-auth-clients 的 yes / optional、协商 {R["ver"][0]}、建连代价 {cn["plain_med"]:.2f}→{cn["tls_med"]:.2f} ms、往返 {rt["plain_med"]:.0f}→{rt["tls_med"]:.0f} µs、证书 CN 映射 ACL 用户。',
    lead='给 Redis 加 TLS,配起来不难,难的是知道每个开关到底挡住了什么、代价多大。这篇用 openssl 自己生成一套测试 CA 和证书,在本机跑通明文口 + TLS 口并存,把证书校验、双向认证、握手与往返代价、以及把证书 CN 映射到 ACL 用户都量一遍。',
    facts=[(f'{cn["plain_med"]:.2f} → {cn["tls_med"]:.2f} ms', '新建连接 + 1 次 PING 的中位耗时:明文 → TLS(本机回环)'), (f'{rt["plain_med"]:.0f} → {rt["tls_med"]:.0f} µs', '已建立连接上一次 PING 往返的中位耗时:明文 → TLS'), ('回落 default', '开了 tls-auth-clients-user CN,证书 CN 没有对应用户时,连接不会被拒,而是当作 default 用户')],
    body=[
        sec('测试证书', '', term('', blk('r127', 1)), '<p>全部是本机 openssl 现生成的测试证书(EC P-256,30 天):一个 CA,一张 SAN 为 <code>localhost</code> 和 <code>127.0.0.1</code> 的服务端证书,一张 CN=svc-app 的客户端证书,以及另一个 CA(rogue)签的同名 CN 证书,用来验证「CN 相同但 CA 不受信任」的情形。</p>'),
        sec('服务端证书校验', '', term('', blk('r127', 2)), '<p>TLS 口拒绝明文协议(连接被重置)。客户端不给 CA、给了不相关的 CA,都是 <code>certificate verify failed</code>。<code>--insecure</code> 能连上,但客户端什么都不校验——它防不了中间人,只在测试里用。</p>'),
        sec('客户端证书:tls-auth-clients', '', term('', blk('r127', 3)), '<p><code>yes</code> 要求每个客户端出示受信任 CA 签发的证书,没有或不受信任都在握手阶段被拒(服务端直接关闭连接,客户端看到 Server closed the connection)。<code>optional</code> 允许不出示,但出示了就必须可信。注意 rogue 证书的 CN 与合法证书相同也没用,信任来自签发者。</p>'),
        sec('协议版本与主机名', '', term('', blk('r127', 4)), '<p>握手协商到 TLS 1.3。本文没有测试强制服务端只允许旧版本(<code>tls-protocols</code> 保持默认为空)。主机名校验是客户端的事:证书里没有的名字握手就失败。</p>'),
        sec('代价', '', term('', blk('r127', 5)), '<p>建连的代价明显(握手),已建立连接上单次往返的差别很小,吞吐下降的幅度见上面的 redis-benchmark 数字。都是本机回环、单次运行的数字,不是通用结论;真实网络里延迟主要来自往返本身。</p>'),
        sec('证书 CN → ACL 用户', '', term('', blk('r127', 6)), '<p>8.10.2 里有 <code>tls-auth-clients-user</code>(默认 <code>off</code>):设成 <code>CN</code> 后,客户端证书的 CN 直接作为登录的 ACL 用户名,不用再 <code>AUTH</code>。<b>关键的坑:</b>CN 对应的用户不存在时,连接没有被拒绝,而是当作 <code>default</code> 用户继续用——只有把 default 用户关掉或设了密码,这里才安全(<code>INFO</code> 里的 <code>acl_access_denied_tls_cert</code> 会计数)。</p>'),
        sec('分步演示:TLS 的每一层', '', demo('Redis TLS', [('n', 'flow', '连接与结果'), ('t', 'term', '客户端结果'), ('b', 'bars', '代价'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。openssl 3.6.4,证书为测试用 EC P-256;明文口和 TLS 口在同一个实例上', '没有验证:tls-replication / tls-cluster、tls-protocols 限制旧版本、tls-ciphers 定制、证书轮换(tls-cert-file 变更后 CONFIG SET / 重载)、CRL / OCSP、跨机器网络下的延迟、其它客户端库的默认校验行为'],
)
