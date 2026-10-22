import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v20'); reset()
print('nginx 的被动健康检查:不主动探测,只看真实请求的结果。upstream 里每个 server 有 max_fails(默认 1)和 fail_timeout(默认 10 s):在 fail_timeout 时间内累计失败 max_fails 次,就把它标记为不可用 fail_timeout 这么久,期间不再选它,到期后放一个请求去试。什么算“失败”由 proxy_next_upstream 决定(默认只有 error 和 timeout,不含 HTTP 5xx)。后端 A 与 B,client 以 50 个/秒顺序发请求')
def mk_ng(name, A_port, B_port, max_fails=3, fail_timeout=2, nu='error timeout'):
    return Nginx(name, f'upstream u {{ server 127.0.0.1:{A_port} max_fails={max_fails} fail_timeout={fail_timeout}s; server 127.0.0.1:{B_port}; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; proxy_next_upstream {nu}; proxy_connect_timeout 1s; }} }}').start()
def paced(ng, dur, rate, hook=None):
    out = []; t0 = time.perf_counter(); n = int(dur * rate)
    for i in range(n):
        d = t0 + i / rate - time.perf_counter()
        if d > 0: time.sleep(d)
        if hook: hook(time.perf_counter() - t0)
        st, b, dt = rpc(ng.port, '/', 3.0); out.append((time.perf_counter() - t0, st, b.decode() if st == 200 else str(st)))
    return out

