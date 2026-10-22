import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
from etcdt import Px
import redis as redislib
from rl import Node as RNode
import json
import rl
tee('t26'); reset()
def mk_pair(tag, lags):
    """一个 master + 若干 replica;lags[i] 是该 replica 到 master 的单向延迟(ms,代理每个方向都加)。"""
    pm = free_port(); m = RNode(pm, f'{tag}_m').start(); reps = []; pxs = []
    for i, d in enumerate(lags):
        px = Px(free_port(), pm, d); r = RNode(free_port(), f'{tag}_r{i}', conf={'replicaof': f'127.0.0.1 {px.lport}'}).start(); reps.append(r); pxs.append(px)
    cm = redislib.Redis(port=pm, decode_responses=True); cr = [redislib.Redis(port=r.port, decode_responses=True) for r in reps]
    t0 = time.time()
    for c in cr:
        while c.info('replication').get('master_link_status') != 'up' and time.time() - t0 < 20: time.sleep(0.1)
    time.sleep(0.8)
    for i in range(200): cm.set('warm', i)
    while any(c.info('replication').get('slave_repl_offset') != cm.info('replication').get('master_repl_offset') for c in cr) and time.time() - t0 < 40: time.sleep(0.05)
    return dict(m=m, reps=reps, pxs=pxs, cm=cm, cr=cr)
A = mk_pair('t26a', [0, 15]); B = mk_pair('t26b', [0])
M, R1, R2 = A['cm'], A['cr'][0], A['cr'][1]
print(f'Redis 8.10.2:分片 A = 1 个 master + 2 个 replica(R1 直连,延迟约 0;R2 经过延迟代理,每个方向 +15 ms,复制延迟约 30 ms);分片 B = 1 个 master + 1 个 replica(直连);复制是异步的;会话保证(读己之写、单调读、因果)由客户端自己实现,服务端不提供')
def off_m(c=M): return int(c.info('replication')['master_repl_offset'])
def off_r(r): return int(r.info('replication')['slave_repl_offset'])

print('== 一:读己之写(read-your-writes):会话写完 profile 之后,在写后 0、20、40、60、100 ms 各读一次(共 5 次),看读到的是不是自己刚写的;300 次写。三种读法:随机选 replica / 写后 50 ms 内读 master / 带偏移量令牌(只读已经追上写入偏移量的 replica,否则读 master)')
def ryw(strategy, n=300):
    stale = total = from_rep = 0; lat = []; rng = random.Random(26)
    for i in range(n):
        v = f'{strategy}-{i}'; M.set('profile', v); t_w = time.perf_counter(); token = off_m() if strategy == 'token' else None
        for gap in (0, 20, 40, 60, 100):
            while time.perf_counter() - t_w < gap / 1000.0: time.sleep(0.0005)
            t0 = time.perf_counter()
            if strategy == 'random': r = rng.choice([R1, R2]); got = r.get('profile'); rep = True
            elif strategy == 'sticky':
                if (time.perf_counter() - t_w) < 0.05: got = M.get('profile'); rep = False
                else: r = rng.choice([R1, R2]); got = r.get('profile'); rep = True
            else:
                r = rng.choice([R1, R2])
                if off_r(r) >= token: got = r.get('profile'); rep = True
                else: got = M.get('profile'); rep = False
            lat.append(time.perf_counter() - t0); total += 1; stale += (got != v); from_rep += rep
    return stale, total, from_rep, statistics.mean(lat) * 1000
rows = []
for strategy, name in (('random', '随机选一个 replica 读'), ('sticky', '写后 50 ms 内读 master,之后读 replica'), ('token', '偏移量令牌:replica 的偏移量 ≥ 写入时 master 的偏移量才读它,否则读 master')):
    st, tot, fr, lat = ryw(strategy); rows.append((name, f'{st} / {tot}', f'{fr / tot * 100:.0f}%', f'{lat:.2f} ms'))
table(rows, ['读法', '读到不是自己刚写的值(旧值)', '由 replica 服务的读占比', '单次读平均耗时'])
print('  随机选 replica:慢 replica(R2)落后约 30 ms,写后 0、20 ms 时读它必然是旧的,读 R1 也可能旧;“写后 50 ms 内读 master”要求复制延迟小于 50 ms,否则仍会读到旧值(R2 延迟 30 ms,所以这里恰好够);令牌法不依赖延迟上界,代价是每次读多问一次 replica 的偏移量')

