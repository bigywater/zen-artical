import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import urllib.request
tee('v93'); reset()
print('Mesh 的重试和应用自己的重试叠在一起。Envoy 1.39.3(route 的 retry_policy,retry_on 5xx),应用层的重试是 Python 里的循环(失败就再试,最多 1 + N 次)。(一)一跳上两层重试相乘;(二)调用链越深放大越厉害,重试放在哪一层;(三)Envoy 对并发重试的限制(max_retries 和 retry_budget)在失败很快与很慢时的效果;(四)Mesh 不知道哪些请求是幂等的:写请求被重试会重复执行;(五)超时加重试:放弃了的请求后端还在处理')
def admin_conf(admin, y): return f'admin: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {admin}}}}}}}\n' + y
CB1024 = 'circuit_breakers: {thresholds: [{max_retries: 1024}]}'
def conf(admin, port, route_text, cb=CB1024):
    y = envoy_http_conf(route_text, {'back': [port]})
    if cb: y = y.replace('  - name: back\n    type: STATIC\n    connect_timeout: 1s', f'  - name: back\n    type: STATIC\n    connect_timeout: 1s\n    {cb}')
    return admin_conf(admin, y)
def route(retries, timeout='10s', retry_on='5xx', per_try=None):
    pt = f', per_try_timeout: {per_try}' if per_try else ''
    rp = f'\n                  retry_policy: {{retry_on: "{retry_on}", num_retries: {retries}{pt}}}' if retries else ''
    return f'              - match: {{prefix: "/"}}\n                route:\n                  cluster: back\n                  timeout: {timeout}{rp}'
def stat(admin, name):
    t = urllib.request.urlopen(f'http://127.0.0.1:{admin}/stats?filter={name}', timeout=3).read().decode()
    for l in t.splitlines():
        k, _, v = l.partition(': ')
        if k == name: return int(v)
    return 0
class Back:
    """返回 503 的后端:fail 是失败概率;delay 是失败前先睡多久;记录到达的时间戳和 x-req 头。"""
    def __init__(self, fail=1.0, delay=0.0, seed=1):
        self.fail, self.delay, self.rng, self.log, self.lk = fail, delay, random.Random(seed), [], threading.Lock(); self.inflight = 0; self.maxin = 0
        def app(h):
            with self.lk: self.log.append((time.time(), h.headers.get('x-req'))); f = self.rng.random() < self.fail; self.inflight += 1; self.maxin = max(self.maxin, self.inflight)
            if self.delay: time.sleep(self.delay)
            with self.lk: self.inflight -= 1
            h.reply(503 if f else 200, b'x')
        self.svc = Svc(app, 'back'); self.port = self.svc.port
    @property
    def n(self): return len(self.log)
    def stop(self): self.svc.stop()
def app_call(port, retries, timeout=5.0, hdr=None):
    for _ in range(retries + 1):
        s, d, dt = rpc(port, '/', timeout, headers=hdr, keepalive=False)
        if s == 200: return 200
    return s

# ============ 一 ============
print('== 一:一跳上两层重试。客户端(应用层重试 a 次)→ Envoy(Mesh 层重试 m 次,retry_on 5xx;集群的 max_retries 先调到 1024,理由见第三节)→ 后端。后端失败率 100%(整个挂了)与 50%(随机)。每种 200 个客户端请求(8 个线程)。统计后端实际收到的请求数除以客户端请求数(放大倍数)和客户端看到的成功率')
rows = []
for pf in (1.0, 0.5):
    for a in (0, 2):
        for m in (0, 2):
            bk = Back(pf, seed=7); admin = free_port(); E = Envoy('v93a', conf(admin, bk.port, route(m))).start(); time.sleep(0.4)
            res = par(lambda i: app_call(E.port, a), list(range(200)), 8); time.sleep(0.3)
            rows.append((f'{int(pf * 100)}%', f'{a}', f'{m}', f'{bk.n / 200:.2f}', f'{sum(1 for r in res if r == 200) / 2:.1f}%')); E.stop(); bk.stop()
