import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import re, queue as Q, concurrent.futures, pymysql
from txl import MySQL
from opentelemetry import trace, propagate, context as otctx
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
import opentelemetry.sdk.version as otv
tee('v78'); reset()
print(f'数据库调用的追踪:慢查询怎么定位到调用链。自己起的 MySQL(版本见下)+ pymysql + OpenTelemetry Python SDK {otv.__version__}(手写的数据库 span,没有用自动插桩)。(一)把 traceparent 放进 SQL 注释,让服务端的慢查询日志能对上调用链;(二)performance_schema 里能不能按注释找到语句;(三)N+1 查询在 trace 里的样子;(四)db.statement 属性写字面值还是占位符;(五)连接池等待有没有算进数据库 span')
M = MySQL('v78', opts=['--performance-schema=ON', '--slow-query-log=ON', '--long-query-time=0.08', '--log-output=TABLE']).start()
ver = M.q('select version()')[0][0]; print(f'  MySQL {ver}')
M.q('create database shop'); M.q('create table orders(id int primary key, user_id int, amount decimal(10,2))', db='shop'); M.q('create table items(id int auto_increment primary key, order_id int, sku int, qty int, key(order_id))', db='shop'); M.q('create table users(id int primary key, email varchar(100), key(email))', db='shop')
c = M.conn('shop'); cur = c.cursor(); rnd = random.Random(3)
cur.executemany('insert into orders values (%s,%s,%s)', [(i, rnd.randrange(500), round(rnd.uniform(5, 500), 2)) for i in range(2000)])
cur.executemany('insert into items(order_id, sku, qty) values (%s,%s,%s)', [(i % 2000, rnd.randrange(150), rnd.randrange(1, 5)) for i in range(30000)])
cur.executemany('insert into users values (%s,%s)', [(i, f'user{i}@example.com') for i in range(2000)]); c.commit(); c.close()
tp = TracerProvider(); mem = InMemorySpanExporter(); tp.add_span_processor(SimpleSpanProcessor(mem)); tracer = tp.get_tracer('db')
def db(conn, sql, args=None, comment=False, stmt=None):
    with tracer.start_as_current_span('db.query', kind=SpanKind.CLIENT, attributes={'db.system': 'mysql', 'db.statement': stmt or sql}) as sp:
        s = sql
        if comment:
            h = {}; propagate.inject(h); s = f"/*traceparent='{h['traceparent']}'*/ " + sql
        with conn.cursor() as cur:
            cur.execute(s, args); return cur.fetchall()
SLOW = 'select count(*) from items a join items b on a.sku = b.sku where a.order_id < %s'
conn0 = M.conn('shop'); t = time.perf_counter(); db(conn0, SLOW, (2000,)); dt = time.perf_counter() - t; print(f'  热身:慢查询(items 自连接,order_id < 2000)耗时 {dt * 1000:.0f} ms'); conn0.close(); mem.clear()

# ============ 一 ============
print('== 一:慢查询日志与调用链。服务端设置 long_query_time = 0.08 s,慢日志写到表 mysql.slow_log。3 个端点(e1、e2、e3)各处理 40 个请求,6 个线程并发,每个请求执行同一条慢 SQL(只有 order_id 的字面值不同)。(a)SQL 前面带 /*traceparent=…*/ 注释;(b)不带注释。对慢日志里的每一行,试着对应到客户端的某一个 db.query span:有注释的按 trace_id 对应;没有注释的按 “SQL 文本规整后相同(把数字和占位符都换成 N) + 时间相近” 对应,统计候选 span 的个数')
def endpoint_work(args):
    ep, i, comment = args; conn = pools.get()
    try:
        with tracer.start_as_current_span(f'GET /{ep}', kind=SpanKind.SERVER, attributes={'ep': ep}):
            db(conn, SLOW, (1600 + 200 * (i % 3),), comment=comment)
    finally: pools.put(conn)
def run_mode(comment):
    global pools
    pools = Q.Queue()
    for _ in range(6): pools.put(M.conn('shop'))
    M.q('truncate mysql.slow_log'); mem.clear()
    jobs = [(f'e{k % 3 + 1}', i, comment) for k in range(3) for i in range(40)]; random.Random(1).shuffle(jobs)
    with concurrent.futures.ThreadPoolExecutor(6) as ex: list(ex.map(endpoint_work, jobs))
    time.sleep(0.5); rows = M.q('select start_time, query_time, convert(sql_text using utf8mb4) from mysql.slow_log'); spans = list(mem.get_finished_spans())
    while not pools.empty(): pools.get().close()
    return rows, spans
