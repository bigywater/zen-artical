import sys, os, json, time, signal, subprocess, textwrap, threading, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import redis
tee('p66')
d = pdir('p66'); P = free_port(9700)
srvp = subprocess.Popen(['redis-server', '--port', str(P), '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--dir', str(d), '--daemonize', 'no'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
r = redis.Redis(port=P, decode_responses=True)
for _ in range(100):
    try: r.ping(); break
    except Exception: time.sleep(0.05)
CLAIM = """local x = redis.call('RPOP', KEYS[1]); if not x then return nil end
local t = redis.call('TIME'); redis.call('ZADD', KEYS[2], t[1] + t[2] / 1e6 + ARGV[1], x); return x"""
REAP = """local t = redis.call('TIME'); local now = t[1] + t[2] / 1e6
local ex = redis.call('ZRANGEBYSCORE', KEYS[2], '-inf', now); local n = 0
for _, x in ipairs(ex) do
  redis.call('ZREM', KEYS[2], x); local a = redis.call('HINCRBY', KEYS[3], x, 1)
  if tonumber(ARGV[1]) > 0 and a >= tonumber(ARGV[1]) then redis.call('LPUSH', KEYS[4], x) else redis.call('LPUSH', KEYS[1], x); n = n + 1 end
end
return n"""
CHILD = textwrap.dedent('''
    import sys, os, json, time, signal, threading, redis
    cfg = json.loads(sys.argv[1]); r = redis.Redis(port=cfg['port'], decode_responses=True)
    name, mode = cfg['name'], cfg['mode']; claim = r.register_script(cfg['claim'])
    def die(): os.kill(os.getpid(), signal.SIGKILL)
    def beat(x, stop):
        while not stop.wait(cfg['hb']):
            r.eval("local t = redis.call('TIME'); return redis.call('ZADD', KEYS[1], 'XX', t[1] + t[2] / 1e6 + ARGV[1], ARGV[2])", 1, 'leases', cfg['lease'], x)
    idle = 0
    while True:
        if mode == 'naive': it = r.brpop('queue', timeout=1); x = it[1] if it else None
        elif mode == 'lmove': x = r.blmove('queue', 'proc:' + name, 1, 'RIGHT', 'LEFT')
        elif mode == 'lease': x = claim(keys=['queue', 'leases'], args=[cfg['lease']]); 
        elif mode == 'nonatomic':
            x = r.rpop('queue')
            if x and cfg.get('die_between') == x and r.set('crashed', 1, nx=True): die()
            if x: r.eval("local t = redis.call('TIME'); return redis.call('ZADD', KEYS[1], t[1] + t[2] / 1e6 + ARGV[1], ARGV[2])", 1, 'leases', cfg['lease'], x)
        if not x:
            idle += 1
            if idle >= cfg.get('idle', 2): break
            time.sleep(0.2); continue
        idle = 0; n = r.hincrby('execs', x, 1); r.rpush('log', f'{time.time():.3f} {name} start {x} #{n}')
        if cfg.get('die_after_claim') == x and r.set('crashed', 1, nx=True): die()
        if cfg.get('die_on') == x and (cfg.get('always') or r.set('crashed:' + x, 1, nx=True)): die()
        stop = threading.Event()
        if cfg.get('hb') and mode == 'lease': threading.Thread(target=beat, args=(x, stop), daemon=True).start()
        time.sleep(cfg['slow'] if x == cfg.get('slow_task') else cfg.get('work', 0.02)); stop.set()
        r.incr('effects_raw')
        if r.sadd('effected', x): r.incr('effects_guarded')
        r.sadd('done', x); r.rpush('log', f'{time.time():.3f} {name} finish {x}')
        if cfg.get('die_before_ack') == x and r.set('crashed:' + x, 1, nx=True): die()
        if mode == 'lmove': r.lrem('proc:' + name, 1, x)
        elif mode in ('lease', 'nonatomic'): r.zrem('leases', x)
''')
open(d / 'child.py', 'w').write(CHILD)
def waitall(ws, timeout=None):
    t0 = time.time()
    for w in ws:
        try: w.wait(None if timeout is None else max(0.01, timeout - (time.time() - t0)))
        except subprocess.TimeoutExpired: w.terminate(); w.wait()
def reset(n, prefix='t'):
    r.flushall(); r.lpush('queue', *[f'{prefix}{i}' for i in range(n)])
def spawn(name, mode, **kw):
    cfg = dict(port=P, name=name, mode=mode, claim=CLAIM, lease=0.5, **kw)
    return subprocess.Popen([sys.executable, str(d / 'child.py'), json.dumps(cfg)])
def reaper(stop, every=0.1, max_attempts=0):
    rp = r.register_script(REAP); cnt = [0]
    def run():
        while not stop.wait(every): cnt[0] += rp(keys=['queue', 'leases', 'attempts', 'dead'], args=[max_attempts])
    th = threading.Thread(target=run, daemon=True); th.start(); return cnt
def summary(n):
    done = r.scard('done'); lost = sorted(set(f't{i}' for i in range(n)) - set(r.smembers('done')) - set(r.lrange('queue', 0, -1)) - set(r.zrange('leases', 0, -1)) - set(r.lrange('dead', 0, -1)))
    return done, lost
def execs(): return {k: int(v) for k, v in r.hgetall('execs').items()}
try:
    print('== 一:最简单的队列:worker 用 BRPOP 取任务(取出就从队列里删了),第一个取到 t50 的 worker 在处理它时被 kill -9')
    N = 200; reset(N); ws = [spawn(f'w{k}', 'naive', die_on='t50') for k in range(3)]
    waitall(ws)
    done, lost = summary(N); ex = execs(); dead = [f'w{k}' for k, w in enumerate(ws) if w.returncode and w.returncode < 0]
    print(f'  {N} 个任务,3 个 worker(其中 {dead} 被信号 {[-w.returncode for w in ws if w.returncode and w.returncode < 0]} 杀掉):完成 {done} 个,队列里剩 {r.llen("queue")} 个,丢失(既不在队列里也没完成){len(lost)} 个 {lost};t50 被执行了 {ex.get("t50")} 次')
    print('== 二:把任务先移到"正在处理"列表(BLMOVE queue → proc:<worker>),处理完再从列表删除(ack);worker 死了之后,由监控进程把它的列表放回队列')
    for lab, kw in (('处理 t50 中途被杀', dict(die_on='t50')), ('t50 处理完、ack 之前被杀', dict(die_before_ack='t50'))):
        reset(N); ws = [spawn(f'w{k}', 'lmove', **kw) for k in range(3)]
        waitall(ws)
        dk = [f'w{k}' for k, w in enumerate(ws) if w.returncode and w.returncode < 0]; stuck = r.lrange('proc:' + dk[0], 0, -1) if dk else []; done0, _ = summary(N)
        print(f'  {lab}:worker 结束后(死掉的是 {dk}) 完成 {done0} 个,队列剩 {r.llen("queue")} 个,死掉的 worker 的"正在处理"列表里留着 {stuck}')
        for x in stuck: r.lmove('proc:' + dk[0], 'queue', 'LEFT', 'RIGHT')      # 监控进程看到该 worker 退出码非 0,把它的任务放回队列
        w3 = spawn('w3', 'lmove'); w3.wait(); ex = execs(); d3, _ = summary(N)
        print(f'     放回队列、w3 接手后:完成 {d3} 个;t50 被执行 {ex.get("t50")} 次;全部任务共执行 {sum(ex.values())} 次(去重后 {len(ex)} 个任务)')
    print('== 三:租约(lease):取任务时在有序集合 leases 里记下到期时间(租约 0.5 秒),处理完删除;监控线程每 0.1 秒把到期的任务放回队列。取任务这一步用 Lua 脚本一次做完')
    reset(10); stop = threading.Event(); cnt = reaper(stop)
    ws = [spawn('w0', 'lease', die_on='t5'), spawn('w1', 'lease')]
    waitall(ws)
    stop.set(); time.sleep(0.2)
    # w0 死了之后 w1 可能已退出;再起一个 worker 收尾
    stop = threading.Event(); cnt = reaper(stop); w2 = spawn('w2', 'lease'); w2.wait(); stop.set()
    lg = [l.split() for l in r.lrange('log', 0, -1)]; st = [float(l[0]) for l in lg if l[2] == 'start' and l[3] == 't5']
    done, lost = summary(10)
    print(f'  (a) 某个 worker 处理 t5 时被杀:最终完成 {done}/10,丢失 {len(lost)};t5 两次开始执行相隔 {st[1] - st[0]:.2f} 秒(租约 0.5 秒,监控每 0.1 秒扫一次)' if len(st) >= 2 else f'  (a) t5 开始执行 {len(st)} 次;完成 {done}/10')
    for lab, kw, mx, cap in (('(b) 租约 0.5 秒,t0 要处理 0.8 秒,不续约,只让 worker 跑 4 秒', dict(slow_task='t0', slow=0.8), 0, 4.0), ('(c) 同上,但处理期间每 0.2 秒续约一次', dict(slow_task='t0', slow=0.8, hb=0.2), 0, 8.0), ('(d) 同 (b),但监控最多把同一个任务放回 3 次,再多就放进 dead 列表', dict(slow_task='t0', slow=0.8), 3, 8.0)):
        reset(6); stop = threading.Event(); cnt = reaper(stop, 0.1, mx)
        ws = [spawn('w0', 'lease', **kw), spawn('w1', 'lease', **kw)]
        waitall(ws, cap); stop.set(); ex = execs(); lg = [l.split() for l in r.lrange('log', 0, -1) if ' t0' in l]
        names = [f'{l[1]}:{l[2]}' for l in lg]
        print(f'  {lab}:t0 被执行 {ex.get("t0")} 次;监控把到期的任务放回队列 {cnt[0]} 次,进了 dead 列表 {r.lrange("dead", 0, -1)};t0 的事件顺序 {names}')
    print('== 四:取任务分两步(RPOP 再 ZADD 记租约)与一个 Lua 脚本的区别——在两步之间让 worker 崩溃(崩溃点是我注入的)')
    N = 10; reset(N)
    ws = [spawn('w0', 'nonatomic', die_between='t3', idle=3)]; waitall(ws); stop = threading.Event(); cnt = reaper(stop); w1 = spawn('w1', 'nonatomic', idle=4); w1.wait(); time.sleep(0.8); stop.set()
    w1 = spawn('w1b', 'nonatomic', idle=3); w1.wait(); done, lost = summary(N)
    print(f'  两步取任务,在 RPOP 之后、ZADD 之前崩溃:最终完成 {done}/{N},丢失 {len(lost)} 个 {lost}(任务不在队列里、也没有租约,监控找不到它)')
    reset(N); w0 = spawn('w0', 'lease', die_after_claim='t3'); w0.wait(); stop = threading.Event(); cnt = reaper(stop); w1 = spawn('w1', 'lease', idle=4); w1.wait(); time.sleep(0.8); stop.set(); w1 = spawn('w1b', 'lease', idle=3); w1.wait(); done, lost = summary(N)
    print(f'  Lua 脚本一次完成"取出 + 记租约",在脚本返回之后(开始处理之前)崩溃:最终完成 {done}/{N},丢失 {len(lost)} 个;t3 靠租约到期被放回(监控放回 {cnt[0]} 次)')
    print('== 五:至少一次投递意味着可能执行多次;副作用要幂等(对照:租约 0.5 秒、t0 要处理 0.8 秒、不续约,6 个任务,2 个 worker,只让 worker 跑 3 秒)')
    reset(6); stop = threading.Event(); cnt = reaper(stop); ws = [spawn('w0', 'lease', slow_task='t0', slow=0.8), spawn('w1', 'lease', slow_task='t0', slow=0.8)]
    waitall(ws, 3.0)
    stop.set(); ex = execs()
    print(f'  任务执行次数 {sum(ex.values())}(6 个任务,t0 被执行 {ex.get("t0")} 次);不去重的副作用计数 {r.get("effects_raw")};用"已处理集合"做 SADD 去重后的副作用计数 {r.get("effects_guarded")}(= 不同任务数 {r.scard("effected")})')
    print('== 六:毒任务——处理它必然让 worker 崩溃(任务 t7)。监控把到期的任务放回队列,有没有重试上限')
    for lab, mx in (('没有重试上限', 0), ('最多 3 次(超过就放进 dead 列表)', 3)):
        reset(10); stop = threading.Event(); cnt = reaper(stop, 0.1, mx); crashes = 0; t0 = time.time()
        while time.time() - t0 < 4.0:
            w = spawn('w', 'lease', die_on='t7', always=True, idle=2); waitall([w], 10)
            if w.returncode and w.returncode < 0: crashes += 1
            if r.llen('queue') == 0 and r.zcard('leases') == 0: break
        time.sleep(0.2); stop.set(); ex = execs(); done, _ = summary(10)
        print(f'  {lab}:{time.time() - t0:.1f} 秒内 worker 因 t7 崩溃 {crashes} 次;t7 被执行 {ex.get("t7")} 次;其他任务完成 {done} 个;dead 列表 {r.lrange("dead", 0, -1)};队列剩 {r.llen("queue")} 个')
finally:
    try: r.shutdown(nosave=True)
    except Exception: pass
    try: srvp.wait(5)
    except Exception: srvp.kill()
purge()
