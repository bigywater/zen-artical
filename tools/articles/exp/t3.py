import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from tpc import Coord, pgconn
tee('t3'); reset()
A = PG('t3_a'); B = PG('t3_b')
ths = [threading.Thread(target=n.start) for n in (A, B)]; [t.start() for t in ths]; [t.join() for t in ths]
A.q('create table orders(id int primary key, status text)'); B.q('create table stock(sku text primary key, qty int)'); B.q("insert into stock values('sku-1', 100), ('sku-2', 100)")
PORTS = {'订单库': A.port, '库存库': B.port}
CODES = {'0': '开始之前', '1': '第一个参与者 prepare 之后', '2': '全部 prepare 之后、写决定日志之前', '3': '决定日志落盘之后、发出第一个 COMMIT PREPARED 之前', '4': '第一个 COMMIT PREPARED 之后、第二个之前'}
print(f'两个独立的 PostgreSQL 实例(订单库 {A.port}、库存库 {B.port});协调者是 tools/articles/tpc.py 里自己写的 Python 程序,作为独立进程运行,决定日志在它自己的 SQLite 文件里;业务:订单库 insert 一条订单 + 库存库 sku-1 扣 1(初始库存 100)')


def fresh():
    for n in (A, B):
        try:
            with pgconn(n.port) as c:
                for (g,) in c.execute('select gid from pg_prepared_xacts').fetchall(): c.execute(f"rollback prepared '{g}'")
        except Exception: pass
    A.q('delete from orders'); B.q("update stock set qty = 100 where sku='sku-1'")


def spawn(code, k, order='ok'):
    log = TT / f't3_dec_{k}_{order}.sqlite3'; log.unlink(missing_ok=True)
    r = subprocess.run([sys.executable, str(HERE / 'tpc.py'), str(log), f'x{k}', code, order, f'订单库={A.port}', f'库存库={B.port}'], capture_output=True, text=True, timeout=60)
    return r, log


def snap(log=None, xid=None):
    pa = A.q('select gid from pg_prepared_xacts'); pb = B.q('select gid from pg_prepared_xacts')
    o = A.q('select count(*) from orders')[0][0]; q = B.q("select qty from stock where sku='sku-1'")[0][0]
    d = Coord(PORTS, str(log), say=lambda *x: None).decision(xid) if log else None
    return dict(pa=len(pa), pb=len(pb), orders=o, qty=q, dec=d or '(无)')


def verdict(o, q): return '一致' if (o, q) in ((0, 100), (1, 99)) else '不一致'

print('== 一:协调者在 2PC 的五个位置各被 kill -9 一次,看两个参与者当场停在什么状态(用 pg_prepared_xacts 和业务数据看)')
rows = []
for code in '01234':
    fresh(); r, log = spawn(code, code)
    s = snap(log, f'x{code}')
    rows.append((f'{code}. {CODES[code]}', f'rc={r.returncode}', s['pa'], s['pb'], s['orders'], s['qty'], s['dec']))
    if code == '3': r3 = r.stdout
table(rows, ['协调者在哪个位置被杀', '退出码', '订单库 prepared 数', '库存库 prepared 数', '订单数', '库存', '决定日志'])
print('  位置 3 时协调者进程打印的最后几行:'); [print('   ', l) for l in r3.strip().splitlines()]

print('== 二:两边都已经 prepare、协调者死了(位置 2):参与者只能干等——被 prepare 的行锁一直握着,别的事务写同一行被挡;同时它还挡住 VACUUM 清理死元组')
fresh(); r, log = spawn('2', 'w')
ages = lambda: [(g, float(a)) for g, a in B.q("select gid, round(extract(epoch from now() - prepared)::numeric, 1) from pg_prepared_xacts")]
print('  库存库 pg_prepared_xacts(gid, 已经 prepare 了多少秒):', ages())
c = pgconn(B.port); c.execute("set lock_timeout = '3000ms'"); t0 = time.perf_counter()
try: c.execute("update stock set qty = qty - 1 where sku='sku-1'")
except Exception as e: print(f'  业务会话 UPDATE sku-1(被卡住的那一行):等了 {ms(time.perf_counter() - t0)} 后 {type(e).__name__}')
t0 = time.perf_counter(); c.execute("update stock set qty = qty - 1 where sku='sku-2'"); print(f'  同一个会话 UPDATE sku-2(别的行):{ms(time.perf_counter() - t0)} 完成,没被挡 —— 锁的粒度是被 prepare 的那一行')
c.close(); time.sleep(1.0)
print('  又过了一会儿,库存库 pg_prepared_xacts:', ages(), '—— 协调者没了,它只会越来越老')
B.q('create table churn(id int primary key, v int)'); B.q('insert into churn select g, 0 from generate_series(1, 2000) g')
def vac():
    notes = []
    c = pgconn(B.port); c.add_notice_handler(lambda d: notes.append(d.message_primary)); c.execute('vacuum (verbose) churn')
    c.close(); return [l for m in notes for l in m.splitlines() if l.startswith('tuples:') or l.startswith('removable cutoff')]
B.q('create table churn2(id int primary key, v int)')
for _ in range(3): B.q('update churn set v = v + 1')
print('  有 prepared 事务挂着时,把 churn 表(2000 行)整体 UPDATE 3 次后 VACUUM:')
for l in vac(): print('   ', l)
ca = pgconn(B.port); ca.execute("rollback prepared 'xw'"); ca.close()
print("  把 prepared 事务 ROLLBACK PREPARED 'xw' 之后再 VACUUM:")
for l in vac(): print('   ', l)

