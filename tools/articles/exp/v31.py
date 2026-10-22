import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v31'); reset()
print('流量分流:按权重、按请求头、按 cookie。两个后端 S(稳定版)和 C(新版本)是本进程里的 Python 服务,回自己的名字。网关用 nginx 1.31.6 和 Envoy 1.39.3(Homebrew,静态配置,1 个工作线程)')
S_ = Svc(lambda h: h.reply(200, b'S')); C_ = Svc(lambda h: h.reply(200, b'C'))
def nginx_conf(split):
    return f'''upstream stable {{ server 127.0.0.1:{S_.port}; }} upstream canary {{ server 127.0.0.1:{C_.port}; }}
  upstream mixed {{ server 127.0.0.1:{S_.port} weight=9; server 127.0.0.1:{C_.port} weight=1; }}
  {split}
  server {{ listen {{port}}; location / {{ proxy_pass http://$target; }} }}'''
def envoy_conf(routes):
    return envoy_http_conf(routes, {'stable': [S_.port], 'canary': [C_.port]})
def drive(port, n, headers_fn=None, workers=8):
    def one(i):
        st, b, _ = rpc(port, '/', 5.0, headers=headers_fn(i) if headers_fn else None); return b.decode() if st == 200 else str(st)
    return par(one, list(range(n)), workers)

# ============ 一 ============
print('== 一:按权重分 90% / 10%。每种配置发 10000 个请求(8 个并发)。nginx 三种:(a) split_clients 以 $request_id 为 key(每个请求一个随机的 id);(b) upstream 里 weight=9 / weight=1(加权轮询);(c) split_clients 以固定的字符串为 key(同一个 key 总是同一个桶,仅作对照)。Envoy:weighted_clusters stable 90 / canary 10。期望值 C = 1000;随机分配时标准差约 30')
rows = []
for name, split, mode in (('(a) nginx split_clients $request_id', 'split_clients "${request_id}" $target { 10% canary; * stable; }', 'req'), ('(b) nginx upstream weight=9:1', 'map $uri $target { default mixed; }', 'req'), ('(c) nginx split_clients 固定 key', 'split_clients "fixed-key" $target { 10% canary; * stable; }', 'req')):
    ng = Nginx('v31a', nginx_conf(split)).start(); res = drive(ng.port, 10000); ng.stop(); c = collections.Counter(res)
    rows.append((name, c.get('S', 0), c.get('C', 0), f'{c.get("C", 0) / 100:.1f}%'))
routes = '''              - match: {prefix: "/"}
                route:
                  weighted_clusters:
                    clusters:
                    - {name: stable, weight: 90}
                    - {name: canary, weight: 10}'''
ev = Envoy('v31e', envoy_conf(routes)).start(); res = drive(ev.port, 10000); ev.stop(); c = collections.Counter(res)
rows.append(('Envoy weighted_clusters 90:10', c.get('S', 0), c.get('C', 0), f'{c.get("C", 0) / 100:.1f}%'))
table(rows, ['做法', 'S(稳定)', 'C(新版本)', 'C 的比例'])
print('  (b) 是确定性的加权轮询,正好 9000 / 1000;(a) 和 Envoy 是按随机数分,有抖动,10000 个请求时标准差约 30;(c) 固定 key 每个请求都落到同一个桶,10% 的权重没有意义,这就是 split_clients 必须选一个随请求(或随用户)变化的 key 的原因')

# ============ 二 ============
print('== 二:按请求头 / cookie 定向。规则:带 X-Canary: 1 头的请求去 C;带 cookie canary=1 的请求去 C;其余去 S。每种请求发 20 个,统计 C 的数量')
ngmap = 'map "$http_x_canary:$cookie_canary" $target { default stable; "~^1:" canary; "~:1$" canary; }'
ng = Nginx('v31b', nginx_conf(ngmap)).start()
routes2 = '''              - match: {prefix: "/", headers: [{name: "x-canary", string_match: {exact: "1"}}]}
                route: {cluster: canary}
              - match: {prefix: "/", headers: [{name: "cookie", string_match: {safe_regex: {regex: ".*(^|;\\\\s*)canary=1(;|$).*"}}}]}
                route: {cluster: canary}
              - match: {prefix: "/"}
                route: {cluster: stable}'''
ev = Envoy('v31e2', envoy_conf(routes2)).start()
reqs = [('无头无 cookie', None), ('X-Canary: 1', {'X-Canary': '1'}), ('X-Canary: 0', {'X-Canary': '0'}), ('Cookie: canary=1', {'Cookie': 'canary=1'}), ('Cookie: a=b; canary=1', {'Cookie': 'a=b; canary=1'}), ('Cookie: canary=10', {'Cookie': 'canary=10'}), ('Cookie: mycanary=1', {'Cookie': 'mycanary=1'})]
rows = []
for name, hd in reqs:
    a = collections.Counter(drive(ng.port, 20, (lambda i, hd=hd: hd) if hd else None, 4)); b = collections.Counter(drive(ev.port, 20, (lambda i, hd=hd: hd) if hd else None, 4))
    rows.append((name, a.get('C', 0), b.get('C', 0)))
table(rows, ['请求', 'nginx:去 C 的个数(共 20)', 'Envoy:去 C 的个数(共 20)'])
ng.stop(); ev.stop()
print('  相近的 cookie(canary=10、mycanary=1)都没有被误命中:nginx 用 $cookie_canary 按 cookie 名取值再比较,Envoy 对整个 cookie 头写了一个要求 canary=1 前后是分隔符的正则;两者都要把匹配写精确,否则 canary=10 之类的值会被当成 canary=1')

# ============ 三 ============
print('== 三:同一个用户看到的版本是否一致。200 个用户,每个用户发 20 个请求(带头 X-User: uN),目标 C 占 10%。三种做法:nginx split_clients 以 $http_x_user 为 key(同一用户总是同一个桶);nginx upstream weight=9:1(每个请求独立随机/轮询);Envoy weighted_clusters(每个请求独立随机)。统计“只看到 S 的用户”、“只看到 C 的用户”、“两个版本都看到过的用户”')
def users_test(port):
    res = {}
    def one(u):
        seen = set()
        for k in range(20):
            st, b, _ = rpc(port, '/', 5.0, headers={'X-User': f'u{u}'}); seen.add(b.decode())
        res[u] = seen
    par(one, list(range(200)), 8)
    s_only = sum(1 for v in res.values() if v == {'S'}); c_only = sum(1 for v in res.values() if v == {'C'}); both = sum(1 for v in res.values() if len(v) == 2)
    return s_only, c_only, both
rows = []
for name, split in (('nginx split_clients $http_x_user', 'split_clients "${http_x_user}" $target { 10% canary; * stable; }'), ('nginx upstream weight=9:1', 'map $uri $target { default mixed; }')):
    ng = Nginx('v31c', nginx_conf(split)).start(); rows.append((name,) + users_test(ng.port)); ng.stop()
ev = Envoy('v31e3', envoy_conf(routes)).start(); rows.append(('Envoy weighted_clusters 90:10',) + users_test(ev.port)); ev.stop()
table(rows, ['做法', '只看到 S 的用户', '只看到 C 的用户', '两个版本都看到过的用户'])
print('  按用户(或会话)哈希分流,同一个用户始终落在同一个版本,体验一致,也便于排查;每个请求独立随机的分流,10% 的流量会让约 1 − 0.9^20 = 88% 的用户在 20 个请求内碰到过新版本')
