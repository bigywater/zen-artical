import json
from lib import *
txt = out('108').splitlines(); R = json.load(open('out/108.json'))
S, S2, log, W = R['S'], R['S2'], R['log'], R['W']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
w, wo, w2, wo2 = S['with'], S['without'], S2['with'], S2['without']
t = [x[0] for x in log]           # 5 次状态转换的时间
FL = lambda cur, done=(): {'nodes': [['closed', '正常放行'], ['open', '直接拒绝'], ['half_open', '放一个探针'], ['closed', '恢复']], 'cur': cur, 'done': list(done)}
def wbars(k, i, cur=()): return {'items': [[f'{j*0.5:.1f}–{j*0.5+0.5:.1f} s', W[k][j].get('ok', 0) + W[k][j].get('fail', 0) + W[k][j].get('fast_fail', 0), ' / '.join(f'{name} {n}' for name, n in (('成功', W[k][j].get('ok', 0)), ('报错', W[k][j].get('fail', 0)), ('快速失败', W[k][j].get('fast_fail', 0))) if n)] for j in range(i + 1)], 'max': 30, 'cur': list(cur)}
steps = [
    step("正常时熔断器是 closed:所有请求直接放行到下游。0–0.5 s 内 25 个请求全部成功。", fl=FL([0]), b=wbars('with', 0, [0]), kv={'items': [['状态', 'closed'], ['0.0–0.5 s', '25 成功']], 'hl': ['状态']}),
    step(f"0.5 s 下游开始故障:每次调用要等 0.15 s 才报错。熔断器统计连续失败,达到阈值 5 次后,在 {t[0]:.3f} s 转成 open。", fl=FL([1], [0]), b=wbars('with', 1, [1]), kv={'items': [['状态', f'closed → open({t[0]:.3f} s)'], ['0.5–1.0 s', '12 报错 + 13 快速失败']], 'hl': ['状态']}),
    step(f"open 期间请求根本不去碰下游,立刻失败(中位延迟 {w['p50_out']:.1f} ms,而不是等 150 ms 超时)。0.5–1.5 s 内打到下游的调用大幅减少。", fl=FL([1], [0]), b=wbars('with', 2, [2]), kv={'items': [['1.0–1.5 s', '24 快速失败 + 1 报错'], ['故障期请求延迟(中位)', f"{w['p50_out']:.1f} ms(无熔断器 {wo['p50_out']:.0f} ms)"]], 'hl': ['故障期请求延迟(中位)']}),
    step(f"{t[1]:.3f} s:open 已满 0.5 s 的冷却时间,转成 half_open,只放行一个探针请求。但下游要到 1.5 s 才恢复——探针失败,{t[2]:.3f} s 重新回到 open。", fl=FL([2], [0, 1]), b=wbars('with', 3, [3]), kv={'items': [['状态', f'open → half_open({t[1]:.3f} s) → open({t[2]:.3f} s)'], ['1.5–2.0 s', '25 快速失败']], 'hl': ['状态']}),
    step(f"这就是熔断器的代价:下游 1.5 s 就恢复了,但熔断器要等到 {t[3]:.3f} s 才再次探测——期间 25 个请求本来能成功却被快速失败。无熔断器组在 1.5 s 就立刻恢复。", fl=FL([1], [0, 2]), b=wbars('without', 3, [3]), kv={'items': [['无熔断器 1.5–2.0 s', '25 成功'], ['有熔断器 1.5–2.0 s', '25 快速失败(下游已恢复)']], 'hl': ['有熔断器 1.5–2.0 s']}),
    step(f"{t[3]:.3f} s 第二次探针成功 → {t[4]:.3f} s 回到 closed,请求恢复正常。", fl=FL([3], [0, 1, 2]), b=wbars('with', 5, [5]), kv={'items': [['状态', f'half_open → closed({t[4]:.3f} s)'], ['2.5–3.0 s', '25 成功']], 'hl': ['状态']}),
    step(f"级联的场景:请求速率提高到 100/秒(超过 8 个线程的处理能力)。无熔断器时,请求在上游排队,故障期请求延迟中位 {wo2['p50_out']:.0f} ms、最大 {wo2['max_out']:.0f} ms;故障结束后队列还要几百毫秒才消化完(恢复后最大 {wo2['max_after']:.0f} ms)。", fl=FL([0]),
         b={'items': [['无熔断器 · 故障期中位', wo2['p50_out'], f"{wo2['p50_out']:.0f} ms"], ['无熔断器 · 故障期最大', wo2['max_out'], f"{wo2['max_out']:.0f} ms"], ['有熔断器 · 故障期中位', max(w2['p50_out'], 0.5), f"{w2['p50_out']:.1f} ms"], ['有熔断器 · 故障期最大', w2['max_out'], f"{w2['max_out']:.0f} ms"]], 'max': 650, 'cur': [0, 1]}, kv={'items': [['打到下游的调用', f"无 {wo2['calls']} 次 / 有 {w2['calls']} 次"], ['恢复后 1 秒内最大延迟', f"无 {wo2['max_after']:.0f} ms / 有 {w2['max_after']:.1f} ms"]], 'hl': ['恢复后 1 秒内最大延迟']}),
]
A = dict(
    n=108,
    tags='Python,可靠性,熔断器,并发,真实验证,动画演示',
    desc=f'本机自己实现熔断器并对一个 0.5–1.5 s 故障的下游做对照(8 个工作线程):50 请求/秒时熔断器把打到下游的调用从 {wo["calls"]} 次降到 {w["calls"]} 次、故障期失败延迟从约 {wo["p50_out"]:.0f} ms 降到 {w["p50_out"]:.1f} ms,但下游 1.5 s 就恢复而熔断器到 {t[3]:.2f} s 才恢复放行;100 请求/秒(超过线程池能力)时无熔断器的请求排队,故障期延迟中位 {wo2["p50_out"]:.0f} ms、最大 {wo2["max_out"]:.0f} ms,有熔断器中位 {w2["p50_out"]:.1f} ms。',
    lead='下游服务变慢或挂掉时,上游继续硬调,只会让自己的线程一个个被耗尽,最后连本来健康的功能也一起挂——这就是级联故障。熔断器的思路是:失败太多就暂时「断开」,直接拒绝请求,等一会儿再放一个探针看看好了没有。这篇自己实现一个,让它在真实线程池和真实计时下工作,不光看好处,也把它的代价量出来。',
    facts=[(f'{wo["calls"]} → {w["calls"]}', '50 请求/秒下,故障期间真正打到下游的调用次数(无熔断器 → 有熔断器)'), (f'{wo["p50_out"]:.0f} ms → {w["p50_out"]:.1f} ms', '故障期间一个失败请求的中位延迟:等下游超时 vs 直接快速失败'), (f'+{t[3]-1.5:.2f} s', '下游 1.5 s 已恢复,熔断器到 %.2f s 才恢复放行——熔断的代价' % t[3])],
    body=[
        sec('做的事:一个三状态的熔断器', '', src('熔断器(核心)', '''class Breaker:
    def call(self, f):
        with self.lock:
            if self.state == "open":
                if now - self.opened_at >= self.reset_timeout and not self.probing:
                    self._set("half_open"); self.probing = True   # 冷却到了: 放一个探针
                else: raise Open()                                  # 否则直接拒绝
            elif self.state == "half_open" and self.probing: raise Open()
        try: r = f()
        except Exception:                                           # 失败: half_open → open;closed 累计到阈值 → open
            ...
        # 成功: half_open → closed;closed 里失败计数清零'''),
            '<p>参数:连续失败 5 次就打开、冷却 0.5 s。下游模型:0.5–1.5 s 是故障期,每次调用要等 0.15 s 才抛出超时错误;其余时间 5 ms 内成功。请求由 8 个工作线程的线程池处理。</p>'),
        sec('验证一:状态转换', '', term('', block('== 一', '== 二')),
            f'<p>完整的循环都出现了:closed → open(故障开始约 0.2 s 后累计 5 次失败)→ half_open(冷却期满,放行探针)→ 因为下游还没恢复,探针失败又回到 open → 再冷却 → half_open → 探针成功 → closed。注意时间点:下游 1.5 s 就恢复了,但第一次探针发生在 {t[1]:.2f} s(还在故障期,失败),第二次要到 {t[3]:.2f} s——熔断器不会立刻发现恢复。</p>'),
        sec('验证二:有无熔断器的对照(50 请求/秒)', '', term('', block('== 二', '== 三')),
            f'<p>故障期间,无熔断器时每个请求都老老实实等 0.15 s 下游超时才失败(中位 {wo["p50_out"]:.0f} ms),{wo["calls"]} 次调用全部打到下游;有熔断器时 {w["fast_fail"]} 个请求被快速失败(中位仅 {w["p50_out"]:.1f} ms),下游只收到 {w["calls"]} 次。<b>但要看代价:</b>在这个速率下线程池(8 个)并没有被耗尽——50 请求/秒 × 0.15 s ≈ 7.5 个并发,刚好够——所以无熔断器组并没有出现级联,只是每个失败请求慢了一些。熔断器反而在下游已经恢复后的那 0.5 秒里,让本可以成功的 25 个请求快速失败(见下面的窗口表)。</p>'),
        sec('验证三:窗口内的结果', '每 0.5 秒', term('', block('== 三', '== 四')),
            '<p>「有熔断器」那一列在 1.5–2.0 s 全部是 <code>fast_fail</code>,而「无熔断器」已经在 1.5 s 恢复了全部成功。这是熔断器固有的取舍:用一段「本可以成功的失败」换取故障期间对下游和自己资源的保护。冷却时间(<code>reset_timeout</code>)越短,这个损失越小,探针失败的次数越多。</p>'),
        sec('验证四:请求速率超过线程池能力时——级联', '', term('', block('== 四', 'zzzz')),
            f'<p>把速率提高到 100 请求/秒(故障期每次调用占用线程 0.15 s,需要约 15 个并发,而线程池只有 8 个)。无熔断器:请求在上游排队,故障期请求的延迟中位 {wo2["p50_out"]:.0f} ms、最大 {wo2["max_out"]:.0f} ms;故障结束之后队列里积压的请求还要被逐个处理,恢复后的第一秒里最大延迟仍有 {wo2["max_after"]:.0f} ms。有熔断器:失败请求直接被快速拒绝,中位延迟 {w2["p50_out"]:.1f} ms,打到下游的调用只有 {w2["calls"]} 次(无熔断器 {wo2["calls"]} 次),恢复后最大延迟 {w2["max_after"]:.1f} ms——上游的资源没有被故障的下游拖住。<b>熔断器的价值在这里才真正体现:保护调用方自己。</b></p>'),
        sec('分步演示:熔断器的一生,和它的代价', '状态与时间点取自上面的真实日志',
            demo('熔断器', [('fl', 'flow', '状态'), ('b', 'bars', '每 0.5 秒的请求结果 / 延迟'), ('kv', 'kv', '观察')], steps, '当前状态 / 时间窗')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,自己实现的熔断器(threading + time),线程池 <code>concurrent.futures.ThreadPoolExecutor</code>(8 个线程);时间取自 <code>time.perf_counter</code>,线程调度有毫秒级抖动,数字每次运行会略有不同',
          '没有验证:按失败率(而非连续次数)判断的熔断器、探针并发数大于 1、与重试组合使用(见第 107 篇)、真实网络超时与连接池的行为、成熟库(如 pybreaker)的实现差异'],
)
