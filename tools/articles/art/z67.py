from lib import *
R = J('z67')
def S(k): return [l for l in out('z67').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("一个没有任何认证的连接,通过四字命令(白名单 *)能看到什么:conf → 数据目录路径与大小;envi → Java 版本、操作系统、运行用户名(user.name)、工作目录、完整 classpath;cons → 所有客户端连接的来源地址与会话 id;dump → 所有会话以及它们持有的临时节点路径(这里能看到 /svc/payments-prod);wchp → 被监听的路径(/secret-config)。这些都是信息泄漏:攻击者能借此了解部署结构与服务名。", t=tl(S(1)), done=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], kv=KV([['泄漏的内容', '路径名、会话、客户端地址、环境信息']], ['泄漏的内容'])),
    step(f"但四字命令读不到 znode 的数据内容:/secret-config 里的 db.password=hunter2 没有出现在任何输出里,也没有命令能创建、修改、删除 znode。唯一会改变服务端状态的是统计类命令:srst 把 zk_packets_received 从 {R['srst'][0]} 清零到 {R['srst'][1]}——会破坏监控数据,所以不应当开放给不受信任的网络。", t=tl(S(2)), done=[1], mark=[0], kv=KV([['数据', '读不到,也改不了'], ['srst / crst', '会清零监控统计']], ['数据'])),
    step("收紧白名单:4lw.commands.whitelist=ruok,srvr 时,ruok → imok、srvr 正常;envi、cons、dump、conf 都返回「envi is not executed because it is not in the whitelist.」。默认配置下(不写白名单)同样只有 srvr 可用。运维需要的命令可以逐个加进白名单,而不是用 *。", t=tl(S(3)), done=[0, 1], mark=[2, 3, 4, 5], kv=KV([['白名单', '只放监控真正需要的命令']], ['白名单'])),
    step("没有写白名单的默认节点:五个常用命令里只有 srvr 可用,被禁止的命令(例如 envi)返回「envi is not executed because it is not in the whitelist.」。默认配置本身就是安全的;风险来自有人为了方便把白名单设成 *,同时又让客户端端口对外网可达。", t=tl(S(4)), done=[0], kv=KV([['默认', '安全,别随意改成 *']], ['默认'])),
]
A = dict(
    n=67, series='zookeeper', tags='ZooKeeper,四字命令,安全,白名单,真实验证,动画演示',
    desc='四字命令的安全风险实测:白名单 * 时无需认证即可读到 conf / envi / cons / dump / wchp 里的路径、会话、客户端地址、运行环境(但读不到 znode 数据,也不能改数据,srst 会清零统计);白名单收紧为 ruok,srvr 后其它命令被拒绝;默认配置只有 srvr 可用。',
    lead='把四字命令白名单设成 * 很方便,但代价是什么?这篇站在防御者的角度,看一个没有认证的连接最多能通过四字命令拿到什么,以及怎么用白名单与网络隔离把暴露面压到最小。',
    facts=[('不能读数据,但泄漏很多', '路径、会话、客户端地址、运行环境都能看到'), ('srst 会改监控数据', '统计类命令是唯一会改变状态的'), ('默认只开 srvr', '不要为了方便设成 *')],
    body=[
        sec('通过四字命令能看到什么', '', term('', blk('z67', 1)), '<p>这是在我自己的本机实例上、用自己造的假数据测的。重点是对照默认配置:这些信息平时是被白名单挡住的。</p>'),
        sec('读不到数据,也改不了数据', '', term('', blk('z67', 2))),
        sec('收紧白名单', '', term('', blk('z67', 3) + '\n' + blk('z67', 4))),
        sec('建议的做法', '', '<p>(1)保持默认白名单,或只放监控必需的命令;(2)客户端端口只绑定内网地址(<code>clientPortAddress</code>)并用防火墙限制来源;(3)指标监控改用只监听本机或内网的 Prometheus 端点(第 63 篇);(4)需要认证的访问用 SASL / TLS(第 75–77 篇)。这些是防御建议,其中白名单的行为是本文实测的。</p>'),
        sec('分步演示', '', demo('四字命令的暴露面', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,仅 127.0.0.1;用自己造的假数据(/secret-config、/svc/payments-prod);没有做任何针对他人系统的测试', '没有验证:通过网络从另一台机器访问、四字命令对 TLS 端口的行为、AdminServer 的暴露面(第 68 篇)、DoS 类风险'],
)
