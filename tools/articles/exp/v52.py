import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import shutil
import dns.resolver
tee('v52'); reset()
print('Consul 的分工与健康检查。Consul 2.0.4,3 个 server(Raft)+ 2 个 client 模式的 agent,全部在 127.0.0.1;服务登记在 client agent 上,健康检查由登记它的那个 agent 执行。后端是本进程里的小 HTTP 服务,状态码可以随时改。下面只描述测到的现象,不同版本和配置的默认值可能不同')
for n in ('v52c', 'v52a0', 'v52a1'):
    for i in range(3): shutil.rmtree(TT / f'{n}_{i}', ignore_errors=True)
    shutil.rmtree(TT / n, ignore_errors=True)
CC = ConsulCluster('v52c', 3).start()
A0 = ConsulAgent('v52a0', CC).start(); A1 = ConsulAgent('v52a1', CC).start(); time.sleep(2.0)
def J(s, d):
    try: return json.loads(d)
    except Exception: return None

# ============ 一 ============
print('== 一:谁是谁。3 个 server + 2 个 client agent 组成的集群:gossip 成员表(/v1/agent/members)里的角色、Raft 的投票成员(/v1/operator/raft/configuration)、在 client agent 上登记的服务在 catalog 里挂在哪个节点上')
s, d = CC.http(0, 'GET', '/v1/agent/members'); mem = J(s, d)
s, d = CC.http(0, 'GET', '/v1/operator/raft/configuration'); raft = J(s, d)
A0.http('PUT', '/v1/agent/service/register', {'Name': 'web', 'ID': 'web-on-a0', 'Port': 8081})
time.sleep(1.5)
table([(m['Name'], m['Tags'].get('role', '?'), {1: 'alive', 3: 'left', 4: 'failed'}.get(m['Status'], m['Status'])) for m in sorted(mem, key=lambda m: m['Name'])], ['gossip 成员', 'role 标签', '状态'])
print(f'  Raft 投票成员数(configuration.Servers 中 Voter 为真):{sum(1 for x in raft["Servers"] if x["Voter"])};其中节点名:{sorted(x["Node"] for x in raft["Servers"])}')
s, d = A1.http('GET', '/v1/catalog/service/web'); cat = J(s, d)
print(f'  在 client agent v52a0 上登记 web;通过另一个 client agent(v52a1)查 catalog:{[(x["Node"], x["ServiceID"], x["ServiceAddress"] or x["Address"]) for x in cat]}')
s, d = CC.http(0, 'GET', '/v1/status/peers'); print(f'  /v1/status/peers 返回 {len(J(s, d))} 个 server 地址')

# ============ 二 ============
print('== 二:gossip 怎么发现一个节点没了。在 client agent v52a1 上登记服务 gsvc(没有任何健康检查),然后分别:SIGKILL 这个 agent(3 次,每次重启并等它重新出现),或者让它优雅离开(consul leave)。从 server 0 的视角,每 50 ms 查一次,记录:成员状态变成非 alive 的时间,节点的 serfHealth 检查变成 critical 的时间,以及这期间服务 gsvc 在 catalog 里和在 ?passing 里的数量')
def reg_gsvc():
    A1.http('PUT', '/v1/agent/service/register', {'Name': 'gsvc', 'ID': 'gsvc-1', 'Port': 8082}); time.sleep(1.5)
reg_gsvc()
def peek():
    s, d = CC.http(0, 'GET', '/v1/agent/members'); mem = J(s, d) or []
    st = next((m['Status'] for m in mem if m['Name'] == A1.node), None)
    s, d = CC.http(0, 'GET', f'/v1/health/node/{A1.node}'); h = J(s, d) or []
    sh = next((c['Status'] for c in h if c['CheckID'] == 'serfHealth'), None)
    s, d = CC.http(0, 'GET', '/v1/catalog/service/gsvc'); cn = len(J(s, d) or [])
    s, d = CC.http(0, 'GET', '/v1/health/service/gsvc?passing'); pn = len(J(s, d) or [])
    return st, sh, cn, pn
