import sys, os, json, http.client, hashlib, uuid; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import pymysql
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
tee('t28'); reset()
M = MySQL('t28').start(); M.q('create database shop')
M.q('create table orders(id bigint auto_increment primary key, ext_id varchar(40) unique, amount int, created datetime(3) default current_timestamp(3))', db='shop')
M.q('create table idem(k varchar(60) primary key, fp varchar(64), status varchar(12), code int, body text, created datetime(3) default current_timestamp(3))', db='shop')
TTL = {'s': 3600.0}; tl = threading.local()
def dbc():
    if getattr(tl, 'c', None) is None: tl.c = M.conn('shop', autocommit=False)
    return tl.c
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def reply(self, code, obj, extra=None):
        data = json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data)))
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers()
        try: self.wfile.write(data)
        except Exception: pass
    def body(self): n = int(self.headers.get('Content-Length') or 0); return self.rfile.read(n) if n else b''
    def slow(self): time.sleep(int(self.headers.get('X-Slow-Ms', '0')) / 1000.0)
    def do_POST(self):
        raw = self.body(); c = dbc(); cur = c.cursor()
        if self.path == '/orders':                                         # 没有任何幂等处理
            self.slow(); cur.execute('insert into orders(amount) values (%s)', (json.loads(raw)['amount'],)); oid = cur.lastrowid; c.commit(); return self.reply(201, {'order_id': oid})
        if self.path == '/v2/orders':                                      # 带 Idempotency-Key
            key = self.headers.get('Idempotency-Key')
            if not key: return self.reply(400, {'error': '缺少 Idempotency-Key'})
            fp = hashlib.sha256(raw).hexdigest()
            for _try in range(2):
                try: cur.execute("insert into idem(k, fp, status) values (%s, %s, 'PROCESSING')", (key, fp)); c.commit(); break
                except pymysql.err.IntegrityError:
                    c.rollback(); cur.execute("select fp, status, code, body, created < now(3) - interval %s microsecond from idem where k = %s", (int(TTL['s'] * 1e6), key)); r = cur.fetchone(); c.commit()
                    if r and r[4] and r[1] == 'DONE': cur.execute('delete from idem where k = %s', (key,)); c.commit(); continue      # 记录已经过期:当作新请求,清掉旧记录再占位
                    if r is None: return self.reply(409, {'error': '记录刚被清理,请重试'}, {'Retry-After': '0'})
                    if r[0] != fp: return self.reply(422, {'error': '同一个 Idempotency-Key 对应了不同的请求内容'})
                    if r[1] == 'PROCESSING': return self.reply(409, {'error': '这个请求正在处理中'}, {'Retry-After': '0'})
                    return self.reply(r[2], json.loads(r[3]), {'Idempotent-Replayed': 'true'})
            self.slow()
            cur.execute('insert into orders(amount) values (%s)', (json.loads(raw)['amount'],)); oid = cur.lastrowid
            cur.execute("update idem set status = 'DONE', code = 201, body = %s where k = %s", (json.dumps({'order_id': oid}), key)); c.commit(); return self.reply(201, {'order_id': oid})
        self.reply(404, {})
    def do_PUT(self):                                                      # 客户端自己选订单号:天然幂等
        raw = self.body(); c = dbc(); cur = c.cursor(); ext = self.path.rsplit('/', 1)[-1]; self.slow()
        cur.execute('insert into orders(ext_id, amount) values (%s, %s) on duplicate key update amount = values(amount)', (ext, json.loads(raw)['amount'])); c.commit(); self.reply(200, {'ext_id': ext})
PORT = free_port(); srv = ThreadingHTTPServer(('127.0.0.1', PORT), H); srv.daemon_threads = True; threading.Thread(target=srv.serve_forever, daemon=True).start()
print(f'一个很小的 HTTP 服务(Python http.server,线程化,{PORT} 端口)+ MySQL {M.q("select version()")[0][0]}:POST /orders 没有任何幂等处理;POST /v2/orders 要求 Idempotency-Key 头(idem 表:key 主键 + 请求指纹 + 状态 + 保存的响应);PUT /orders/<外部订单号> 由客户端选订单号。请求头 X-Slow-Ms 让服务端这次处理故意慢多少毫秒(模拟下游慢),客户端超时设 100 ms')
def call(method, path, body, headers=None, timeout=0.1):
    c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=timeout)
    try:
        c.request(method, path, json.dumps(body), {'Content-Type': 'application/json', **(headers or {})}); r = c.getresponse(); d = r.read(); return r.status, (json.loads(d) if d else {}), dict(r.getheaders())
    except (socket.timeout, TimeoutError): return 'timeout', None, {}
    finally: c.close()
def reset_db(): M.q('delete from orders', db='shop'); M.q('delete from idem', db='shop')
def n_orders(): return M.q('select count(*) from orders', db='shop')[0][0]
def run_logical(n, path, use_key, slow_ratio=0.3, seed=28, method='POST', attempts=3, ext=False):
    reset_db(); rng = random.Random(seed); seqs = {}; outcome = {'client 最终拿到订单号': 0, 'client 放弃了(没拿到响应)': 0}
    for i in range(n):
        slow = 250 if rng.random() < slow_ratio else 0; hdr = {'X-Slow-Ms': str(slow)}; key = f'k-{uuid.uuid4().hex[:8]}'
        if use_key: hdr['Idempotency-Key'] = key
        p = f'{path}/{key}' if ext else path; trace = []; got = False
        for a in range(attempts):
            st, body, h = call(method, p, {'amount': 100}, hdr); trace.append(st if h.get('Idempotent-Replayed') != 'true' else f'{st}(重放)')
            if st in (200, 201): got = True; break
            if st == 409: time.sleep(0.2)
        outcome['client 最终拿到订单号' if got else 'client 放弃了(没拿到响应)'] += 1; seqs[tuple(map(str, trace))] = seqs.get(tuple(map(str, trace)), 0) + 1
    time.sleep(0.5); return seqs, outcome

