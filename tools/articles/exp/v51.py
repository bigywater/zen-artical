import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import dns.resolver, dns.message, dns.query, dns.exception, dns.flags
tee('v51'); reset()
print('用 DNS 做服务发现:服务名解析成一组 SRV 记录(优先级 priority、权重 weight、端口 port、目标主机 target),客户端按 RFC 2782 的规则挑一个。DNS 服务是我用 dnspython 写的权威服务(UDP 和 TCP,区域可随时修改,统计收到的查询数);客户端的缓存用 dnspython 的 Resolver.cache(遵守记录里的 TTL)。后端是本进程里的 Python 服务,各占一个端口')
D = MiniDNS(neg_ttl=20)
def resolver(cache=True):
    r = dns.resolver.Resolver(configure=False); r.nameservers = ['127.0.0.1']; r.port = D.port; r.lifetime = 3
    r.cache = dns.resolver.Cache() if cache else None; return r
def pick(srvs, rng):
    best = min(s[0] for s in srvs); cands = [s for s in srvs if s[0] == best]; tot = sum(max(s[1], 0) for s in cands) or len(cands); x = rng.random() * tot; acc = 0
    for s in cands:
        acc += (s[1] if tot != len(cands) or s[1] else 1)
        if x < acc: return s
    return cands[-1]

# ============ 一 ============
print('== 一:TTL 决定“摘掉的实例多久之后不再被访问”。web.svc.local 有 3 个 SRV 目标(三个后端,优先级 10,权重 1)。client 以 50 个请求/秒发 14 秒;第 4 秒(遵守 TTL 的缓存还会换 4.7 s、5.4 s 两个删除时刻,为了错开缓存过期的相位)把第 3 个后端从 DNS 里删掉并立刻停掉这个后端。三种解析方式:(a) 遵守 TTL 的缓存(TTL 2 s / 5 s / 10 s);(b) 启动时解析一次、之后一直用(很多长连接客户端的实际行为);(c) 不缓存,每个请求都解析一次。统计错误请求数、错误的时间范围、DNS 收到的查询数')
def run1(mode, ttl, t_del=4.0, dur=14.0):
    inst = [Svc(lambda h, k=k: h.reply(200, str(k).encode())) for k in range(3)]
    D.zone.clear(); D.set('web.svc.local', 'SRV', [(ttl, f'10 1 {s.port} i{k}.svc.local.') for k, s in enumerate(inst)])
    for k in range(3): D.set(f'i{k}.svc.local', 'A', [(ttl, '127.0.0.1')])
    D.queries = 0; r = resolver(cache=(mode == 'ttl')); rng = random.Random(3); once = [None]
    if mode == 'once': once[0] = [(a.priority, a.weight, a.port) for a in r.resolve('web.svc.local', 'SRV')]
    T0 = time.perf_counter()
    def ev():
        time.sleep(t_del); D.set('web.svc.local', 'SRV', [(ttl, f'10 1 {s.port} i{k}.svc.local.') for k, s in enumerate(inst[:2])]); inst[2].svc.stop() if hasattr(inst[2], 'svc') else inst[2].stop()
    threading.Thread(target=ev, daemon=True).start(); lk = threading.Lock()
    def one(i):
        srvs = once[0] if mode == 'once' else [(a.priority, a.weight, a.port) for a in r.resolve('web.svc.local', 'SRV')]
        s = pick(srvs, rng); st, b, dt = rpc(s[2], '/', 1.0, keepalive=False); return st
    out = openloop(one, 50, dur, workers=100)
    errs = [ts for ts, st in out if st != 200]
    for s in inst[:2]: s.stop()
    return len(errs), (min(errs), max(errs)) if errs else None, D.queries
rows = []
for name, mode, ttl in (('(a) 遵守 TTL · TTL 2 s', 'ttl', 2), ('(a) 遵守 TTL · TTL 5 s', 'ttl', 5), ('(a) 遵守 TTL · TTL 10 s', 'ttl', 10), ('(b) 启动时解析一次', 'once', 5), ('(c) 不缓存', 'none', 5)):
    phases = (4.0, 4.7, 5.4) if mode == 'ttl' else (4.0,)
    rs = [run1(mode, ttl, t_del=p) for p in phases]
    rows.append((name, ' / '.join(str(r[0]) for r in rs), ' | '.join(f'{r[1][0]:.1f}~{r[1][1]:.1f}' if r[1] else '-' for r in rs), ' / '.join(str(r[2]) for r in rs)))
table(rows, ['解析方式', '错误请求数(每次共 700 个;遵守 TTL 的做了 3 次,删除时刻 4.0 / 4.7 / 5.4 s)', '错误发生的时间范围(秒)', 'DNS 收到的查询数'])
print('  遵守 TTL 的缓存:删掉记录之后,缓存最多还能再用一个 TTL(具体多久取决于删除时刻与缓存过期的相位,所以做了 3 次),这期间约三分之一的请求打到已经停掉的后端;TTL 越短错误越少,但 DNS 查询越多;启动时只解析一次的客户端永远不会发现变化,错误一直持续到结束;不缓存的客户端在删除之后立刻不再出错,代价是每个请求一次 DNS 查询(50 个/秒)')

