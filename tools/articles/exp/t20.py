import sys, os, itertools; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import pymysql
tee('t20'); reset()
M = MySQL('t20').start(); M.q('create database shop')
M.q('create table orders(id int primary key, status varchar(12) not null, version int not null default 0)', db='shop')
M.q('create table order_events(id bigint auto_increment primary key, order_id int, seq int, from_status varchar(12), to_status varchar(12), unique key u (order_id, seq))', db='shop')
M.q('create table effects(id bigint auto_increment primary key, order_id int, kind varchar(20), key k (order_id))', db='shop')
STATES = ['CREATED', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'REFUNDED']
ALLOWED = {'CREATED': {'PAID', 'CANCELLED'}, 'PAID': {'SHIPPED', 'REFUNDED'}, 'SHIPPED': {'DELIVERED'}, 'DELIVERED': set(), 'CANCELLED': set(), 'REFUNDED': set()}
ALLOWED_PAIRS = {(a, b) for a, bs in ALLOWED.items() for b in bs}
print(f'MySQL {M.q("select version()")[0][0]};订单状态机:CREATED → PAID | CANCELLED;PAID → SHIPPED | REFUNDED;SHIPPED → DELIVERED;DELIVERED / CANCELLED / REFUNDED 是终态(共 {len(ALLOWED_PAIRS)} 条合法流转,{len(STATES) * len(STATES)} 个(from, to)组合);orders(status, version)、order_events(order_id, seq 唯一)、effects(流转触发的副作用:收款、释放库存、发货……)')
def conn(): return M.conn('shop', autocommit=False)
def reset_orders(n, status='CREATED'):
    for t in ('orders', 'order_events', 'effects'): M.q(f'delete from {t}', db='shop')
    c = conn(); cur = c.cursor(); cur.executemany('insert into orders values (%s, %s, 0)', [(i, status) for i in range(1, n + 1)]); c.commit(); c.close()

print('== 一:非法流转:对每个订单状态试每一个目标状态(6 × 6 = 36 个组合),朴素写法(UPDATE SET status = ?)与带源状态条件的写法(WHERE status IN 允许的源状态)分别接受了几个')
c = conn(); cur = c.cursor(); acc_naive = set(); acc_guard = set()
for a, b in itertools.product(STATES, STATES):
    reset_orders(1, a)
    cur.execute('update orders set status = %s where id = 1', (b,)); 
    if cur.rowcount == 1 and a != b: acc_naive.add((a, b))
    c.commit(); reset_orders(1, a)
    froms = [x for x in STATES if (x, b) in ALLOWED_PAIRS]
    if froms:
        cur.execute(f"update orders set status = %s where id = 1 and status in ({','.join(['%s'] * len(froms))})", (b, *froms)); ok = cur.rowcount == 1
        if ok and a != b: acc_guard.add((a, b))
        c.commit()
c.close()
bad = sorted(acc_naive - ALLOWED_PAIRS)
print(f'  合法的流转 {len(ALLOWED_PAIRS)} 条;朴素写法接受了 {len(acc_naive)} 条不同状态之间的流转(其中 {len(bad)} 条是非法的,例如 {bad[:4]});带源状态条件的写法接受了 {len(acc_guard)} 条,其中非法的 {len(acc_guard - ALLOWED_PAIRS)} 条,漏掉的合法流转 {len(ALLOWED_PAIRS - acc_guard)} 条')

print('== 二:并发的“支付回调”和“用户取消”抢同一个 CREATED 订单(各 1000 个订单,两个线程过屏障后同时动手);流转成功的一方要触发副作用:支付 → 记一笔 PAYMENT_CAPTURED,取消 → 记一笔 STOCK_RELEASED')
def race(mode, n=1000):
    reset_orders(n); both = 0; paid_only = 0; cancel_only = 0; final_mismatch = 0
    def actor(oid, kind, bar):
        c = conn(); cur = c.cursor(); bar.wait()
        to = 'PAID' if kind == 'pay' else 'CANCELLED'; eff = 'PAYMENT_CAPTURED' if kind == 'pay' else 'STOCK_RELEASED'
        if mode == 'readwrite':
            cur.execute('select status from orders where id = %s', (oid,)); st = cur.fetchone()[0]; c.commit()
            if st == 'CREATED':
                time.sleep(0.0005); cur.execute('update orders set status = %s where id = %s', (to, oid)); cur.execute('insert into effects(order_id, kind) values (%s, %s)', (oid, eff)); c.commit()
        else:
            cur.execute("update orders set status = %s, version = version + 1 where id = %s and status = 'CREATED'", (to, oid))
            if cur.rowcount == 1: cur.execute('insert into effects(order_id, kind) values (%s, %s)', (oid, eff))
            c.commit()
        c.close()
    for oid in range(1, n + 1):
        bar = threading.Barrier(2); ts = [threading.Thread(target=actor, args=(oid, k, bar)) for k in ('pay', 'cancel')]; [t.start() for t in ts]; [t.join() for t in ts]
    eff = {}
    for oid, kind in M.q('select order_id, kind from effects', db='shop'): eff.setdefault(oid, set()).add(kind)
    for oid in range(1, n + 1):
        k = eff.get(oid, set()); both += ('PAYMENT_CAPTURED' in k and 'STOCK_RELEASED' in k); paid_only += (k == {'PAYMENT_CAPTURED'}); cancel_only += (k == {'STOCK_RELEASED'})
    st = {r[0]: r[1] for r in M.q('select status, count(*) from orders group by status', db='shop')}
    return both, paid_only, cancel_only, st