table([['后端失败率', '应用层重试次数 a', 'Mesh 层重试次数 m', '后端收到的请求数 / 客户端请求数', '客户端成功率']] + [list(r) for r in rows])
print('  后端完全挂掉(100%)时,两层重试的放大倍数相乘,每一层单独看都只重试 2 次,合起来是表里最后一行的倍数;后端只有 50% 失败时,重试把成功率拉高,代价是后端多收的请求(见表)')

# ============ 二 ============
print('== 二:调用链越深放大越厉害。客户端 → A → B → C,C 总是返回 503(叶子服务挂了)。每个服务调下一个服务,失败就把 503 往回传。重试的位置不同:(a)谁都不重试;(b)只有客户端重试 2 次;(c)每一层(客户端、A→B、B→C)应用层都重试 2 次;(d)只有 A→B 与 B→C 两跳用 Envoy 重试 2 次(应用不重试);(e)每一层应用都重试 2 次,A→B 与 B→C 两跳还各有 Envoy 重试 2 次(Envoy 的 max_retries 都是 1024)。每种 50 个客户端请求(4 个线程),统计叶子 C 收到的请求数除以客户端请求数')
rows = []
for lab, cr, ar, mesh in (('(a)谁都不重试', 0, 0, 0), ('(b)只有客户端重试 2 次', 2, 0, 0), ('(c)每一层应用都重试 2 次', 2, 2, 0), ('(d)只有两跳的 Envoy 重试 2 次', 0, 0, 2), ('(e)应用和 Envoy 每一层都重试 2 次', 2, 2, 2)):
    leaf = Back(1.0); hold = []
    def hop(port_next, retries, m):
        if m:
            E = Envoy('v93b' + str(len(hold)), conf(free_port(), port_next, route(m))).start(); hold.append(E); target = E.port
        else: target = port_next
        return Svc(lambda h: h.reply(app_call(target, retries), b'x'), 'hop')
    B = hop(leaf.port, ar, mesh); A = hop(B.port, ar, mesh); time.sleep(0.4)
    res = par(lambda i: app_call(A.port, cr), list(range(50)), 4); time.sleep(0.5)
    rows.append((lab, f'{leaf.n}', f'{leaf.n / 50:.1f}', f'{sum(1 for r in res if r == 200)}')); [e.stop() for e in hold]; A.stop(); B.stop(); leaf.stop()
table([['重试放在哪里', '叶子 C 收到的请求数', '叶子 C 收到的请求数 / 客户端请求数', '客户端成功数(共 50)']] + [list(r) for r in rows])
print(f'  各层的重试次数相乘:(b)只在入口重试,叶子收到 {rows[1][2]} 倍;(c)三层应用都重试,{rows[2][2]} 倍(3 的三次方);(d)两跳 Envoy 重试,{rows[3][2]} 倍(3 的平方);(e)应用和 Envoy 都重试,{rows[4][2]} 倍(= 3 × 9 × 9)。链越深,同样的 “只重试 2 次” 在叶子上放大得越多')

