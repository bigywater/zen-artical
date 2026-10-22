import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v2'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')
print('每一层(client、网关、服务)都“失败就重试,总共试 3 次”,没有退避、没有预算;最底层的 C 是本进程里的小 HTTP 服务,其余各层是同样的小服务(失败时 503);“放大倍数”= C 收到的调用次数 ÷ client 发出的请求数;网关用本机的 nginx 1.31.6')

C_hits = [0]; C_lock = threading.Lock(); C_p = [1.0]; C_rng = random.Random(2)
def c_app(h):
    with C_lock: C_hits[0] += 1; bad = C_rng.random() < C_p[0]
    h.reply(503 if bad else 200, b'x')
def layer(down_port, attempts=3):
    def app(h):
        for _ in range(attempts):
            st, _, _ = rpc(down_port, '/', 3.0)
            if st == 200: return h.reply(200, b'ok')
        h.reply(503, b'fail')
    return Svc(app)
def chain(L, attempts=3):
    C = Svc(c_app); top = C; svs = [C]
    for _ in range(L): top = layer(top.port, attempts); svs.append(top)
    return top, svs

# ============ 一 ============
print('== 一:C 完全不可用(一直 503)时,每多一层“试 3 次”,C 收到的调用乘以 3。client 只发 20 个请求,每个请求从最上层到 C')
rows = []
for L in (0, 1, 2, 3, 4):
    top, svs = chain(L); C_p[0] = 1.0; C_hits[0] = 0; N = 20
    for _ in range(N): rpc(top.port, '/', 30.0)
    rows.append((L, f'{L} 层各试 3 次' if L else '没有重试层', C_hits[0], f'{C_hits[0] / N:.0f}', 3 ** L))
    [s.stop() for s in svs]
table(rows, ['重试层数', '说明', 'C 收到的调用', '每个 client 请求', '3 的 L 次方']); nerr()

# ============ 二 ============
print('== 二:C 偶发失败(每次调用独立地以概率 p 返回 503),3 层各试 3 次。每种 p 发 600 个请求(16 个并发)。公式:f₀ = p;一层的失败概率 f = f_前³;一层的平均尝试次数 = 1 + f_前 + f_前²,各层相乘就是 C 的平均收到调用数')
def formula(p, L):
    f, h = p, 1.0
    for _ in range(L): h *= (1 + f + f * f); f = f ** 3
    return h, f
rows = []
for p in (0.1, 0.3, 0.5, 0.9):
    top, svs = chain(3); C_p[0] = p; C_hits[0] = 0; N = 600
    res = par(lambda i: rpc(top.port, '/', 30.0)[0], list(range(N)), 16)
    ok = sum(1 for r in res if r == 200); h, f = formula(p, 3)
    rows.append((f'{p:.0%}', f'{C_hits[0] / N:.2f}', f'{h:.2f}', f'{ok / N:.1%}', f'{1 - f:.1%}'))
    [s.stop() for s in svs]
table(rows, ['C 的失败率 p', '实测:每个请求 C 收到的调用', '公式', '实测:client 拿到成功', '公式'])
nerr()
print('  C 偶发失败时重试确实让成功率变高了(p = 30% 时单次调用成功率 70%,3 层重试后 600 个请求全部成功),代价是 C 多收到的调用;p 越高放大越厉害,而这时 C 恰恰最撑不住')

# ============ 三 ============
print('== 三:C 的容量有限时的放大。C 同时最多处理 4 个请求,每个 20 ms(容量 200/s),多出来的立刻回 503;client 以 120/s 的固定速率(开环)发请求,共 8 秒;第 2 到 3.5 秒 C 的处理时间变成 3 倍(容量降到约 67/s)。比较没有重试层与 3 层各试 3 次。每秒:C 收到的调用数 / client 成功率')
state = {'slow': 1.0}; sem = threading.Semaphore(4); arr = collections.Counter(); T0 = [0.0]
def c_cap(h):
    arr[int(time.time() - T0[0])] += 1
    if not sem.acquire(blocking=False): return h.reply(503, b'busy')
    try: time.sleep(0.02 * state['slow'])
    finally: sem.release()
    h.reply(200, b'ok')