rows = []
for mode, name in (('readwrite', '先读状态,是 CREATED 就改并触发副作用'), ('cond', '条件 UPDATE(WHERE status = CREATED),影响 1 行才触发副作用')):
    both, po, co, st = race(mode); rows.append((name, 1000, po, co, both, str(st)))
table(rows, ['写法', '订单数', '只收款', '只释放库存', '既收款又释放库存(矛盾)', '最终状态分布'])
print('  读后写:两个线程都读到 CREATED,各自改并各自触发副作用,订单最终只有一个状态,但“已收款”和“库存已释放”同时发生了;条件 UPDATE 让两个动作中只有一个能抢到流转,副作用只由抢到的那个触发')

print('== 三:重复的支付回调(同一个订单收到 3 次):盲写 + 副作用 vs 条件 UPDATE,对已经是 PAID 的订单把重复回调当作成功但不再触发副作用')
def dup_cb(mode, n=500):
    reset_orders(n); results = {'成功返回': 0, '报错': 0}; c = conn(); cur = c.cursor()
    for oid in range(1, n + 1):
        for _ in range(3):
            if mode == 'blind':
                cur.execute("update orders set status = 'PAID' where id = %s", (oid,)); cur.execute("insert into effects(order_id, kind) values (%s, 'PAYMENT_CAPTURED')", (oid,)); c.commit(); results['成功返回'] += 1
            else:
                cur.execute("update orders set status = 'PAID', version = version + 1 where id = %s and status = 'CREATED'", (oid,))
                if cur.rowcount == 1: cur.execute("insert into effects(order_id, kind) values (%s, 'PAYMENT_CAPTURED')", (oid,)); results['成功返回'] += 1
                else:
                    cur.execute('select status from orders where id = %s', (oid,)); st = cur.fetchone()[0]
                    if st == 'PAID': results['成功返回'] += 1            # 已经是目标状态:幂等地当作成功,不再触发副作用
                    else: results['报错'] += 1
                c.commit()
    c.close(); per = {r[0]: r[1] for r in M.q('select order_id, count(*) from effects group by order_id', db='shop')}
    return results, sum(1 for v in per.values() if v > 1), sum(per.values())
rows = []
for mode, name in (('blind', '盲写 PAID + 每次都触发副作用'), ('cond', '条件 UPDATE + 已是 PAID 就幂等返回')):
    r, multi, tot = dup_cb(mode); rows.append((name, 500 * 3, r['成功返回'], r['报错'], tot, multi))
table(rows, ['写法', '收到的回调', '回复成功', '回复报错', '收款副作用总数(应为 500)', '被收了多次款的订单'])

