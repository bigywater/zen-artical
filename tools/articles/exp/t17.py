import sys, os, uuid; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
import redis as redislib
from rl import Node as RNode
tee('t17'); reset()
M = MySQL('t17').start(); M.q('create database shop')
M.q('create table ctr(id int primary key, v int, token bigint default 0)', db='shop'); M.q('create table acct(id int primary key, bal int)', db='shop')
RP = free_port(); RN = RNode(RP, 't17_redis').start(); R = redislib.Redis(port=RP, decode_responses=True)
print(f'MySQL {M.q("select version()")[0][0]}(计数器表 ctr、账户表 acct)+ Redis {R.info()["redis_version"]}(自己起的实例,端口 {RP});加锁是 SET key token NX PX ttl,解锁用 Lua 比较 token 之后再删;客户端是 PyMySQL / redis-py')
UNLOCK = R.register_script("if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end")
def acquire(key, ttl_ms, spin=True, timeout=10):
    tok = uuid.uuid4().hex; t0 = time.time()
    while True:
        if R.set(key, tok, nx=True, px=ttl_ms): return tok
        if not spin or time.time() - t0 > timeout: return None
        time.sleep(0.002)
def reset_ctr(v=0): M.q('delete from ctr', db='shop'); M.q('insert into ctr values (1, %s, 0)', (v,), db='shop')
def get_v(): return M.q('select v from ctr where id = 1', db='shop')[0][0]

print('== 一:分布式锁保护“读-改-写”:8 个线程各给同一个计数器加 100 次(应得 800)。不加锁 / 加 Redis 锁 / 不用锁而用一条原子 UPDATE')
def workload(mode, threads=8, per=100):
    reset_ctr(0); lat = []; lk = threading.Lock()
    def w():
        c = M.conn('shop'); cur = c.cursor(); loc = []
        for _ in range(per):
            t0 = time.perf_counter()
            if mode == 'nolock':
                cur.execute('select v from ctr where id = 1'); v = cur.fetchone()[0]; time.sleep(0.0005); cur.execute('update ctr set v = %s where id = 1', (v + 1,))
            elif mode == 'lock':
                tok = acquire('lock:ctr', 5000)
                try:
                    cur.execute('select v from ctr where id = 1'); v = cur.fetchone()[0]; time.sleep(0.0005); cur.execute('update ctr set v = %s where id = 1', (v + 1,))
                finally: UNLOCK(keys=['lock:ctr'], args=[tok])
            else: cur.execute('update ctr set v = v + 1 where id = 1')
            loc.append(time.perf_counter() - t0)
        c.close()
        with lk: lat.extend(loc)
    t0 = time.perf_counter(); ts = [threading.Thread(target=w) for _ in range(threads)]; [t.start() for t in ts]; [t.join() for t in ts]
    return get_v(), time.perf_counter() - t0, lat
rows = []
for mode, name in (('nolock', '不加锁(SELECT 再 UPDATE)'), ('lock', 'Redis 锁 + SELECT 再 UPDATE'), ('atomic', '一条原子 UPDATE v = v + 1')):
    v, dt, lat = workload(mode); rows.append((name, v, 800 - v, f'{dt:.2f} s', f'{800 / dt:.0f}'))
table(rows, ['写法', '最终值(应为 800)', '丢失的更新', '总用时', '操作/秒'])