def run3(L):
    C = Svc(c_cap); top = C; svs = [C]
    for _ in range(L): top = layer(top.port, 3); svs.append(top)
    arr.clear(); state['slow'] = 1.0; T0[0] = time.time()
    def trig():
        time.sleep(2.0); state['slow'] = 3.0; time.sleep(1.5); state['slow'] = 1.0
    threading.Thread(target=trig, daemon=True).start()
    res = openloop(lambda i: rpc(top.port, '/', 3.0)[0], 120, 8, workers=500)
    ok = collections.Counter(); tot = collections.Counter()
    for ts, st in res: tot[int(ts)] += 1; ok[int(ts)] += (st == 200)
    [s.stop() for s in svs]
    return [arr[s] for s in range(8)], [ok[s] / max(tot[s], 1) for s in range(8)]
rows = []
for name, L in (('没有重试层', 0), ('3 层各试 3 次', 3)):
    a, o = run3(L); rows.append((name, '收到的调用/s') + tuple(a)); rows.append(('', 'client 成功率') + tuple(f'{x:.0%}' for x in o))
table(rows, ['', '', '第 0 秒', '1', '2', '3', '4', '5', '6', '7'])
nerr()
print('  触发的那 1.5 秒里,有重试层时 C 收到的调用是没有重试层时的十几倍;触发结束后的下一秒就接近恢复;这个实验里请求是同步重试的,重试不会在触发结束后继续累积,所以最终能恢复。负载更高(160/s)时,发请求的这个 Python 进程自己撑不住(大量连接错误),那一档的数字不可信,没有放进来')

# ============ 四 ============
print('== 四:网关再加一层。client → nginx(两个上游实例 A1、A2)→ A(失败就对 C 试 3 次)→ C(一直 503)。比较 nginx 的 proxy_next_upstream 默认值(error timeout,不会因为 503 换上游)与加上 http_503,以及 client 自己是否也试 3 次。每种配置 20 个 client 请求')
def run4(client_tries, next_up, srv_opt=''):
    C = Svc(c_app); C_p[0] = 1.0; A = [layer(C.port, 3) for _ in range(2)]
    ups = ''.join(f'server 127.0.0.1:{a.port} {srv_opt};' for a in A)
    ng = Nginx('v2n', f'upstream u {{ {ups} }}\n  server {{ listen {{port}}; location / {{ proxy_pass http://u; {next_up} }} }}').start()
    C_hits[0] = 0; N = 20; got = collections.Counter()
    for _ in range(N):
        for k in range(client_tries):
            st, _, _ = rpc(ng.port, '/', 30.0)
            if st == 200: break
        got[st] += 1
    hits = C_hits[0]; ng.stop(); [a.stop() for a in A]; C.stop(); return hits, dict(got)
rows = []
U = 'proxy_next_upstream error timeout http_503;'
for name, ct, nu, so in (('client 试 1 次 / nginx 默认', 1, '', ''), ('client 试 3 次 / nginx 默认', 3, '', ''), ('client 试 1 次 / 加 http_503(上游 server 保持默认 max_fails=1)', 1, U, ''), ('client 试 1 次 / 加 http_503 + max_fails=0', 1, U, 'max_fails=0'), ('client 试 3 次 / 加 http_503 + max_fails=0', 3, U, 'max_fails=0')):
    hits, got = run4(ct, nu, so); rows.append((name, hits, f'{hits / 20:.1f}', got))
table(rows, ['配置', 'C 收到的调用', '每个 client 请求', 'client 最终看到的状态码'])
nerr()
print('  每一层的重试次数是相乘的:client 3 × nginx 换上游 2 × 服务 3 = 18;各层单独看都“只试几次”,合起来是放大的根源。第三行的另一个后果:http_503 让 nginx 把每个 503 记成一次失败,默认的 max_fails=1 / fail_timeout=10s 会把两个上游都摘掉,之后的请求是 nginx 自己回的 502(error log:no live upstreams),根本到不了服务')
