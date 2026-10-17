from lib import *
R = J('d134'); s = R['serial']; e = R['exhaust']
def S(k): return [l for l in out('d134').split('== ')[k].splitlines()[1:] if l.strip()]
k0, k1, k2 = list(s.keys())
x1, x2 = list(e.keys())
steps = [
    step(f"2 个 sync worker,200 个串行请求(每个 1 次查询,预热 10 个请求后开始计数):CONN_MAX_AGE=0(默认)数据库那边新建了 {s[k0]['conns']} 次连接,中位延迟 {s[k0]['med']:.2f} ms;CONN_MAX_AGE=60 新建 {s[k1]['conns']} 次,{s[k1]['med']:.2f} ms;连接池(OPTIONS pool)新建 {s[k2]['conns']} 次,{s[k2]['med']:.2f} ms。默认配置每个请求都新建一条数据库连接。", t=tl(S(1)), b=bars([['CONN_MAX_AGE=0', s[k0]['med'], f"{s[k0]['med']:.2f} ms"], ['CONN_MAX_AGE=60', s[k1]['med'], f"{s[k1]['med']:.2f} ms"], ['连接池', s[k2]['med'], f"{s[k2]['med']:.2f} ms"]], 2.8, mark=[0], done=[1, 2]), kv=KV([['CONN_MAX_AGE=0', '每请求新建连接,慢约 2 ms'], ['持久连接 / 连接池', '复用连接']], ['CONN_MAX_AGE=0'])),
    step(f"连接数的另一面:max_connections=20 的 PostgreSQL,gunicorn gthread 2 进程 × 20 线程,同时 40 个请求(每个持有连接 0.5 s)。CONN_MAX_AGE=60:每个线程一条持久连接,要 40 条,结果 {e[x1]['codes']}——20 个成功、20 个 500,PostgreSQL 日志里是「FATAL: sorry, too many clients already」。", t=tl(S(2)[:1] + S(2)[2:]), mark=[0], b=bars([['成功', e[x1]['codes'].get('200', e[x1]['codes'].get(200, 0)), '20'], ['失败(500)', e[x1]['codes'].get('500', e[x1]['codes'].get(500, 0)), '20']], 40, mark=[1], done=[0]), kv=KV([['持久连接', '连接数 = 线程数,会撑爆数据库']], ['持久连接'])),
    step(f"同样的压力用连接池(每个进程 min 2、max 4):40 个请求全部 200,总耗时 {e[x2]['total']:.0f} ms(对比持久连接的 {e[x1]['total']:.0f} ms 里有一半是失败)。连接池把每个进程的连接数限制在 4 条,多出来的请求排队等连接——慢一些,但不会被数据库拒绝。", t=tl(S(2)[1:2]), done=[0], b=bars([['持久连接(一半失败)', e[x1]['total'], f"{e[x1]['total']:.0f} ms"], ['连接池(全部成功)', e[x2]['total'], f"{e[x2]['total']:.0f} ms"]], 3100, mark=[0], done=[1]), kv=KV([['连接池', '限制连接数,请求排队']], ['连接池'])),
]
A = dict(
    n=134, series='django', tags='Django,连接池,PostgreSQL,CONN_MAX_AGE,部署,真实验证,动画演示',
    desc=f'连接池:默认 CONN_MAX_AGE=0 每个请求新建数据库连接({s[k0]["conns"]}/200 次,中位 {s[k0]["med"]:.2f} ms),持久连接与连接池都不再新建({s[k1]["med"]:.2f} / {s[k2]["med"]:.2f} ms);max_connections=20 时 40 线程持久连接有 20 个请求被拒,连接池全部成功。',
    lead='Django 默认每个请求新建一条数据库连接。持久连接(CONN_MAX_AGE)和 Django 的原生连接池(OPTIONS pool)分别带来什么?它们又会在什么时候出问题?这篇在自己起的 PostgreSQL 上数连接、量延迟,再把连接数压到上限。',
    facts=[(f'{s[k0]["conns"]} / 200', '默认配置下每个请求新建一次数据库连接(预热后计数)'), (f'{s[k0]["med"]:.2f} → {s[k2]["med"]:.2f} ms', '请求中位延迟:新建连接 → 连接池'), ('20 个失败', '持久连接 + 40 个线程撞上 max_connections=20,连接池则全部成功')],
    body=[
        sec('每个请求新建连接的代价', '', term('', blk('d134', 1)), '<p>新建连接的次数来自 PostgreSQL 日志里的 <code>connection authorized</code> 行(排除了 psql 自己)。本机回环、fsync 关闭,所以绝对值很小,生产环境里 TLS 与网络延迟会让这个差距更大(本文没有测)。</p>'),
        sec('持久连接撞上连接数上限', '', term('', blk('d134', 2)), '<p>持久连接是每个线程一条,<code>线程数 × 进程数</code> 就是最多需要的连接数,它必须小于数据库的 <code>max_connections</code>(还要给迁移、监控等留出空位)。连接池把「同时使用的连接数」和「线程数」解耦。</p>'),
        sec('代价与边界', '', '<p>连接池要求 <code>psycopg</code> 3 加 <code>psycopg_pool</code>,本文只测了 <code>CONN_MAX_AGE</code> 与连接池各自单独使用,没有测同时设置。使用 pgbouncer 事务级池化时的注意事项、服务端游标的兼容性,本文没有测。</p>'),
        sec('分步演示', '', demo('连接池', [('t', 'term', '输出'), ('b', 'bars', '数字'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。自己起的临时 PostgreSQL 16(log_connections=on、max_connections=20、fsync=off);gunicorn 26.2.0;psycopg 3.3.6 + psycopg_pool 3.3.3;连接池 min_size 2 / max_size 4(每进程)', '没有验证:pgbouncer、连接池的 timeout / 健康检查、CONN_HEALTH_CHECKS、MySQL、异步视图下的连接行为(第 115 篇)、长事务占用连接的影响、生产环境的网络延迟'],
)
