import json
from lib import *
R = J('r94'); C_ = R['cases']; a, b, c, d = C_
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("min-replicas-to-write N:主库只有在至少有 N 个「好」从库(延迟不超过 min-replicas-max-lag 秒)时才接受写入。配置 to-write=1、max-lag=3:一主两从,客户端每 10 ms 写一次。", n=fl([['主库', 'min-replicas-to-write 1,max-lag 3'], ['从库 ×2', '正常']], done=[1]), kv=KV([['正常时', 'good replicas = 2,写入 OK']], ['正常时'])),
    step(f"把两个从库都冻结(SIGSTOP):主库仍接受写入 {a['first_reject']*1000:.0f} ms(≈ max-lag 3 s),期间 {a['ok_before']} 条写入被接受;之后 INFO 里 min_slaves_good_slaves 变 0,写入收到 NOREPLICAS Not enough good replicas to write.", n=fl([['主库', '3.4 s 后拒绝写入'], ['从库 ×2', '冻结']], mark=[0]), b=bars([['首条被拒', a['first_reject'] * 1000, f"{a['first_reject']*1000:.0f} ms"], ['max-lag', 3000, '3000 ms']], 7000, mark=[0]), kv=KV([['错误', 'NOREPLICAS']], ['错误'])),
    step(f"解冻从库后 {a['back']*1000:.0f} ms 写入恢复。只冻结 1 个从库(仍有 1 个好从库)时,始终没有拒绝({b['ok_before']} 条全部接受)。", n=fl([['主库', '恢复写入'], ['仍有 1 个好从库', '不拒绝']], done=[0, 1]), b=bars([['两个从库冻结:恢复', a['back'] * 1000, f"{a['back']*1000:.0f} ms"], ['只冻结一个:是否拒绝', 5, '未拒绝']], 600, done=[0]), kv=KV([['恢复', f"{a['back']*1000:.0f} ms"]], ['恢复'])),
    step(f"to-write 改成 2、只冻结 1 个从库:好从库只剩 1 个 < 2,{c['first_reject']*1000:.0f} ms 后拒绝写入。to-write 设得越大,越容易因为单个从库的故障让主库停写——这是用可用性换数据安全。", n=fl([['主库', 'to-write 2:1 个从库冻结即停写']], mark=[0]), b=bars([['to-write 2,冻结 1 个:被拒', c['first_reject'] * 1000, f"{c['first_reject']*1000:.0f} ms"]], 7000, mark=[0]), kv=KV([['to-write 2', '单个从库故障即停写']], ['to-write 2'])),
    step(f"max-lag 改成 6:被拒的时间跟着变成 {d['first_reject']*1000:.0f} ms。所以 max-lag 就是「主库最多在联系不上从库多久之后还继续写」——也是可能丢数据的窗口大小。", n=fl([['max-lag 3', f"{a['first_reject']*1000:.0f} ms 拒绝"], ['max-lag 6', f"{d['first_reject']*1000:.0f} ms 拒绝"]], mark=[0, 1]), b=bars([['max-lag 3', a['first_reject'] * 1000, f"{a['first_reject']*1000:.0f} ms"], ['max-lag 6', d['first_reject'] * 1000, f"{d['first_reject']*1000:.0f} ms"]], 7000, mark=[0, 1]), kv=KV([['被拒时间', f"{a['first_reject']*1000:.0f} → {d['first_reject']*1000:.0f} ms"]], ['被拒时间'])),
]
A = dict(
    n=94, series='redis', tags='Redis,复制,min-replicas,真实验证,动画演示',
    desc=f'实测 min-replicas-to-write:一主两从、max-lag 3 时冻结全部从库,主库在 {a["first_reject"]*1000:.0f} ms 后开始拒绝写入(NOREPLICAS Not enough good replicas to write.),此前接受 {a["ok_before"]} 条;只冻结 1 个从库不拒绝;to-write 2 时冻结 1 个从库即停写({c["first_reject"]*1000:.0f} ms);解冻后约 {a["back"]*1000:.0f} ms 恢复。',
    lead='Redis 复制是异步的:主库写完就回复客户端。min-replicas-to-write 给主库加了一个保险:如果联系得上的「好从库」少于 N 个,就拒绝写入,免得把数据只写在一个没人备份的节点上。这篇把它的行为量出来:多久才拒绝、拒绝时的错误、什么时候恢复、to-write 与 max-lag 各起什么作用。',
    facts=[(f'{a["first_reject"]*1000:.0f} ms', 'max-lag 3 s、从库全冻结时,主库第一次拒绝写入的时间'), ('NOREPLICAS', '被拒时的错误:Not enough good replicas to write.'), (f'{a["back"]*1000:.0f} ms', '解冻从库后写入恢复所用的时间')],
    body=[
        sec('四种配置', '从库用 SIGSTOP 冻结、再用 SIGCONT 解冻;主库由一个客户端每 10 ms 写一次', term('', blk('r94', 1)) if False else term('', out('r94')),
            f'<p>规律:主库并不是从库一冻结就停写,而是要等到「距上次收到从库应答」超过 <code>min-replicas-max-lag</code>(约每秒一次 REPLCONF ACK)才把它算作不好——所以被拒的时间约是 max-lag 加零点几秒({a["first_reject"]*1000:.0f} ms 对 3 s;{d["first_reject"]*1000:.0f} ms 对 6 s)。冻结全部从库时,此前的 {a["ok_before"]} 条写入都被接受了,这就是主库可能「只写在自己身上」的窗口。只冻结 1 个从库而要求 1 个时,始终不拒绝;要求 2 个时冻结 1 个就停写。</p>'),
        sec('取舍', '', '<p><code>min-replicas-to-write</code> 是拿可用性换数据安全:设得越严,越容易因为从库的暂时故障(网络抖动、重启、fork 卡顿)让主库停写。它也只是「限制窗口」,不是「消除丢失」——窗口内(max-lag 之内)的写入仍然只在主库上。下一篇看它对脑裂的实际效果。</p>'),
        sec('分步演示:何时开始拒绝写入', '', demo('min-replicas-to-write', [('n', 'flow', '节点'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。一主两从;每种配置一个新实例;冻结 SIGSTOP、恢复 SIGCONT', '没有验证:从库网络断开(而非进程冻结)时的表现、复制延迟大但仍在应答时的判定(lag 的精度是秒)、min-replicas 与 WAIT 命令的组合'],
)