rows = []
for rnd in range(3):
    st, sh, cn, pn = peek(); assert st == 1 and sh == 'passing' and cn == 1 and pn == 1, (st, sh, cn, pn)
    t0 = time.perf_counter(); A1.kill(); t_mem = t_sh = t_pass0 = None; last = None
    while time.perf_counter() - t0 < 60:
        st, sh, cn, pn = peek(); el = time.perf_counter() - t0; last = (st, sh, cn, pn)
        if t_mem is None and st != 1: t_mem = el
        if t_sh is None and sh == 'critical': t_sh = el
        if t_pass0 is None and pn == 0: t_pass0 = el
        if t_mem and t_sh and t_pass0: break
        time.sleep(0.05)
    rows.append(('SIGKILL', f'{t_mem:.2f}' if t_mem else '-', f'{t_sh:.2f}' if t_sh else '-', f'{t_pass0:.2f}' if t_pass0 else '-', f'catalog {last[2]} / passing {last[3]}'))
    A1.start(); time.sleep(2.0); reg_gsvc()
def leave_a1():
    try: A1.http('PUT', '/v1/agent/leave', timeout=30.0)
    except Exception: pass
st, sh, cn, pn = peek(); t0 = time.perf_counter(); threading.Thread(target=leave_a1, daemon=True).start(); t_mem = None; t_gone = None; last = None
while time.perf_counter() - t0 < 60:
    st, sh, cn, pn = peek(); el = time.perf_counter() - t0
    s, d = CC.http(0, 'GET', '/v1/catalog/nodes'); nodes = [n['Node'] for n in (J(s, d) or [])]
    last = (st, sh, cn, pn, A1.node in nodes)
    if t_mem is None and st != 1: t_mem = el
    if t_gone is None and A1.node not in nodes: t_gone = el
    if t_mem is not None and t_gone is not None: break
    time.sleep(0.05)
rows.append(('consul leave', f'{t_mem:.2f}' if t_mem else '-', '-(节点已被移除,没有 serfHealth)' if last and last[1] is None else (last[1] if last else '-'), f'{t_gone:.2f}(节点从 catalog 消失)' if t_gone else '-', f'catalog {last[2]} / passing {last[3]}'))
table(rows, ['怎么没的', '成员状态不再是 alive(s)', 'serfHealth 变 critical(s)', '服务不再出现在 ?passing(s)', '结束时'])
print('  SIGKILL 的节点被 gossip 判为 failed 要几秒(探测、怀疑、确认);在那之前服务照样 passing。节点被标成 failed 之后,它上面的服务因为 serfHealth 变成 critical 而不再出现在 ?passing 里,但 catalog 里还在。优雅离开则是节点自己通知集群,节点直接从 catalog 里消失')
A1.kill(); A1.start(); time.sleep(2.0)

# ============ 三 ============
print('== 三:健康检查的状态流转(HTTP 检查)。client agent v52a0 上登记 2 个检查指向同一个后端:default(interval 1 s,timeout 1 s,其余默认)和 slow(同样,但 failures_before_critical=3,success_before_passing=2)。后端状态码依次改成 429 → 500 → 200,重复 6 轮(每次改动之间随机多等 0~1 s,让改动落在检查周期的不同位置);记录改动之后每个检查变成目标状态用了多久')
bk = {'code': 200, 'sleep': 0.0}
def app(h):
    if bk['sleep']: time.sleep(bk['sleep'])
    h.reply(bk['code'], b'x')
S0 = Svc(app, 'bk')
def checks(agent=A0):
    s, d = agent.http('GET', '/v1/agent/checks'); return J(s, d) or {}
