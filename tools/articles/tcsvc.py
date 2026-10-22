"""TM / RM / TC 三种角色的手写原型(Python + MySQL + HTTP/JSON,不是 Seata):
  python tcsvc.py tc <mysql socket> <port> <事件日志文件>      事务协调者:global_tx / branch / global_lock 三张表在自己的库 tc_db 里,二阶段由后台线程驱动并重试,超时扫描器回滚超时的全局事务,重启后从库里恢复
  python tcsvc.py rm <mysql socket> <port> <库名> <TC 端口> <事件日志文件>   资源管理器:本地事务做分支(前后镜像 + undo_log + 向 TC 申请全局锁),并提供 TC 回调用的 branch_commit / branch_rollback
TM(事务管理器)就是实验脚本里调用 TC 的 /begin /commit /rollback 的那段代码。"""
import sys, json, time, threading, urllib.request, urllib.error, os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import pymysql
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from at import TC as ATC, RM as ATRM, LockConflict, DirtyWrite


def post(url, body, timeout=5):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())


def serve(port, handler_map, name, evlog):
    lk = threading.Lock(); calls = {}
    def log(msg):
        with lk, open(evlog, 'a') as f: f.write(f'{time.time():.4f} [{name}] {msg}\n')
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _do(self):
            n = int(self.headers.get('Content-Length') or 0); body = json.loads(self.rfile.read(n) or b'{}') if n else {}
            path = self.path.split('?')[0]; fn = handler_map.get(path)
            if path == '/stats' and body.get('reset'): calls.clear()
            if path == '/stats':
                data = json.dumps(dict(calls)).encode(); self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data); return
            with lk: calls[path] = calls.get(path, 0) + 1
            try:
                if fn is None: code, out = 404, {'error': 'no such path'}
                else: code, out = fn(body, log)
            except Exception as e: code, out = 500, {'error': f'{type(e).__name__}: {e}'}
            data = json.dumps(out).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        do_POST = _do; do_GET = _do
    srv = ThreadingHTTPServer(('127.0.0.1', port), H); srv.daemon_threads = True
    log(f'启动,监听 {port}'); return srv, log


