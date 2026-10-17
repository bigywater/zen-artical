import json
from lib import *
R = J('r89'); ev = R['events']; o = R['outage']; rj = R['rejoin']
def f(ch, i=None): return next(r for r in ev if r[0] == ch and (i is None or r[1] == i))
sw = f('+switch-master', 1)[2]; end = f('+failover-end')[2]
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps_names = [('+sdown', 's_down'), ('+odown', 'o_down'), ('+elected-leader', '当选'), ('+selected-slave', '选定从库'), ('+failover-state-send-slaveof-noone', '发 SLAVEOF NO ONE'), ('+promoted-slave', '确认升主'), ('+switch-master', '切换主库(sentinel1)'), ('+slave-reconf-done', '其它从库改指完成'), ('+failover-end', '故障转移结束')]
T = {}
for ch, nm in steps_names:
    r = f(ch, 1) if ch == '+switch-master' else f(ch); T[nm] = r[2]
steps = [
    step(f"kill -9 主库。sentinel 在 {T['s_down']:.0f} ms 标 s_down,{T['o_down']:.0f} ms 达成 o_down 并当选领导者({T['当选']:.0f} ms,投票见第 88 篇)。", n=fl([['sentinel', 's_down → o_down → 当选']], cur=[0]), b=bars([[k, T[k], f'{T[k]:.0f} ms'] for k in ('s_down', 'o_down', '当选')], 6000, done=[0, 1, 2]), kv=KV([['当选', f"{T['当选']:.0f} ms"]], ['当选'])),
    step(f"选新主库:+failover-state-select-slave → +selected-slave 127.0.0.1:7741({T['选定从库']:.0f} ms,两个从库优先级相同,选了 7741;选择依据是优先级、复制偏移量,这里我没有对照)。", n=fl([['从库 7741', '被选中'], ['从库 7742', '未选中']], done=[0]), kv=KV([['选定', '7741']], ['选定'])),
    step(f"领导者向 7741 发 SLAVEOF NO ONE({T['发 SLAVEOF NO ONE']:.0f} ms),等它升主:sentinel 看到 7741 汇报的角色变成 master({T['确认升主']:.0f} ms,+promoted-slave),约 {T['确认升主']-T['发 SLAVEOF NO ONE']:.0f} ms 内完成——sentinel 是靠周期性 INFO 看到角色变化的。", n=fl([['7741', 'slave → master']], done=[0]), b=bars([['发 SLAVEOF NO ONE', T['发 SLAVEOF NO ONE'], f"{T['发 SLAVEOF NO ONE']:.0f} ms"], ['+promoted-slave', T['确认升主'], f"{T['确认升主']:.0f} ms"]], 6000, done=[1]), kv=KV([['升主确认', f"{T['确认升主']:.0f} ms"]], ['升主确认'])),
    step(f"+switch-master:领导者通过 hello 频道通知其它 sentinel(+config-update-from),sentinel1、sentinel2 在 {T['切换主库(sentinel1)']:.0f} ms 就切换了主库地址。此后向 sentinel 询问主库地址得到 7741。", n=fl([['sentinel1、2', '+switch-master 7740 → 7741']], done=[0]), b=bars([['+switch-master', T['切换主库(sentinel1)'], f"{T['切换主库(sentinel1)']:.0f} ms"]], 6000, done=[0]), kv=KV([['新地址', '127.0.0.1:7741']], ['新地址'])),
    step(f"其它从库(7742)被指向新主库(+slave-reconf-sent → -inprog → -done,{T['其它从库改指完成']:.0f} ms),领导者 {T['故障转移结束']:.0f} ms +failover-end,整个流程约 {T['故障转移结束']/1000:.1f} s。parallel-syncs 1 表示一次只让 1 个从库同步新主库。", n=fl([['7742', '改指 7741 完成']], done=[0]), b=bars([['+failover-end', T['故障转移结束'], f"{T['故障转移结束']:.0f} ms"]], 6000, done=[0]), kv=KV([['全流程', f"{T['故障转移结束']/1000:.1f} s"]], ['全流程'])),
    step(f"客户端视角:一个写线程每 20 ms 通过 sentinel 查主库地址再 SET:kill 后 {o['first_fail']*1000:.0f} ms 第一次失败,共 {o['nfail']} 次失败,{o['recovered']*1000:.0f} ms 在新主库上第一次成功——不可用约 {o['recovered']:.1f} s,大部分是 down-after-milliseconds(3000 ms)。", b=bars([['首次失败', o['first_fail'] * 1000, f"{o['first_fail']*1000:.0f} ms"], ['首次在新主库成功', o['recovered'] * 1000, f"{o['recovered']*1000:.0f} ms"]], 6000, mark=[0], done=[1]), kv=KV([['不可用', f"约 {o['recovered']:.1f} s"], ['失败写入', str(o['nfail'])]], ['不可用'])),
    step(f"旧主库 7740 重启后:sentinel 把它改成新主库 7741 的从库,{rj:.1f} s 后 role = slave、link up。(sentinel 会持续把「回来了的旧主库」重配成从库。)", n=fl([['7740(旧主)', '重启 → 从库 → link up']], done=[0]), b=bars([['旧主库回归为从库', rj * 1000, f'{rj:.1f} s']], 12000, done=[0]), kv=KV([['旧主库回归', f'{rj:.1f} s']], ['旧主库回归'])),
]
A = dict(
    n=89, series='redis', tags='Redis,Sentinel,故障转移,真实验证,动画演示',
    desc=f'订阅 Sentinel 的事件流,完整还原一次自动故障转移:kill -9 主库后 {T["s_down"]:.0f} ms s_down、{T["o_down"]:.0f} ms o_down、{T["当选"]:.0f} ms 当选领导者、{T["确认升主"]:.0f} ms 从库升主、{T["切换主库(sentinel1)"]:.0f} ms 切换主库、{T["故障转移结束"]:.0f} ms 结束;写客户端不可用约 {o["recovered"]:.1f} s;旧主库重启 {rj:.1f} s 后变成从库。',
    lead='Sentinel 的自动故障转移由一串事件组成,每个都有名字(+sdown、+odown、+elected-leader、+promoted-slave、+switch-master……)。这篇订阅 sentinel 的事件流,把一次真实 kill -9 之后的每一个事件和毫秒数都列出来,再从写客户端的角度量不可用时长。',
    facts=[(f'{T["故障转移结束"]/1000:.1f} s', 'kill -9 主库到 +failover-end 的总时间(down-after-milliseconds = 3000)'), (f'约 {o["recovered"]:.1f} s', '写客户端(经 sentinel 找主库)不可用的时长'), (f'{rj:.1f} s', '旧主库重启后被 sentinel 改成从库并 link up 所用的时间')],
    body=[
        sec('完整的事件流', '时间相对 kill -9;s0/s1/s2 是三个 sentinel', term('', '\n'.join(f'+{r[2]:6.0f} ms  s{r[1]}  {r[0]:<36} {r[3][:64]}' for r in ev)),
            '<p>阶段:检测(<code>+sdown</code>/<code>+odown</code>)→ 选领导者(<code>+try-failover</code>/<code>+vote-for-leader</code>/<code>+elected-leader</code>)→ 选从库(<code>+selected-slave</code>)→ 发 <code>SLAVEOF NO ONE</code> 并等升主(<code>+promoted-slave</code>)→ 广播新配置(<code>+config-update-from</code>/<code>+switch-master</code>)→ 其它从库改指新主库(<code>+slave-reconf-*</code>)→ 结束(<code>+failover-end</code>)。</p>'),
        sec('客户端看到的', '', term('', blk('r89', 2)), '<p>一个每 20 ms 经 sentinel 查主库地址再写的客户端:主库被杀 22 ms 后第一次失败,直到新主库可写才恢复。整个不可用窗口里最长的一段是检测(<code>down-after-milliseconds</code>),真正的「选举 + 提升」只占约一秒。</p>'),
        sec('复制拓扑', '', term('', blk('r89', 3)), '<p>最终 7741 是主库,7742 是它的从库并且 link up。</p>'),
        sec('旧主库回来', '', term('', blk('r89', 4)), f'<p>旧主库重启后,sentinel 把它配置成新主库的从库(重启后一直处于「主库」身份,直到 sentinel 发现并降级);这里用了 {rj:.1f} s。这期间旧主库如果被写入,数据会在降级时丢弃(第 91、93 篇)。</p>'),
        sec('分步演示:自动故障转移', '', demo('Sentinel 自动故障转移', [('n', 'flow', '对象'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。1 主 2 从 + 3 个 sentinel,quorum 2,down-after 3000,parallel-syncs 1;事件来自订阅 * ;写客户端每 20 ms 经 sentinel 找主库', '没有验证:从库优先级与复制偏移量对选择的影响、parallel-syncs 更大时的拓扑收敛、旧主库降级由哪一步触发以及耗时 10 秒的来源、跨机器网络'],
)
