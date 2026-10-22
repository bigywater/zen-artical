"""Saga 实验用的三个“服务”:订单、库存、支付。三个服务各自只读写自己的库(同一个 mysqld 里的三个 schema:order_db / stock_db / pay_db),
没有任何跨库事务;每个本地动作都是幂等的(用 order_id 做主键)。故障可以按名字注入:shop.inject('pay_charge', times=2) 让前两次调用抛 Transient。"""
import threading, time, pymysql


class StepFailed(Exception): pass          # 业务上失败(库存不足、余额不足):重试没有意义
class Transient(Exception): pass           # 临时错误(超时、服务不可用):可以重试


class Shop:
    def __init__(self, mysql):
        self.m = mysql; self.tl = threading.local(); self.faults = {}; self.calls = {}; self.lock = threading.Lock()
        for db in ('order_db', 'stock_db', 'pay_db'): mysql.q(f'create database if not exists {db}')
        mysql.q('create table if not exists orders(id varchar(40) primary key, status varchar(12), created datetime(3) default current_timestamp(3))', db='order_db')
        mysql.q('create table if not exists stock(sku varchar(20) primary key, qty int)', db='stock_db')
        mysql.q('create table if not exists reservations(order_id varchar(40) primary key, sku varchar(20), qty int, status varchar(10))', db='stock_db')
        mysql.q('create table if not exists wallet(user_id int primary key, balance int)', db='pay_db')
        mysql.q('create database if not exists points_db'); mysql.q('create table if not exists points(order_id varchar(40) primary key, n int, status varchar(10))', db='points_db')
        mysql.q('create table if not exists payments(order_id varchar(40) primary key, user_id int, amount int, status varchar(10))', db='pay_db')

    def reset(self, stock=100, balance=10 ** 6):
        for db, t in (('points_db', 'points'), ('order_db', 'orders'), ('stock_db', 'stock'), ('stock_db', 'reservations'), ('pay_db', 'wallet'), ('pay_db', 'payments')): self.m.q(f'delete from {t}', db=db)
        self.m.q("insert into stock values('sku-1', %s)", (stock,), db='stock_db'); self.m.q('insert into wallet values(1, %s)', (balance,), db='pay_db')
        self.faults.clear(); self.calls.clear()

    def c(self, db):
        d = getattr(self.tl, 'd', None)
        if d is None: d = self.tl.d = {}
        if db not in d: d[db] = self.m.conn(db, autocommit=False)
        return d[db]

    def inject(self, name, times=1, exc=Transient): self.faults[name] = [times, exc]

    def _enter(self, name):
        with self.lock:
            self.calls[name] = self.calls.get(name, 0) + 1
            f = self.faults.get(name)
            if f and f[0] > 0: f[0] -= 1; raise f[1](f'{name} 注入的故障')

    def _tx(self, db, fn):
        c = self.c(db); cur = c.cursor()
        try:
            r = fn(cur); c.commit(); return r
        except Exception: c.rollback(); raise

    # -------- 订单服务
    def order_create(self, oid):
        self._enter('order_create'); self._tx('order_db', lambda cur: cur.execute("insert ignore into orders(id, status) values (%s, 'PENDING')", (oid,)))
    def order_set(self, oid, status, only_from=None):
        self._enter('order_set')
        def f(cur):
            if only_from: cur.execute('update orders set status = %s where id = %s and status = %s', (status, oid, only_from))
            else: cur.execute('update orders set status = %s where id = %s', (status, oid))
            return cur.rowcount
        return self._tx('order_db', f)
    def order_status(self, oid):
        c = self.c('order_db'); cur = c.cursor(); cur.execute('select status from orders where id = %s', (oid,)); r = cur.fetchone(); c.commit(); return r[0] if r else None

    # -------- 库存服务
    def stock_reserve(self, oid, sku, qty):
        self._enter('stock_reserve')
        def f(cur):
            cur.execute("insert ignore into reservations values (%s, %s, %s, 'RESERVED')", (oid, sku, qty))
            if cur.rowcount == 0: return 'DUP'                         # 已经预留过(重复消息):什么都不做
            cur.execute('update stock set qty = qty - %s where sku = %s and qty >= %s', (qty, sku, qty))
            if cur.rowcount == 0: raise StepFailed(f'{sku} 库存不足')
            return 'OK'
        return self._tx('stock_db', f)
    def stock_release(self, oid):
        self._enter('stock_release')
        def f(cur):
            cur.execute("select sku, qty from reservations where order_id = %s and status = 'RESERVED' for update", (oid,)); r = cur.fetchone()
            if not r: return 'NOOP'
            cur.execute('update stock set qty = qty + %s where sku = %s', (r[1], r[0])); cur.execute("update reservations set status = 'RELEASED' where order_id = %s", (oid,)); return 'RELEASED'
        return self._tx('stock_db', f)

    # -------- 支付服务
    def pay_charge(self, oid, user, amt):
        self._enter('pay_charge')
        def f(cur):
            cur.execute("insert ignore into payments values (%s, %s, %s, 'CHARGED')", (oid, user, amt))
            if cur.rowcount == 0: return 'DUP'
            cur.execute('update wallet set balance = balance - %s where user_id = %s and balance >= %s', (amt, user, amt))
            if cur.rowcount == 0: raise StepFailed(f'用户 {user} 余额不足')
            return 'OK'
        return self._tx('pay_db', f)
    def pay_refund(self, oid):
        self._enter('pay_refund')
        def f(cur):
            cur.execute("select user_id, amount from payments where order_id = %s and status = 'CHARGED' for update", (oid,)); r = cur.fetchone()
            if not r: return 'NOOP'
            cur.execute('update wallet set balance = balance + %s where user_id = %s', (r[1], r[0])); cur.execute("update payments set status = 'REFUNDED' where order_id = %s", (oid,)); return 'REFUNDED'
        return self._tx('pay_db', f)

    # -------- 积分服务(第 8 篇“加一个步骤”时用)
    def points_grant(self, oid, n=10):
        self._enter('points_grant'); return self._tx('points_db', lambda cur: cur.execute("insert ignore into points values (%s, %s, 'GRANTED')", (oid, n)))
    def points_release(self, oid):
        self._enter('points_release'); return self._tx('points_db', lambda cur: cur.execute("update points set status = 'RELEASED' where order_id = %s and status = 'GRANTED'", (oid,)))

    def snapshot(self):
        q = self.m.q
        return dict(orders={r[0]: r[1] for r in q('select id, status from orders order by id', db='order_db')},
                    stock=q("select qty from stock where sku = 'sku-1'", db='stock_db')[0][0], reserved=q("select count(*) from reservations where status = 'RESERVED'", db='stock_db')[0][0],
                    balance=q('select balance from wallet where user_id = 1', db='pay_db')[0][0], charged=q("select count(*) from payments where status = 'CHARGED'", db='pay_db')[0][0])