print('== 四:流转日志:每次流转在同一个事务里追加 order_events(seq 用 version + 1,(order_id, seq) 唯一)。2 万次随机尝试(目标状态随机)之后:日志重放得到的状态是否等于 orders.status,日志里有没有非法流转,seq 有没有断档')
def chaos(guarded, n_orders=500, tries=20000, seed=20):
    reset_orders(n_orders); rng = random.Random(seed); acc = rej = 0; c = conn(); cur = c.cursor()
    for _ in range(tries):
        oid = rng.randrange(1, n_orders + 1); to = rng.choice(STATES)
        cur.execute('select status, version from orders where id = %s', (oid,)); frm, ver = cur.fetchone(); c.commit()
        if guarded:
            cur.execute('update orders set status = %s, version = version + 1 where id = %s and version = %s and (%s)', (to, oid, ver, '1' if (frm, to) in ALLOWED_PAIRS else '0'))
        else:
            cur.execute('update orders set status = %s, version = version + 1 where id = %s and version = %s', (to, oid, ver))
        if cur.rowcount == 1:
            cur.execute('insert into order_events(order_id, seq, from_status, to_status) values (%s, %s, %s, %s)', (oid, ver + 1, frm, to)); acc += 1
        else: rej += 1
        c.commit()
    c.close()
    ev = {}
    for oid, seq, fr, to in M.q('select order_id, seq, from_status, to_status from order_events order by order_id, seq', db='shop'): ev.setdefault(oid, []).append((seq, fr, to))
    cur_st = {r[0]: r[1] for r in M.q('select id, status from orders', db='shop')}
    replay_ok = sum(1 for oid in cur_st if (ev.get(oid, [(0, None, 'CREATED')])[-1][2]) == cur_st[oid]); gaps = sum(1 for oid, l in ev.items() if [s for s, _, _ in l] != list(range(1, len(l) + 1)))
    illegal = sum(1 for l in ev.values() for _, fr, to in l if (fr, to) not in ALLOWED_PAIRS)
    return acc, rej, replay_ok, n_orders, gaps, illegal
rows = []
for g, name in ((False, '只有 version 乐观锁,不检查流转是否合法'), (True, 'version 乐观锁 + 检查流转合法')):
    acc, rej, ok, n, gaps, il = chaos(g); rows.append((name, acc, rej, f'{ok} / {n}', gaps, il))
table(rows, ['写法', '接受的流转', '被拒绝的', '日志重放 = 当前状态的订单', 'seq 断档的订单', '日志里的非法流转'])
print('  version 保证每次流转看到的是最新状态、日志没有断档;“这个流转合法吗”是另一件事,要靠状态机本身来检查')

print('== 五:状态机放在应用里还是放在数据库里:另一个写入方(运维脚本、别的服务)绕过应用直接 UPDATE 时,只有数据库里的约束(这里用 BEFORE UPDATE 触发器)才拦得住')
reset_orders(1, 'DELIVERED')
cs = M.conn('shop'); cur = cs.cursor()
cur.execute("update orders set status = 'CREATED' where id = 1"); print('  没有触发器:另一个写入方执行 UPDATE orders SET status = CREATED —— 受影响行数', cur.rowcount, ',订单现在是', M.q('select status from orders where id = 1', db='shop')[0][0], '(已送达的订单“回到”了待支付)')
pairs = ' OR '.join(f"(OLD.status = '{a}' AND NEW.status = '{b}')" for a, b in sorted(ALLOWED_PAIRS))
M.q(f"create trigger orders_flow before update on orders for each row begin if NEW.status <> OLD.status and not ({pairs}) then signal sqlstate '45000' set message_text = 'illegal order status transition'; end if; end", db='shop')
reset_orders(1, 'DELIVERED')
try: cur.execute("update orders set status = 'CREATED' where id = 1"); print('  有触发器:UPDATE 成功了(不该发生)')
except Exception as e: print(f'  有触发器:同一条 UPDATE 被数据库拒绝:{type(e).__name__} {e.args[0]} {e.args[1]}')
cur.execute("update orders set status = 'DELIVERED' where id = 1"); print('  同一状态再写一次(DELIVERED → DELIVERED)仍然允许,受影响行数', cur.rowcount)
reset_orders(1, 'CREATED'); cur.execute("update orders set status = 'PAID' where id = 1"); print('  合法的流转 CREATED → PAID 通过,订单现在是', M.q('select status from orders where id = 1', db='shop')[0][0])
def bench_upd(n=3000):
    reset_orders(1000); lat = []; c = M.conn('shop'); cc = c.cursor()
    for i in range(n): t0 = time.perf_counter(); cc.execute("update orders set version = version + 1 where id = %s", (1 + i % 1000,)); lat.append(time.perf_counter() - t0)
    c.close(); return statistics.median(lat)
with_trig = [bench_upd() for _ in range(3)]
M.q('drop trigger orders_flow', db='shop'); without = [bench_upd() for _ in range(3)]
print(f'  触发器的代价:对不改 status 的 UPDATE,中位数 {statistics.median(without) * 1e6:.0f} µs(没有触发器)→ {statistics.median(with_trig) * 1e6:.0f} µs(有触发器);流转检查在应用里做则每次多一次往返')
cs.close(); reset(); shutil.rmtree(TT / 'my_t20', ignore_errors=True)
