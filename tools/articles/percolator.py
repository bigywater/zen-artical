"""Percolator 风格事务的最小实现(自己写的,Python + MySQL;不是 Google 的 Percolator,也不是 TiKV):
data(k, ts, v) 存多版本的值;lk(k, ts, pk, expire) 每个 key 最多一把锁(记着它的主锁是哪个 key);wr(k, commit_ts, start_ts) 是提交记录;tso 是单调递增的时间戳。
提交 = 预写(给每个 key 写 data + lock,发现更新的 write 或别人的 lock 就中止)→ 提交主锁(写 wr、删 lock:这一刻整个事务算提交)→ 提交次锁。读 = 快照读:遇到 start_ts 之前的 lock,就去看它的主锁是提交了、回滚了还是还在持有,决定前滚 / 回滚 / 等待。"""
import time, threading, pymysql


class Conflict(Exception): pass
class Aborted(Exception): pass


class Store:
    def __init__(self, mysql, db='perc'):
        self.m = mysql; self.db = db; self.tl = threading.local()
        mysql.q(f'create database if not exists {db}')
        mysql.q('create table if not exists data(k varchar(20), ts bigint, v int, primary key (k, ts))', db=db)
        mysql.q('create table if not exists lk(k varchar(20) primary key, ts bigint, pk varchar(20), expire datetime(3))', db=db)
        mysql.q('create table if not exists wr(k varchar(20), commit_ts bigint, start_ts bigint, primary key (k, commit_ts), key by_start (k, start_ts))', db=db)
        mysql.q('create table if not exists tso(id int primary key, v bigint)', db=db); mysql.q('insert ignore into tso values (1, 100)', db=db)
        self.stats = {'resolved_forward': 0, 'resolved_back': 0, 'waits': 0}; self.slk = threading.Lock()

    def conn(self):
        if getattr(self.tl, 'c', None) is None:
            self.tl.c = self.m.conn(self.db, autocommit=False); self.tl.c.cursor().execute('set session transaction isolation level read committed')   # 每条语句读最新已提交的数据,不用快照
        return self.tl.c

    def reset(self):
        for t in ('data', 'lk', 'wr'): self.m.q(f'delete from {t}', db=self.db)
        self.m.q('update tso set v = 100', db=self.db); self.stats.update(resolved_forward=0, resolved_back=0, waits=0)

    def tso(self):
        c = self.conn(); cur = c.cursor(); cur.execute('update tso set v = last_insert_id(v + 1) where id = 1'); cur.execute('select last_insert_id()'); v = cur.fetchone()[0]; c.commit(); return v

    def bump(self, k):
        with self.slk: self.stats[k] += 1

    # ---------------- 读
    def get(self, k, start_ts, wait=5.0):
        t0 = time.time(); c = self.conn(); cur = c.cursor()
        while True:
            cur.execute('select ts, pk, expire < now(3) from lk where k = %s', (k,)); lock = cur.fetchone(); c.commit()
            if lock and lock[0] <= start_ts:
                if self.resolve(k, lock[0], lock[1], bool(lock[2])): continue
                self.bump('waits')
                if time.time() - t0 > wait: raise Conflict(f'{k} 上的锁(start_ts={lock[0]})一直没有消失')
                time.sleep(0.01); continue
            cur.execute('select start_ts from wr where k = %s and commit_ts <= %s order by commit_ts desc limit 1', (k, start_ts)); w = cur.fetchone()
            if not w: c.commit(); return None
            cur.execute('select v from data where k = %s and ts = %s', (k, w[0])); v = cur.fetchone(); c.commit(); return v[0] if v else None

    def get_ignoring_locks(self, k, start_ts):
        c = self.conn(); cur = c.cursor(); cur.execute('select start_ts from wr where k = %s and commit_ts <= %s order by commit_ts desc limit 1', (k, start_ts)); w = cur.fetchone()
        if not w: c.commit(); return None
        cur.execute('select v from data where k = %s and ts = %s', (k, w[0])); v = cur.fetchone(); c.commit(); return v[0] if v else None

    def resolve(self, k, lock_ts, primary, expired):
        """遇到别人的锁:看主锁的状态。返回 True = 这把锁已经被处理掉(前滚或回滚),可以重读;False = 主锁还有效,要等。"""
        c = self.conn(); cur = c.cursor()
        cur.execute('select ts, expire < now(3) from lk where k = %s', (primary,)); pl = cur.fetchone()                      # 先读主锁、再读提交记录:提交是“删锁 + 写提交记录”的一个事务,
        cur.execute('select commit_ts from wr where k = %s and start_ts = %s', (primary, lock_ts)); w = cur.fetchone(); c.commit()   # 先读到锁、后读到提交记录 = 刚好在两次读之间提交了,按已提交处理
        if w:                                                                  # 主锁已经提交:前滚这个次锁
            self._commit_key(k, lock_ts, w[0]); self.bump('resolved_forward'); return True
        if pl and pl[0] == lock_ts:
            if not pl[1]: return False                                          # 主锁还在、还没过期:事务可能还在进行
            if not self._rollback_key(primary, lock_ts): return True            # 主锁过期,抢着回滚;没抢到说明刚被提交了,重新判断
        self._rollback_key(k, lock_ts); self.bump('resolved_back'); return True  # 主锁已不在也没有提交记录:事务已经回滚

    def _rollback_key(self, k, ts):
        """删锁(谁删成功谁说了算:回滚和提交抢同一把主锁,只有一个能删到)并清掉这次写入的数据。返回是否真的回滚了。"""
        c = self.conn(); cur = c.cursor()
        try:
            cur.execute('delete from lk where k = %s and ts = %s', (k, ts)); n = cur.rowcount
            if n: cur.execute('delete from data where k = %s and ts = %s', (k, ts))
            c.commit(); return bool(n)
        except Exception: c.rollback(); raise

    def _commit_key(self, k, start_ts, commit_ts):
        c = self.conn(); cur = c.cursor()
        try:
            cur.execute('delete from lk where k = %s and ts = %s', (k, start_ts)); n = cur.rowcount
            if n: cur.execute('insert ignore into wr values (%s, %s, %s)', (k, commit_ts, start_ts))
            c.commit(); return bool(n)
        except Exception: c.rollback(); raise


