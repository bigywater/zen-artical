from lib import *
S = SS('v31')
steps = [
    step("按权重分 90% / 10%,各发 10000 个请求。(a) nginx split_clients 以 $request_id 为 key:S 8962、C 1038(10.4%),随机分,期望 1000、标准差约 30。(b) nginx upstream weight=9:1:正好 S 9000、C 1000(10.0%),这是确定性的加权轮询,不是随机。(c) split_clients 用固定 key:S 10000、C 0——每个请求都落到同一个桶,10% 的权重没有意义,split_clients 必须选一个随请求或随用户变化的 key。Envoy weighted_clusters 90:10:S 9018、C 982(9.8%)。", t=tl(S(1)), mark=lidx(S(1), '(c)'), done=lidx(S(1), '(a)', '(b)', 'Envoy'), b=bars([['(a) split_clients $request_id:C', 1038, '1038'], ['(b) weight=9:1:C', 1000, '1000(确定性)'], ['(c) 固定 key:C', 0, '0'], ['Envoy weighted_clusters:C', 982, '982']], 1100, done=[0, 1, 3], mark=[2]), kv=KV([['split_clients $request_id', 'C 10.4%'], ['weight=9:1', '正好 10.0%'], ['固定 key', 'C 0%'], ['Envoy weighted_clusters', 'C 9.8%']], ['固定 key'])),
    step("按请求头 / cookie 定向。规则:X-Canary: 1 去 C,cookie canary=1 去 C,其余去 S;每种请求发 20 个。无头无 cookie:nginx 和 Envoy 都是 0 个去 C。X-Canary: 1:20 个。X-Canary: 0:0 个。Cookie: canary=1:20 个。Cookie: a=b; canary=1:20 个。Cookie: canary=10:0 个。Cookie: mycanary=1:0 个。两个网关的结果一致。相近的 cookie(canary=10、mycanary=1)都没有被误命中,但两边都要把匹配写精确,否则 canary=10 之类的值会被当成 canary=1。", t=tl(S(2)), mark=lidx(S(2), 'canary=10', 'mycanary=1'), done=lidx(S(2), 'X-Canary: 1', 'Cookie: canary=1', 'Cookie: a=b'), b=bars([['X-Canary: 1 → C', 20, '20 / 20(两个网关)'], ['Cookie: canary=1 → C', 20, '20 / 20'], ['Cookie: canary=10 → C', 0, '0 / 20'], ['Cookie: mycanary=1 → C', 0, '0 / 20']], 20, done=[0, 1], mark=[2, 3]), kv=KV([['nginx 与 Envoy', '七种请求的结果完全一致'], ['canary=10 / mycanary=1', '都没有误命中']], ['canary=10 / mycanary=1'])),
    step("同一个用户看到的版本是否一致。200 个用户各发 20 个请求(头 X-User),C 占 10%。nginx split_clients 以 $http_x_user 为 key:只看到 S 的用户 179 个、只看到 C 的用户 21 个、两个版本都看到的 0 个——同一用户始终落在同一个版本。nginx upstream weight=9:1:24、0、176 个两个版本都看到。Envoy weighted_clusters:22、0、178 个两个版本都看到。每个请求独立分流时,10% 的流量让约 1 − 0.9^20 = 88% 的用户在 20 个请求内碰到过新版本,实测 176/200 = 88% 和 178/200 = 89%。", t=tl(S(3)), mark=lidx(S(3), 'weight=9:1', 'Envoy'), done=lidx(S(3), 'split_clients'), b=bars([['split_clients:两个版本都看到', 0, '0 / 200'], ['weight=9:1:两个版本都看到', 176, '176 / 200'], ['Envoy:两个版本都看到', 178, '178 / 200']], 200, done=[0], mark=[1, 2]), kv=KV([['按用户哈希', '0 个用户两个版本都见到'], ['每个请求独立分流', '约 88% 的用户见到两个版本']], ['按用户哈希'])),
]
A = mkartv('v31', 31, '微服务,网关,流量分流,灰度,nginx,Envoy,真实验证,动画演示',
    '实测 nginx 与 Envoy 1.39.3 的流量分流:90/10 权重下 split_clients 得到 10.4%、upstream weight 正好 10.0%、Envoy 9.8%;split_clients 用固定 key 时 C 是 0;按请求头和 cookie 定向两个网关结果一致;按用户哈希分流 0 个用户见到两个版本,每个请求独立分流则有 88% 的用户见到。',
    '灰度的 10% 流量怎么分?按权重、按请求头还是按 cookie?同一个用户会不会一会儿旧版本一会儿新版本?这篇用 nginx 1.31.6 和 Envoy 1.39.3 把几种分流方式量出来。',
    [('10.4% / 10.0% / 9.8%', 'nginx split_clients、nginx upstream weight=9:1、Envoy weighted_clusters 在 10000 个请求里分给新版本的比例'), ('0%', 'split_clients 用固定字符串当 key 时新版本得到的流量(10% 的权重完全无效)'), ('0 对 176', '200 个用户各 20 个请求:按用户哈希分流与 nginx 加权轮询下,两个版本都见到过的用户数')],
    [('按权重', '<p>split_clients 随机;upstream weight 是确定性的加权轮询;Envoy 是随机选择簇;key 必须随请求或用户变化。</p>'),
     ('按头和 cookie', '<p>两个网关的结果一致,匹配要写精确。</p>'),
     ('一致性', '<p>按用户哈希分流让同一用户始终落在同一个版本;每个请求独立分流,约 88% 的用户在 20 个请求内碰到过新版本。</p>')],
    steps,
    [ENV_V + '。nginx 是 Homebrew 的 1.31.6;Envoy 是 Homebrew 的 1.39.3(为本系列 brew install envoy,静态配置,--concurrency 1);后端是本进程里的 Python 服务;cookie 匹配在 Envoy 里用了对整个 cookie 头的 safe_regex;每种配置只跑一轮',
     '没有验证:Envoy 的 runtime 流量分配和 header_hash 一致性;nginx split_clients 的哈希算法(MurmurHash2)在用户数很少时的分布偏差;gRPC / HTTP/2 长连接上的请求级分流;服务网格(Istio)里的 VirtualService 权重'],
    '流量分流')
