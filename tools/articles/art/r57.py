import json
from lib import *
R = J('r57'); fz = R['freeze']; ok = R['ok']; wa = R['waitaof']; af = R['allfrozen']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
a11 = wa['1_1_3000']
steps = [
    step(f"两个从库正常时:SET 之后 WAIT 2 100,200 次全部返回 2,耗时中位 {ok[0]:.2f} ms、最大 {ok[1]:.2f} ms——复制本身很快,WAIT 通常几乎不增加延迟。", n=cells(['主 SET', 'B ack', 'C ack', 'WAIT → 2']), b=bars([['WAIT 2 中位', ok[0], f'{ok[0]:.2f} ms'], ['WAIT 2 最大', ok[1], f'{ok[1]:.2f} ms']], 1, done=[0, 1]), kv=KV([['返回值', '2(200/200)']], ['返回值'])),
    step(f"把从库 B 用 SIGSTOP 冻结:SET 之后 WAIT 2 200,等满超时(耗时 {fz['ms2']:.0f} ms)才返回 {fz['r2']},只确认了 C。", n=cells(['主 SET', 'B(冻结)', 'C ack', f'WAIT 2 200 → {fz["r2"]}({fz["ms2"]:.0f} ms)'], mark=[1], cur=[3]), b=bars([['WAIT 2 200', fz['ms2'], f'{fz["ms2"]:.0f} ms']], 250, mark=[0]), kv=KV([['WAIT 2 200', f'返回 {fz["r2"]},{fz["ms2"]:.0f} ms']], ['WAIT 2 200'])),
    step(f"改成 WAIT 1 200:C 已经确认,{fz['ms1']:.2f} ms 就返回 {fz['r1']}。WAIT 的第一个参数是「至少要几个」,够了立刻返回。", n=cells(['主 SET', 'B(冻结)', 'C ack', f'WAIT 1 200 → {fz["r1"]}'], done=[2], cur=[3]), b=bars([['WAIT 1 200', max(fz['ms1'], 0.5), f'{fz["ms1"]:.2f} ms']], 250, done=[0]), kv=KV([['WAIT 1 200', f'返回 {fz["r1"]},{fz["ms1"]:.2f} ms']], ['WAIT 1 200'])),
    step("WAIT 只是「等」,不是「撤销」:WAIT 返回 1(没到 2)之后,主库上的写入已经生效,C 上能读到,B 解冻后也追上了——WAIT 没有回滚能力。", n=cells(['主 GET k = during-freeze2', 'C GET k = during-freeze2', 'B 解冻后 GET k = during-freeze2'], done=[0, 1, 2]), kv=KV([['结论', 'WAIT 不回滚,只告诉你有几个从库收到了']], ['结论'])),
    step(f"WAIT 只等「从库内存里收到」,不等落盘。WAITAOF 才等 AOF fsync:主从都开 appendonly、appendfsync everysec 时,WAITAOF 1 1 的耗时最小 {a11[1]:.0f} ms、中位 {a11[2]:.0f} ms——正好是 everysec 的一个 fsync 周期,而 WAIT 只要 {wa['wait'][1]:.2f} ms。", n=cells(['WAIT 2:内存收到', 'WAITAOF 1 1:fsync 完成'], mark=[1]), b=bars([['WAIT 2 中位', wa['wait'][1], f"{wa['wait'][1]:.2f} ms"], ['WAITAOF 1 1 中位', a11[2], f'{a11[2]:.0f} ms']], 1100, mark=[1]), kv=KV([['WAITAOF 1 1', f'返回 {a11[0]},约 1 秒'], ['WAIT 2', '不到 1 ms']], ['WAITAOF 1 1'])),
    step(f"两个从库都冻结时 WAIT 1 300:返回 {af[0]},耗时 {af[1]:.0f} ms——没人应答,就等到超时。给 WAIT 的超时,就是你愿意为「从库确认」付出的最坏延迟。", n=cells(['主 SET', 'B(冻结)', 'C(冻结)', f'WAIT 1 300 → {af[0]}({af[1]:.0f} ms)'], mark=[1, 2], cur=[3]), kv=KV([['WAIT 1 300', f'返回 {af[0]},{af[1]:.0f} ms']], ['WAIT 1 300'])),
]
A = dict(
    n=57, series='redis', tags='Redis,复制,WAIT,真实验证,动画演示',
    desc=f'在本机一主两从上验证 WAIT:正常时 WAIT 2 中位 {ok[0]:.2f} ms;冻结一个从库后 WAIT 2 200 等满超时({fz["ms2"]:.0f} ms)只返回 {fz["r2"]},WAIT 1 200 仍是 {fz["ms1"]:.2f} ms 就返回;WAIT 返回后写入并不回滚;WAIT 只等复制不等落盘,everysec 下 WAITAOF 1 1 耗时约 {a11[2]:.0f} ms。',
    lead='Redis 的复制是异步的:主库写完就回复客户端,从库晚一点才收到。WAIT 命令让客户端可以「等一等」:这条写入至少被 N 个从库收到了再往下走。这篇验证它能保证什么、不能保证什么:超时怎么算、返回值代表什么、写入会不会回滚,以及它和 WAITAOF 的区别。',
    facts=[(f'{ok[0]:.2f} ms', '两个从库都健康时,WAIT 2 的耗时中位数'), (f'{fz["r2"]}', f'冻结一个从库后,WAIT 2 200 等满 {fz["ms2"]:.0f} ms 的返回值'), (f'{a11[2]:.0f} ms', 'everysec 下 WAITAOF 1 1 的耗时中位数(WAIT 不到 1 ms)')],
    body=[
        sec('健康时:几乎零代价', '', term('', blk('r57', 1)), f'<p>SET 之后立刻 <code>WAIT 2 100</code>,200 次全部返回 2,耗时中位 {ok[0]:.2f} ms、最大 {ok[1]:.2f} ms。复制通道本身很快,WAIT 通常不会明显增加延迟。</p>'),
        sec('从库慢/挂了:超时', '用 SIGSTOP 冻结从库进程', term('', blk('r57', 2)), f'<p>冻结从库 B 之后,<code>WAIT 2 200</code> 只能等满 200 ms 超时,返回 {fz["r2"]}(耗时 {fz["ms2"]:.0f} ms);<code>WAIT 1 200</code> 则在 {fz["ms1"]:.2f} ms 就返回 {fz["r1"]}。第一个参数是「至少要几个」,够数立即返回,不够就等到超时,<b>返回的是超时那一刻实际确认的从库数</b>。</p>'),
        sec('WAIT 不回滚', '', term('', blk('r57', 3)), '<p>WAIT 返回 1(没有达到 2)之后,主库上的这次写入已经生效,C 能读到,冻结的 B 解冻后也追上了。所以 WAIT 只是「问一问有几个从库收到了」,不是分布式事务:凭返回值没达标就认为「写失败」是错的,该怎么处理要由应用决定。</p>'),
        sec('WAIT 与 WAITAOF', '主从都开 appendonly yes,appendfsync everysec', term('', blk('r57', 4)), f'<p>WAIT 只保证从库把数据收进了内存。<code>WAITAOF numlocal numreplicas timeout</code> 等的是 AOF 的 fsync。在 everysec 下,<code>WAITAOF 1 0 / 1 1 / 1 2</code> 的耗时都是约 1 秒(最小 {a11[1]:.0f} ms、中位 {a11[2]:.0f} ms),对应一次 everysec 的 fsync 周期,返回值 <code>[本地已 fsync 数, 从库已 fsync 数]</code>。我第一次跑用的超时是 1000 ms,恰好和这个周期一样长,所以拿到了不完整的结果——超时要比 fsync 周期留出余量。</p>'),
        sec('全部从库冻结', '', term('', blk('r57', 5)), f'<p>两个从库都冻结时,<code>WAIT 1 300</code> 等到超时({af[1]:.0f} ms)返回 {af[0]}。给 WAIT 设的超时,就是你为「从库确认」愿意付出的最坏延迟。(超时参数为 0 表示无限等待——这一点没有在这里验证,不建议用。)</p>'),
        sec('分步演示:WAIT 返回什么、等多久', '', demo('WAIT', [('n', 'cells', '状态'), ('b', 'bars', '耗时'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。一主两从,从库用 SIGSTOP/SIGCONT 冻结与恢复;主从的 appendonly 为 yes、appendfsync everysec', '没有验证:WAIT 超时为 0 的行为、网络分区(而非进程冻结)下的表现、集群模式下的 WAIT、appendfsync always 时 WAITAOF 的耗时'],
)