# ============ 一 ============
print('== 一:什么算失败,多久摘除。A 在第 1 秒出故障、第 4 秒恢复(共 8 秒)。max_fails=3、fail_timeout=2s。三种故障:(a) A 是一个独立进程,第 1 秒被 kill -9、第 4 秒重新拉起(端口没人监听,连接被拒,属于 error);(b) A 回 503,proxy_next_upstream 保持默认(不含 http_503);(c) A 回 503,proxy_next_upstream error timeout http_503。统计第 1 到 4 秒:client 看到的 5xx 数、nginx 发给 A 的尝试次数(A 自己的到达计数,或 error.log 里 connect() failed 的行数)、由 B 应答的请求数')
BACK = HERE / 'vtmp/v20/backend.py'
def run1(mode):
    state = {'down': False}; B = Svc(lambda h: h.reply(200, b'B')); proc = [None]; Aport = free_port(); A = None
    def a_app(h):
        if state['down']: h.reply(503, b'A503')
        else: h.reply(200, b'A')
    if mode == 'a': proc[0] = subprocess.Popen([sys.executable, str(BACK), str(Aport), 'A'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); wait_port(Aport, 10)
    else: A = Svc(a_app); Aport = A.port
    nu = 'error timeout http_503' if mode == 'c' else 'error timeout'
    ng = mk_ng('v20a', Aport, B.port, 3, 2, nu); T = [0.0]
    def hook(t):
        if mode == 'a':
            if t >= 1.0 and proc[0] is not None and not state['down']: state['down'] = True; proc[0].kill(); proc[0].wait()
            if t >= 4.0 and state['down']: proc[0] = subprocess.Popen([sys.executable, str(BACK), str(Aport), 'A'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); state['down'] = False
        else: state['down'] = 1.0 <= t < 4.0
    out = paced(ng, 8.0, 50, hook)
    err = (ng.d / 'err.log').read_text(); conn = err.count('connect() failed'); ng.stop(); B.stop()
    if A: A.stop()
    if proc[0]: proc[0].kill()
    during = [(st, b) for t, st, b in out if 1.0 <= t < 4.0]
    return sum(1 for st, b in during if st != 200), conn, collections.Counter(b for st, b in during)
rows = []
for mode, name in (('a', '(a) A 被 kill,连接被拒'), ('b', '(b) A 回 503,默认 next_upstream'), ('c', '(c) A 回 503,next_upstream 含 http_503')):
    c5, conn, cnt = run1(mode)
    rows.append((name, c5, conn if mode == 'a' else '见右列', dict(cnt)))
table(rows, ['故障', '第 1 到 4 秒 client 看到的 5xx', '其中 nginx 的 connect() failed 行数', '第 1 到 4 秒各自应答的请求(键:返回的内容或状态码)'])
# ============ 二 ============
print('== 二:偶发失败的节点。A 对每个请求独立地以概率 p 返回 503(用固定种子),B 一直正常;proxy_next_upstream error timeout http_503(失败重试到 B,client 看不到 5xx);max_fails=3、fail_timeout=5s;client 以 100 个/秒顺序发 20 秒(2000 个请求)。nginx 只数失败次数,不看比例。“A 的份额”= 由 A 成功应答的请求占比(没有故障、等权重时应约 50%);“摘除时间”= 估计 A 被摘除的总时长(统计 A 连续 4 秒以上收不到请求的间隔)')
rows = []
for p in (0.0, 0.02, 0.1, 0.3, 0.7):
    rng = random.Random(6); B = Svc(lambda h: h.reply(200, b'B')); A = Svc(lambda h: h.reply(503, b'x') if rng.random() < p else h.reply(200, b'A'))
    ng = mk_ng('v20b', A.port, B.port, 3, 5, 'error timeout http_503'); out = paced(ng, 20.0, 100); ng.stop(); A.stop(); B.stop()
    c5 = sum(1 for t, st, b in out if st != 200); ta = [t for t, st, b in out if b == 'A']
    gaps = [b - a for a, b in zip([0.0] + ta, ta + [20.0]) if b - a >= 4.0]
    rows.append((f'{p:.0%}', f'{len(ta) / len(out):.0%}', c5, f'{sum(gaps):.1f} s', len(gaps)))
table(rows, ['A 的失败率 p', 'A 的份额', 'client 看到的 5xx', 'A 被摘除的总时长(估计)', '摘除的次数'])
print('  失败率只有 2% 的节点也会被偶尔摘除:nginx 数的是 5 秒内累计 3 次失败,而 100 个/秒、一半流量给 A 时 5 秒里 A 会收到约 250 个请求,2% 就是约 5 个失败;所以只看“次数”的被动检查对高流量的节点非常敏感,对低流量的节点又很迟钝')

# ============ 三 ============
print('== 三:恢复要多久。A 回 503 并计入失败(next_upstream 含 http_503),只改 fail_timeout:2 s / 5 s / 10 s;每个 fail_timeout 跑 3 次,故障分别从第 1.0 / 1.4 / 1.8 秒开始、持续 3 秒(为了改变故障与摘除时刻的相位)。“恢复用了”= 故障结束之后 A 第一次重新成功应答用了多久;“A 收到的失败请求”是故障期间 A 自己看到的 503 的时刻(秒)。nginx 摘除后到期的第一个请求去试 A,试失败了就再摘除一个 fail_timeout')
rows = []
for ft in (2, 5, 10):
    recs = []; logs = []
    for off in (1.0, 1.4, 1.8):
        state = {'down': False}; log = []; T0 = [0.0]; B = Svc(lambda h: h.reply(200, b'B'))
        def a_app(h):
            d = state['down']; log.append(round(time.perf_counter() - T0[0], 1)) if d else None; h.reply(503 if d else 200, b'A503' if d else b'A')
        A = Svc(a_app); ng = mk_ng('v20c', A.port, B.port, 3, ft, 'error timeout http_503'); T0[0] = time.perf_counter()
        out = []; t0 = T0[0]; end = off + 3.0
        for i in range(int((end + 2 * ft + 3) * 50)):
            d = t0 + i / 50 - time.perf_counter()
            if d > 0: time.sleep(d)
            t = time.perf_counter() - t0; state['down'] = off <= t < end
            st, b, _ = rpc(ng.port, '/', 3.0); out.append((t, st, b.decode() if st == 200 else str(st)))
        ng.stop(); A.stop(); B.stop()
        after = next((t for t, st, b in out if t >= end and b == 'A'), None)
        recs.append(after - end if after else None); logs.append(log)
    rows.append((f'{ft} s', ' / '.join(f'{r:.1f} s' if r is not None else '没有' for r in recs), ' | '.join(str(l) for l in logs)))
table(rows, ['fail_timeout', '3 次的恢复用了(故障起点 1.0 / 1.4 / 1.8 秒)', '故障期间 A 收到的失败请求的时刻(3 次,秒)'])
print('  看右列:fail_timeout 较短时,有的运行里故障期间 A 多收到了一个失败请求(摘除到期后放过去试的那个请求,A 还没恢复,试失败就再摘除一个完整的 fail_timeout);有的运行里试探恰好发生在 A 恢复之后,恢复很快。fail_timeout 越长,故障结束后越晚才重新用上 A,而且同一个 fail_timeout 下恢复用的时间随故障与摘除时刻的相位而变')
