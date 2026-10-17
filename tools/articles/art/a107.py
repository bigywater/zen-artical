import json
from lib import *
txt = out('107').splitlines(); R = json.load(open('out/107.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
fx, ex, ej = R['fixed'], R['exp'], R['exp_jitter']
labels = [f'{i*50}–{i*50+50} ms' for i in range(16)]
def hist(r, cur=()): return {'items': [[labels[i], v, str(v)] for i, v in enumerate(r['bins'])], 'max': 210, 'cur': list(cur), 'mark': list(range(6))}
FL = lambda cur, done=(): {'nodes': [['固定间隔', '每次 50 ms'], ['指数退避', '20·2^n, 上限 320'], ['指数 + 抖动', '在 [0, 上限] 随机'], ['对比', '']], 'cur': cur, 'done': list(done)}
steps = [
    step("场景:100 个客户端在 t=0 同时开始请求。服务先宕机 300 ms(全部失败),恢复后每 20 ms 只能处理 15 个请求,多出来的被拒绝。下面每条横线是 50 ms 内发给服务的请求数(前 6 格是宕机期)。", fl=FL([]), b={'items': [[labels[i], 0.5, '—'] for i in range(16)], 'max': 210, 'cur': [], 'mark': list(range(6))}, kv={'items': [['客户端', '100 个线程,同时开始'], ['服务', '0–300 ms 宕机;之后每 20 ms 最多处理 15 个']], 'hl': []}),
    step(f"固定间隔 50 ms:所有客户端一起失败、一起等 50 ms、一起重试——每一格都是整整 100 个请求,形成整齐的「请求墙」。服务恢复那一格(300–350 ms)仍收到 98 个,大量被拒绝({fx['reject']} 次限流拒绝);总共 {fx['attempts']} 个请求,{fx['finish']*1000:.0f} ms 才全部完成。", fl=FL([0]), b=hist(fx, [6]), kv={'items': [['总请求', str(fx['attempts'])], ['宕机期间', str(fx['down'])], ['被限流拒绝', str(fx['reject'])], ['全部完成', f"{fx['finish']*1000:.0f} ms"]], 'hl': ['被限流拒绝']}),
    step(f"指数退避、无抖动:间隔 20、40、80、160、320 ms——重试次数少了,但因为所有客户端的间隔完全一样,请求仍然「同一时刻齐发」:格子里不是 0 就是整 100。恢复后的那一波 100 个同时到达,{ex['reject']} 次被限流拒绝;被拒的又一起等 320 ms 再来,最后一批 {ex['finish']*1000:.0f} ms 才完成——最慢。", fl=FL([1], [0]), b=hist(ex, [6, 12, 13]), kv={'items': [['总请求', str(ex['attempts'])], ['宕机期间', str(ex['down'])], ['被限流拒绝', str(ex['reject'])], ['全部完成', f"{ex['finish']*1000:.0f} ms"]], 'hl': ['全部完成']}),
    step(f"指数退避 + 全抖动:每次等待是 [0, 指数上限] 内的随机值,各客户端的重试时刻被打散,请求平滑地分布在时间轴上。恢复后没有一次被限流拒绝({ej['reject']} 次),{ej['finish']*1000:.0f} ms 全部完成——既没有请求墙,也是最快之一。", fl=FL([2], [0, 1]), b=hist(ej, list(range(6, 12))), kv={'items': [['总请求', str(ej['attempts'])], ['宕机期间', str(ej['down'])], ['被限流拒绝', str(ej['reject'])], ['全部完成', f"{ej['finish']*1000:.0f} ms"]], 'hl': ['被限流拒绝']}),
    step("汇总对比:完成时间与限流拒绝次数。抖动同时把这两项都压到了最低。", fl=FL([3], [0, 1, 2]), b={'items': [['固定 · 拒绝次数', fx['reject'], str(fx['reject'])], ['指数 · 拒绝次数', ex['reject'], str(ex['reject'])], ['指数+抖动 · 拒绝次数', ej['reject'], str(ej['reject'])]], 'max': 200, 'cur': [2]}),
]
A = dict(
    n=107,
    tags='Python,可靠性,重试,并发,真实验证,动画演示',
    desc=f'本机用 100 个真实线程冲击一个先宕机 300 ms、之后每 20 ms 只能处理 15 个请求的服务:固定 50 ms 间隔产生每格整整 100 个请求的「请求墙」({fx["reject"]} 次限流拒绝、{fx["finish"]*1000:.0f} ms 完成);指数退避无抖动仍然齐发({ex["reject"]} 次拒绝、{ex["finish"]*1000:.0f} ms,最慢);加全抖动后 0 次限流拒绝、{ej["finish"]*1000:.0f} ms 完成。并验证只应对暂时性错误重试。',
    lead='服务出问题时,客户端会重试;重试策略选不好,反而会把恢复中的服务再次压垮。这篇不靠推公式,而是启动 100 个真实线程,让它们分别用固定间隔、指数退避、指数退避加抖动去重试同一个「先宕机、后限流」的服务,把每 50 ms 打出去多少请求真的数出来。',
    facts=[(f'{fx["reject"]} → {ej["reject"]}', '固定间隔与「指数退避+抖动」下,服务恢复后被限流拒绝的请求数'), (f'{ex["finish"]*1000:.0f} ms', '指数退避但没有抖动时的完成时间——比固定间隔还慢(固定 %.0f ms、加抖动 %.0f ms)' % (fx['finish'] * 1000, ej['finish'] * 1000)), ('每格恰好 100', '固定间隔重试时,每 50 ms 内的请求数:所有客户端步调完全一致')],
    body=[
        sec('做的事:模拟一次「服务先挂、后限流」', '',
            src('三种重试间隔', '''def delays(strategy, rng, n):
    for k in range(n):
        if strategy == "fixed":      yield 0.05
        elif strategy == "exp":      yield min(0.02 * 2 ** k, 0.32)
        elif strategy == "exp_jitter": yield rng.uniform(0, min(0.02 * 2 ** k, 0.32))   # 全抖动'''),
            term('', block('== 一', '== 二')),
            '<p>固定间隔永远是 50 ms;指数退避每次翻倍直到 320 ms 封顶;加了全抖动(full jitter)之后,每次等待是 0 到指数上限之间的随机值,同一个客户端的每次间隔不同,不同客户端之间更不同。</p>'
            '<p>服务端的模型:0 到 300 ms 完全不可用,之后每个 20 ms 的窗口只能处理 15 个请求,多的被拒绝。100 个线程同时开始。每种策略跑 3 次,取总请求数居中的那一次。</p>'),
        sec('验证一:三种策略的结果', '', term('', block('== 二', '== 三')),
            f'<p>固定间隔:重试最多,{fx["attempts"]} 个请求里 {fx["reject"]} 个被限流拒绝。指数退避(无抖动):请求总数少了,但被拒绝的更多({ex["reject"]}),而且完成得最晚({ex["finish"]*1000:.0f} ms)。指数退避加抖动:{ej["reject"]} 次被拒绝,{ej["finish"]*1000:.0f} ms 完成。<b>「指数退避」本身并不等于「更好」——没有抖动时,所有客户端的重试时刻依然完全同步。</b>(表里「服务恢复后任意 10 ms 内最多」一列的数字包含了 t=0 时 100 个客户端同时开始的那一次齐发,所以不是判断重试风暴的好指标;请看下一节的分布。)</p>'),
        sec('验证二:时间分布', '每 50 ms 一格,前 6 格(0–300 ms)是宕机期', term('', block('== 三', '== 四')),
            '<p>固定间隔:前 6 格每格整整 100 个请求——所有客户端步调一致。指数退避无抖动:格子里不是 0 就是 100 的整数倍(<code>[200, 100, 0, 100, 0, 0, 100, …]</code>),请求集中在几个瞬间同时到达,像一次次脉冲。抖动之后是平滑衰减的曲线:<code>[290, 77, 74, 45, 31, 28, …]</code>(第一格的 290 包含了 t=0 时 100 个客户端的第一次请求)。</p>'),
        sec('验证三:只该重试暂时性错误', '', term('', block('== 四', 'zzzz')),
            '<p>重试函数用 <code>retry_on=Transient</code> 限定要重试的异常。暂时性错误重试到上限(共 4 次调用);参数错误(<code>ValueError</code>)只调用 1 次就抛出——重试不会让错误的参数变对。另外,对有副作用的操作(比如「扣款」)重试还要保证幂等,这一点本篇没有验证。</p>'),
        sec('分步演示:三种重试策略下,每 50 ms 打向服务的请求数', '数字取自上面的真实运行',
            demo('固定 / 指数 / 指数+抖动', [('fl', 'flow', '策略'), ('b', 'bars', '每 50 ms 的请求数'), ('kv', 'kv', '汇总')], steps, '宕机期(前 6 格)/ 关键格')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>threading</code>、<code>random</code>;时间用 <code>time.perf_counter</code>,线程调度存在毫秒级抖动,因此每种策略跑 3 次取居中结果,具体数字每次会略有不同',
          '没有验证:decorrelated jitter、equal jitter 等其他抖动变体、服务端有排队而非直接拒绝的情形、跨机器网络延迟、重试预算(限制总重试比例)'],
)
