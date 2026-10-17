from lib import *
R = J('z26'); d, g10, t10, t1 = R['default'], R['gol10'], R['thr10'], R['thr1']
def S(k): return [l for l in out('z26').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"20000 次流水线异步 create:默认 {d['tput']:.0f} 次/秒;-Dzookeeper.globalOutstandingLimit=10(服务端同时在处理的请求上限)降到 {g10['tput']:.0f} 次/秒;-Dzookeeper.request_throttle_max_requests=10 降到 {t10['tput']:.0f} 次/秒,最大延迟 {t10['max_lat']} ms;设成 1 只有 {t1['tput']:.0f} 次/秒、最大延迟 {t1['max_lat']} ms。两个参数都是通过「让请求排队」来保护服务端。", t=tl(S(1)), b=bars([['默认', d['tput'], f"{d['tput']:.0f}/s"], ['globalOutstandingLimit=10', g10['tput'], f"{g10['tput']:.0f}/s"], ['request_throttle_max_requests=10', t10['tput'], f"{t10['tput']:.0f}/s"], ['request_throttle_max_requests=1', t1['tput'], f"{t1['tput']:.0f}/s"]], d['tput'] * 1.1, mark=[1, 2, 3], done=[0]), kv=KV([['限流越紧', '吞吐越低,排队越久']], ['限流越紧'])),
    step(f"mntr 里看得到限流的痕迹:request_throttle_max_requests=10 时 throttle 队列的平均等待 {t10['thr_wait']} ms、=1 时 {t1['thr_wait']} ms,而默认只有 {d['thr_wait']} ms。globalOutstandingLimit 的队列等待指标几乎没变(我推测它在这个队列之前限流,没有读源码确认)({g10['thr_wait']} ms)。zk_throttled_ops 在所有场景都是 0,它统计的是别的事情,不是这个队列(本文没有查它的含义)。", t=tl(S(2)), kv=KV([['request_throttler', '有队列等待指标'], ['globalOutstandingLimit', '在读之前限流,看不到队列等待']], ['request_throttler'])),
]
A = dict(
    n=26, series='zookeeper', tags='ZooKeeper,限流,RequestThrottler,真实验证,动画演示',
    desc=f'请求限流实测:20000 次流水线异步写默认 {d["tput"]:.0f} 次/秒;globalOutstandingLimit=10 降到 {g10["tput"]:.0f};request_throttle_max_requests=10 降到 {t10["tput"]:.0f}(throttle 队列平均等待 {t10["thr_wait"]} ms),=1 降到 {t1["tput"]:.0f}。',
    lead='ZooKeeper 有两层限制「同时在处理的请求数」的机制:globalOutstandingLimit 和 request_throttle_max_requests。它们的效果、副作用和能在 mntr 里看到什么,这篇都实测一遍。',
    facts=[(f'{d["tput"]:.0f} → {t1["tput"]:.0f} 次/秒', '默认 → request_throttle_max_requests=1 时的异步写吞吐'), (f'{t10["thr_wait"]} ms', 'request_throttle_max_requests=10 时 throttle 队列的平均等待'), ('两个机制', 'globalOutstandingLimit 在读数据前限流;RequestThrottler 是处理链里的一个排队线程')],
    body=[
        sec('限流参数与吞吐', '', term('', blk('z26', 1)), '<p>这些参数是保护服务端不被突发流量压垮的「刹车」:设得太紧,正常流量也会被排队。数值只是本机单机的测量,不是推荐值。</p>'),
        sec('指标里的痕迹', '', term('', blk('z26', 2))),
        sec('分步演示', '', demo('请求限流', [('t', 'term', '输出'), ('b', 'bars', '吞吐'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;参数通过 JVM 系统属性设置;20000 次异步 create(100 字节),每个配置只测一次', '没有验证:集群里的限流、连接限流 connection throttling(BlueThrottle)、大请求限制(large request)、客户端侧的反压、参数的官方默认值(只测了「不设置」的行为)'],
)
