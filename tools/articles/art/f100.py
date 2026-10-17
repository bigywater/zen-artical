from lib import *
S = SS('f100')
R = J('f100'); rs = R['restart']; dn = R['down']; rc = R['recover']
steps = [
    step(f"数据库重启之后,连接池里 5 个空闲连接都变成了坏连接(重启前池状态是 Connections in pool: 5)。默认配置接着发 8 个串行请求,状态码是 {rs['默认(无 pre_ping)']}:只有第一个失败,不是 5 个——SQLAlchemy 检测到断线(connection_invalidated)之后把池里其余旧连接都标记成失效、下次借出时换新的。pool_pre_ping=True 时 8 个全部成功,失败 0 个。", b=bars([['默认 失败请求数', 1, '1'], ['pre_ping 失败请求数', 0.05, '0']], 5, mark=[0], done=[1]), t=tl(S(1)), mark=lidx(S(1), '[默认(无 pre_ping)] 重启后'), done=lidx(S(1), '[pool_pre_ping=True] 重启后'), kv=KV([['默认', '重启后第一个请求失败'], ['pre_ping=True', '0 个失败']], ['pre_ping=True'])),
    step("失败的那个请求返回的是我们的 errorhandler 映射出来的 503:{\"error\":\"db unavailable\",\"invalidated\":true}——OperationalError 上的 connection_invalidated 为 True,说明这是断线类的错误,可以重试;不是 SQL 写错了。", t=tl(S(2)), mark=lidx(S(2), '第一个请求'), kv=KV([['e.connection_invalidated', 'True = 连接已失效,重试有意义']], ['e.connection_invalidated'])),
    step(f"数据库停机期间:请求 {dn[2]:.0f} ms 就失败(连接被拒绝,503,connection_invalidated 为 false——这是「连不上」而不是「连接断了」);启动数据库之后第 {rc[0]} 次请求就恢复了(自 pg_ctl start 返回起 {rc[1]:.0f} ms),应用没有重启,连接池自己重新建连接。", t=tl(S(3)), mark=lidx(S(3), '数据库停机时'), done=lidx(S(3), '启动数据库之后'), kv=KV([['停机', f'约 {dn[2]:.0f} ms 内快速失败'], ['恢复', '不用重启应用']], ['恢复'])),
    step("请求里自己重试一次:捕获 DBAPIError,只在 e.connection_invalidated 为真时 rollback 并重试一次;数据库刚重启、没开 pre_ping 的默认配置下,这个请求返回 200「ok after 2 attempt(s)」。", t=tl(S(4)), done=lidx(S(4), '默认配置、数据库刚重启'), kv=KV([['重试条件', 'connection_invalidated 为真'], ['次数', '一次就够']], ['重试条件'])),
    step("请求执行到一半时连接被服务端杀掉(pg_terminate_backend):正在执行的那个请求失败(503,invalidated=true)——pre_ping 只在「借出连接时」探测,救不了正在用的连接;紧接着的下一个请求是 200。执行中的事务丢了,是否能安全重试取决于这次请求有没有副作用(见第 107 篇 Idempotency-Key)。", t=tl(S(5)), mark=lidx(S(5), '正在执行的请求'), done=lidx(S(5), '下一个请求'), kv=KV([['借出时探测', 'pre_ping 能处理'], ['执行中被杀', '这个请求会失败']], ['执行中被杀'])),
    step("pool_recycle=1(秒):隔 1.3 秒再查,pg_backend_pid() 变了——旧连接超龄后在借出时被换成新连接;没有 pool_recycle 时前后是同一个连接。recycle 是按连接年龄换,不探测连接是否还活着;用来避开防火墙或数据库按空闲时长杀连接的情况。", t=tl(S(6)), mark=lidx(S(6), 'pool_recycle=1'), done=lidx(S(6), '没有 pool_recycle'), kv=KV([['pool_recycle', '按年龄换连接'], ['pool_pre_ping', '借出时探测是否存活']], ['pool_recycle'])),
]
A = mkartf('f100', 100, 'Flask,SQLAlchemy,断线重连,pool_pre_ping,真实验证,动画演示',
    '在真实的 PostgreSQL 上重启与停掉数据库,实测断线后的恢复:默认配置重启后只有第一个请求失败(池整体失效),pool_pre_ping 时 0 个失败;停机时快速 503、启动后第一次请求就恢复;connection_invalidated 判断能否重试;执行中被杀的请求 pre_ping 救不了;pool_recycle 按年龄换连接。',
    '数据库重启或网络闪断之后,应用要重启吗?会有几个请求失败?pool_pre_ping 和 pool_recycle 各管什么?这篇真的把 PostgreSQL 重启、停机、杀连接,把每种情况的结果量出来。',
    [('1 → 0', '数据库重启后失败的请求数:默认配置与 pool_pre_ping=True'), ('不用重启应用', '数据库恢复之后,连接池自己重新建连接'), ('connection_invalidated', '区分断线类错误(可重试)与 SQL 错误的标志')],
    [('重启之后', '<p>上一篇:<a href="flask-sqlite-vs-postgresql.html">SQLite 与 PostgreSQL 行为差异</a>;下一篇:<a href="flask-json-api.html">Flask 实现 JSON API</a>。</p>'), ('失败请求的样子', None), ('停机与恢复', '<p>这一节我自己对 pg_ctl 的调用也踩过坑:不带 -o 启动会去用默认端口,所以所有重启命令都显式带了端口与 socket 目录。</p>'), ('请求里重试', None), ('执行中被杀', None), ('pool_recycle', None)],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、psycopg 3.3.6、自己起的 PostgreSQL(非默认端口),用 pg_ctl restart、stop、start 与 pg_terminate_backend 制造断线', '没有验证:网络层面的假死(丢包而不是连接被拒绝)与 TCP keepalive、读写分离下的主从切换、云数据库的故障转移、断线期间长事务的数据一致性、DNS 变化后的重连'], '数据库断线恢复', panels=[('t', 'term', '实验输出'), ('b', 'bars', '失败请求数'), ('kv', 'kv', '要点')])