print('== 一:没有幂等处理的 POST /orders:客户端超时 100 ms、最多尝试 3 次;30% 的请求服务端这次处理要 250 ms(客户端会先超时)。200 个逻辑请求,看库里一共多出多少订单')
seqs, out = run_logical(200, '/orders', False); total = n_orders()
print(f'  客户端:{out};库里的订单数 {total}(逻辑请求 200 个,多出 {total - 200} 个重复订单)')
print('  各种请求序列(每次尝试的结果)的个数:' + ';'.join(f'{"→".join(k)}:{v}' for k, v in sorted(seqs.items(), key=lambda x: -x[1])))
print('  超时的那次其实已经(或者马上)在服务端建好了订单,客户端不知道,重试又建一个')

print('== 二:同样的负载,POST /v2/orders + Idempotency-Key(每个逻辑请求一个 key,重试用同一个 key;遇到 409 等 0.2 秒再试)')
seqs, out = run_logical(200, '/v2/orders', True); total = n_orders()
print(f'  客户端:{out};库里的订单数 {total}(多出 {total - 200} 个);idem 表 {M.q("select count(*) from idem", db="shop")[0][0]} 行(DONE {M.q("select count(*) from idem where status = %s", ("DONE",), db="shop")[0][0]} 行)')
print('  各种请求序列的个数:' + ';'.join(f'{"→".join(k)}:{v}' for k, v in sorted(seqs.items(), key=lambda x: -x[1])))
print('  慢请求:第一次超时(服务端还在处理)→ 第二次遇到 PROCESSING 返回 409 → 等 0.2 s 后第三次拿到保存的响应(带 Idempotent-Replayed: true);服务端从头到尾只执行了一次')

print('== 三:两个相同的请求同时到达(同一个 key):100 对,各自是什么结果')
reset_db(); res = {}
for i in range(100):
    key = f'c-{i}'; out = []; bar = threading.Barrier(2); lk = threading.Lock()
    def w():
        bar.wait(); st, body, h = call('POST', '/v2/orders', {'amount': 100}, {'Idempotency-Key': key, 'X-Slow-Ms': '30'}, timeout=2)
        with lk: out.append(f'{st}(重放)' if h.get('Idempotent-Replayed') == 'true' else str(st))
    ts = [threading.Thread(target=w) for _ in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]; k = tuple(sorted(out)); res[k] = res.get(k, 0) + 1
print('  结果组合:' + ';'.join(f'{" + ".join(k)}:{v}' for k, v in res.items()) + f';库里订单数 {n_orders()}(应为 100)')
print('  两个同时到达的相同请求里只有一个抢到 PROCESSING 占位去执行,另一个拿到 409(正在处理中);订单只建一个')

print('== 四:同一个 key、不同的请求内容:不能把旧请求的响应原样还给新请求')
reset_db(); st1, b1, _ = call('POST', '/v2/orders', {'amount': 100}, {'Idempotency-Key': 'same-key'}, 2); st2, b2, h2 = call('POST', '/v2/orders', {'amount': 100}, {'Idempotency-Key': 'same-key'}, 2); st3, b3, _ = call('POST', '/v2/orders', {'amount': 999}, {'Idempotency-Key': 'same-key'}, 2)
print(f'  第 1 次(amount=100):{st1} {b1};第 2 次(同样内容):{st2} {b2} Idempotent-Replayed={h2.get("Idempotent-Replayed")};第 3 次(amount=999,同一个 key):{st3} {b3};库里订单数 {n_orders()}')

print('== 五:幂等键的有效期:key 记录只保留 TTL 这么久。TTL 设成 0.5 秒时,客户端 1 秒之后才重试(比如离线重发),服务端已经不认识这个 key')
reset_db(); TTL['s'] = 0.5
st1, b1, _ = call('POST', '/v2/orders', {'amount': 100}, {'Idempotency-Key': 'late-key'}, 2); time.sleep(1.0); st2, b2, h2 = call('POST', '/v2/orders', {'amount': 100}, {'Idempotency-Key': 'late-key'}, 2)
print(f'  第 1 次:{st1} {b1};1 秒后用同一个 key 重试:{st2} {b2} Idempotent-Replayed={h2.get("Idempotent-Replayed")};库里订单数 {n_orders()}(同一个请求被执行了两次)'); TTL['s'] = 3600.0
print('  key 的保留期必须比客户端可能重试的最长窗口(包括离线队列、人工重发)长')

print('== 六:不用幂等键,让客户端自己选订单号:PUT /orders/<外部订单号>(服务端用 INSERT ... ON DUPLICATE KEY UPDATE)。同样 200 个逻辑请求、同样的超时重试')
seqs, out = run_logical(200, '/orders', False, method='PUT', ext=True); total = n_orders()
print(f'  客户端:{out};库里的订单数 {total}(多出 {total - 200} 个);idem 表 {M.q("select count(*) from idem", db="shop")[0][0]} 行')
print('  各种请求序列的个数:' + ';'.join(f'{"→".join(k)}:{v}' for k, v in sorted(seqs.items(), key=lambda x: -x[1])))
print('  PUT 本身就是幂等的:同一个外部订单号重复提交只会覆盖同一行,不需要额外的 key 表;但它要求客户端能提前生成稳定的订单号,而且“两次 PUT 之间别人改过”的情形要靠版本 / 条件请求(If-Match)另外处理')
srv.shutdown(); reset(); shutil.rmtree(TT / 'my_t28', ignore_errors=True)