class Txn:
    def __init__(self, store, ttl_ms=1500):
        self.s = store; self.start_ts = store.tso(); self.writes = {}; self.ttl = ttl_ms

    def get(self, k): return self.writes[k] if k in self.writes else self.s.get(k, self.start_ts)
    def set(self, k, v): self.writes[k] = v

    def prewrite(self, stop_after=None):
        keys = list(self.writes); self.primary = keys[0]; c = self.s.conn(); cur = c.cursor(); done = []
        for k in keys:                                                        # 主锁所在的 key 排第一
            try:
                try: cur.execute('insert into lk values (%s, %s, %s, now(3) + interval %s microsecond)', (k, self.start_ts, self.primary, self.ttl * 1000))     # 主键唯一:已经有锁就是冲突,不等待
                except pymysql.err.IntegrityError: raise Conflict(f'{k}:已经被别的事务锁住')
                cur.execute('select commit_ts from wr where k = %s and commit_ts >= %s limit 1', (k, self.start_ts))        # 拿到锁之后再查:此后没有别人能提交这个 key,之前已经提交的都看得到
                if cur.fetchone(): raise Conflict(f'{k}:有比 start_ts 更新的提交记录(写写冲突)')
                cur.execute('insert into data values (%s, %s, %s)', (k, self.start_ts, self.writes[k])); c.commit(); done.append(k)
            except pymysql.err.OperationalError as e:
                c.rollback()
                for d in done: self.s._rollback_key(d, self.start_ts)
                raise Conflict(f'{k}:数据库报告 {e.args[0]}(死锁 / 锁等待),当作冲突中止')
            except Exception:
                c.rollback()
                for d in done: self.s._rollback_key(d, self.start_ts)
                raise
        return done

    def commit(self, crash=None):
        self.prewrite()
        if crash == 'after_prewrite': return 'CRASH'
        self.commit_ts = self.s.tso()
        if not self.s._commit_key(self.primary, self.start_ts, self.commit_ts): raise Aborted('主锁已经不在了(事务被别人回滚)')
        if crash == 'after_primary': return 'CRASH'
        for k in self.writes:
            if k != self.primary: self.s._commit_key(k, self.start_ts, self.commit_ts)
        return self.commit_ts