# ============ 二 ============
print('== 二:SRV 的优先级与权重。三个目标:A(优先级 10,权重 1)、B(优先级 10,权重 3)、C(优先级 20,权重 5)。按 RFC 2782 的规则选(先选最小的优先级,同一优先级里按权重加权随机)10000 次;然后把 A、B 都从 DNS 里删掉(模拟都挂了),再选 10000 次')
D.zone.clear(); D.set('web.svc.local', 'SRV', [(5, '10 1 8001 a.svc.local.'), (5, '10 3 8002 b.svc.local.'), (5, '20 5 8003 c.svc.local.')])
r = resolver(cache=False); rng = random.Random(5); names = {8001: 'A', 8002: 'B', 8003: 'C'}
def draw(n=10000):
    srvs = [(a.priority, a.weight, a.port) for a in r.resolve('web.svc.local', 'SRV')]; c = collections.Counter(names[pick(srvs, rng)[2]] for _ in range(n)); return c
c1 = draw(); D.set('web.svc.local', 'SRV', [(5, '20 5 8003 c.svc.local.')]); c2 = draw()
table([('A、B、C 都在', c1.get('A', 0), c1.get('B', 0), c1.get('C', 0), f"{c1.get('A', 0) / 100:.1f}% / {c1.get('B', 0) / 100:.1f}% / {c1.get('C', 0) / 100:.1f}%"), ('A、B 都被删掉', c2.get('A', 0), c2.get('B', 0), c2.get('C', 0), f"{c2.get('C', 0) / 100:.1f}% 给 C")], ['情形', 'A 被选', 'B 被选', 'C 被选', '占比'])
print('  优先级是“备用”的语义:只要还有优先级更高(数字更小)的目标,低优先级的目标一点流量都得不到;同优先级里按权重 1 : 3 分(约 25% / 75%);高优先级的都被删掉之后,备用的 C 才接管全部流量。注意:SRV 本身不包含健康状态,“都挂了”要靠有人把它们从区域里删掉')

# ============ 三 ============
print('== 三:负缓存。服务 new.svc.local 还没登记时,查询得到 NXDOMAIN,SOA 的 minimum(负缓存 TTL)是 20 s,遵守缓存的客户端会把“不存在”也缓存这么久。client 在第 0 秒查询一次(NXDOMAIN),第 2 秒服务登记上线(记录 TTL 5 s),之后每 1 s 查询一次直到成功。对照不缓存的客户端')
rows = []
for name, cache in (('遵守缓存(含负缓存)', True), ('不缓存', False)):
    D.zone.clear(); D.queries = 0; r = resolver(cache=cache); t0 = time.perf_counter(); first = None; reg_at = [None]
    try: r.resolve('new.svc.local', 'SRV')
    except dns.resolver.NXDOMAIN: pass
    def reg():
        time.sleep(2.0); D.set('new.svc.local', 'SRV', [(5, '10 1 9000 n.svc.local.')]); reg_at[0] = time.perf_counter() - t0
    threading.Thread(target=reg, daemon=True).start()
    while time.perf_counter() - t0 < 40:
        time.sleep(1.0)
        try: r.resolve('new.svc.local', 'SRV'); first = time.perf_counter() - t0; break
        except dns.resolver.NXDOMAIN: pass
    rows.append((name, f'{reg_at[0]:.1f} s', f'{first:.1f} s' if first else '40 s 内没有成功', f'{first - reg_at[0]:.1f} s' if first else '-', D.queries))
table(rows, ['客户端', '服务上线时刻', '客户端第一次解析成功', '上线之后又过了多久才发现', 'DNS 收到的查询数'])
print('  “不存在”也是会被缓存的答案:服务晚于客户端的第一次查询才登记,遵守负缓存的客户端要等到负缓存 TTL(SOA minimum)过期才会再去问;不缓存的客户端在上线后下一次查询就成功')

# ============ 四 ============
print('== 四:UDP 应答放不下。web.svc.local 有 N 个 SRV 目标,查询不带 EDNS(传统 DNS 的 UDP 上限 512 字节)。N = 5 / 20 / 40 / 100:看 UDP 应答里的记录数、TC(截断)标志、应答大小,以及用 TCP 重查拿到的完整记录数')
rows = []
for n in (5, 20, 40, 100):
    D.zone.clear(); D.set('web.svc.local', 'SRV', [(5, f'10 1 {8000 + i} instance-{i:03d}.svc.local.') for i in range(n)])
    q = dns.message.make_query('web.svc.local', 'SRV', use_edns=False)
    ru = dns.query.udp(q, '127.0.0.1', port=D.port, timeout=2); rt = dns.query.tcp(q, '127.0.0.1', port=D.port, timeout=2)
    rows.append((n, len(ru.answer[0]) if ru.answer else 0, bool(ru.flags & dns.flags.TC), len(ru.to_wire()), len(rt.answer[0]), len(rt.to_wire())))
table(rows, ['目标数 N', 'UDP 应答里的记录数', 'TC 标志', 'UDP 应答大小(字节)', 'TCP 应答里的记录数', 'TCP 应答大小(字节)'])
print('  应答超过 512 字节时,这个服务端把答案清空并置 TC 位,告诉客户端“去用 TCP 重查”(这是我这个服务端的做法;有的服务端会保留放得下的那部分记录再置 TC);客户端库一般会自动回退到 TCP,多一次连接;实例数多的服务不适合只靠一个 SRV 记录集合,要么用 EDNS 提高 UDP 上限,要么拆分')
D.close()
