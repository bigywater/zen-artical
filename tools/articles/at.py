"""最小的 AT 模式实现(自己写的,Python + MySQL;不是 Seata):
- RM(资源管理器)= 一个业务库连接 + 本库的 undo_log 表;分支执行时在同一个本地事务里:读前镜像(FOR UPDATE)→ 改 → 读后镜像 → 写 undo_log → 向 TC 申请全局锁 → 本地提交(本地行锁此时就释放了)。
- TC(事务协调者)= 自己的库里的 global_lock(rid, pk 唯一)和 global_tx 表;全局提交只是删 undo_log、放全局锁;全局回滚是按后镜像校验、按前镜像恢复。"""
import json, time, threading, pymysql


class LockConflict(Exception): pass
class DirtyWrite(Exception): pass


class TC:
    def __init__(self, mysql, db='tc_db'):
        self.m = mysql; self.db = db; mysql.q(f'create database if not exists {db}')
        mysql.q('create table if not exists global_lock(rid varchar(20), pk varchar(40), xid varchar(40), primary key (rid, pk))', db=db)
        mysql.q('create table if not exists global_tx(xid varchar(40) primary key, status varchar(12), created datetime(3) default current_timestamp(3))', db=db)
        self.tl = threading.local()

    def c(self):
        if getattr(self.tl, 'c', None) is None: self.tl.c = self.m.conn(self.db)
        return self.tl.c

    def begin(self, xid): self.c().cursor().execute("insert into global_tx(xid, status) values (%s, 'BEGIN')", (xid,))
    def set_status(self, xid, st): self.c().cursor().execute('update global_tx set status = %s where xid = %s', (st, xid))

    def acquire(self, xid, rid, pk, timeout=2.0):
        t0 = time.perf_counter(); cur = self.c().cursor()
        while True:
            try: cur.execute('insert into global_lock values (%s, %s, %s)', (rid, str(pk), xid)); return time.perf_counter() - t0
            except pymysql.err.IntegrityError:
                cur.execute('select xid from global_lock where rid = %s and pk = %s', (rid, str(pk))); r = cur.fetchone()
                if r and r[0] == xid: return time.perf_counter() - t0
                if time.perf_counter() - t0 > timeout: raise LockConflict(f'{rid}:{pk} 的全局锁被 {r[0] if r else "?"} 持有,等了 {timeout}s')
                time.sleep(0.005)

    def release(self, xid): self.c().cursor().execute('delete from global_lock where xid = %s', (xid,))
    def holder(self, rid, pk):
        cur = self.c().cursor(); cur.execute('select xid from global_lock where rid = %s and pk = %s', (rid, str(pk))); r = cur.fetchone(); return r[0] if r else None


class RM:
    def __init__(self, mysql, db, tc, rid):
        self.m = mysql; self.db = db; self.tc = tc; self.rid = rid; self.tl = threading.local()
        mysql.q(f'create table if not exists undo_log(id bigint auto_increment primary key, xid varchar(40), tbl varchar(30), pk varchar(40), before_image json, after_image json, key kx (xid))', db=db)

    def c(self):
        if getattr(self.tl, 'c', None) is None: self.tl.c = self.m.conn(self.db, autocommit=False)
        return self.tl.c

    def _row(self, cur, tbl, pk):
        cur.execute(f'select * from {tbl} where id = %s', (pk,)); r = cur.fetchone()
        return dict(zip([d[0] for d in cur.description], r)) if r else None

    def branch_update(self, xid, tbl, pk, sets, params, lock_timeout=2.0, use_global_lock=True):
        c = self.c(); cur = c.cursor()
        try:
            cur.execute(f'select * from {tbl} where id = %s for update', (pk,)); r = cur.fetchone(); before = dict(zip([d[0] for d in cur.description], r)) if r else None
            cur.execute(f'update {tbl} set {sets} where id = %s', (*params, pk)); after = self._row(cur, tbl, pk)
            cur.execute('insert into undo_log(xid, tbl, pk, before_image, after_image) values (%s, %s, %s, %s, %s)', (xid, tbl, str(pk), json.dumps(before), json.dumps(after)))
            waited = self.tc.acquire(xid, self.rid + '.' + tbl, pk, lock_timeout) if use_global_lock else 0.0     # 全局锁在本地提交之前拿
            c.commit(); return before, after, waited
        except Exception: c.rollback(); raise

    def commit_global(self, xid):
        c = self.c(); c.cursor().execute('delete from undo_log where xid = %s', (xid,)); c.commit()

    def rollback_global(self, xid, retry=5):
        c = self.c(); cur = c.cursor(); cur.execute('select id, tbl, pk, before_image, after_image from undo_log where xid = %s order by id desc', (xid,)); logs = cur.fetchall(); c.commit(); done = []
        for id_, tbl, pk, bi, ai in logs:
            bi = json.loads(bi) if isinstance(bi, str) else bi; ai = json.loads(ai) if isinstance(ai, str) else ai
            cur.execute(f'select * from {tbl} where id = %s for update', (pk,)); r = cur.fetchone(); now = dict(zip([d[0] for d in cur.description], r)) if r else None
            norm = lambda d: {k: (str(v) if v is not None else None) for k, v in (d or {}).items()}
            if norm(now) != norm(ai): c.rollback(); raise DirtyWrite(f'{tbl}#{pk} 当前值 {now} 不等于这个分支提交后的值 {ai}:有人在全局事务之外改过它,不能直接按前镜像恢复')
            sets = ', '.join(f'{k} = %s' for k in bi if k != 'id'); cur.execute(f'update {tbl} set {sets} where id = %s', ([bi[k] for k in bi if k != 'id'] + [pk])); cur.execute('delete from undo_log where id = %s', (id_,)); done.append((tbl, pk, bi))
        c.commit(); return done
