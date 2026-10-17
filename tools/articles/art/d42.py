from lib import *
R = J('d42'); df = R['default']; th = R['threads']
steps = [
    step(f"连接是惰性的:一个还没有任何查询的请求里 connection.connection 是 {R['nodb']['has_conn']}(还没建立)。默认 CONN_MAX_AGE=0,连续 6 个请求,每个请求里 pg_backend_pid() 都不同:{df['pids']};每个请求开始时 connection.connection 都是 None({all(df['none'])})。", t=tl([f"请求 {i+1}: pg_backend_pid = {p}" for i, p in enumerate(df['pids'])], mark=list(range(6))), kv=KV([['CONN_MAX_AGE=0', '每个请求一个新连接']], ['CONN_MAX_AGE=0'])),
    step(f"请求结束后数据库端还剩 {df['left']} 个来自应用的连接——请求结束时(request_finished 信号)Django 把连接关掉了。所以默认配置下每个请求都要付一次「建连 + 认证」的代价(第 43 篇量它)。", n=fl([['请求开始', '连接 = None'], ['第一次查询', '建立连接'], ['请求结束', '关闭连接']], done=[1, 2]), kv=KV([['请求结束后', f"{df['left']} 个连接"]], ['请求结束后'])),
    step(f"连接是线程局部的:CONN_MAX_AGE=None(不关闭),1 个 worker、4 个线程,40 个并发请求用到了 {th['pids']} 个不同的数据库连接、{th['threads']} 个处理线程——每个线程一个连接,互不共享。请求全部结束后数据库端仍保持 {th['left']} 个连接;服务停止后回到 0。", b=bars([['处理线程数', th['threads'], str(th['threads'])], ['数据库连接数', th['pids'], str(th['pids'])], ['结束后仍保持的连接', th['left'], str(th['left'])]], 5, done=[0, 1, 2]), kv=KV([['持久连接', '每个线程一个,不共享']], ['持久连接'])),
]
A = dict(
    n=42, series='django', tags='Django,数据库连接,PostgreSQL,gunicorn,真实验证,动画演示',
    desc=f'在 gunicorn + PostgreSQL 上观察 Django 的数据库连接生命周期:连接是惰性的;默认每个请求一个新的数据库后端进程(6 个请求 6 个 pid);请求结束连接被关闭;连接是线程局部的(4 个线程 = {th["pids"]} 个连接);CONN_MAX_AGE=None 时连接在请求结束后仍保持。',
    lead='Django 什么时候连数据库?什么时候断?多线程时连接是共享的吗?这篇在真实的 gunicorn 下,用 PostgreSQL 的 pg_backend_pid() 和 pg_stat_activity 直接观察。',
    facts=[('惰性', '第一次查询才建立连接;没有查询的请求里 connection.connection 是 None'), ('每请求一个', '默认 CONN_MAX_AGE=0:6 个连续请求 6 个不同的 pg_backend_pid,请求结束连接关闭'), ('线程局部', f'4 个处理线程 → {th["pids"]} 个数据库连接,互不共享')],
    body=[
        sec('默认:每个请求一个连接', '', term('', blk('d42', 1)), '<p>用 <code>pg_backend_pid()</code> 看数据库端处理这条连接的后端进程:每个请求都不一样,说明每次都是新连接。请求结束时连接被关闭,数据库端只剩 0 个。</p>'),
        sec('线程局部的连接', '', term('', blk('d42', 2)), '<p><code>connection</code> 是 <code>connections[DEFAULT_DB_ALIAS]</code> 的代理,内部是线程局部存储。所以「连接数 = 处理线程数(× worker 数)」——线程池的大小直接决定持久连接的上限(第 43 篇看到它的后果)。</p>'),
        sec('分步演示:连接的一生', '', demo('数据库连接生命周期', [('t', 'term', '观察'), ('n', 'flow', '过程'), ('b', 'bars', '数量'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。gunicorn 26.2 1 worker × 1 线程 / 4 线程;PostgreSQL 16.15(本机临时实例,端口 9411);连接数用 pg_stat_activity 统计', '没有验证:ASGI(uvicorn)下的连接模型、异步视图里的连接、多数据库别名、connection.close() / close_if_unusable_or_obsolete 的细节、请求外(管理命令、Celery)的连接生命周期'],
)