# ============ 三 ============
print('== 三:Envoy 自己对并发重试的限制。后端总是返回 503,到达率 100 个/秒、5 s 共 500 个请求,Envoy 的 retry_on 5xx、num_retries 2(所以每个请求最多 3 次尝试),应用不重试。后端返回 503 之前先睡:0 ms(失败很快)与 100 ms(失败较慢)。三种配置:(a)集群熔断器的默认值(max_retries 默认 3,即同时最多 3 个重试在进行);(b)max_retries 提高到 1024;(c)max_retries 1024 + retry_budget 20%(budget_percent 20,min_retry_concurrency 3)')
CBS = {'(a)默认 max_retries', '(b)max_retries 1024', '(c)max_retries 1024 + retry_budget 20%'}
cfgs = (('(a)默认 max_retries', ''), ('(b)max_retries 1024', 'circuit_breakers: {thresholds: [{max_retries: 1024}]}'), ('(c)max_retries 1024 + retry_budget 20%', 'circuit_breakers: {thresholds: [{max_retries: 1024, retry_budget: {budget_percent: {value: 20.0}, min_retry_concurrency: 3}}]}'))
rows = []
for delay in (0.0, 0.1):
    for lab, cb in cfgs:
        bk = Back(1.0, delay); admin = free_port(); y = envoy_http_conf(route(2), {'back': [bk.port]})
        if cb: y = y.replace('  - name: back\n    type: STATIC\n    connect_timeout: 1s', f'  - name: back\n    type: STATIC\n    connect_timeout: 1s\n    {cb}')
        E = Envoy('v93c', admin_conf(admin, y)).start(); time.sleep(0.4)
        openloop(lambda i: rpc(E.port, '/', 10.0, keepalive=False)[0], 100, 5.0, workers=300); time.sleep(1.0)
        rows.append((f'{int(delay * 1000)} ms', lab, f'{bk.n / 500:.2f}', stat(admin, 'cluster.back.upstream_rq_retry'), stat(admin, 'cluster.back.upstream_rq_retry_overflow'))); E.stop(); bk.stop()
table([['后端失败前的延迟', '配置', '后端收到的请求数 / 客户端请求数', 'upstream_rq_retry(发起的重试)', 'upstream_rq_retry_overflow(被限制掉的重试)']] + [list(r) for r in rows])
g = {(r[0], r[1][:3]): r for r in rows}
print(f'  默认的 max_retries(同时最多 3 个重试在进行)确实在限制重试:后端失败前延迟 0 ms 时,放大倍数是 {rows[0][2]}(上限 3.00,{rows[0][4]} 个重试被拒绝);延迟 100 ms 时只有 {rows[3][2]}({rows[3][4]} 个重试被拒绝)。失败越慢,同时在进行的重试越多,被拦得越多。把 max_retries 调到 1024 就拦不住了(两种延迟下都是 {rows[1][2]} 倍)。retry_budget 20%(下限 min_retry_concurrency 3)在这个负载下的结果与默认的 max_retries 几乎一样({rows[2][2]} 和 {rows[5][2]}),我的解释是这个负载的并发请求数太小,20% 算出来还不到下限 3,没有单独验证,所以我没有量出 retry_budget 比固定上限多做了什么')

# ============ 四 ============
print('== 四:Mesh 不知道哪些请求是幂等的。客户端 POST /pay(带请求号 x-req),后端「先执行写入,再返回 503」(模拟写入已提交但响应出错),同一个请求号第二次到达时返回 200。100 个请求,应用层不重试。(a)Envoy retry_on 5xx、num_retries 1;(b)Envoy retry_on connect-failure(只在连不上时重试);(c)同(a),但后端按请求号去重(同一个请求号只写一次)')
rows = []
for lab, retry_on, dedupe in (('(a)retry_on 5xx,后端不去重', '5xx', False), ('(b)retry_on connect-failure', 'connect-failure', False), ('(c)retry_on 5xx,后端按请求号去重', '5xx', True)):
    seen = {}; writes = [0]; lk = threading.Lock()
    def app(h):
        rid = h.headers.get('x-req')
        with lk:
            first = rid not in seen; seen[rid] = True
            if not (dedupe and not first): writes[0] += 1
        h.reply(503 if first else 200, b'x')
    S_ = Svc(app, 'pay'); E = Envoy('v93d', conf(free_port(), S_.port, route(1, retry_on=retry_on))).start(); time.sleep(0.4)
    res = par(lambda i: rpc(E.port, '/', 5.0, headers={'x-req': f'r{i}'}, method='POST', keepalive=False)[0], list(range(100)), 8); time.sleep(0.3)
    rows.append((lab, f'{sum(1 for r in res if r == 200)}', f'{sum(1 for r in res if r == 503)}', f'{writes[0]}')); E.stop(); S_.stop()