def norm(sql): return re.sub(r'\d+|%s', 'N', re.sub(r'/\*.*?\*/', '', sql)).strip().lower()
res = {}; REF = {'ref': 'end'}; offs = {}
for comment in (True, False):
    rows, spans = run_mode(comment); dbs = [s for s in spans if s.name == 'db.query']; byt = {format(s.context.trace_id, '032x'): s for s in dbs}
    uniq = amb = none = 0; cands = []; o_end = []; o_start = []
    for st, qt, sql in rows:
        st_ns = int(st.replace(tzinfo=None).timestamp() * 1e9) if st.tzinfo is None else int(st.timestamp() * 1e9)
        m = re.search(r"traceparent='00-([0-9a-f]{32})-", sql)
        if comment and m:
            s_ = byt.get(m.group(1))
            if s_ is not None: uniq += 1; cands.append(1); o_end.append((st_ns - s_.end_time) / 1e6); o_start.append((st_ns - s_.start_time) / 1e6)
            else: none += 1
            continue
        ref = (lambda s_: s_.end_time) if REF['ref'] == 'end' else (lambda s_: s_.start_time)
        cs = [s_ for s_ in dbs if norm(s_.attributes['db.statement']) == norm(sql) and abs(ref(s_) - st_ns) <= 30e6]
        cands.append(len(cs))
        if len(cs) == 1: uniq += 1
        elif len(cs) > 1: amb += 1
        else: none += 1
    if comment:
        offs = (statistics.median(o_end), statistics.median(o_start))
        REF['ref'] = 'end' if abs(offs[0]) < abs(offs[1]) else 'start'
    res[comment] = (len(rows), uniq, amb, none, statistics.mean(cands) if cands else float('nan'), max(cands) if cands else 0)
print(f'  慢日志表里 start_time 相对客户端 db.query span 的偏移(用带注释的行精确对应后算出,中位数):相对 span 的结束时刻 {offs[0]:+.1f} ms,相对 span 的开始时刻 {offs[1]:+.1f} ms;因此没有注释时用 “慢日志时间 ≈ span 的{"结束" if REF["ref"] == "end" else "开始"}时刻 ± 30 ms” 且规整后的 SQL 文本相同来找候选 span')
table([('(a)带 traceparent 注释', *res[True][:4], f'{res[True][4]:.1f}', res[True][5]), ('(b)不带注释', *res[False][:4], f'{res[False][4]:.1f}', res[False][5])], ['配置', '慢日志行数', '唯一对应到一个 span', '有多个候选 span(对应不上)', '没有候选', '平均候选 span 数', '最多候选 span 数'])
print('  有注释时,慢日志里的 SQL 文本带着 trace_id,直接对应到那一次调用;没有注释时只能靠 SQL 文本和时间推断,并发请求执行同一条 SQL(只有字面值不同)时,同一时刻有多个候选,分不出是哪一个请求')

# ============ 二 ============
print('== 二:performance_schema。语句不够慢、进不了慢日志时,还能按注释找到吗?打开 events_statements_history_long,执行 30 次快查询(按主键查一行,带 traceparent 注释),然后在 performance_schema 里按 trace_id 找回这些语句,看 SQL_TEXT 和 TIMER_WAIT')
M.q("update performance_schema.setup_consumers set enabled='YES' where name='events_statements_history_long'"); M.q("update performance_schema.setup_instruments set enabled='YES', timed='YES' where name like 'statement/%'")
conn = M.conn('shop'); tids = []; mem.clear()
for i in range(30):
    with tracer.start_as_current_span('GET /fast'):
        db(conn, 'select * from orders where id = %s', (i,), comment=True); tids.append(format(trace.get_current_span().get_span_context().trace_id, '032x'))
conn.close()
found = 0; ex_row = None
for tid in tids:
    r = M.q("select digest_text, timer_wait/1e9, convert(sql_text using utf8mb4) from performance_schema.events_statements_history_long where sql_text like %s", (f'%{tid}%',))
    if r: found += 1; ex_row = ex_row or r[0]
slow_rows = M.q('select count(*) from mysql.slow_log')[0][0]
print(f'  30 次快查询里能按 trace_id 在 performance_schema 里找到的有 {found} 次;其中一条:digest_text = {ex_row[0]!r},TIMER_WAIT = {ex_row[1]:.3f} ms,SQL_TEXT 开头 {ex_row[2][:80]!r};这些快查询不在慢日志里(慢日志表里现有 {slow_rows} 行,都是上一节的慢查询)')
print('  慢日志只记录超过 long_query_time 的语句;performance_schema 的语句历史能记录所有语句(受表大小限制,会被覆盖),SQL 注释里的 trace_id 让两者都能和调用链对上')

# ============ 三 ============
print('== 三:N+1。“列出 20 个订单及其明细”两种写法各处理 100 个请求(顺序执行):(a)N+1:先查订单列表(1 次),再对每个订单单独查明细(20 次);(b)一次 JOIN 查询。看每个请求的 db span 个数、请求耗时 p50 / p99,以及数据库 span 耗时的合计')
conn = M.conn('shop'); mem.clear()
def req_n1(start):
    with tracer.start_as_current_span('GET /orders-n1', kind=SpanKind.SERVER):
        os_ = db(conn, 'select id from orders where id >= %s order by id limit 20', (start,))
        for (oid,) in os_: db(conn, 'select sku, qty from items where order_id = %s', (oid,))
