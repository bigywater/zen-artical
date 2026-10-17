from lib import *
S = SS('f88')
R = J('f88'); cx = R['ctx']
steps = [
    step(f"同一个 session 里,用两种不同的条件(id=1 与 name='u0')查同一行,得到的是同一个 Python 对象(a is b 为 True);第二次查询仍然发了 {R['same'][1]} 条 SQL,只是返回已有对象而不是新建。换一个 session 查同一行得到的是不同对象。identity key 是 (类, (主键,), None)。", t=tl(S(1)), done=lidx(S(1), 'a is b', '不同的 session', 'identity key'), kv=KV([['同一个 session', '一行 = 一个对象'], ['不同 session', '不同对象']], ['同一个 session'])),
    step(f"session.get(User, 1):已经加载过的主键 0 条 SQL(直接从身份映射取),没加载过的发 1 条,再 get 一次 0 条;不存在的主键 999 每次都发 1 条(不存在的结果不缓存)。", t=tl(S(2)), done=lidx(S(2), '已经加载过', '再 get'), mark=lidx(S(2), '没加载过', '不存在'), kv=KV([['命中身份映射', '0 条 SQL'], ['不存在的主键', '每次 1 条']], ['命中身份映射'])),
    step(f"身份映射是弱引用的:加载 5 个对象后 identity_map 大小是 {R['wk1']};del 掉引用并 gc 后是 {R['wk2']};改了一个对象(dirty)再丢引用,gc 后仍是 {R['wk3']}——被修改的对象由 session 强引用,直到 flush。所以它不是一个会无限增长的缓存,也不能当缓存用。", t=tl(S(3)), done=lidx(S(3), '加载 5 个', 'del 掉'), mark=lidx(S(3), '改了一个'), kv=KV([['没人引用', '被回收'], ['被修改', 'session 强引用']], ['没人引用'])),
    step(f"代价是看到旧数据:session A 读到 score=0;另一个 session 把它改成 99 并提交后,session A 重新查询得到的仍是同一个对象,score 还是 {R['stale']}。execution_options(populate_existing=True) 的查询得到 {R['populate']};另一个 session 又改成 100 后,session.refresh(a) 得到 {R['refresh']};再改成 101,session.expire(a) 之后的下一次读取是 {R['expire']}。", t=tl(S(4)), mark=lidx(S(4), '重新查询:a2.score'), done=lidx(S(4), 'populate_existing', 'refresh', 'expire'), kv=KV([['重新查询', '不会刷新已加载的对象'], ['populate_existing', '覆盖已加载对象'], ['refresh / expire', '手动刷新']], ['重新查询'])),
    step("同一个主键的两个对象:session 里已经有 id=1 的 persistent 对象时,再 add 一个 id=1 的新对象并 flush,是数据库唯一约束报 IntegrityError「UNIQUE constraint failed: user.id」——SQLAlchemy 把它当成一次新的 INSERT。", t=tl(S(5)), mark=lidx(S(5), 'IntegrityError'), kv=KV([['add 重复主键', 'flush 时 IntegrityError']], ['add 重复主键'])),
    step(f"Flask 里的边界:每个请求(应用上下文)一个新 session,两个请求里 get 到的不是同一个对象(False);同一个请求里连续 get 两次但不保留返回值,发了 {cx[0]} 条 SQL(第一次的对象没人引用被回收了),保留返回值再 get 则只发 {cx[1]} 条。(第一次运行时我把请求放在外层应用上下文里,两个请求复用了同一个上下文,结果成了 True——测试里在 with app.app_context() 里调 test_client 会遇到这个。)", t=tl(S(6)), done=lidx(S(6), '保留第一次'), mark=lidx(S(6), '两个请求里', '不保留返回值'), kv=KV([['请求之间', '不同的 session 与对象'], ['请求之内', '同一行一个对象,但弱引用']], ['请求之间'])),
]
A = mkartf('f88', 88, 'Flask,SQLAlchemy,Identity Map,Session,真实验证,动画演示',
    f'实测 SQLAlchemy 的身份映射:同一个 session 里同一行永远是同一个对象、session.get 命中时 0 条 SQL、弱引用与被修改对象的强引用、重新查询看到旧数据(stale={R["stale"]})以及 populate_existing 与 refresh 与 expire、重复主键、Flask 里请求之间不共享。',
    'SQLAlchemy 里同一行数据会不会变成两个对象?session.get 什么时候不发 SQL?为什么另一个会话改了数据我这里却看不到?这篇用 SQLite 与两个 session 把身份映射的行为逐个量出来。',
    [('0 条', 'session.get 命中身份映射时发出的 SQL'), ('弱引用', '没人引用也没被修改的对象会从身份映射里消失'), (f'{R["stale"]} → {R["populate"]}', '另一个会话改了数据后,普通重新查询与 populate_existing 读到的 score')],
    [('一行一个对象', '<p>上一篇:<a href="flask-n-plus-one.html">N+1 查询问题</a>;下一篇:<a href="flask-flush-commit.html">Session Flush 与 Commit</a>。</p>'), ('session.get', None), ('弱引用', None), ('旧数据的代价', None), ('重复主键', None), ('Flask 里的边界', None)],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、SQLite 文件库(两个 session 各自连接)', '没有验证:PostgreSQL 的 READ COMMITTED 之外的隔离级别对「看到旧数据」的影响、with_for_update 与身份映射的交互、跨线程共享对象、subclass 继承映射下的身份键'], 'SQLAlchemy Identity Map')