def wait_status(targets, timeout=30.0, agent=A0):
    t0 = time.perf_counter(); got = {}
    while time.perf_counter() - t0 < timeout:
        c = checks(agent)
        for cid, want in targets.items():
            if cid not in got and c.get(cid, {}).get('Status') == want: got[cid] = time.perf_counter() - t0
        if len(got) == len(targets): break
        time.sleep(0.05)
    return got
A0.http('PUT', '/v1/agent/service/register', {'Name': 'chk', 'ID': 'chk-1', 'Port': S0.port, 'Checks': [
    {'CheckID': 'default', 'HTTP': f'http://127.0.0.1:{S0.port}/', 'Interval': '1s', 'Timeout': '1s'},
    {'CheckID': 'slow', 'HTTP': f'http://127.0.0.1:{S0.port}/', 'Interval': '1s', 'Timeout': '1s', 'FailuresBeforeCritical': 3, 'SuccessBeforePassing': 2}]})
c = checks(); init = {k: c[k]['Status'] for k in ('default', 'slow')}
g = wait_status({'default': 'passing', 'slow': 'passing'})
print(f'  刚登记时(后端一直是 200):default {init["default"]},slow {init["slow"]};变成 passing 用了 default {g.get("default", float("nan")):.2f} s,slow {g.get("slow", float("nan")):.2f} s(从登记调用返回算起)')
time.sleep(2.0)
steps = [('200→429', 429, {'default': 'warning', 'slow': 'warning'}), ('429→500', 500, {'default': 'critical', 'slow': 'critical'}), ('500→200', 200, {'default': 'passing', 'slow': 'passing'})]
res = {k: {'default': [], 'slow': []} for k, _, _ in steps}
rnd_ph = random.Random(5)
for rnd in range(6):
    for name, code, tg in steps:
        bk['code'] = code; g = wait_status(tg, 30.0)
        for k in ('default', 'slow'): res[name][k].append(g.get(k))
        time.sleep((1.5 if name != '500→200' else 2.5) + rnd_ph.random())
def rng(xs):
    v = [x for x in xs if x is not None]; return (f'{min(v):.2f}~{max(v):.2f}' + (f'(缺 {len(xs) - len(v)} 次)' if len(v) < len(xs) else '')) if v else '-'
table([(n, rng(res[n]['default']), rng(res[n]['slow'])) for n, _, _ in steps], ['后端状态码改变', 'default:到目标状态用的秒数(6 轮范围)', 'slow(3 次失败 / 2 次成功):同上'])
bk['code'] = 500; wait_status({'default': 'critical'}); o500 = checks()['default']['Output']
bk['code'] = 429; wait_status({'default': 'warning'}); o429 = checks()['default']['Output']
bk['code'] = 200; bk['sleep'] = 2.5; wait_status({'default': 'critical'}); oto = checks()['default']['Output']
bk['sleep'] = 0.0; wait_status({'default': 'passing'}); S0.stop(); wait_status({'default': 'critical'}); orf = checks()['default']['Output']
print('  各情形下 Output 字段的开头(原样):')
for k, v in (('500', o500), ('429', o429), ('后端响应超过 timeout', oto), ('后端已停(连接被拒)', orf)): print(f'    {k:<14} {v.strip()[:110]!r}')