def run_tc(sock, port, evlog):
    class FakeM:   # 让 at.TC 连到 tc_db;同一个线程里复用连接
        def __init__(self): self.tl = threading.local()
        def conn(self, db, autocommit=True, **kw): return pymysql.connect(unix_socket=sock, user='root', password='', database=db, autocommit=autocommit)
        def q(self, sql, args=None, db=None):
            d = getattr(self.tl, 'd', None)
            if d is None: d = self.tl.d = {}
            if db not in d: d[db] = self.conn(db)
            cur = d[db].cursor(); cur.execute(sql, args); return cur.fetchall()
    m = FakeM(); m.q('create database if not exists tc_db')
    m.q('create table if not exists global_lock(rid varchar(20), pk varchar(40), xid varchar(40), primary key (rid, pk))', db='tc_db')
    m.q('create table if not exists global_tx(xid varchar(40) primary key, status varchar(14), timeout_at datetime(3), created datetime(3) default current_timestamp(3))', db='tc_db')
    m.q('create table if not exists branch(id bigint auto_increment primary key, xid varchar(40), rm varchar(20), rm_url varchar(60), status varchar(14), attempts int default 0, next_try datetime(3) default current_timestamp(3), key kx (xid))', db='tc_db')
    tcl = ATC(m)
    def q(sql, args=None): return m.q(sql, args, db='tc_db')
    def begin(b, log):
        xid = b.get('xid') or f'xid-{time.time_ns()}'; q('insert into global_tx(xid, status, timeout_at) values (%s, %s, now(3) + interval %s microsecond)', (xid, 'BEGIN', int(b.get('timeout_ms', 60000)) * 1000)); log(f'TM → TC  begin {xid}(超时 {b.get("timeout_ms", 60000)} ms)'); return 200, {'xid': xid}
    def register(b, log):
        q('insert into branch(xid, rm, rm_url, status) values (%s, %s, %s, %s)', (b['xid'], b['rm'], b['rm_url'], 'REGISTERED')); bid = q('select max(id) from branch where xid = %s', (b['xid'],))[0][0]; log(f'RM({b["rm"]}) → TC  register 分支 {bid} 到 {b["xid"]}'); return 200, {'branch_id': bid}
    def report(b, log):
        q('update branch set status = %s where id = %s', (b['status'], b['branch_id'])); log(f'RM → TC  report 分支 {b["branch_id"]} = {b["status"]}'); return 200, {}
    def lock(b, log):
        try: w = tcl.acquire(b['xid'], b['rid'], b['pk'], b.get('timeout', 2.0)); log(f'RM → TC  lock {b["rid"]}:{b["pk"]} 给 {b["xid"]}(等了 {w * 1000:.0f} ms)'); return 200, {'ok': True, 'waited': w}
        except LockConflict as e: log(f'RM → TC  lock {b["rid"]}:{b["pk"]} 失败:{e}'); return 409, {'ok': False, 'error': str(e)}
    def decide(st):
        def f(b, log):
            r = q('select status from global_tx where xid = %s', (b['xid'],))
            if not r: return 404, {'error': 'unknown xid'}
            if r[0][0] in ('BEGIN',): q('update global_tx set status = %s where xid = %s', (st, b['xid'])); log(f'TM → TC  {"commit" if st == "COMMITTING" else "rollback"} {b["xid"]}(状态 → {st},二阶段由 TC 的后台线程去做)')
            return 200, {'status': q('select status from global_tx where xid = %s', (b['xid'],))[0][0]}
        return f
    def status(b, log):
        r = q('select status from global_tx where xid = %s', (b['xid'],)); return 200, {'status': r[0][0] if r else None}
    handler = {'/begin': begin, '/register': register, '/report': report, '/lock': lock, '/commit': decide('COMMITTING'), '/rollback': decide('ROLLING_BACK'), '/status': status}
    srv, log = serve(port, handler, 'TC', evlog)
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(8); busy = set(); blk = threading.Lock()
    def phase2(xid, st):
        try:
                    ok = True
                    for bid, rm, url, bst, att in q("select id, rm, rm_url, status, attempts from branch where xid = %s and status not in ('DONE') and next_try <= now(3)", (xid,)):
                        path = '/branch_commit' if st == 'COMMITTING' else '/branch_rollback'
                        try:
                            post(url + path, {'xid': xid, 'branch_id': bid}); q("update branch set status = 'DONE' where id = %s", (bid,)); log(f'TC → RM({rm})  {path[1:]} 分支 {bid} 成功(第 {att + 1} 次)')
                        except Exception as e:
                            ok = False; delay_ms = min(100 * 2 ** att, 1600); q('update branch set attempts = attempts + 1, next_try = now(3) + interval %s microsecond where id = %s', (delay_ms * 1000, bid)); log(f'TC → RM({rm})  {path[1:]} 分支 {bid} 失败(第 {att + 1} 次):{str(e)[:60]};{delay_ms} ms 后重试')
                    if q("select count(*) from branch where xid = %s and status <> 'DONE'", (xid,))[0][0] == 0:
                        final = 'COMMITTED' if st == 'COMMITTING' else 'ROLLED_BACK'; tcl.release(xid); q('update global_tx set status = %s where xid = %s', (final, xid)); log(f'TC  全局事务 {xid} → {final}(全局锁已释放)')
        except Exception as e: log(f'TC 后台线程出错:{e}')
        finally:
            with blk: busy.discard(xid)
    def driver():
        while True:
            try:
                for xid, st in q("select xid, status from global_tx where status in ('COMMITTING', 'ROLLING_BACK')"):
                    with blk:
                        if xid in busy: continue
                        busy.add(xid)
                    pool.submit(phase2, xid, st)
            except Exception as e: log(f'TC 后台线程出错:{e}')
            time.sleep(0.01)
    def timeouts():
        while True:
            try:
                for (xid,) in q("select xid from global_tx where status = 'BEGIN' and timeout_at < now(3)"):
                    q("update global_tx set status = 'ROLLING_BACK' where xid = %s and status = 'BEGIN'", (xid,)); log(f'TC  超时扫描:{xid} 一直没有收到 TM 的决定 → ROLLING_BACK')
            except Exception as e: log(f'TC 超时线程出错:{e}')
            time.sleep(0.1)
    recov = q("select xid, status from global_tx where status in ('COMMITTING', 'ROLLING_BACK')")
    if recov: log(f'TC  启动恢复:库里有 {len(recov)} 个没做完二阶段的全局事务 {[(x, s) for x, s in recov]},继续做')
    threading.Thread(target=driver, daemon=True).start(); threading.Thread(target=timeouts, daemon=True).start(); srv.serve_forever()


