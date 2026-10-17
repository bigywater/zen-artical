import json
from lib import *
R = J('r87'); a, b, b2, c = R['a'], R['b'], R['b2'], R['c']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def t(d, key): return next((v * 1000 for k, v in d.items() if key in k), None)
sd = [t(a[str(i)], 's_down') for i in range(3)]; od = [t(a[str(i)], 'o_down') for i in range(3)]
steps = [
    step(f"quorum 2,3 个 sentinel,kill -9 主库。三个 sentinel 各自在 {min(sd):.0f}–{max(sd):.0f} ms 标 s_down(主观下线)。", n=fl([[f'sentinel{i}', f's_down @ {sd[i]:.0f} ms'] for i in range(3)], mark=[0, 1, 2]), b=bars([[f'sentinel{i} s_down', sd[i], f'{sd[i]:.0f} ms'] for i in range(3)], 4500, mark=[0, 1, 2]), kv=KV([['s_down', f'{min(sd):.0f}–{max(sd):.0f} ms']], ['s_down'])),
    step(f"sentinel 之间用 SENTINEL is-master-down-by-addr 互相询问「你也觉得它挂了吗」,达到 quorum 个同意就标 o_down(客观下线):sentinel0 在 {od[0]:.0f} ms、sentinel1 在 {od[1]:.0f} ms(并随即进入 failover_in_progress)、sentinel2 在 {od[2]:.0f} ms——比各自的 s_down 晚约 {od[0]-sd[0]:.0f}–{od[2]-sd[2]:.0f} ms。", n=fl([[f'sentinel{i}', f'o_down @ {od[i]:.0f} ms'] for i in range(3)], done=[0, 1, 2]), b=bars([[f'sentinel{i} o_down', od[i], f'{od[i]:.0f} ms'] for i in range(3)], 4500, done=[0, 1, 2]), kv=KV([['o_down', f'{min(od):.0f}–{max(od):.0f} ms']], ['o_down'])),
    step("quorum 3,但其中一个 sentinel 被冻结:剩下两个 sentinel 各自 s_down,却凑不够 3 个同意——12 秒里始终没有 o_down,主库地址没变(未切换)。", n=fl([['sentinel0', 's_down'], ['sentinel1', 's_down'], ['sentinel2', '冻结']], mark=[0, 1, 2]), kv=KV([['quorum 3,可用 2', '12 s 无 o_down']], ['quorum 3,可用 2'])),
    step("解冻第三个 sentinel 后 15 秒内仍没有完成故障转移:它自己在这段时间里没有及时标出 s_down(我没有查原因)——但可以确定的是:quorum 设成「所有 sentinel 数」会让任何一个 sentinel 的故障都可能阻止自动故障转移。", n=fl([['sentinel2', '解冻后仍未标出 s_down']], mark=[0]), kv=KV([['解冻后 15 s', '主库地址仍是原来的']], ['解冻后 15 s'])),
    step(f"quorum 1:任何一个 sentinel 觉得挂了就够:三个 sentinel 在 {t(c['0'],'o_down'):.0f} / {t(c['1'],'o_down'):.0f} / {t(c['2'],'o_down'):.0f} ms 就已经带着 o_down(s_down 与 o_down 几乎同时)。代价是单个 sentinel 的误判就能触发切换。", n=fl([['quorum 1', 's_down 即 o_down']], mark=[0]), kv=KV([['o_down', f"{t(c['0'],'o_down'):.0f} / {t(c['1'],'o_down'):.0f} / {t(c['2'],'o_down'):.0f} ms"]], ['o_down'])),
]
A = dict(
    n=87, series='redis', tags='Redis,Sentinel,客观下线,quorum,真实验证,动画演示',
    desc=f'实测 Sentinel 客观下线:quorum 2、3 个 sentinel,kill -9 主库后各 sentinel 在 {min(sd):.0f}–{max(sd):.0f} ms 标 s_down、{min(od):.0f}–{max(od):.0f} ms 达成 o_down 并开始故障转移;quorum 3 而只剩 2 个 sentinel 可用时 12 秒都没有 o_down、不切换;quorum 1 时 s_down 即 o_down。',
    lead='一个 sentinel 觉得主库挂了(sdown)还不够,要 quorum 个 sentinel 同意才是客观下线(odown),才会触发故障转移。这篇改变 quorum 与可用 sentinel 的数量,看每种组合下每个 sentinel 眼中主库的状态怎么变。',
    facts=[(f'{min(od)-min(sd):.0f}–{max(od)-max(sd):.0f} ms', 'quorum 2 时,从 s_down 到 o_down 的间隔(sentinel 互相询问所需)'), ('quorum > 可用数', '不会 o_down,主库不切换'), ('quorum 1', 's_down 与 o_down 几乎同时')],
    body=[
        sec('quorum 2:kill -9 主库', '', term('', blk('r87', 1)), '<p>每个 sentinel 先各自 <code>s_down</code>;再通过 <code>SENTINEL is-master-down-by-addr</code>(sentinel 之间的询问命令,这一点来自文档)互相确认,凑够 quorum 就 <code>o_down</code>,然后由第一个准备好的 sentinel 进入 <code>failover_in_progress</code>。sentinel2 的记录里在 1 秒时有一次短暂回到 <code>master</code>,是重连尝试的瞬时状态。</p>'),
        sec('quorum 3 但只有 2 个 sentinel 可用', '', term('', blk('r87', 2)), '<p>剩下的两个 sentinel 各自 <code>s_down</code> 但凑不够 3 票:<b>没有 o_down,也就没有故障转移</b>。解冻第三个 sentinel 之后 15 秒里我仍没有等到切换——被冻结过的 sentinel 没有及时标出 s_down,原因我没有追查。实践上:quorum 不要设成 sentinel 总数,要允许少数 sentinel 不可用。</p>'),
        sec('quorum 1', '', term('', blk('r87', 3)), '<p>quorum 为 1 时,任何一个 sentinel 的 s_down 立刻就是 o_down。反应最快,但单个 sentinel 与主库之间的网络问题就足以触发切换。</p><p>另外要注意:<b>quorum 只决定「客观下线」,真正执行故障转移还需要多数 sentinel 授权</b>(第 88 篇)。</p>'),
        sec('分步演示:从主观到客观', '', demo('Sentinel 客观下线', [('n', 'flow', '各 sentinel 状态'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。1 主 2 从 + 3 个 sentinel;kill -9 主库;冻结用 SIGSTOP', '没有验证:sentinel 之间询问命令的报文、跨网络时的 o_down 延迟、解冻后 sentinel 迟迟不标 s_down 的原因、「授权需要多数 sentinel」这一条(第 88 篇观察)'],
)
