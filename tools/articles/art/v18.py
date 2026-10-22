from lib import *
S = SS('v18')
steps = [
    step("nginx upstream 的实际分布。三个后端 A、B、C,每种配置顺序发 700 个请求。默认轮询:234 / 233 / 233。weight=5:1:1:500 / 100 / 100。weight=3:2:1:350 / 233 / 117。ip_hash:所有请求都来自 127.0.0.1,于是 0 / 0 / 700,全部落到同一个后端。hash $http_x_user(700 个不同的用户名):239 / 214 / 247;加 consistent:252 / 220 / 228。random:252 / 223 / 225。random two least_conn:222 / 243 / 235。权重按比例分,哈希按键散开,ip_hash 在所有 client 地址相同(例如前面还有一层代理)时没有负载均衡的作用。", t=tl(S(1)), mark=lidx(S(1), 'ip_hash'), done=lidx(S(1), 'weight=5:1:1', 'weight=3:2:1', '默认'), b=bars([['weight 5:1:1 的 A', 500, '500 / 100 / 100'], ['weight 3:2:1 的 A', 350, '350 / 233 / 117'], ['ip_hash 的 C', 700, '0 / 0 / 700'], ['hash consistent 的 A', 252, '252 / 220 / 228']], 700, done=[0, 1, 3], mark=[2]), kv=KV([['weight', '按权重比例分,5:1:1 → 500 / 100 / 100'], ['ip_hash', '地址全相同时 700 个全到 C'], ['hash $http_x_user', '700 个用户名散开 239 / 214 / 247']], ['ip_hash'])),
    step("后端速度不一样时的 least_conn。A、B 每个请求 10 ms,C 每个请求 100 ms,16 个并发线程共 1600 个请求。轮询:534 / 533 / 533,延迟中位数 15 ms、p99 111 ms,总吞吐 325/s。least_conn:746 / 739 / 115,中位数 15 ms、p99 110 ms,吞吐 503/s。random two least_conn:724 / 749 / 127,中位数 15 ms、p99 110 ms,吞吐 471/s。轮询把三分之一的请求给了慢节点,least_conn 让慢节点只收到 115 个(它的在途请求一直多),总吞吐从 325/s 升到 503/s;p99 主要由还是落到慢节点的那些请求决定,差不多。", t=tl(S(2)), mark=lidx(S(2), '轮询'), done=lidx(S(2), 'least_conn', 'random two'), b=bars([['轮询 C 收到', 533, '533'], ['least_conn C 收到', 115, '115'], ['轮询 吞吐 /s', 325, '325'], ['least_conn 吞吐 /s', 503, '503']], 533, mark=[0, 2], done=[1, 3]), kv=KV([['轮询', '慢节点 C 收到 533,吞吐 325/s'], ['least_conn', 'C 收到 115,吞吐 503/s'], ['p99', '都约 110 ms']], ['least_conn'])),
    step("手写平滑加权轮询:每个节点有 weight 和 current,每次让所有节点 current += weight,选 current 最大的,再让它 current -= 总权重。拿前 14 个选择和 nginx 真实的顺序逐个比对。weight=5:1:1:nginx 是 AABACAAAABACAA,手写也是 AABACAAAABACAA,相同。weight=3:2:1:ABACBAABACBAAB,相同。weight=1:1:1:ABCABCABCABCAB,相同。朴素地把每个节点重复 weight 次再循环,5:1:1 得到 AAAAABCAAAAABC,同一个节点连续被选 5 次;平滑加权轮询把它们错开,每个节点的次数相同。", t=tl(S(3)), mark=lidx(S(3), '朴素的'), done=lidx(S(3), 'weight=5:1:1', 'weight=3:2:1', 'weight=1:1:1'), b=bars([['5:1:1 比对一致', 1, '相同'], ['3:2:1 比对一致', 1, '相同'], ['1:1:1 比对一致', 1, '相同'], ['朴素重复:A 连续次数', 5, 'AAAAA']], 5, done=[0, 1, 2], mark=[3]), kv=KV([['5:1:1', 'AABACAAAABACAA(nginx = 手写)'], ['3:2:1', 'ABACBAABACBAAB(nginx = 手写)'], ['朴素重复', 'AAAAABC 重复,A 连续 5 次']], ['朴素重复'])),
]
A = mkartv('v18', 18, '微服务,网关,nginx,负载均衡,加权轮询,least_conn,真实验证,动画演示',
    '实测 nginx upstream 的分布:weight=5:1:1 得到 500 / 100 / 100;ip_hash 在所有请求地址相同时 700 个全到同一个后端;least_conn 在一个慢后端时让它只收 115 个、吞吐 325/s → 503/s;手写平滑加权轮询与 nginx 前 14 个选择完全一致。',
    'nginx 的轮询、加权、ip_hash、hash、least_conn 实际怎么分布?后端速度不一样时 least_conn 好在哪?自己写一个平滑加权轮询,和 nginx 的选择顺序一样吗?这篇用三个后端逐项量出来。',
    [('500 / 100 / 100', 'weight=5:1:1 时 700 个请求的分布'), ('115 对 533', '一个慢后端(100 ms,其余 10 ms)上,least_conn 与轮询分给慢后端的请求数;吞吐 503/s 对 325/s'), ('3 / 3', '手写的平滑加权轮询与 nginx 真实选择顺序前 14 个比对一致的配置数(5:1:1、3:2:1、1:1:1)')],
    [('分布', '<p>权重按比例分,哈希按键散开;ip_hash 在 client 地址全相同时没有负载均衡的作用。</p>'),
     ('least_conn', '<p>后端速度不一样时,least_conn 让慢节点少收请求,总吞吐更高。</p>'),
     ('平滑加权轮询', '<p>把节点错开,不是连续选同一个;手写版本和 nginx 的顺序完全一致。</p>')],
    steps,
    [ENV_V + '。nginx 是 Homebrew 的 1.31.6;后端是本进程里的 Python http.server;第一节顺序串行发 700 个请求;第二节 16 个线程各发 100 个;第三节的平滑加权轮询是我按 nginx 文档描述的算法写的 Python 版本',
     '没有验证:nginx 的 least_conn 在 worker 进程之间不共享计数(本机只有 1 个 worker 进程,多 worker 时的分布没有测);upstream 里 zone 共享内存的影响;nginx plus 的 least_time;权重和 backup / down 参数的组合'],
    '负载均衡算法')