print('== 二:单调读(monotonic reads):后台每 2 ms 给 counter 加 1,会话每 3 ms 读一次 counter,共 400 次;看读到的值有没有“倒退”')
def mono(strategy, n=400):
    stop = threading.Event()
    def w():
        c = redislib.Redis(port=A['m'].port, decode_responses=True)
        while not stop.is_set(): c.incr('counter'); time.sleep(0.002)
    wt = threading.Thread(target=w); wt.start(); time.sleep(0.2); rng = random.Random(7); last = -1; back = 0; lags = []; fb = 0; pinned = rng.choice([R1, R2]); mx = -1
    for i in range(n):
        if strategy == 'random': v = int(rng.choice([R1, R2]).get('counter') or 0)
        elif strategy == 'pinned': v = int(pinned.get('counter') or 0)
        else:
            v = int(rng.choice([R1, R2]).get('counter') or 0)
            if v < mx: fb += 1; v = int(M.get('counter'))                      # 比见过的更旧:改读 master
        mx = max(mx, v); back += (v < last); last = v; cur = int(M.get('counter')); lags.append(cur - v); time.sleep(0.003)
    stop.set(); wt.join(); return back, statistics.mean(lags), fb, ('R1' if pinned is R1 else 'R2')
rows = []
for strategy, name in (('random', '每次随机选一个 replica'), ('pinned', '会话固定读同一个 replica'), ('maxseen', '记住读到过的最大值,读到更旧的就改读 master')):
    M.set('counter', 0); time.sleep(0.2); back, lag, fb, pin = mono(strategy)
    rows.append((name + (f'(这次随机抽到 {pin})' if strategy == 'pinned' else ''), back, f'{lag:.1f}', fb))
table(rows, ['读法', '读到的值比上一次小(倒退)的次数', '读到的值平均比 master 当前值落后多少', '改读 master 的次数'])
print('  随机选 replica 会让会话在快慢两个 replica 之间来回跳,值倒退;固定到一个 replica 就不会倒退(同一个 replica 内部是有序的),但固定到慢的那个会一直更旧,而且这个 replica 挂了要换;“记住最大值”的做法不倒退,代价是读到旧值时要多读一次 master')

print('== 三:因果一致(causal):Alice 在分片 A 发帖(帖子号 i),Bob 读到帖子后在分片 B 回复(回复里记着依赖 i)。Carol 先读回复(分片 B 的 replica,几乎无延迟),再读帖子(分片 A 的慢 replica R2,延迟约 30 ms):会不会“看到了回复却看不到帖子”')
MB, RB = B['cm'], B['cr'][0]
def causal(check, n=300):
    viol = 0; waits = 0; lat = []; rng = random.Random(3)
    for i in range(1, n + 1):
        M.set('post', i); MB.set('reply', f'{i}:{i}')       # 先写帖子(分片 A),Bob 看到后写回复(分片 B),回复记着它依赖第 i 号帖子
        time.sleep(rng.random() * 0.06)                                                                    # Carol 在随机的时刻来看
        t0 = time.perf_counter(); rep = RB.get('reply'); rid, dep = (int(x) for x in rep.split(':')) if rep else (0, 0)
        post = int(R2.get('post') or 0)
        if check and post < dep:                                                                           # 因果依赖检查:回复依赖的帖子还没有出现在这个 replica 上
            waits += 1
            while post < dep: time.sleep(0.002); post = int(R2.get('post') or 0)
        lat.append(time.perf_counter() - t0); viol += (rid > 0 and post < dep)
    return viol, waits, statistics.mean(lat) * 1000
rows = []
for check, name in ((False, '不检查依赖:读到回复就直接去读帖子'), (True, '检查依赖:读到回复后,帖子的版本不够就等到够')):
    v, w, l = causal(check); rows.append((name, f'{v} / 300', w, f'{l:.2f} ms'))
table(rows, ['读法', '看到回复却读不到它依赖的帖子的次数', '等待依赖的次数', 'Carol 读两个值平均耗时'])
print('  两个分片各自复制、延迟不同,互相之间没有顺序;因果关系要靠回复里带的依赖版本(这里是帖子号)在读的时候检查,等不到才继续读,代价是在慢 replica 上等')
for d in (A, B):
    d['cm'].close(); [c.close() for c in d['cr']]; [p.close() for p in d['pxs']]; d['m'].kill9(); [r.kill9() for r in d['reps']]
for t in ('t26a', 't26b'):
    for suf in ('_m', '_r0', '_r1'): shutil.rmtree(rl.RDATA / (t + suf), ignore_errors=True)
reset()