print('== 二:锁过期而持有者还不知道:A 拿到锁(TTL 500 ms)、读到 v 之后整个进程被冻住 1 秒(SIGSTOP,模拟 GC 停顿 / 虚拟机迁移 / 被换出),B 在锁过期后拿到锁、读写;A 醒来后接着写')
CLIENT = r'''
import sys, time, uuid, pymysql, redis
rport, sock, name, mode = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
R = redis.Redis(port=rport, decode_responses=True); db = pymysql.connect(unix_socket=sock, user='root', password='', database='shop', autocommit=True); cur = db.cursor()
tok = uuid.uuid4().hex; t0 = time.time()
def log(s): print(f'{time.time():.4f} {s}', flush=True)
while True:
    if R.set('lock:ctr', tok, nx=True, px=500):
        fence = R.incr('fence'); break
    time.sleep(0.005)
log(f'LOCKED fence={fence}')
cur.execute('select v from ctr where id = 1'); v = cur.fetchone()[0]; log(f'READ v={v}')
if name == 'A':
    time.sleep(0.3)                                   # 一段“慢操作”;父进程会在这段时间里冻住我
    if mode == 'check':
        mine = R.get('lock:ctr') == tok; log(f'CHECK lock still mine = {mine}')
        if not mine: sys.exit(0)
        log('CHECK_PASSED'); time.sleep(0.2)          # 检查通过之后,写之前的一点点间隙(父进程在这里冻住我)
if mode == 'fence':
    cur.execute('update ctr set v = %s, token = %s where id = 1 and token < %s', (v + 1, fence, fence)); log(f'WROTE v={v + 1} fence={fence} 受影响行数={cur.rowcount}' + (' —— 被存储端拒绝(令牌太旧)' if cur.rowcount == 0 else ''))
else:
    cur.execute('update ctr set v = %s where id = 1', (v + 1,)); log(f'WROTE v={v + 1}')
if R.get('lock:ctr') == tok: R.delete('lock:ctr')
'''
(TT / 't17_client.py').write_text(CLIENT)
def scenario(mode, pause_on):
    reset_ctr(0); R.delete('lock:ctr', 'fence'); lines = []; lk = threading.Lock()
    def spawn(name):
        p = subprocess.Popen([sys.executable, str(TT / 't17_client.py'), str(RP), M.sock, name, mode], stdout=subprocess.PIPE, text=True)
        def rd():
            for l in p.stdout:
                with lk: lines.append((name, l.rstrip()))
        threading.Thread(target=rd, daemon=True).start(); return p
    a = spawn('A')
    def wait(pat, n=0):
        t0 = time.time()
        while time.time() - t0 < 15:
            with lk:
                if any(l.startswith(pat) or pat in l for nm, l in lines): return
            time.sleep(0.005)
    wait(pause_on); t_stop = time.time(); os.kill(a.pid, signal.SIGSTOP)
    b = spawn('B'); b.wait(timeout=20)
    t_b = time.time(); time.sleep(max(0, 1.0 - (time.time() - t_stop))); os.kill(a.pid, signal.SIGCONT); a.wait(timeout=20)
    return lines, t_stop
for mode, pause_on, title in (('plain', 'READ', '没有任何防护(读 → 写)'), ('check', 'CHECK_PASSED', '写之前检查“锁还是不是我的”,检查通过后被冻住')):
    lines, t_stop = scenario(mode, pause_on)
    print(f'  {title}:')
    for nm, l in sorted(lines, key=lambda x: float(x[1].split()[0])):
        ts, msg = l.split(' ', 1); print(f'    {(float(ts) - t_stop) * 1000:7.0f} ms  [{nm}] {msg}')
    print(f'    两个客户端各加了 1 次,计数器应该是 2,实际是 {get_v()} —— 一次更新悄悄丢了,两边都以为自己是在锁保护下写的')

print('== 三:fencing token:加锁时再 INCR 一个只增不减的令牌,写入时由存储端比较(UPDATE ... WHERE token < ?),令牌更旧的写入被拒绝')
lines, t_stop = scenario('fence', 'READ')
for nm, l in sorted(lines, key=lambda x: float(x[1].split()[0])):
    ts, msg = l.split(' ', 1); print(f'    {(float(ts) - t_stop) * 1000:7.0f} ms  [{nm}] {msg}')
print(f'    计数器 = {get_v()},存储里记录的最大令牌 = {M.q("select token from ctr where id = 1", db="shop")[0][0]}:A 的写入被明确拒绝(它知道自己失败了,可以重来),而不是悄悄覆盖 B 的结果')

