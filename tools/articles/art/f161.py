from lib import *
S = SS('f161')
R = J('f161'); ap = R['app']; bc = R['by_count']
steps = [
    step(f"应用侧统计:用 before_cursor_execute 与 after_cursor_execute 记录每条语句的耗时,按「去掉参数的语句文本」聚合(次数、总耗时、平均、最大),再用 before_request 里设置的 g.ep 记下它来自哪个端点。跑 40 次 /user、5 次 /search、20 次 /report(PostgreSQL,30 万行订单表):总耗时排第一的是 /search 里的 count(*) ... LIKE '%9999%'(没有索引能用的全表扫描),{ap[0][1]} 次共 {ap[0][2]:.1f} ms、最大 {ap[0][3]:.1f} ms;第二名是 /report 里按 id 查金额的语句,{ap[1][1]} 次共 {ap[1][2]:.1f} ms,单次只要约 0.08 ms,但次数多。按总耗时排,一条慢语句和一条被调用很多次的快语句都会上榜。", t=tl(S(1)), done=lidx(S(1), 'search', 'report'), kv=KV([['聚合键', '去掉参数的语句文本'], ['总耗时排序', '同时暴露慢语句与高频语句']], ['总耗时排序'])),
    step(f"按调用次数排序:{bc[0][1]} 次的 SELECT \"order\".amount ... WHERE \"order\".id = ... 排第一,全部来自 /report 这个端点——典型的 N+1(每个订单查一次,第 87 篇)。次数异常大、单次又很快的语句,是改成批量查询的候选;它不一定出现在「最慢」的榜单上。", t=tl(S(2)), done=lidx(S(2), '600 次'), kv=KV([['按次数排', '暴露 N+1'], ['来源端点', 'g.ep 让你知道该改哪个视图']], ['按次数排'])),
    step("服务端统计 pg_stat_statements(要在 postgresql.conf 里加载 shared_preload_libraries 再 create extension):按总耗时排,第一名同样是 count(*) ... LIKE(5 次、64.5 ms、平均 12.9 ms),与应用侧基本一致;但第二、三名不同——那条按 id 查金额的语句在数据库里 600 次总共只有 1.0 ms(平均 0.002 ms),而应用侧记到的是 49.6 ms(平均 0.08 ms):差的部分是网络往返与 Python 驱动的开销。数据库里不慢的语句,在应用里可能因为次数多而慢。", t=tl(S(3)), done=lidx(S(3), 'calls', '5|64.5'), mark=lidx(S(3), '600|1.0'), kv=KV([['数据库侧', '只含服务端执行时间'], ['应用侧', '再加上往返与驱动开销'], ['两者结合', '分别找出慢语句与高频语句']], ['两者结合'])),
]
A = mkartf('f161', 161, 'Flask,慢SQL,pg_stat_statements,SQLAlchemy,N+1,真实验证,动画演示',
    '在真实的 PostgreSQL 上做慢 SQL 统计:应用侧用 SQLAlchemy 游标事件按去参数的语句聚合并标出端点、按总耗时找出全表扫描的 count(*) LIKE、按次数找出 600 次的 N+1 语句,再对照 pg_stat_statements 的服务端统计(同一条 N+1 语句数据库里共 1.0 ms 而应用侧是 49.6 ms)。',
    '怎么找出最该优化的 SQL?按最慢排还是按总耗时排?应用侧统计与数据库侧统计各看到什么?这篇用同一组请求,把两边的榜单摆在一起对比。',
    [('600 次', '/report 里一条按 id 查金额的语句被调用的次数(N+1)'), (f'{ap[0][2]:.0f} ms', '全表扫描的 count(*) LIKE 在 5 次调用里的总耗时'), ('49.6 对 1.0 ms', '那条 N+1 语句在应用侧与数据库侧记到的总耗时')],
    [('应用侧按总耗时', '<p>上一篇:<a href="flask-request-timing.html">请求耗时统计</a>;下一篇:<a href="flask-flask-profiler.html">Flask Profiler</a>。</p><p>第 96 篇讲过 SQLAlchemy 查询日志与慢查询事件,这一篇讲怎么聚合出榜单。</p>'), ('按次数排序', None), ('数据库侧的统计', '<p>pg_stat_statements 是自己起的 PostgreSQL 实例里启用的(shared_preload_libraries),不影响你自己的数据库。</p>')],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、自己起的 PostgreSQL(非默认端口,启用 pg_stat_statements)', '没有验证:执行计划(EXPLAIN ANALYZE)的分析、pg_stat_statements 在长期运行下的重置与存储、慢查询日志 log_min_duration_statement、auto_explain、MySQL 的 performance_schema'], '慢 SQL 统计')
