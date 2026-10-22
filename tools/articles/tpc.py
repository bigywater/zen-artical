"""两阶段提交协调者(自己写的,Python):参与者是真实的 PostgreSQL 实例(PREPARE TRANSACTION / COMMIT PREPARED / ROLLBACK PREPARED)。
决定日志写在协调者自己的 SQLite 文件里(synchronous=FULL,等价于“先把决定落盘再通知参与者”)。
可以当库用,也可以当脚本跑(给 t3 用:python tpc.py <日志文件> <xid> <崩溃点> <name=port> ...,崩溃点到了就 kill -9 自己)。"""
import os, sys, time, signal, sqlite3, json
import psycopg


def pgconn(port, autocommit=True):
    return psycopg.connect(f'host=127.0.0.1 port={port} user=postgres dbname=postgres', autocommit=autocommit)


class Coord:
    def __init__(self, ports, logpath, say=print):
        self.ports = dict(ports); self.logpath = logpath; self.say = say
        db = sqlite3.connect(logpath); db.execute('pragma synchronous=FULL')
        db.execute('create table if not exists decision(xid text primary key, decision text, ts real)'); db.commit(); db.close()

    def log_decision(self, xid, d):
        db = sqlite3.connect(self.logpath); db.execute('pragma synchronous=FULL')
        db.execute('insert or replace into decision values(?,?,?)', (xid, d, time.time())); db.commit(); db.close()

    def decision(self, xid):
        db = sqlite3.connect(self.logpath); r = db.execute('select decision from decision where xid=?', (xid,)).fetchone(); db.close()
        return r[0] if r else None

    def crash(self, here, at):
        if here == at:
            self.say(f'  [协调者] 在“{here}”被 kill -9'); sys.stdout.flush()
            os.kill(os.getpid(), signal.SIGKILL)

    def run(self, xid, work, crash=None, hold=0.0, fail_on=None, conns=None, hook=None, log_first=True):
        """work: {rm 名: [SQL...]};hold: 全部 prepare 完到发 COMMIT PREPARED 之间故意等多久(模拟慢协调者 / 慢网络)。返回 'COMMIT' 或 'ABORT'。"""
        own = conns is None
        conns = conns or {n: pgconn(p) for n, p in self.ports.items() if n in work}
        prepared = []
        self.crash('开始之前', crash)
        try:
            for n, sqls in work.items():
                c = conns[n]; c.execute('begin')
                for q in sqls: c.execute(q)
                if fail_on == n: raise RuntimeError(f'{n} 投了反对票(模拟)')
                c.execute(f"prepare transaction '{xid}'"); prepared.append(n)
                self.say(f'  [协调者] {n}: PREPARE TRANSACTION \'{xid}\' -> 投 YES')
                if len(prepared) == 1:
                    self.crash('第一个参与者 prepare 之后', crash)
                    if hook: hook()
        except Exception as e:
            self.say(f'  [协调者] 阶段一失败:{e}')
            for n in work:
                try:
                    if n in prepared: conns[n].execute(f"rollback prepared '{xid}'")
                    else: conns[n].execute('rollback')
                except Exception as e2: self.say(f'  [协调者] {n} 回滚出错:{e2}')
            self.log_decision(xid, 'ABORT'); return 'ABORT'
        self.crash('全部 prepare 之后、写决定日志之前', crash)
        if log_first:
            self.log_decision(xid, 'COMMIT'); self.say('  [协调者] 决定日志已落盘:COMMIT')
        self.crash('决定日志落盘之后、发出第一个 COMMIT PREPARED 之前', crash)
        if hold: time.sleep(hold)
        for i, n in enumerate(work):
            conns[n].execute(f"commit prepared '{xid}'"); self.say(f'  [协调者] {n}: COMMIT PREPARED \'{xid}\' -> OK')
            if i == 0 and len(work) > 1: self.crash('第一个 COMMIT PREPARED 之后、第二个之前', crash)
            if i == 0 and not log_first:
                self.log_decision(xid, 'COMMIT'); self.say('  [协调者] (错误顺序)决定日志现在才落盘:COMMIT')
        if own:
            for c in conns.values(): c.close()
        return 'COMMIT'

    def prepared(self):
        out = {}
        for n, p in self.ports.items():
            try:
                with pgconn(p) as c: out[n] = [r[0] for r in c.execute('select gid from pg_prepared_xacts order by gid').fetchall()]
            except Exception: out[n] = None
        return out

    def recover(self, how='log'):
        """how='log':按决定日志收尾(有 COMMIT 就提交,没有就回滚);how='abort':没有日志可看,一律回滚。返回 [(rm, gid, 动作)]。"""
        acts = []
        for n, p in self.ports.items():
            with pgconn(p) as c:
                for (gid,) in c.execute('select gid from pg_prepared_xacts order by gid').fetchall():
                    d = self.decision(gid) if how == 'log' else None
                    if d == 'COMMIT': c.execute(f"commit prepared '{gid}'"); acts.append((n, gid, 'COMMIT PREPARED'))
                    else: c.execute(f"rollback prepared '{gid}'"); acts.append((n, gid, 'ROLLBACK PREPARED'))
        return acts


if __name__ == '__main__':
    CRASHES = {'0': '开始之前', '1': '第一个参与者 prepare 之后', '2': '全部 prepare 之后、写决定日志之前', '3': '决定日志落盘之后、发出第一个 COMMIT PREPARED 之前', '4': '第一个 COMMIT PREPARED 之后、第二个之前'}
    log, xid, crash, order = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]   # order:'ok' 先写日志(正确),'bad' 先发 COMMIT PREPARED 再写日志
    ports = dict(a.split('=') for a in sys.argv[5:]); ports = {k: int(v) for k, v in ports.items()}
    co = Coord(ports, log)
    work = {'订单库': ["insert into orders values(1, 'CREATED')"], '库存库': ["update stock set qty = qty - 1 where sku='sku-1'"]}
    print(co.run(xid, work, crash=CRASHES.get(crash), log_first=(order == 'ok')))