print('== 四:锁不是事务:持锁者在两步写之间被 kill -9(转账:A 账户扣 100,B 账户加 100,两次独立提交),锁过期后别人照常拿到锁,已经做完的那一步不会回滚')
M.q('delete from acct', db='shop'); M.q('insert into acct values (1, 1000), (2, 1000)', db='shop'); R.delete('lock:ctr')
XFER = r'''
import sys, time, uuid, pymysql, redis
R = redis.Redis(port=int(sys.argv[1]), decode_responses=True); db = pymysql.connect(unix_socket=sys.argv[2], user='root', password='', database='shop', autocommit=True); cur = db.cursor()
tok = uuid.uuid4().hex
assert R.set('lock:xfer', tok, nx=True, px=800); print('LOCKED', flush=True)
cur.execute('update acct set bal = bal - 100 where id = 1'); print('DEBITED', flush=True)
time.sleep(60)
cur.execute('update acct set bal = bal + 100 where id = 2')
'''
(TT / 't17_xfer.py').write_text(XFER)
p = subprocess.Popen([sys.executable, str(TT / 't17_xfer.py'), str(RP), M.sock], stdout=subprocess.PIPE, text=True)
while not p.stdout.readline().startswith('DEBITED'): pass
os.kill(p.pid, signal.SIGKILL); p.wait()
print('  持锁的转账进程在“已扣款、未入账”时被 kill -9;此刻账户:', [tuple(r) for r in M.q('select id, bal from acct order by id', db='shop')], f',锁 lock:xfer 还剩 {R.pttl("lock:xfer")} ms')
time.sleep(1.0)
tok = acquire('lock:xfer', 800, spin=False)
print(f'  1 秒后:别的进程拿到了锁(返回令牌 {"成功" if tok else "失败"}),账户仍是 {[tuple(r) for r in M.q("select id, bal from acct order by id", db="shop")]},两个账户的钱合计 {M.q("select sum(bal) from acct", db="shop")[0][0]}(应为 2000) —— 锁到期只是放行了别人,扣掉的 100 没有谁去回滚')

print('== 五:同一个热点行,三种保护方式的吞吐(8 个线程各 300 次,每次把计数器加 1)')
def bench(mode, threads=8, per=300):
    reset_ctr(0); lat = []; lk = threading.Lock()
    def w():
        c = M.conn('shop', autocommit=False); cur = c.cursor(); loc = []
        for _ in range(per):
            t0 = time.perf_counter()
            if mode == 'redis-lock':
                tok = acquire('lock:ctr', 5000)
                try: cur.execute('select v from ctr where id = 1'); v = cur.fetchone()[0]; cur.execute('update ctr set v = %s where id = 1', (v + 1,)); c.commit()
                finally: UNLOCK(keys=['lock:ctr'], args=[tok])
            elif mode == 'for-update':
                cur.execute('select v from ctr where id = 1 for update'); v = cur.fetchone()[0]; cur.execute('update ctr set v = %s where id = 1', (v + 1,)); c.commit()
            else: cur.execute('update ctr set v = v + 1 where id = 1'); c.commit()
            loc.append(time.perf_counter() - t0)
        c.close()
        with lk: lat.extend(loc)
    t0 = time.perf_counter(); ts = [threading.Thread(target=w) for _ in range(threads)]; [t.start() for t in ts]; [t.join() for t in ts]; dt = time.perf_counter() - t0
    return get_v(), threads * per / dt, sorted(lat)[int(len(lat) * 0.99) - 1], statistics.median(lat)
res = {m: [] for m in ('redis-lock', 'for-update', 'atomic')}
for rnd in range(3):
    for m in res: res[m].append(bench(m))
rows = []
for m, name in (('redis-lock', 'Redis 锁 + SELECT 再 UPDATE'), ('for-update', 'SELECT ... FOR UPDATE 再 UPDATE(一个事务)'), ('atomic', '一条原子 UPDATE v = v + 1')):
    r = res[m]; tps = sorted(x[1] for x in r); p99 = statistics.median(x[2] for x in r); med = statistics.median(x[3] for x in r)
    rows.append((name, f'{statistics.median(tps):.0f}', f'{tps[0]:.0f} ~ {tps[-1]:.0f}', f'{med * 1000:.2f} ms', f'{p99 * 1000:.2f} ms', r[-1][0]))
table(rows, ['写法', '操作/秒(3 轮中位数)', '3 轮范围', '延迟中位数', '延迟 p99', '最终值(应为 2400)'])
print('  数据库自己的行锁 / 原子更新比外面再套一个 Redis 锁便宜,而且不会有“锁过期”的问题;外部锁主要用在被保护的资源没有这种原子能力的时候')
R.close(); RN.kill9()
reset(); (TT / 't17_client.py').unlink(missing_ok=True); (TT / 't17_xfer.py').unlink(missing_ok=True)
shutil.rmtree(TT / 'my_t17', ignore_errors=True)
import rl; shutil.rmtree(rl.RDATA / 't17_redis', ignore_errors=True)