def req_join(start):
    with tracer.start_as_current_span('GET /orders-join', kind=SpanKind.SERVER):
        db(conn, 'select o.id, i.sku, i.qty from (select id from orders where id >= %s order by id limit 20) o join items i on i.order_id = o.id', (start,))
rows = []
for name, fn in (('(a)N+1', req_n1), ('(b)一次 JOIN', req_join)):
    mem.clear(); lat = []
    for k in range(100):
        t = time.perf_counter(); fn(k * 10); lat.append((time.perf_counter() - t) * 1000)
    spans = mem.get_finished_spans(); dbs = [s for s in spans if s.name == 'db.query']
    rows.append((name, f'{len(dbs) / 100:.1f}', f'{pct(lat, 50):.2f}', f'{pct(lat, 99):.2f}', f'{sum(s.end_time - s.start_time for s in dbs) / 100 / 1e6:.2f}'))
conn.close()
table(rows, ['写法', '每个请求的 db span 个数', '请求耗时 p50(ms)', 'p99(ms)', '每个请求 db span 耗时合计(ms)'])
print('  N+1 在 trace 里是一串等宽的短 db span 紧挨着排开,单个都不慢,所以慢日志抓不到;发现它靠看一个请求下 db span 的个数')

# ============ 四 ============
print('== 四:db.statement 写字面值还是占位符。1000 个请求按邮箱查用户:(a)把带字面值的完整 SQL 作为 db.statement;(b)把占位符形式的 SQL(…email = %s)作为 db.statement。统计 span 里不同的 db.statement 个数,包含邮箱地址的 span 数,以及 db.statement 属性的总字节数')
conn = M.conn('shop'); rows = []
for name, mode in (('(a)字面值', 'lit'), ('(b)占位符', 'ph')):
    mem.clear()
    for i in range(1000):
        em = f'user{i % 2000}@example.com'
        sql = 'select id from users where email = %s'
        stmt = (sql.replace('%s', f"'{em}'")) if mode == 'lit' else sql
        with tracer.start_as_current_span('GET /user'): db(conn, sql, (em,), stmt=stmt)
    dbs = [s for s in mem.get_finished_spans() if s.name == 'db.query']
    rows.append((name, len({s.attributes['db.statement'] for s in dbs}), sum(1 for s in dbs if '@example.com' in s.attributes['db.statement']), sum(len(s.attributes['db.statement']) for s in dbs)))
conn.close()
table(rows, ['写法', '不同的 db.statement 个数', '含邮箱地址的 span 数', 'db.statement 总字节数'])
print('  字面值把每个请求的参数都带进 span:不同语句的个数和请求数一样多,按语句聚合(比如统计各 SQL 的耗时)就没有意义,用户的邮箱也进了追踪后端;占位符形式的语句只有一种,聚合有意义也不含用户数据')

# ============ 五 ============
print('== 五:连接池等待算在谁头上。连接池只有 3 个连接,12 个并发请求(12 个线程同时开始),每个请求执行一条约 200 ms 的查询(SELECT SLEEP(0.2))。(a)一个 db.query span 包住“取连接 + 执行”;(b)分成 pool.acquire 和 db.execute 两个 span。看这些 span 的耗时分布')
pool = Q.Queue()
for _ in range(3): pool.put(M.conn('shop'))
mem.clear(); bar = threading.Barrier(12)
def req_pool(i):
    bar.wait()
    with tracer.start_as_current_span('GET /slow', kind=SpanKind.SERVER):
        with tracer.start_as_current_span('db.query.total'):
            with tracer.start_as_current_span('pool.acquire'): cn = pool.get()
            try:
                with tracer.start_as_current_span('db.execute'):
                    with cn.cursor() as cur: cur.execute('select sleep(0.2)'); cur.fetchall()
            finally: pool.put(cn)
with concurrent.futures.ThreadPoolExecutor(12) as ex: list(ex.map(req_pool, range(12)))
sp = mem.get_finished_spans(); d = lambda n: sorted((s.end_time - s.start_time) / 1e6 for s in sp if s.name == n)
table([(n, f'{statistics.median(d(n)):.0f}', f'{d(n)[0]:.0f}', f'{d(n)[-1]:.0f}') for n in ('db.query.total', 'pool.acquire', 'db.execute')], ['span', '耗时中位数(ms)', '最小(ms)', '最大(ms)'])
print('  只用一个 span 把“取连接 + 执行”包在一起时,看到的是“数据库慢”;其实一部分是排队等连接——拆成 pool.acquire 和 db.execute 才能看出数据库本身只用了约 200 ms,其余是等连接')
for _ in range(3): pool.get().close()
M.stop()
print('ERRORS', dict(ERRORS))
