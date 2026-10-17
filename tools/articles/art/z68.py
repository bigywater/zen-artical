from lib import *
R = J('z68'); cm = R['commands']
def S(k): return [l for l in out('z68').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"AdminServer(Jetty)用 zoo.cfg 里的 admin.enableServer=true、admin.serverPort=7392、admin.serverAddress=127.0.0.1 开启。GET /commands 返回的是一个 HTML 链接列表(不是 JSON),共 {len(cm)} 个命令:{', '.join(cm[:12])} …… 默认端口 8080 我没有用(那是你机器上别的服务在用)。", t=tl(S(1)), done=[0], kv=KV([['端点', '/commands,返回 HTML 链接'], ['命令数', str(len(cm))]], ['端点'])),
    step("单个命令返回 JSON:/commands/ruok → {command: ruok, error: null};/commands/stats → version、read_only、server_stats(18 个字段)、client_response、node_count、connections;/commands/monitor → server_state、ephemerals_count、num_alive_connections、avg_latency、outstanding_requests……;/commands/configuration → client_port、data_dir、data_log_dir……;/commands/connections → 连接列表。", t=tl(S(2)), done=[0, 1, 2, 3, 4], kv=KV([['格式', 'JSON,字段名是 snake_case']], ['格式'])),
    step(f"与四字命令 mntr 的关系:monitor 里的 znode_count 与 mntr 的 zk_znode_count 都是 {R['cmp'][0]};monitor 有 {R['counts'][0]} 个字段、mntr 有 {R['counts'][1]} 个指标——monitor 含更多(带分位数 / 累计的 *_count、*_sum 等派生字段)。AdminServer 是四字命令的 HTTP 版,但有自己独立的命令名(environment、stats 等)。", t=tl(S(3)), done=[0], kv=KV([['AdminServer', 'mntr 的超集 + HTTP / JSON']], ['AdminServer'])),
    step("不存在的命令:GET /commands/nope → HTTP 200(不是 404),正文是 {command: nope, error: \"Unknown command: nope\"}——错误在 JSON 的 error 字段里,监控脚本要检查 error 而不是只看状态码。", t=tl(S(4)), mark=[0], kv=KV([['错误', 'HTTP 200 + error 字段']], ['错误'])),
]
A = dict(
    n=68, series='zookeeper', tags='ZooKeeper,AdminServer,REST,监控,真实验证,动画演示',
    desc=f'AdminServer REST 接口实测:admin.enableServer=true + admin.serverPort 开启后 /commands 列出 {len(cm)} 个命令(HTML 链接),/commands/<name> 返回 JSON(stats、monitor、configuration、connections…);monitor 比四字命令 mntr 的指标更多;未知命令返回 HTTP 200 加 error 字段。',
    lead='AdminServer 是 ZooKeeper 3.5 起内置的 HTTP 管理接口,默认端口 8080,命令比四字命令多、输出是 JSON。这篇在自己选定的端口上开启它,看有哪些命令、返回什么、和 mntr 的关系。',
    facts=[(f'{len(cm)} 个命令', 'GET /commands 列出的 AdminServer 命令数'), ('JSON', '每个命令返回 JSON,包含 error 字段'), ('默认 8080', '很容易与别的服务冲突,要改 admin.serverPort')],
    body=[
        sec('开启与命令列表', '', term('', blk('z68', 1)), '<p>默认端口 8080 是个常见的冲突点(很多服务都用它),我在本机就遇到了这种情况,所以全部实验里都关闭了 AdminServer(<code>admin.enableServer=false</code>),只有这一篇用自选的端口打开它。</p>'),
        sec('命令的返回', '', term('', blk('z68', 2))),
        sec('与四字命令的关系', '', term('', blk('z68', 3))),
        sec('错误处理', '', term('', blk('z68', 4)), '<p>AdminServer 也没有内置认证(是否需要 HTTPS / 客户端证书用 <code>admin.portUnification</code>、<code>admin.forceHttps</code> 之类的参数,本文没有测),所以与四字命令一样,应当只绑定内网或本机。</p>'),
        sec('分步演示', '', demo('AdminServer', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;AdminServer 端口 7392,绑定 127.0.0.1;请求用 Python http.client', '没有验证:HTTPS / 认证配置、POST 请求(部分命令如 snapshot 需要)、命令的完整字段含义、与 Prometheus 端点(第 63 篇)的关系'],
)