def run_rm(sock, port, db, tc_port, evlog):
    class FakeM:
        def __init__(self): self.tl = threading.local()
        def conn(self, db_, autocommit=True, **kw): return pymysql.connect(unix_socket=sock, user='root', password='', database=db_, autocommit=autocommit)
        def q(self, sql, args=None, db=None):
            d = getattr(self.tl, 'd', None)
            if d is None: d = self.tl.d = {}
            k = db or db_
            if k not in d: d[k] = self.conn(k)
            cur = d[k].cursor(); cur.execute(sql, args); return cur.fetchall()
    fm = FakeM()
    class TCClient:   # RM 访问 TC 的全局锁,走 HTTP
        def acquire(self, xid, rid, pk, timeout=2.0):
            try: return post(f'http://127.0.0.1:{tc_port}/lock', {'xid': xid, 'rid': rid, 'pk': str(pk), 'timeout': timeout}, timeout=timeout + 3)['waited']
            except urllib.error.HTTPError as e: raise LockConflict(json.loads(e.read()).get('error', '全局锁冲突'))
    rm = ATRM(fm, db, TCClient(), db)
    faults = {'branch_rollback': 0, 'branch_commit': 0}; flk = threading.Lock()
    def do(b, log):
        xid = b['xid']; rep = post(f'http://127.0.0.1:{tc_port}/register', {'xid': xid, 'rm': db, 'rm_url': f'http://127.0.0.1:{port}'}); bid = rep['branch_id']
        try:
            before, after, waited = rm.branch_update(xid, b['table'], b['pk'], b['sets'], b['params'], lock_timeout=b.get('lock_timeout', 2.0))
            post(f'http://127.0.0.1:{tc_port}/report', {'branch_id': bid, 'status': 'PHASE1_DONE'}); log(f'TM → RM({db})  业务调用:{b["table"]}#{b["pk"]} {before} → {after},本地已提交,分支 {bid} 报告 PHASE1_DONE'); return 200, {'branch_id': bid}
        except Exception as e:
            post(f'http://127.0.0.1:{tc_port}/report', {'branch_id': bid, 'status': 'PHASE1_FAILED'}); log(f'RM({db})  分支 {bid} 一阶段失败:{type(e).__name__}'); return 500, {'error': f'{type(e).__name__}: {e}'}
    def maybe_fail(name):
        with flk:
            if faults[name] > 0: faults[name] -= 1; raise RuntimeError(f'{name} 被注入了故障')
    def bcommit(b, log):
        maybe_fail('branch_commit'); rm.commit_global(b['xid']); log(f'RM({db})  branch_commit:删除 undo_log({b["xid"]})'); return 200, {}
    def brollback(b, log):
        maybe_fail('branch_rollback'); done = rm.rollback_global(b['xid']); log(f'RM({db})  branch_rollback:按 undo_log 恢复 {[(t, p) for t, p, _ in done]},删除 undo_log'); return 200, {}
    def fault(b, log):
        with flk: faults[b['path']] = int(b['n'])
        return 200, {}
    srv, log = serve(port, {'/do': do, '/branch_commit': bcommit, '/branch_rollback': brollback, '/fault': fault}, f'RM:{db}', evlog); srv.serve_forever()


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'tc': run_tc(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    else: run_rm(sys.argv[2], int(sys.argv[3]), sys.argv[4], int(sys.argv[5]), sys.argv[6])
