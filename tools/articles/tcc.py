"""TCC 的最小实现(自己写的,Python):账户服务和库存服务各占一个 MySQL 实例,每个服务的 Try / Confirm / Cancel 都是本服务自己的本地事务。
t6 用的是不带任何防护的朴素版本(Try 里做业务检查并冻结资源,Confirm / Cancel 直接改数字);t7 在它上面加 tcc_log 来防空回滚、悬挂和重复。"""
import threading, pymysql


class Insufficient(Exception): pass


class Svc:
    def __init__(self, node, db='shop'):
        self.node = node; self.db = db; self.tl = threading.local()

    def c(self):
        if getattr(self.tl, 'conn', None) is None:
            self.tl.conn = self.node.conn(self.db); self.tl.conn.cursor().execute('set session innodb_lock_wait_timeout = 5')
        return self.tl.conn

    def run(self, sql, args=None):
        cur = self.c().cursor(); cur.execute(sql, args); return cur.rowcount

    def one(self, sql, args=None):
        cur = self.c().cursor(); cur.execute(sql, args); return cur.fetchone()


class AccountSvc(Svc):
    """account(user_id, balance, frozen, spent):冻结 = 从 balance 挪到 frozen。"""
    def try_(self, user, amt):
        if self.run('update account set balance = balance - %s, frozen = frozen + %s where user_id = %s and balance >= %s', (amt, amt, user, amt)) == 0:
            raise Insufficient(f'账户 {user} 余额不足')
    def confirm(self, user, amt): self.run('update account set frozen = frozen - %s, spent = spent + %s where user_id = %s', (amt, amt, user))
    def cancel(self, user, amt): self.run('update account set balance = balance + %s, frozen = frozen - %s where user_id = %s', (amt, amt, user))
    def row(self, user): return self.one('select balance, frozen, spent from account where user_id = %s', (user,))


class StockSvc(Svc):
    """stock(sku, avail, locked, sold):预留 = 从 avail 挪到 locked。"""
    def try_(self, sku, n):
        if self.run('update stock set avail = avail - %s, locked = locked + %s where sku = %s and avail >= %s', (n, n, sku, n)) == 0:
            raise Insufficient(f'{sku} 库存不足')
    def confirm(self, sku, n): self.run('update stock set locked = locked - %s, sold = sold + %s where sku = %s', (n, n, sku))
    def cancel(self, sku, n): self.run('update stock set avail = avail + %s, locked = locked - %s where sku = %s', (n, n, sku))
    def row(self, sku): return self.one('select avail, locked, sold from stock where sku = %s', (sku,))


def tcc_order(acct, stock, user, sku, qty, price, decide='confirm', hold=0.0, log=None):
    """事务管理器:先 Try 两个服务;全部成功后按 decide 做 confirm / cancel('abandon' = 管理器在 Try 之后崩了,什么都不再发);任何一个 Try 失败就 Cancel 已经 Try 过的。返回 'CONFIRMED' / 'CANCELLED' / 'REJECTED' / 'ABANDONED'。"""
    import time
    say = log or (lambda *a: None); tried = []
    try:
        acct.try_(user, qty * price); tried.append('acct'); say(f'Try   账户:冻结 {qty * price}')
        stock.try_(sku, qty); tried.append('stock'); say(f'Try   库存:预留 {qty}')
    except Insufficient as e:
        say(f'Try 失败:{e},对已 Try 的 {tried} 发 Cancel')
        if 'acct' in tried: acct.cancel(user, qty * price); say('Cancel 账户:解冻')
        return 'REJECTED'
    if hold: time.sleep(hold)
    if decide == 'abandon': return 'ABANDONED'
    if decide == 'cancel':
        acct.cancel(user, qty * price); stock.cancel(sku, qty); say('Cancel 账户、库存'); return 'CANCELLED'
    acct.confirm(user, qty * price); stock.confirm(sku, qty); say('Confirm 账户、库存'); return 'CONFIRMED'


# ---------------------------------------------------------------- t7:带 tcc_log 防护的版本
import pymysql


class Rejected(Exception): pass


class GuardedAccountSvc(AccountSvc):
    """每个动作都带 xid,先查 / 写 tcc_log(xid 主键,status = TRIED / CONFIRMED / CANCELLED),再改业务列,两者在同一个本地事务里。
    防空回滚:Cancel 找不到记录时,插一条 CANCELLED(什么业务都不改)。防悬挂:Try 一开始就 INSERT,已经有记录(CANCELLED)时主键冲突 → 拒绝。防重复:状态已经是目标状态时直接返回。"""
    def _begin(self):
        c = self.c(); c.autocommit(False); return c, c.cursor()

    def try_(self, xid, user, amt):
        c, cur = self._begin()
        try:
            try: cur.execute("insert into tcc_log(xid, status, amt) values (%s, 'TRIED', %s)", (xid, amt))
            except pymysql.err.IntegrityError: c.rollback(); raise Rejected(f'{xid} 已经有记录,拒绝 Try')
            cur.execute('update account set balance = balance - %s, frozen = frozen + %s where user_id = %s and balance >= %s', (amt, amt, user, amt))
            if cur.rowcount == 0: c.rollback(); raise Insufficient(f'账户 {user} 余额不足')
            c.commit()
        except (Rejected, Insufficient): raise
        except Exception: c.rollback(); raise
        finally: c.autocommit(True)

    def confirm(self, xid, user, amt):
        c, cur = self._begin()
        try:
            cur.execute('select status from tcc_log where xid = %s for update', (xid,)); r = cur.fetchone()
            if r is None: c.rollback(); raise Rejected(f'{xid} 没有 Try 记录,拒绝 Confirm')
            if r[0] == 'CANCELLED': c.rollback(); raise Rejected(f'{xid} 已经 Cancel,拒绝 Confirm')
            if r[0] == 'TRIED':
                cur.execute('update account set frozen = frozen - %s, spent = spent + %s where user_id = %s', (amt, amt, user))
                cur.execute("update tcc_log set status = 'CONFIRMED' where xid = %s", (xid,))
            c.commit()                                             # 已经是 CONFIRMED:重复调用,什么都不做
        except Rejected: raise
        except Exception: c.rollback(); raise
        finally: c.autocommit(True)

    def cancel(self, xid, user, amt):
        c, cur = self._begin()
        try:
            cur.execute("insert ignore into tcc_log(xid, status, amt) values (%s, 'CANCELLED', %s)", (xid, amt))
            if cur.rowcount == 1: c.commit(); return 'EMPTY'       # 没有 Try 记录:空回滚,只记一条 CANCELLED
            cur.execute('select status from tcc_log where xid = %s for update', (xid,)); st = cur.fetchone()[0]
            if st == 'TRIED':
                cur.execute('update account set balance = balance + %s, frozen = frozen - %s where user_id = %s', (amt, amt, user))
                cur.execute("update tcc_log set status = 'CANCELLED' where xid = %s", (xid,)); c.commit(); return 'CANCELLED'
            c.commit(); return 'NOOP'                                # 已经 CANCELLED(重复)或 CONFIRMED(不该发生)
        except Exception: c.rollback(); raise
        finally: c.autocommit(True)