# ============ 四 ============
print('== 四:其他类型的检查。TTL 检查(应用自己汇报,过期没汇报就 critical)、TCP 检查、脚本检查(默认配置下登记)')
A0.http('PUT', '/v1/agent/service/register', {'Name': 'ttl', 'ID': 'ttl-1', 'Port': 1, 'Check': {'CheckID': 'ttlc', 'TTL': '3s'}})
st0 = checks()['ttlc']['Status']; rows = [('刚登记', st0, checks()['ttlc']['Output'][:50])]
A0.http('PUT', '/v1/agent/check/pass/ttlc', headers={}); t_pass = time.perf_counter(); rows.append(('汇报 pass', checks()['ttlc']['Status'], ''))
got = wait_status({'ttlc': 'critical'}, 20); rows.append(('之后不再汇报', checks()['ttlc']['Status'], f'{got.get("ttlc", float("nan")):.2f} s 后变 critical(TTL 3 s);Output:{checks()["ttlc"]["Output"][:40]!r}'))
A0.http('PUT', '/v1/agent/check/warn/ttlc'); rows.append(('汇报 warn', checks()['ttlc']['Status'], ''))
A0.http('PUT', '/v1/agent/check/fail/ttlc'); rows.append(('汇报 fail', checks()['ttlc']['Status'], ''))
table(rows, ['操作', '状态', '备注'])
S1 = Svc(lambda h: h.reply(200, b'ok'), 'tcp')
A0.http('PUT', '/v1/agent/service/register', {'Name': 'tcp', 'ID': 'tcp-1', 'Port': S1.port, 'Check': {'CheckID': 'tcpc', 'TCP': f'127.0.0.1:{S1.port}', 'Interval': '1s', 'Timeout': '1s'}})
g1 = wait_status({'tcpc': 'passing'}); S1.stop(); g2 = wait_status({'tcpc': 'critical'})
print(f'  TCP 检查:端口监听时变 passing 用了 {g1.get("tcpc", float("nan")):.2f} s;关掉端口后变 critical 用了 {g2.get("tcpc", float("nan")):.2f} s;Output:{checks()["tcpc"]["Output"][:60]!r}')
r = A0.http('PUT', '/v1/agent/service/register', {'Name': 'scr', 'ID': 'scr-1', 'Check': {'CheckID': 'scrc', 'Args': ['true'], 'Interval': '1s'}})
print(f'  脚本检查(Args)在默认配置下登记:HTTP {r[0]},响应 {r[1].decode(errors="replace").strip()[:120]!r}')

# ============ 五 ============
print('== 五:服务和检查的权威状态在 client agent 本地,再同步给 server。杀掉 3 个 server 中的 2 个(没有 leader,只剩一个 server),然后在 client agent v52a0 上:新登记服务 api、把 dep 的后端改成返回 500;看 agent 本地和 catalog 各是什么,再把 server 拉起来,看多久之后 catalog 追上')
bk2 = {'code': 200}
S2 = Svc(lambda h: h.reply(bk2['code'], b'x'), 'bk2')
A0.http('PUT', '/v1/agent/service/register', {'Name': 'dep', 'ID': 'dep-1', 'Port': S2.port, 'Check': {'CheckID': 'depc', 'HTTP': f'http://127.0.0.1:{S2.port}/', 'Interval': '1s', 'Timeout': '1s'}})
wait_status({'depc': 'passing'}); time.sleep(2.0)
def cat_dep():
    s, d = A0.http('GET', '/v1/health/service/dep?stale'); j = J(s, d)
    return s, (j[0]['Checks'] if j else None)
s, ch = cat_dep(); print(f'  拆 server 之前,经 agent 查 catalog 里 dep 的检查状态:{[(c["CheckID"], c["Status"]) for c in ch]}')
lp = int(CC.leader().split(':')[1]); li = next(i for i in range(3) if CC.ports[i]['srv'] == lp); other = next(i for i in range(3) if i != li)
CC.kill_node(li); CC.kill_node(other); time.sleep(4.0)
bk2['code'] = 500; g = wait_status({'depc': 'critical'}, 10)
r_reg = A0.http('PUT', '/v1/agent/service/register', {'Name': 'api', 'ID': 'api-1', 'Port': 8083})
s, d = A0.http('GET', '/v1/agent/services'); local = sorted(J(s, d) or {})
def tries(path, n=8, depstat=False):
    out = collections.Counter()
    for _ in range(n):
        try:
            s_, d_ = A0.http('GET', path, timeout=8.0)
            if depstat and s_ == 200: out['HTTP 200 depc=' + next(c['Status'] for c in J(s_, d_)[0]['Checks'] if c['CheckID'] == 'depc')] += 1
            else: out[f'HTTP {s_} ' + (d_.decode(errors='replace').strip()[:48] if s_ != 200 else f'({len(J(s_, d_) or [])} 条)')] += 1
        except Exception as e: out[f'异常 {type(e).__name__}'] += 1
    return '; '.join(f'{k} ×{v}' for k, v in out.items())