table([['配置', '客户端看到 200', '客户端看到 503', '后端执行的写入次数(共 100 个请求)']] + [list(r) for r in rows])
print(f'  Envoy 对 POST 也按 retry_on 重试:(a)后端已经写入又返回 503,重试把同一笔写入再执行一次,后端执行了 {rows[0][3]} 次写入(请求只有 100 个),客户端却看到 {rows[0][1]} 个成功;(b)只在连不上时重试,没有重复写入,但客户端看到的 503 是 {rows[1][2]} 个;(c)后端按请求号去重后写入次数回到 {rows[2][3]}。Mesh 不知道哪些接口是幂等的,对非幂等接口配 retry_on 5xx 要先确认后端能去重')

# ============ 五 ============
print('== 五:超时和重试叠在一起,放弃了的请求还在后端干活。后端每个请求先睡 1.5 s 再返回 503(后端不会因为客户端走了而取消)。20 个请求(4 个线程)。(a)客户端超时 1 s、不重试,Envoy retry_on 5xx、num_retries 2、路由总超时 10 s;(b)客户端超时 1 s、应用层重试 2 次,Envoy 不重试;(c)客户端超时 2 s、不重试,Envoy retry_on 5xx、num_retries 2、per_try_timeout 0.5 s、路由总超时 1.5 s。统计后端一共收到多少次尝试、同时在后端处理的最大并发数、客户端看到的状态')
rows = []
for lab, ctmo, capp, rt in (('(a)客户端 1 s、不重试;Envoy 重试 2 次,总超时 10 s', 1.0, 0, route(2, timeout='10s')), ('(b)客户端 1 s、应用重试 2 次;Envoy 不重试', 1.0, 2, route(0, timeout='10s')), ('(c)客户端 2 s、不重试;Envoy per_try_timeout 0.5 s 重试 2 次,总超时 1.5 s', 2.0, 0, route(2, timeout='1.5s', per_try='0.5s'))):
    bk = Back(1.0, 1.5); E = Envoy('v93e', conf(free_port(), bk.port, rt)).start(); time.sleep(0.4)
    def one(i):
        last = None
        for _ in range(capp + 1):
            last = rpc(E.port, '/', ctmo, headers={'x-req': f'r{i}'}, keepalive=False)[0]
            if last == 200: break
        return last
    res = par(one, list(range(20)), 4); time.sleep(4.0)
    rows.append((lab, str(dict(collections.Counter(res))).replace("'", ''), bk.n, f'{bk.n / 20:.1f}', bk.maxin)); E.stop(); bk.stop()
table([['配置', '客户端最后看到', '后端收到的尝试数(共 20 个请求)', '每个请求的尝试数', '后端同时处理的最大并发']] + [list(map(str, r)) for r in rows])
print(f'  (a)客户端 1 s 就走了,Envoy 没有继续替它重试(每个请求只有 {rows[0][3]} 次尝试);我的解释是客户端断开让 Envoy 放弃了这个请求,没有单独验证。(b)客户端自己超时后重试:每个请求 {rows[1][3]} 次尝试。(c)Envoy 的 per_try_timeout 把每次尝试限制在 0.5 s,每个请求 {rows[2][3]} 次尝试,最后客户端看到的是 Envoy 的 504。三种配置下后端同时处理的最大并发是 {rows[0][4]} / {rows[1][4]} / {rows[2][4]},客户端同时只有 4 个线程,说明被放弃的尝试后端仍在处理(后端是我写的,不会取消);(c)的并发最高。超时只是调用方不等了,不等于后端停止干活;超时加重试会让后端同时处理的请求数超过客户端的并发')
print('说明(哪些是测到的,哪些没有测)\n  每个场景只跑了一次(随机失败用固定种子);没有测:Envoy 的退避参数(retry_back_off)对放大的影响、重试预算在高并发慢失败下的长期行为、gRPC 的重试策略、Istio 的 VirtualService 重试默认值(它默认会重试,这里没有验证)、应用层的指数退避加抖动')
print('ERRORS', dict(ERRORS))
