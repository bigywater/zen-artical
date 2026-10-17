from lib import *
R = J('d43'); sq = R['seq']; lim = R['limit']
labs = list(sq)
steps = [
    step(f"同一条 keep-alive 连接连续发 300 个请求(gunicorn 1 worker × 1 线程),延迟中位数:CONN_MAX_AGE=0(默认){sq[labs[0]]['med']:.2f} ms、=60 {sq[labs[1]]['med']:.2f} ms、=None {sq[labs[2]]['med']:.2f} ms;p99 分别 {sq[labs[0]]['p99']:.2f} / {sq[labs[1]]['p99']:.2f} / {sq[labs[2]]['p99']:.2f} ms。持久连接把每请求的延迟压到默认的约 1/5。", b=bars([[f'CONN_MAX_AGE={k} 中位(ms)', sq[k]['med'], f"{sq[k]['med']:.2f}"] for k in labs], sq[labs[0]]['med'] * 1.1, mark=[0], done=[1, 2]), kv=KV([['默认', f"{sq[labs[0]]['med']:.2f} ms"], ['持久连接', f"{sq[labs[1]]['med']:.2f} ms"]], ['持久连接'])),
    step(f"用到的数据库连接数:默认 300 个请求用了 {sq[labs[0]]['pids']} 个不同的连接;=60 与 =None 都只用 1 个。请求全部结束后数据库端还剩:默认 {sq[labs[0]]['left']} 个,持久连接 {sq[labs[1]]['left']} 个(=60 是「最多存活 60 秒」,不是立刻关)。", b=bars([[f'CONN_MAX_AGE={k} 用到的连接数', sq[k]['pids'], str(sq[k]['pids'])] for k in labs], sq[labs[0]]['pids'], mark=[0], done=[1, 2]), kv=KV([['CONN_MAX_AGE=0', f"{sq[labs[0]]['pids']} 个连接 / 300 请求"], ['=60 / None', '1 个连接']], ['CONN_MAX_AGE=0'])),
    step(f"代价:数据库 max_connections=30 时,服务 A(4 worker × 4 线程,CONN_MAX_AGE=None)被打满后占 {lim['a_conns']} 个持久连接、0 个错误;再开一个同样配置的服务 B,数据库回 FATAL: sorry, too many clients already,B 的请求出现 500({lim['b_errs']}),连 psql 也连不上。持久连接的总数 = 所有服务的 worker × 线程,必须放在数据库的连接上限之内。", n=fl([['服务 A(16 线程)', f"{lim['a_conns']} 个持久连接"], ['服务 B(16 线程)', '请求 500'], ['数据库 max_connections=30', 'too many clients already']], done=[0], mark=[1, 2]), kv=KV([['持久连接的账', 'worker × 线程 × 服务个数 ≤ max_connections']], ['持久连接的账'])),
]
A = dict(
    n=43, series='django', tags='Django,CONN_MAX_AGE,持久连接,PostgreSQL,真实验证,动画演示',
    desc=f'量 CONN_MAX_AGE:300 个请求中位延迟 {sq[labs[0]]["med"]:.2f} ms(默认)→ {sq[labs[1]]["med"]:.2f} ms(60 秒);默认 300 个请求 300 个连接,持久连接只用 1 个;但持久连接数 = worker × 线程,max_connections=30 的库上开第二个服务就出现 too many clients。',
    lead='CONN_MAX_AGE 能省多少?代价是什么?这篇在 gunicorn + PostgreSQL 上分别量 0 / 60 / None 三种设置的延迟和连接数,再故意把数据库连接上限调到 30,看第二个服务起来之后会发生什么。',
    facts=[(f'{sq[labs[0]]["med"]:.2f} → {sq[labs[1]]["med"]:.2f} ms', '300 个请求的中位延迟:CONN_MAX_AGE=0 → 60(本机回环)'), (f'{sq[labs[0]]["pids"]} → 1', '300 个请求用到的数据库连接数'), ('too many clients', '持久连接总数超过 max_connections 时,新请求得到 500')],
    body=[
        sec('延迟与连接数', '', term('', blk('d43', 1)), '<p>本机回环上,每请求建连的代价大约 2 ms(认证 + 后端进程 fork);持久连接把它省掉。真实网络、TLS、连接认证更复杂时,这个差距会更大(本文没有测)。</p>'),
        sec('持久连接的代价', '', term('', blk('d43', 2)), '<p>每个 worker × 线程都会各自占一个连接,并且在空闲时也占着。服务实例多了(扩容、滚动发布时新旧实例并存)很容易超过数据库的 <code>max_connections</code>。解决办法是限制线程/进程数,或者在应用和数据库之间放连接池(第 134 篇)。</p>'),
        sec('分步演示:延迟与连接', '', demo('CONN_MAX_AGE', [('b', 'bars', '数据'), ('n', 'flow', '连接账'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。gunicorn 26.2;PostgreSQL 16.15(本机临时实例,端口 9413,max_connections=30);延迟取 300 个请求的中位数与 p99', '没有验证:CONN_HEALTH_CHECKS、数据库端超时断开连接后的恢复、pgbouncer 等外部连接池、其它数据库(MySQL)的建连代价、跨机器网络与 TLS 的建连代价'],
)