print('== 三:协调者死在第一个 COMMIT PREPARED 之后(位置 4):订单库已提交,库存库还 prepared。库存库自己该怎么决定?')
fresh(); r, log = spawn('4', 'v')
s = snap(log, 'xv')
print(f"  现场:订单库 prepared={s['pa']} 条、订单 {s['orders']} 条(已提交);库存库 prepared={s['pb']} 条、库存 {s['qty']}(扣减还不可见);协调者的决定日志:{s['dec']}")
print("  库存库的 DBA 能看到的:本库 pg_prepared_xacts 有 'xv';订单库那边 pg_prepared_xacts 里已经没有 'xv' —— 没有了可能是已提交,也可能是已回滚,看不出来")
print("  做法 A(等不到协调者就自己回滚,“超时即 abort”):库存库 ROLLBACK PREPARED 'xv'")
B.q("rollback prepared 'xv'"); s = snap(); print(f"    结果:订单 {s['orders']} 条,库存 {s['qty']} —— {verdict(s['orders'], s['qty'])}(订单已经提交了,库存却没扣)")
fresh(); r, log = spawn('4', 'v2')
print(f"  做法 B(去问协调者留下的决定日志):日志里是 {snap(log, 'xv2')['dec']} -> 库存库 COMMIT PREPARED 'xv2'")
B.q("commit prepared 'xv2'"); s = snap(); print(f"    结果:订单 {s['orders']} 条,库存 {s['qty']} —— {verdict(s['orders'], s['qty'])}")

print('== 四:有决定日志时的恢复(重启协调者后扫描两边的 pg_prepared_xacts:日志里是 COMMIT 就 COMMIT PREPARED,没有记录就 ROLLBACK PREPARED)')
rows = []
for code in '01234':
    fresh(); r, log = spawn(code, 'r' + code)
    co = Coord(PORTS, str(log), say=lambda *x: None); acts = co.recover('log'); s = snap(log, 'xr' + code)
    rows.append((f'{code}. {CODES[code]}', '; '.join(f'{n[:2]}:{a.split()[0]}' for n, g, a in acts) or '(无事可做)', s['orders'], s['qty'], verdict(s['orders'], s['qty'])))
table(rows, ['协调者在哪个位置被杀', '恢复动作(订单/库存:动作)', '订单数', '库存', '结论'])

print('== 五:决定日志丢了(协调者的磁盘坏了),恢复程序只能“一律回滚”')
rows = []
for code in '01234':
    fresh(); r, log = spawn(code, 'n' + code)
    co = Coord(PORTS, str(log), say=lambda *x: None); acts = co.recover('abort'); s = snap()
    rows.append((f'{code}. {CODES[code]}', '; '.join(f'{n[:2]}:{a.split()[0]}' for n, g, a in acts) or '(无事可做)', s['orders'], s['qty'], verdict(s['orders'], s['qty'])))
table(rows, ['协调者在哪个位置被杀', '恢复动作', '订单数', '库存', '结论'])
print('  位置 3 虽然也“一致”,但那是把一个本来已经决定提交的事务回滚了;位置 4 订单库已经提交,只能靠人工补')

print('== 六:决定日志的落盘必须在发出任何 COMMIT PREPARED 之前:把顺序调换(先发第一个 COMMIT PREPARED,再写日志),在位置 4 杀协调者')
rows = []
for order, name in (('ok', '先写日志再发 COMMIT PREPARED(正确)'), ('bad', '先发第一个 COMMIT PREPARED 再写日志(错误)')):
    fresh(); r, log = spawn('4', 'o' + order, order)
    co = Coord(PORTS, str(log), say=lambda *x: None); before = snap(log, 'xo' + order); acts = co.recover('log'); s = snap(log, 'xo' + order)
    rows.append((name, before['dec'], '; '.join(f'{n[:2]}:{a.split()[0]}' for n, g, a in acts), s['orders'], s['qty'], verdict(s['orders'], s['qty'])))
table(rows, ['协调者的写法', '崩溃时决定日志', '恢复动作', '订单数', '库存', '结论'])

print('== 七:另一半:参与者在投票之前死了(库存库在订单库 PREPARE 成功之后、轮到自己之前被 kill -9),协调者怎么办')
fresh()
lines = []
co = Coord(PORTS, str(TT / 't3_dec_p.sqlite3'), say=lines.append)
work = {'订单库': ["insert into orders values(1, 'CREATED')"], '库存库': ["update stock set qty = qty - 1 where sku='sku-1'"]}
res = co.run('xp', work, hook=B.kill)
print('  协调者打印:'); [print('   ', l.strip().splitlines()[0][:160]) for l in lines]
print(f'  协调者的结论:{res};决定日志:{co.decision("xp")}')
print('  订单库 prepared 事务数:', len(A.q('select gid from pg_prepared_xacts')), ',订单数:', A.q('select count(*) from orders')[0][0], '(订单库的 prepared 事务已被协调者回滚)')
B.start(); print('  库存库重启后 prepared 事务数:', len(B.q('select gid from pg_prepared_xacts')), ',库存:', B.q("select qty from stock where sku='sku-1'")[0][0], '—— 没有投票就死了,什么都没留下,整体 ABORT')
reset()
for n in ('pg_t3_a', 'pg_t3_b'): shutil.rmtree(TT / n, ignore_errors=True)
for f in TT.glob('t3_*'): f.unlink()
