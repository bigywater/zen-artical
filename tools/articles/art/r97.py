import json
from lib import *
R = J('r97'); lt = R['latest']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("latency-monitor-threshold = 5(毫秒):任何事件超过 5 ms 都被记下来。这个实例还开了 AOF(appendfsync always)。我依次制造:3 个 DEBUG SLEEP(30/60/90 ms)、KEYS *、BGSAVE、BGREWRITEAOF、几百次带 fsync 的 SET。", t=tm(['threshold = 5 ms', 'appendfsync always', 'DEBUG SLEEP ×3 · KEYS * · BGSAVE · BGREWRITEAOF · SET ×400']), kv=KV([['阈值', '5 ms']], ['阈值'])),
    step("LATENCY DOCTOR 给出一份文字报告:先列出观察到的事件——「1. command: 2 latency spikes (average 55ms, mean deviation 44ms, period 2.50 sec). Worst all time event 100ms.」「2. aof-fsync-always: 1 latency spikes (average 9ms …)」。", t=tm(['1. command: 2 latency spikes (average 55ms, …). Worst 100ms', '2. aof-fsync-always: 1 latency spikes (average 9ms, …). Worst 9ms'], cur=[0, 1]), kv=KV([['事件', 'command、aof-fsync-always']], ['事件'])),
    step("再按检测到的事件给建议:command → 检查慢日志、把 slowlog-log-slower-than 设成与延迟阈值一致('CONFIG SET slowlog-log-slower-than 5000');aof-fsync-always → 「很难拿到好性能,尽量放宽到 everysec(报告里写作 'onesec')」;以及一条关于删除/过期/淘汰大对象是阻塞操作的通用建议。", t=tm(['command → 用 SLOWLOG 找具体命令', "aof-fsync-always → 放宽 fsync 策略", '通用:大对象的删除/过期/淘汰会阻塞'], mark=[0, 1, 2]), kv=KV([['建议', '与事件类型一一对应']], ['建议'])),
    step("注意:BGSAVE 和 BGREWRITEAOF 的 fork 在这台机器上没有超过 5 ms 阈值,所以没有 fork 事件,DOCTOR 也没有给出 fork 相关的建议。DOCTOR 只对「被记录下来的事件」说话。", t=tm(['fork:未超过阈值 → 不出现在报告里']), kv=KV([['没有 fork 事件', '阈值 5 ms 未达到']], ['没有 fork 事件'])),
    step("阈值决定记不记:把阈值调到 100 ms,DEBUG SLEEP 0.05 之后 LATENCY LATEST 为空(没记录);DEBUG SLEEP 0.15 之后出现 command 事件(151 ms)。latency-monitor-threshold = 0 表示关闭监控。", t=tm(['阈值 100 ms · 50 ms 的阻塞 → 不记录', '阈值 100 ms · 150 ms 的阻塞 → command 151 ms'], cur=[1]), kv=KV([['阈值', '不到不记']], ['阈值'])),
]
A = dict(
    n=97, series='redis', tags='Redis,LATENCY,延迟诊断,真实验证,动画演示',
    desc='用 latency-monitor-threshold 5 ms 在开了 appendfsync always 的实例上制造慢命令与 fsync 延迟,LATENCY DOCTOR 输出了两类事件(command 与 aof-fsync-always)和对应的建议(查慢日志、放宽 fsync 策略、大对象删除的提示);没超过阈值的 fork 不会出现;阈值调到 100 ms 时 50 ms 的阻塞不被记录。',
    lead='LATENCY DOCTOR 是 Redis 自带的「延迟医生」:它读取延迟监控记录下来的事件,输出一份带建议的文字报告。这篇不评价建议好不好,只做一件事:让它在受控条件下报告,对照我制造的事件,看它的输出与什么对应、什么情况下不会出现。',
    facts=[('2 类事件', 'command 与 aof-fsync-always(阈值 5 ms)'), ('原文输出', 'LATENCY DOCTOR 的报告和建议全文在下面'), ('阈值决定', '延迟监控只记录超过 latency-monitor-threshold 的事件')],
    body=[
        sec('完整的报告', '', term('', blk('r97', 5)),
            '<p>报告分两块:先是「观察到的事件」(事件名、尖峰次数、平均值、平均偏差、周期、历史最大值),然后是根据这些事件生成的「建议」。命令类事件会提示查慢日志并把慢日志阈值与监控阈值对齐(<code>CONFIG SET slowlog-log-slower-than 5000</code>);<code>aof-fsync-always</code> 会提示放宽 fsync 策略(报告里把 <code>everysec</code> 写成了 <code>onesec</code>);最后一条是关于大对象删除的通用提示。这些建议是服务器的通用规则,不是根据你的具体负载算出来的。</p>'),
        sec('事件怎么来的', '', term('', blk('r97', 2)), '<p>我制造了 DEBUG SLEEP、KEYS、BGSAVE、BGREWRITEAOF 和带 fsync 的 SET,LATENCY LATEST 里只有两类事件:<code>command</code>(慢命令)与 <code>aof-fsync-always</code>。fork 的耗时(这台机器上约几毫秒)没有超过 5 ms 阈值,所以没有 <code>fork</code> 事件——第 66 篇量过 fork 的停顿,这里能不能记录取决于阈值。LATEST / HISTORY / GRAPH 的细节见第 98 篇。</p>'),
        sec('阈值', '', term('', blk('r97', 7)), '<p>把 <code>latency-monitor-threshold</code> 调到 100 ms:50 ms 的阻塞不被记录,150 ms 的才被记录(151 ms)。0 表示关闭。所以「LATENCY DOCTOR 说没问题」可能只是「没有超过阈值的事件」。</p>'),
        sec('分步演示:一份延迟报告', '', demo('LATENCY DOCTOR', [('t', 'term', '报告'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。appendonly yes + appendfsync always;延迟事件用 DEBUG SLEEP 等命令制造', '没有验证:在 Linux 上 fork / transparent-huge-page 等事件的报告、报告里 "Dave" 那句开场白的出处(只是原文)、更多事件类型(expire-cycle、eviction-cycle 等)'],
)
