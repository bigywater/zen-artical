import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v85'); reset()
print('Envoy 的 HTTP 过滤器链。Envoy 1.39.3,本机的 Python 后端。(一)过滤器的顺序会改变结果(故障注入和本地限流谁在前);(二)router 必须是最后一个,否则 Envoy 拒绝加载配置;(三)路由级配置覆盖过滤器级配置;(四)每多一个过滤器的延迟开销')
BACK = Svc(lambda h: h.reply(200, b'ok'), 'back')
FAULT = lambda pct: f'''          - name: envoy.filters.http.fault
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.fault.v3.HTTPFault
              abort: {{http_status: 503, percentage: {{numerator: {pct}, denominator: HUNDRED}}}}'''
RL = lambda tokens, per_route=False: f'''          - name: envoy.filters.http.local_ratelimit
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
              stat_prefix: rl
              token_bucket: {{max_tokens: {tokens}, tokens_per_fill: {tokens}, fill_interval: 1s}}
              filter_enabled: {{runtime_key: rl_on, default_value: {{numerator: 100, denominator: HUNDRED}}}}
              filter_enforced: {{runtime_key: rl_enf, default_value: {{numerator: 100, denominator: HUNDRED}}}}'''
LUA = lambda i: f'''          - name: envoy.filters.http.lua
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua
              default_source_code:
                inline_string: |
                  function envoy_on_request(h) h:headers():add("x-lua-{i}", "1") end'''
ROUTES = '              - match: {prefix: "/"}\n                route: {cluster: back}'
def env(pre, routes=ROUTES, tag='x'):
    return Envoy('v85' + tag, envoy_http_conf(routes, {'back': [BACK.port]}, pre_filters=pre)).start()
def hit(port, n, rate, path='/'):
    def one(i):
        s, d, dt = rpc(port, path, 3.0, keepalive=False); return s
    r = openloop(one, rate, n / rate, workers=100); return collections.Counter(x for _, x in r)

# ============ 一 ============
print('== 一:过滤器的顺序。两个过滤器:故障注入(abort,50% 的请求直接返回 503)和本地限流(令牌桶 20 个令牌、每秒补充 20 个,超出返回 429)。(a)故障注入在前、限流在后;(b)限流在前、故障注入在后。每种发 400 个请求(100 个/秒,4 s),统计各状态码')
rows = []
for name, pre, tag in (('(a)fault → local_ratelimit → router', FAULT(50) + '\n' + RL(20), 'a'), ('(b)local_ratelimit → fault → router', RL(20) + '\n' + FAULT(50), 'b')):
    e = env(pre, tag=tag); time.sleep(0.5); c = hit(e.port, 400, 100); e.stop()
    rows.append((name, c.get(200, 0), c.get(429, 0), c.get(503, 0), sum(c.values())))
table(rows, ['过滤器顺序', '200', '429(被限流)', '503(被故障注入中止)', '合计'])
print('  请求按顺序依次经过每个过滤器,谁先处理就先作用:故障注入在前时,被中止的请求(503)根本没有走到限流,不消耗令牌;限流在前时所有请求(包括之后会被中止的)都先消耗令牌,所以令牌更早用完,429 更多、通过的请求更少')

# ============ 二 ============
print('== 二:router 必须是最后一个。把一个 router 过滤器放在 lua 过滤器前面(这样 router 就不是最后一个了;我的配置生成器会在末尾再加一个 router)。看 Envoy 启动时的结果')
ROUTER = '''          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router'''
try:
    e = env(ROUTER + '\n' + LUA(1), tag='c'); msg = 'Envoy 启动成功了'; e.stop()
except Exception as ex: msg = str(ex)
lines = [l.strip() for l in msg.splitlines() if 'terminal' in l or 'must be' in l or 'error' in l.lower() or 'critical' in l][:3]
print('  启动结果:' + (' | '.join(l[-230:] for l in lines) if lines else msg[-300:]))
print('  router 是 “终结过滤器”(它把请求转给上游并结束过滤器链),它后面不能再有别的过滤器;Envoy 在加载配置时就检查并拒绝')

# ============ 三 ============
print('== 三:路由级配置覆盖过滤器级配置。HCM 里的本地限流过滤器的令牌桶是每秒 5 个;/api 路由用过滤器级配置,/health 路由用 typed_per_filter_config 覆盖成每秒 1000 个令牌。100 个请求/秒打 /api,同时 100 个请求/秒打 /health,各发 3 s,统计状态码')
routes3 = '''              - match: {prefix: "/health"}
                route: {cluster: back}
                typed_per_filter_config:
                  envoy.filters.http.local_ratelimit:
                    "@type": type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
                    stat_prefix: rl_health
                    token_bucket: {max_tokens: 1000, tokens_per_fill: 1000, fill_interval: 1s}
                    filter_enabled: {runtime_key: rl_on2, default_value: {numerator: 100, denominator: HUNDRED}}
                    filter_enforced: {runtime_key: rl_enf2, default_value: {numerator: 100, denominator: HUNDRED}}
              - match: {prefix: "/"}
                route: {cluster: back}'''
e = env(RL(5), routes3, tag='d'); time.sleep(0.5)
res = {}
def run(path, key): res[key] = hit(e.port, 300, 100, path)
ts = [threading.Thread(target=run, args=('/api', 'api')), threading.Thread(target=run, args=('/health', 'health'))]
for t in ts: t.start()
for t in ts: t.join()
e.stop()
table([('/api(用过滤器级配置:5 个/秒)', res['api'].get(200, 0), res['api'].get(429, 0)), ('/health(路由级覆盖:1000 个/秒)', res['health'].get(200, 0), res['health'].get(429, 0))], ['路径', '200', '429'])
print('  路由级的 typed_per_filter_config 覆盖了过滤器自己的配置:同一个过滤器在不同路由上可以有不同的限流参数,健康检查之类的路径可以不被限流')

# ============ 四 ============
print('== 四:每多一个过滤器的开销。后端直接返回一个小响应。单线程顺序发 4000 个请求(保持连接),统计经过 Envoy 的延迟 p50 / p99。过滤器链:(a)只有 router;(b)router 之前加 5 个很简单的 Lua 过滤器(各加一个请求头);(c)加 20 个。每种做 3 轮取 p50 的中位数。Envoy 以 --concurrency 1 运行')
rows = []
base = None
for n, tag in ((0, 'e0'), (5, 'e5'), (20, 'e20')):
    e = env('\n'.join(LUA(i) for i in range(n)), tag=tag); time.sleep(0.5)
    for _ in range(300): rpc(e.port, '/', 3.0)
    p50s = []; p99s = []
    for _ in range(3):
        lat = [rpc(e.port, '/', 3.0)[2] * 1000 for _ in range(4000)]; p50s.append(pct(lat, 50)); p99s.append(pct(lat, 99))
    e.stop(); m50 = statistics.median(p50s); m99 = statistics.median(p99s); base = base if base is not None else m50
    rows.append((n, f'{m50:.3f}', f'{m99:.3f}', f'{(m50 - base) * 1000:+.0f}'))
table(rows, ['router 之前的 Lua 过滤器个数', '延迟 p50(ms)', '延迟 p99(ms)', 'p50 相对没有 Lua 过滤器多出的微秒'])
print('  过滤器链里每多一个过滤器,每个请求都要多经过一次;Lua 过滤器要进入脚本虚拟机,开销比纯 C++ 的过滤器大。这里测的是一个很简单的脚本,真实的脚本越复杂开销越大')
print('ERRORS', dict(ERRORS))
