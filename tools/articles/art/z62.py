from lib import *
R = J('z62'); g = R['gc']; ps = g['pauses']
def S(k): return [l for l in out('z62').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"制造真实的 GC 停顿:JVM 堆 300 MiB、串行 GC,树里 10 万个 znode × 500 字节(约 110 MiB 在堆里),后台持续写,每 1.5 秒用 jcmd GC.run 触发一次 Full GC。GC 日志里的 Full GC 停顿(ms):{', '.join(f'{p:.0f}' for p in ps)}(随堆里数据变多从 14 涨到 60~80 ms)。普通写延迟中位 {g['base']:.2f} ms,而压测期间的最大写延迟是 {g['max_lat']:.0f} ms——最大延迟和最长的 GC 停顿同量级:请求在 GC 期间被挂起。", t=tl(S(1)), b=bars([[f'第 {i + 1} 次', p, f'{p:.0f} ms'] for i, p in enumerate(ps)], max(ps) * 1.1, done=list(range(len(ps)))), kv=KV([['Full GC 停顿', f"{min(ps):.0f}–{max(ps):.0f} ms"], ['写延迟最大值', f"{g['max_lat']:.0f} ms(≈ 最长停顿)"]], ['写延迟最大值'])),
    step(f"ZooKeeper 自带的 JvmPauseMonitor(zoo.cfg:jvm.pause.monitor=true,阈值 info 50 ms / warn 200 ms):它每 500 ms 睡一次、看醒来晚了多久。结果:日志里只有启动那一行,没有任何「检测到停顿」的告警;mntr 的 zk_max_jvm_pause_time_ms 只有 {R['mntr']['zk_max_jvm_pause_time_ms']} ms、平均 {float(R['mntr']['zk_avg_jvm_pause_time_ms']):.1f} ms——而真实的 Full GC 停顿有 {max(ps):.0f} ms。这个监视器是采样式的(只有停顿恰好落在它睡眠的窗口里才被看到),会低估停顿,GC 日志才是准确的。", t=tl(S(2)), mark=[1, 2], kv=KV([['JvmPauseMonitor', f"最大 {R['mntr']['zk_max_jvm_pause_time_ms']} ms(低估)"], ['GC 日志', f"最大 {max(ps):.0f} ms"]], ['JvmPauseMonitor'])),
]
A = dict(
    n=62, series='zookeeper', tags='ZooKeeper,GC,JVM,停顿,真实验证,动画演示',
    desc=f'GC 停顿对 ZooKeeper 的影响:串行 GC 下 10 万 znode 的 Full GC 停顿 {min(ps):.0f}–{max(ps):.0f} ms,压测中最大写延迟 {g["max_lat"]:.0f} ms;自带的 JvmPauseMonitor 只记录到 {R["mntr"]["zk_max_jvm_pause_time_ms"]} ms(采样式,会低估),要以 GC 日志为准。',
    lead='JVM 的 GC 停顿是 ZooKeeper 运维里最常见的「莫名其妙」:请求突然变慢、会话莫名过期、follower 被踢出。这篇用真实的 Full GC 量一下停顿有多长、请求延迟怎么跟着变,再看 ZooKeeper 自带的停顿监视器靠不靠谱。',
    facts=[(f'{min(ps):.0f}–{max(ps):.0f} ms', '串行 GC 下 6 次 Full GC 的停顿(堆里约 110 MiB 数据)'), (f'{g["max_lat"]:.0f} ms', '同一时期最大的同步写延迟(基线中位 ' + f'{g["base"]:.1f} ms)'), (f'{R["mntr"]["zk_max_jvm_pause_time_ms"]} ms', 'JvmPauseMonitor 报告的最大停顿(远小于真实停顿)')],
    body=[
        sec('制造 GC 停顿', '', term('', blk('z62', 1)), '<p>这是为了观察而人为制造的:小堆 + 串行 GC + 手动触发 Full GC。生产环境用 G1 / ZGC 时停顿会短得多,但原理一样——停顿期间 ZooKeeper 的所有线程(包括处理请求和发心跳的)都停了。</p>'),
        sec('ZooKeeper 自带的停顿监视器', '', term('', blk('z62', 2))),
        sec('停顿的后果(引用前面的实验)', '', '<p>停顿超过 <code>syncLimit × tickTime</code> 时,leader 会把 follower 判定为掉线(第 46 篇);停顿超过会话超时的客户端会话过期(第 13 篇),临时节点消失。所以堆大小、GC 选择、会话超时和 syncLimit 要一起考虑。</p>'),
        sec('分步演示', '', demo('GC 停顿', [('t', 'term', '输出'), ('b', 'bars', '停顿'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。堆 300 MiB、-XX:+UseSerialGC、GC 日志 -Xlog:gc;树里 10 万个 znode × 500 字节;Full GC 用 jcmd GC.run 触发 6 次', '没有验证:G1 / ZGC 的停顿、真实负载下自然发生的 GC、停顿对集群选举的影响(只在第 46 篇用 SIGSTOP 模拟过)、堆更大(数十 GiB)时的停顿'],
)