r_cat = tries('/v1/catalog/service/api'); r_cat_stale = tries('/v1/catalog/service/api?stale')
rows = [('agent 本地:depc 检查(把后端改成 500 后)', checks()['depc']['Status'] + (f'(改完后 {g.get("depc", float("nan")):.2f} s 变化)' if g else '')), ('登记 api(PUT /v1/agent/service/register)', f'HTTP {r_reg[0]}'), ('agent 本地服务列表', ','.join(local)),
        ('经 agent 查 catalog 的 api(默认)8 次', r_cat), ('经 agent 查 catalog 的 api(?stale)8 次', r_cat_stale), ('经 agent 查 catalog 里 dep 的 depc 状态(?stale)8 次', tries('/v1/health/service/dep?stale', depstat=True)), ('(agent 本地 dep 的检查状态)', checks()['depc']['Status'])]
table(rows, ['观察(只剩 1 个 server,没有 leader)', '结果'])
t0 = time.perf_counter(); CC.start_node(li); CC.start_node(other); t_leader = None; t_api = None; t_dep = None
while time.perf_counter() - t0 < 90:
    if t_leader is None:
        for k in range(3):
            try:
                s, d = CC.http(k, 'PUT', '/v1/kv/probe', b'1', timeout=1.0)
                if s == 200 and d.strip() == b'true': t_leader = time.perf_counter() - t0; break
            except Exception: pass
    try:
        s, d = A0.http('GET', '/v1/catalog/service/api', timeout=1.0)
        if t_api is None and s == 200 and len(J(s, d) or []) == 1: t_api = time.perf_counter() - t0
        s, d = A0.http('GET', '/v1/health/service/dep', timeout=1.0)
        j = J(s, d)
        if t_dep is None and s == 200 and j and any(c['CheckID'] == 'depc' and c['Status'] == 'critical' for c in j[0]['Checks']): t_dep = time.perf_counter() - t0
    except Exception: pass
    if t_api and t_dep: break
    time.sleep(0.1)
f = lambda x: f'{x:.2f} s' if x is not None else '90 s 内没有'
print(f'  把两个 server 拉起来之后(从启动命令算起):可以写入(选出 leader){f(t_leader)};catalog 里出现 api {f(t_api)};catalog 里 dep 的检查变成 critical {f(t_dep)}')
S2.stop()

# ============ 六 ============
print('== 六:同一个服务的三个实例,检查状态不同时,各个接口看到什么。web1 passing、web2 返回 429(warning)、web3 返回 500(critical),都登记在 client agent v52a0 上;比较 catalog、/v1/health/service、?passing 和 DNS(SRV 查询)')
bs = [{'code': c} for c in (200, 429, 500)]
svcs = [Svc((lambda b: (lambda h: h.reply(b['code'], b'x')))(b), f'w{i}') for i, b in enumerate(bs)]
for i, sv in enumerate(svcs):
    A0.http('PUT', '/v1/agent/service/register', {'Name': 'tri', 'ID': f'tri-{i + 1}', 'Port': sv.port, 'Check': {'CheckID': f'tri{i + 1}', 'HTTP': f'http://127.0.0.1:{sv.port}/', 'Interval': '1s', 'Timeout': '1s'}})
wait_status({'tri1': 'passing', 'tri2': 'warning', 'tri3': 'critical'}); time.sleep(1.5)
def cnt(path):
    s, d = A0.http('GET', path); j = J(s, d) or []; return len(j), j
n_cat, _ = cnt('/v1/catalog/service/tri'); n_all, jall = cnt('/v1/health/service/tri'); n_pass, jp = cnt('/v1/health/service/tri?passing')
def agg(e): 
    sts = [c['Status'] for c in e['Checks']]; return 'critical' if 'critical' in sts else ('warning' if 'warning' in sts else 'passing')
rs = dns.resolver.Resolver(configure=False); rs.nameservers = ['127.0.0.1']; rs.port = A0.p['dns']
ans = rs.resolve('tri.service.consul', 'SRV'); dns_ports = sorted(int(r.port) for r in ans)
ports = {sv.port: f'tri-{i + 1}' for i, sv in enumerate(svcs)}
table([('catalog(/v1/catalog/service/tri)', f'{n_cat} 个', '不看健康状态'), ('/v1/health/service/tri', f'{n_all} 个', ' '.join(f'{e["Service"]["ID"]}:{agg(e)}' for e in sorted(jall, key=lambda e: e['Service']['ID']))), ('/v1/health/service/tri?passing', f'{n_pass} 个', ' '.join(e['Service']['ID'] for e in jp)), ('DNS SRV tri.service.consul', f'{len(dns_ports)} 个', ' '.join(ports.get(p, str(p)) for p in dns_ports))], ['接口', '实例数', '内容'])
print('  四个入口对 warning 实例的处理不一样:catalog 全部列出,health 列出并带状态,?passing 去掉 warning,DNS 的 SRV 应答里有 warning 的实例、没有 critical 的实例')
for sv in svcs: sv.stop()

# ============ 七 ============
print('== 七:登记时没写 Status 的检查,在第一次检查完成之前是什么状态;服务连续 critical 之后被自动注销(DeregisterCriticalServiceAfter)。4 个服务都指向没人监听的端口,interval 1 s,DeregisterCriticalServiceAfter 分别是 10s、10s、30s、90s;每 0.5 s 看一次 agent 本地的服务列表,最多看 160 s,记录每个服务从检查变成 critical 起多久后消失')
sv = Svc(lambda h: h.reply(200), 'x'); dead = sv.port; sv.stop()
cfg = [('d10a', '10s'), ('d10b', '10s'), ('d30', '30s'), ('d90', '90s')]; reg_t = {}
for sid, dur in cfg:
    reg_t[sid] = time.perf_counter()
    A0.http('PUT', '/v1/agent/service/register', {'Name': 'dereg', 'ID': sid, 'Port': dead, 'Check': {'CheckID': 'c-' + sid, 'HTTP': f'http://127.0.0.1:{dead}/', 'Interval': '1s', 'Timeout': '1s', 'DeregisterCriticalServiceAfter': dur}})
init = checks()['c-d10a']['Status']
t_crit = {}; gone = {}; T0 = time.perf_counter()
while time.perf_counter() - T0 < 160 and len(gone) < len(cfg):
    c = checks(); s, d = A0.http('GET', '/v1/agent/services'); sv_ = J(s, d) or {}; now = time.perf_counter()
    for sid, dur in cfg:
        if sid not in t_crit and c.get('c-' + sid, {}).get('Status') == 'critical': t_crit[sid] = now
        if sid not in gone and sid not in sv_: gone[sid] = now
    time.sleep(0.5)
print(f'  刚登记时检查状态:{init}(登记后马上读)')
table([(sid, dur, f'{t_crit[sid] - reg_t[sid]:.1f}' if sid in t_crit else '-', f'{gone[sid] - t_crit[sid]:.1f}' if sid in gone and sid in t_crit else '160 s 内没有消失') for sid, dur in cfg], ['服务', 'DeregisterCriticalServiceAfter', '登记后多久变 critical(s)', '变 critical 后多久从 agent 本地消失(s)'])
s, d = CC.http(0, 'GET', '/v1/catalog/service/dereg'); print(f'  结束时 catalog 里 dereg 的实例数:{len(J(s, d) or [])}')

A0.kill(); A1.kill(); CC.stop_all()
print('ERRORS', dict(ERRORS))
